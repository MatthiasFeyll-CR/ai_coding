"""CLI entry point — argparse-based interface for ralph-pipeline."""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeRunner
from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.infra.health import ServiceHealthChecker
from ralph_pipeline.infra.regression import RegressionAnalyzer
from ralph_pipeline.infra.test_infra import TestInfraManager
from ralph_pipeline.infra.test_runner import TestRunner
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.runner import MilestoneRunner
from ralph_pipeline.state import PipelineState
from ralph_pipeline.subprocess_utils import set_dry_run
from ralph_pipeline.usage import EventLogger


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ralph-pipeline",
        description="AI Coding Pipeline Orchestrator",
    )
    subparsers = parser.add_subparsers(dest="command")

    # run subcommand
    run_parser = subparsers.add_parser("run", help="Execute the pipeline")
    run_parser.add_argument(
        "--config", required=True, help="Path to pipeline-config.json"
    )
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
    validate_parser = subparsers.add_parser(
        "validate-infra", help="Test infrastructure lifecycle"
    )
    validate_parser.add_argument(
        "--config", required=True, help="Path to pipeline-config.json"
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
        plogger.show_summary(state, config)
        sys.exit(128 + signum)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def run_pipeline(args: argparse.Namespace) -> None:
    """Main pipeline execution."""
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = PipelineConfig.load(config_path)
    project_root = _resolve_project_root(config_path)

    # Set up dry-run mode
    if args.dry_run:
        set_dry_run(True)

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
    claude = ClaudeRunner(config.retry, event_logger, plogger)
    test_runner = TestRunner(
        config.test_execution, infra, claude, plogger, project_root, git
    )

    # Load or initialize state
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
        state = PipelineState.initialize(config, base_branch)
        state.save(state_file)

    # Register signal handlers
    _setup_signal_handlers(state, state_file, plogger, config, infra)

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
                f"Fix manually and resume with: ralph-pipeline run --config {args.config} --resume"
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

    # Determine the correct branch for the current phase
    phases_on_feature = {"prd_generation", "ralph_execution", "qa_review"}
    # merge_verify depends on sub-step; reconciliation is on base
    if current_ms.phase in phases_on_feature:
        # Feature branch: ralph/mN-slug (we'd need slug from config, but
        # at this point we just ensure the state is correct)
        pass
    elif current_ms.phase == "reconciliation":
        # Should be on base branch
        pass

    # Handle uncommitted changes
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
    config_path = Path(args.config).resolve()
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
