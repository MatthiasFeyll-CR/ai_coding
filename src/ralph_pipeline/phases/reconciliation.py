"""Phase 4: Merge + Reconciliation — merge feature branch, update specs.

Combines the merge operation (previously a separate phase) with spec
reconciliation.  In the linear single-agent pipeline there is only one
coding agent working sequentially, so the feature branch diverges from
the base branch at a point where nothing else can change.  The merge is
therefore a trivial fast-forward (recorded as --no-ff for history) and
the merged code is byte-identical to what QA already validated.

Post-merge verification (tests, regression analysis, gate checks) is
intentionally omitted — it would re-test identical code.
"""

from __future__ import annotations

from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeError, ClaudeRunner
from ralph_pipeline.ai.prompts import reconciliation_prompt
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.git_ops import GitOps, MergeConflictError
from ralph_pipeline.infra.regression import RegressionAnalyzer
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.phases.deterministic_recon import \
    run_deterministic_reconciliation
from ralph_pipeline.state import PipelineState
from ralph_pipeline.subprocess_utils import is_dry_run, run_command


class ReconciliationScopeViolation(Exception):
    """Reconciliation modified files outside the allowed docs/ directory."""

    pass


class MergeError(Exception):
    """Fatal error during merge."""

    pass


# Directories the reconciler is allowed to modify.
# docs/ is the primary target; .ralph/ holds pipeline working artifacts.
_ALLOWED_PREFIXES = ("docs/", ".ralph/")


def _check_docs_only_changes(
    config: PipelineConfig,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
    milestone_id: int,
) -> None:
    """Verify that reconciliation only modified files under docs/.

    Checks both staged and unstaged changes. If any file outside the
    allowed directories was created or modified, reverts ALL unstaged
    changes and raises ReconciliationScopeViolation (hard exit).
    """
    # Collect all changed files (staged + unstaged + untracked)
    result = run_command(
        ["git", "diff", "--name-only"],
        cwd=project_root,
        check=False,
    )
    unstaged = [f for f in result.stdout.splitlines() if f.strip()]

    result = run_command(
        ["git", "diff", "--cached", "--name-only"],
        cwd=project_root,
        check=False,
    )
    staged = [f for f in result.stdout.splitlines() if f.strip()]

    result = run_command(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=project_root,
        check=False,
    )
    untracked = [f for f in result.stdout.splitlines() if f.strip()]

    all_changed = set(unstaged + staged + untracked)

    # Filter to violations — files outside allowed directories
    violations = [
        f for f in all_changed
        if not any(f.startswith(prefix) for prefix in _ALLOWED_PREFIXES)
    ]

    if not violations:
        return

    # Log each violation
    plogger.error(
        f"RECONCILIATION SCOPE VIOLATION: M{milestone_id} reconciler "
        f"modified {len(violations)} file(s) outside docs/:"
    )
    for v in violations:
        plogger.error(f"  - {v}")

    # Revert all uncommitted changes to prevent non-docs modifications
    # from persisting
    run_command(
        ["git", "checkout", "."],
        cwd=project_root,
        check=False,
    )
    run_command(
        ["git", "clean", "-fd"],
        cwd=project_root,
        check=False,
    )

    plogger.error(
        "All uncommitted changes reverted. Reconciliation aborted. "
        "The Spec Reconciler must only modify files under docs/."
    )

    raise ReconciliationScopeViolation(
        f"Reconciliation for M{milestone_id} modified files outside docs/: "
        f"{', '.join(violations)}"
    )


def _merge_feature_branch(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    state: PipelineState,
    regression_analyzer: RegressionAnalyzer,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
    state_file: Path | None = None,
) -> None:
    """Merge the milestone feature branch into the base branch.

    Performs only the merge, test-ownership registration, tagging, and
    branch cleanup.  No post-merge verification — QA already validated
    the identical code on the feature branch.
    """
    slug = milestone.slug
    branch = f"ralph/m{milestone.id}-{slug}"
    base_branch = state.base_branch

    plogger.info(f"Merging M{milestone.id} ({slug}): {branch} → {base_branch}")

    # Commit any dirty pipeline artifacts before switching branches
    git.commit_all(f"chore: pipeline artifacts after M{milestone.id} QA")

    # Switch to base branch and create a safety tag
    git.checkout(base_branch)
    try:
        git.tag(f"pre-m{milestone.id}-merge")
    except Exception:
        pass  # Tag may already exist on resume

    # Merge
    try:
        git.merge(branch, no_ff=True, message=f"Merge M{milestone.id}: {slug}")
    except MergeConflictError:
        plogger.error(
            f"Merge conflict on M{milestone.id}. "
            f"This should not happen in a linear single-agent pipeline. "
            f"Resolve manually and resume."
        )
        raise MergeError(
            f"Merge conflict on M{milestone.id}. "
            f"Resolve manually and resume with --milestone {milestone.id}"
        )

    # Register test ownership — needed so future milestones can
    # classify failures as REGRESSION vs CURRENT during QA.
    test_map = regression_analyzer.build_test_map(milestone.id)
    state.test_milestone_map = test_map
    if state_file:
        state.save(state_file)

    # Tag completion and clean up feature branch
    git.tag(f"m{milestone.id}-complete")
    plogger.success(
        f"M{milestone.id} merged and tagged m{milestone.id}-complete"
    )

    try:
        git.delete_branch(branch)
    except Exception:
        plogger.warning(f"Could not delete branch {branch}")


def _run_spec_reconciliation(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    claude: ClaudeRunner,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
) -> bool:
    """Invoke the Spec Reconciler agent — 2 attempts, non-fatal.

    Updates upstream docs to match actual implementation.

    Returns True if reconciliation succeeded (changelog produced),
    False otherwise.
    """
    slug = milestone.slug

    skills_dir = Path(config.paths.skills_dir).expanduser()
    archive_dir = project_root / config.paths.archive_dir
    qa_dir = project_root / config.paths.qa_dir
    recon_dir = project_root / config.paths.reconciliation_dir

    recon_dir.mkdir(parents=True, exist_ok=True)

    # Step 2a: Deterministic reconciliation — catches structural drift
    # without relying on AI (file paths, directories referenced in docs).
    run_deterministic_reconciliation(
        project_root=project_root,
        docs_dir=config.paths.docs_dir,
        recon_dir=recon_dir,
        milestone_id=milestone.id,
        plogger=plogger,
    )

    log_dir = project_root / ".ralph" / "logs" / f"m{milestone.id}-{slug}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Load skill content
    skill_path = skills_dir / "spec_reconciler" / "SKILL.md"
    skill_content = ""
    if skill_path.exists():
        skill_content = skill_path.read_text()

    prompt = reconciliation_prompt(
        skill_content=skill_content,
        milestone=milestone.id,
        slug=slug,
        archive_dir=str(archive_dir),
        qa_dir=str(qa_dir),
        recon_dir=str(recon_dir),
    )

    changelog = recon_dir / f"m{milestone.id}-changes.md"

    for attempt in range(1, 3):
        try:
            claude.run(
                prompt,
                model=config.models.reconciliation,
                phase="reconciliation",
                milestone=milestone.id,
                log_file=log_dir / f"reconciliation-attempt-{attempt}.log",
            )
        except ClaudeError:
            plogger.warning(
                f"Spec Reconciler attempt {attempt} failed for M{milestone.id}"
            )

        if changelog.exists():
            # Guard: verify reconciliation only modified docs
            _check_docs_only_changes(
                config=config,
                git=git,
                plogger=plogger,
                project_root=project_root,
                milestone_id=milestone.id,
            )

            git.commit_all(f"docs: spec reconciliation after M{milestone.id}")
            plogger.success(
                f"Reconciliation complete for M{milestone.id} (changelog: {changelog})"
            )
            return True

        if attempt == 1:
            plogger.info("Changelog not produced — retrying reconciliation (attempt 2)")

    plogger.warning(
        f"Spec Reconciler did not produce {changelog} after 2 attempts — continuing.\n"
        f"Future milestone PRDs may reference stale specs. Consider running /spec_reconciler manually."
    )
    return False


def run_reconciliation(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    state: PipelineState,
    claude: ClaudeRunner,
    regression_analyzer: RegressionAnalyzer,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
    state_file: Path | None = None,
) -> bool:
    """Merge feature branch and reconcile specs.

    Two-step phase:
      1. Merge the feature branch into base (trivial in linear pipeline)
      2. Run the Spec Reconciler to update upstream docs

    Raises MergeError if the merge itself fails (should not happen in
    normal operation).  Spec reconciliation failures are non-fatal but
    tracked via return value.

    Returns True if reconciliation succeeded, False if it failed.
    """
    slug = milestone.slug

    plogger.info(
        f"Phase 4 (Merge + Reconciliation): M{milestone.id} ({slug})"
    )

    if is_dry_run():
        plogger.info(
            f"[DRY RUN] Would merge and reconcile M{milestone.id}"
        )
        return True

    # Step 1: Merge feature branch
    _merge_feature_branch(
        milestone=milestone,
        config=config,
        state=state,
        regression_analyzer=regression_analyzer,
        git=git,
        plogger=plogger,
        project_root=project_root,
        state_file=state_file,
    )

    # Step 2: Spec reconciliation (non-fatal)
    return _run_spec_reconciliation(
        milestone=milestone,
        config=config,
        claude=claude,
        git=git,
        plogger=plogger,
        project_root=project_root,
    )
