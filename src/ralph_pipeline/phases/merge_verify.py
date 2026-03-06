"""Phase 4: Merge + Verify — merge, post-merge tests, gate checks.

Bash reference: merge_and_verify() in pipeline.sh lines 1532-1640
                run_gate_checks() lines 1528-1570.
"""

from __future__ import annotations

from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeError, ClaudeRunner
from ralph_pipeline.ai.prompts import gate_fix_prompt
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.git_ops import GitOps, MergeConflictError
from ralph_pipeline.infra.regression import RegressionAnalyzer
from ralph_pipeline.infra.test_runner import TestFixExhausted, TestRunner
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.state import PipelineState
from ralph_pipeline.subprocess_utils import SubprocessError, is_dry_run, run_command


class MergeVerifyError(Exception):
    """Fatal error during merge+verify phase."""

    pass


def _run_gate_checks(
    config: PipelineConfig,
    project_root: Path,
    plogger: PipelineLogger,
) -> tuple[bool, str]:
    """Run config-driven gate checks.

    Returns (all_passed, error_details).
    """
    checks = config.gate_checks.checks if config.gate_checks else []
    if not checks:
        plogger.info("[gates] No gate checks configured")
        return True, ""

    errors: list[str] = []
    all_pass = True

    for check in checks:
        # Evaluate condition
        if check.condition:
            try:
                result = run_command(
                    check.condition,
                    cwd=project_root,
                    check=False,
                    shell=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    plogger.info(f"  Skipping {check.name} (condition not met)")
                    continue
            except SubprocessError:
                plogger.info(f"  Skipping {check.name} (condition failed)")
                continue

        plogger.info(f"  Running: {check.name}")
        try:
            result = run_command(
                check.command,
                cwd=project_root,
                check=False,
                shell=True,
                timeout=300,
            )
            if result.returncode == 0:
                plogger.info(f"  {check.name} passed")
            else:
                if check.required:
                    all_pass = False
                    output_tail = "\n".join((result.stdout or "").splitlines()[-50:])
                    errors.append(f"=== {check.name} FAILED ===\n{output_tail}\n")
                    plogger.error(f"  FAILED: {check.name}")
                else:
                    plogger.warning(f"  WARNING: {check.name} failed (non-required)")
        except SubprocessError as e:
            if check.required:
                all_pass = False
                errors.append(f"=== {check.name} FAILED ===\n{e.output[-500:]}\n")
                plogger.error(f"  FAILED: {check.name}")
            else:
                plogger.warning(f"  WARNING: {check.name} failed (non-required)")

    return all_pass, "\n".join(errors)


def run_merge_verify(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    state: PipelineState,
    claude: ClaudeRunner,
    test_runner: TestRunner,
    regression_analyzer: RegressionAnalyzer,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
    state_file: Path | None = None,
) -> None:
    """Merge milestone branch, run post-merge tests, gate checks.

    Raises MergeVerifyError on unrecoverable failure.
    """
    slug = milestone.slug
    branch = f"ralph/m{milestone.id}-{slug}"
    base_branch = state.base_branch
    qa_dir = project_root / config.paths.qa_dir

    plogger.info(f"Phase 4 (Merge+Verify): M{milestone.id} ({slug}) into {base_branch}")

    if is_dry_run():
        plogger.info(f"[DRY RUN] Would merge {branch} into {base_branch} and verify")
        return

    log_dir = project_root / ".ralph" / "logs" / f"m{milestone.id}-{slug}"
    log_dir.mkdir(parents=True, exist_ok=True)
    qa_path = Path(qa_dir)
    qa_path.mkdir(parents=True, exist_ok=True)

    # Commit any dirty artifacts
    git.commit_all(f"chore: pipeline artifacts after M{milestone.id} QA")

    # Checkout base branch and tag for safety
    git.checkout(base_branch)
    try:
        git.tag(f"pre-m{milestone.id}-merge")
    except Exception:
        pass  # Tag may already exist on resume

    # Dry-run conflict check
    if not git.merge_dry_run(branch):
        plogger.warning(f"Dry-run detected merge conflicts for {branch}")

    # Merge
    try:
        git.merge(branch, no_ff=True, message=f"Merge M{milestone.id}: {slug}")
    except MergeConflictError:
        plogger.error(
            f"Merge conflict on M{milestone.id}. Resolve manually and resume."
        )
        raise MergeVerifyError(
            f"Merge conflict on M{milestone.id}. Resolve manually and resume with --milestone {milestone.id}"
        )

    # Register test ownership
    test_map = regression_analyzer.build_test_map(milestone.id)
    state.test_milestone_map = test_map
    if state_file:
        state.save(state_file)

    # Post-merge heavy tests with regression-aware fix cycles
    try:
        result = test_runner.run_test_fix_cycle(
            label=f"post-merge M{milestone.id}",
            max_cycles=config.test_execution.max_fix_cycles,
            milestone=milestone.id,
            regression_analyzer=regression_analyzer,
            model=config.models.test_fix,
            log_dir=log_dir,
        )
        test_runner.store_results(
            result,
            qa_path / f"test-results-post-merge-m{milestone.id}.md",
        )
    except TestFixExhausted:
        test_runner.store_results(
            test_runner.run_test_suite(
                f"post-merge M{milestone.id} (final)", tier=2, log_dir=log_dir
            ),
            qa_path / f"test-results-post-merge-m{milestone.id}.md",
        )
        raise MergeVerifyError(
            f"Post-merge tests failed for M{milestone.id} after "
            f"{config.test_execution.max_fix_cycles} fix cycles. "
            f"Fix manually and --resume."
        )

    # Integration tests (if configured)
    if config.test_execution.integration_test_command:
        plogger.info(f"Running integration tests after merging M{milestone.id}...")
        try:
            test_runner.run_test_fix_cycle(
                label=f"integration M{milestone.id}",
                max_cycles=config.test_execution.max_fix_cycles,
                milestone=milestone.id,
                regression_analyzer=regression_analyzer,
                model=config.models.test_fix,
                test_command=config.test_execution.integration_test_command,
                log_dir=log_dir,
            )
        except TestFixExhausted:
            raise MergeVerifyError(
                f"Integration tests failed after merging M{milestone.id}. "
                f"Fix manually and --resume."
            )

    # Gate checks with fix cycles
    max_gate_cycles = config.gate_checks.max_fix_cycles if config.gate_checks else 0
    for cycle in range(max_gate_cycles + 1):
        gate_pass, gate_errors = _run_gate_checks(config, project_root, plogger)
        if gate_pass:
            plogger.success(f"Gate checks PASSED for M{milestone.id}")
            break

        plogger.error(f"Gate checks FAILED for M{milestone.id} (cycle {cycle})")

        if cycle == max_gate_cycles:
            plogger.error(f"Gate errors:\n{gate_errors}")
            raise MergeVerifyError(
                f"Gate checks failed after {max_gate_cycles} fix cycles for M{milestone.id}. "
                f"Fix manually and --resume."
            )

        plogger.info(f"Invoking Claude to fix gate errors (cycle {cycle + 1})...")
        prompt = gate_fix_prompt(
            base_branch=base_branch,
            milestone=milestone.id,
            slug=slug,
            project_root=str(project_root),
            gate_errors=gate_errors,
        )
        try:
            claude.run(
                prompt,
                model=config.models.gate_fix,
                phase="gate_fix",
                milestone=milestone.id,
                log_file=log_dir / f"gate-fix-cycle-{cycle + 1}.log",
            )
        except ClaudeError:
            plogger.warning(f"Claude gate fix attempt {cycle + 1} failed")

        git.commit_all(f"fix: gate check fixes for M{milestone.id} (cycle {cycle + 1})")

    # Tag and cleanup
    git.tag(f"m{milestone.id}-complete")
    plogger.success(
        f"M{milestone.id} merged, verified, and tagged m{milestone.id}-complete"
    )

    try:
        git.delete_branch(branch)
    except Exception:
        plogger.warning(f"Could not delete branch {branch}")
        plogger.warning(f"Could not delete branch {branch}")
