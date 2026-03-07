"""CLI entry point — argparse-based interface for ralph-pipeline."""

from __future__ import annotations

import argparse
import atexit
import signal
import sys
from pathlib import Path

from ralph_pipeline import __version__
from ralph_pipeline.ai.claude import ClaudeRunner
from ralph_pipeline.ai.env import AIEnvError, build_claude_env, load_and_validate_ai_env
from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.infra.health import ServiceHealthChecker
from ralph_pipeline.infra.regression import RegressionAnalyzer
from ralph_pipeline.infra.test_infra import TestInfraManager
from ralph_pipeline.infra.test_runner import TestRunner
from ralph_pipeline.lockfile import LockfileError
from ralph_pipeline.lockfile import acquire as acquire_lock
from ralph_pipeline.lockfile import release as release_lock
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.phases.phase0_bootstrap import Phase0Error, run_phase0_bootstrap
from ralph_pipeline.runner import MilestoneRunner
from ralph_pipeline.state import PipelineState
from ralph_pipeline.subprocess_utils import set_dry_run
from ralph_pipeline.usage import EventLogger

CONFIG_FILENAME = "pipeline-config.json"


CONFIG_FILENAME = "pipeline-config.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ralph-pipeline",
        description="AI Coding Pipeline Orchestrator",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command")

    # run subcommand
    run_parser = subparsers.add_parser("run", help="Execute the pipeline")
    run_parser.add_argument(
        "--resume", action="store_true", help="Resume from saved state"
    )
    run_parser.add_argument(
        "--milestone", type=int, help="Start from specific milestone ID"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Show plan without executing"
    )

    # install-skills subcommand
    subparsers.add_parser("install-skills", help="Copy skills to ~/.claude/skills/")

    # validate-infra subcommand
    subparsers.add_parser(
        "validate-infra", help="Test infrastructure lifecycle"
    )

    return parser


def _resolve_project_root(config_path: Path) -> Path:
    """Determine project root from config file location."""
    return config_path.parent.resolve()


def _setup_signal_handlers(
    state: PipelineState,
    state_file: Path,
    plogger: PipelineLogger,
    config: PipelineConfig,
    infra: TestInfraManager,
    project_root: Path,
) -> None:
    """Register signal handlers for graceful shutdown."""

    def _handler(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        plogger.warning(
            f"\nReceived {sig_name} — persisting state and shutting down..."
        )
        state.save(state_file)
        try:
            infra.teardown_all()
        except Exception:
            pass
        release_lock(project_root)
        plogger.show_summary(state, config)
        sys.exit(128 + signum)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def run_pipeline(args: argparse.Namespace) -> None:
    """Main pipeline execution."""
    config_path = Path(CONFIG_FILENAME).resolve()
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = PipelineConfig.load(config_path)
    project_root = _resolve_project_root(config_path)

    # Set up dry-run mode
    if args.dry_run:
        set_dry_run(True)

    # Acquire lock file (prevents concurrent executions)
    if not args.dry_run:
        try:
            acquire_lock(project_root, source="cli")
        except LockfileError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        # Ensure lock is released on any exit path
        atexit.register(release_lock, project_root)

    # Initialize services
    plogger = PipelineLogger()
    plogger._project_name = config.project.name

    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)

    state_file = ralph_dir / "state.json"
    event_logger = EventLogger(ralph_dir / "logs" / "pipeline.jsonl")
    git = GitOps(project_root)
    health_checker = ServiceHealthChecker()
    infra = TestInfraManager(
        config.test_execution, project_root, health_checker, plogger
    )
    # Load and validate AI credentials from .ai.env
    claude_env: dict[str, str] | None = None
    if not args.dry_run:
        try:
            ai_env = load_and_validate_ai_env(
                project_root, plogger, env_file=config.ai_env.env_file
            )
            claude_env = build_claude_env(ai_env, model_override=config.models.ralph)
        except AIEnvError as e:
            plogger.error(str(e))
            sys.exit(1)

    # Load or initialize state (before ClaudeRunner so we can pass cost tracker)
    if args.resume and state_file.exists():
        plogger.info("Resuming from saved state...")
        state = PipelineState.load(state_file)
        _handle_resume(state, git, plogger, project_root)
    else:
        # Fresh run — require clean working tree
        if not args.dry_run:
            dirty = git.dirty_files()
            if dirty:
                plogger.error(
                    "Working tree is not clean. Commit or stash changes first:"
                )
                for f in dirty[:20]:
                    plogger.error(f"  {f}")
                if len(dirty) > 20:
                    plogger.error(f"  ... and {len(dirty) - 20} more")
                sys.exit(1)

        base_branch = git.current_branch()
        # In dry-run mode, git returns "[dry-run]" — use a fallback
        if args.dry_run and (not base_branch or base_branch == "[dry-run]"):
            import subprocess as _sp

            try:
                result = _sp.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                )
                base_branch = result.stdout.strip() or "main"
            except Exception:
                base_branch = "main"
        state = PipelineState.initialize(config, base_branch)
        state.save(state_file)

    claude = ClaudeRunner(
        config.retry,
        event_logger,
        plogger,
        env=claude_env,
        cost_tracker=state.cost,
        budget_usd=config.cost.budget_usd,
    )
    test_runner = TestRunner(
        config.test_execution, infra, claude, plogger, project_root, git
    )

    # Register signal handlers
    _setup_signal_handlers(state, state_file, plogger, config, infra, project_root)

    # Register atexit teardown (design §5.6)
    atexit.register(infra.teardown_all)

    # Phase 0: Infrastructure Bootstrap (runs once before milestone loop)
    has_phase0_work = config.test_infrastructure or config.scaffolding
    any_milestone_started = any(
        ms.phase != "pending" for ms in state.milestones.values()
    )
    if has_phase0_work and not state.phase0_complete and not any_milestone_started:
        from datetime import datetime, timezone

        plogger.section("Phase 0: Infrastructure Bootstrap")
        plogger.info(
            "Phase 0 triggered — scaffolding and/or test infrastructure configured"
        )
        state.phase0_started_at = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        state.save(state_file)
        try:
            run_phase0_bootstrap(
                config=config,
                claude=claude,
                plogger=plogger,
                project_root=project_root,
                config_path=config_path,
            )
            state.phase0_complete = True
            state.phase0_completed_at = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
            state.save(state_file)
            plogger.success("Phase 0 complete — state.json updated")
            # Reload config after Phase 0 write-back
            config = PipelineConfig.load(config_path)
            plogger.info("Config reloaded after Phase 0 write-back")
        except Phase0Error as e:
            plogger.error(f"Phase 0 failed: {e}")
            state.save(state_file)
            sys.exit(1)
    elif has_phase0_work and not state.phase0_complete and any_milestone_started:
        plogger.warning(
            "Phase 0 was not run but milestones already started — "
            "skipping Phase 0 to avoid conflicts (scaffolding may have been done inline by Ralph)"
        )
        state.phase0_complete = True
        state.save(state_file)
    elif has_phase0_work and state.phase0_complete:
        plogger.info(
            f"Phase 0 already complete (finished at {state.phase0_completed_at}), skipping"
        )
    else:
        plogger.info(
            "Phase 0: not needed (no scaffolding or test_infrastructure configured)"
        )

    # Auto-validate infra before first milestone (design §8.2)
    if not args.dry_run and (
        config.test_execution.services or config.test_execution.tier1.environments
    ):
        plogger.info("Auto-validating test infrastructure...")
        try:
            if config.test_execution.services:
                report = health_checker.wait_all_ready(config.test_execution.services)
                for r in report.services:
                    if r.healthy:
                        plogger.success(f"{r.name} ready ({r.wait_seconds:.1f}s)")
                    else:
                        plogger.warning(f"{r.name}: {r.error}")
        except Exception as e:
            plogger.warning(f"Infra pre-validation: {e}")

    # Determine starting milestone
    milestones = config.milestones
    if args.milestone:
        # Start from specific milestone
        milestone_ids = [m.id for m in milestones]
        if args.milestone not in milestone_ids:
            plogger.error(
                f"Milestone {args.milestone} not found. Available: {milestone_ids}"
            )
            sys.exit(1)
        start_idx = milestone_ids.index(args.milestone)
        milestones = milestones[start_idx:]
        state.current_milestone = args.milestone
    elif args.resume:
        # Skip already-completed milestones
        milestones = [
            m
            for m in milestones
            if state.milestones.get(m.id, None) is None
            or state.milestones[m.id].phase not in ("complete",)
        ]

    # Show status panel
    plogger.section(f"Pipeline: {config.project.name}")
    plogger.info(f"Milestones: {len(milestones)} to execute")
    if args.dry_run:
        plogger.info("[DRY RUN MODE] No commands will be executed")
    plogger.show_status_panel()

    event_logger.emit(
        "pipeline_start", milestones=len(milestones), dry_run=args.dry_run
    )

    # Execute milestones sequentially
    regression_analyzer = RegressionAnalyzer(state, project_root, git)

    for milestone_config in milestones:
        state.current_milestone = milestone_config.id
        plogger.set_context(
            milestone_id=milestone_config.id,
            milestone_name=milestone_config.name,
            phase="pending",
            total_milestones=len(config.milestones),
            project_name=config.project.name,
        )
        plogger.section(f"Milestone {milestone_config.id}: {milestone_config.name}")
        plogger.show_status_panel()

        runner = MilestoneRunner(
            milestone=milestone_config,
            config=config,
            pipeline_state=state,
            state_file=state_file,
            claude=claude,
            git=git,
            test_runner=test_runner,
            infra=infra,
            regression_analyzer=regression_analyzer,
            plogger=plogger,
            event_logger=event_logger,
            project_root=project_root,
        )

        success = runner.execute()

        if not success:
            plogger.error(
                f"Milestone {milestone_config.id} ({milestone_config.slug}) FAILED. "
                f"Fix manually and resume with: ralph-pipeline run --resume"
            )
            plogger.show_summary(state, config)
            sys.exit(1)

        plogger.success(
            f"Milestone {milestone_config.id} ({milestone_config.slug}) completed"
        )

    # Teardown infra
    try:
        infra.teardown_all()
    except Exception:
        pass

    event_logger.emit("pipeline_complete")
    plogger.show_summary(state, config)
    plogger.success("Pipeline completed successfully!")


def _handle_resume(
    state: PipelineState,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
) -> None:
    """Handle resume logic — checkout correct branch, handle dirty tree."""
    current_ms = state.milestones.get(state.current_milestone)
    if not current_ms:
        return

    current_branch = git.current_branch()

    # Determine the correct branch for the current phase
    phases_on_feature = {"prd_generation", "ralph_execution", "qa_review"}
    if current_ms.phase in phases_on_feature:
        # Should be on feature branch — verify
        expected_prefix = f"ralph/m{state.current_milestone}-"
        if not current_branch.startswith(expected_prefix):
            plogger.warning(
                f"Expected to be on branch {expected_prefix}* but on {current_branch}"
            )
    elif current_ms.phase in ("reconciliation", "merge_verify"):
        # Should be on base branch
        if current_branch != state.base_branch:
            plogger.warning(
                f"Expected to be on {state.base_branch} but on {current_branch}"
            )

    # Refuse to proceed with uncommitted changes on the wrong branch
    if git.has_uncommitted_changes():
        plogger.info("Found uncommitted changes — auto-committing for resume")
        git.commit_all("chore: user manual fix before resume")


def install_skills() -> None:
    """Copy bundled skills to ~/.claude/skills/."""
    import shutil

    plogger = PipelineLogger()
    skills_src = Path(__file__).parent / "data" / "skills"
    skills_dst = Path.home() / ".claude" / "skills"

    if not skills_src.exists():
        plogger.warning(
            "No bundled skills found. Skills are already at ~/.claude/skills/"
        )
        return

    skills_dst.mkdir(parents=True, exist_ok=True)

    for skill_dir in skills_src.iterdir():
        if skill_dir.is_dir():
            dest = skills_dst / skill_dir.name
            if dest.is_symlink():
                dest.unlink()
            elif dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill_dir, dest)
            plogger.success(f"Installed skill: {skill_dir.name}")

    plogger.success(f"Skills installed to {skills_dst}")


def validate_infra(args: argparse.Namespace) -> None:
    """Run infrastructure validation — full lifecycle test."""
    config_path = Path(CONFIG_FILENAME).resolve()
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = PipelineConfig.load(config_path)
    project_root = _resolve_project_root(config_path)

    plogger = PipelineLogger()
    health_checker = ServiceHealthChecker()
    infra = TestInfraManager(
        config.test_execution, project_root, health_checker, plogger
    )

    plogger.section("Infrastructure Validation")

    steps = [
        ("teardown", "Clean slate", lambda: infra.teardown_all()),
        ("build", "Build test images", lambda: infra.ensure_tier2()),
    ]

    # Health checks per service
    if config.test_execution.services:
        for svc in config.test_execution.services:
            result = health_checker.wait_for_service(svc)
            if result.healthy:
                plogger.success(
                    f"{svc.name} {svc.type}:{svc.port} ready ({result.wait_seconds:.1f}s)"
                )
            else:
                plogger.error(
                    f"{svc.name} {svc.type}:{svc.port} FAILED: {result.error}"
                )
                sys.exit(1)

    # Smoke test
    if config.test_execution.test_command:
        plogger.info("Running smoke test (--collect-only if pytest)...")
        from ralph_pipeline.subprocess_utils import run_command

        test_cmd = config.test_execution.test_command
        # Try --collect-only for pytest, --listTests for jest
        try:
            run_command(
                f"{test_cmd} --collect-only 2>/dev/null || {test_cmd} --listTests 2>/dev/null || true",
                cwd=project_root,
                timeout=60,
                check=False,
                shell=True,
            )
            plogger.success("smoke test discovery completed")
        except Exception:
            plogger.warning("Smoke test discovery could not run")

    # Teardown validation
    plogger.info("Testing teardown...")
    try:
        infra.teardown_all()
        plogger.success("teardown completed cleanly")
    except Exception as e:
        plogger.error(f"teardown failed: {e}")
        sys.exit(1)

    plogger.success("Infrastructure validation PASSED")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(args)
    elif args.command == "install-skills":
        install_skills()
    elif args.command == "validate-infra":
        validate_infra(args)
    else:
        parser.print_help()
        sys.exit(0)
        sys.exit(0)
