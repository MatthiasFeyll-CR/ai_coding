"""Phase 5: Spec Reconciliation — update upstream docs to match reality.

Bash reference: run_reconcile() in pipeline.sh lines 1644-1690.
"""

from __future__ import annotations

from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeError, ClaudeRunner
from ralph_pipeline.ai.prompts import reconciliation_prompt
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import is_dry_run


def run_reconciliation(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    claude: ClaudeRunner,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
) -> None:
    """Run spec reconciliation — 2 attempts, non-fatal.

    Updates upstream docs to match actual implementation.
    """
    slug = milestone.slug

    plogger.info(f"Phase 5 (Reconciliation): M{milestone.id} ({slug})")

    if is_dry_run():
        plogger.info(f"[DRY RUN] Would run Spec Reconciler for M{milestone.id}")
        return

    skills_dir = Path(config.paths.skills_dir).expanduser()
    archive_dir = project_root / config.paths.archive_dir
    qa_dir = project_root / config.paths.qa_dir
    recon_dir = project_root / config.paths.reconciliation_dir

    recon_dir.mkdir(parents=True, exist_ok=True)

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
            git.commit_all(f"docs: spec reconciliation after M{milestone.id}")
            plogger.success(
                f"Reconciliation complete for M{milestone.id} (changelog: {changelog})"
            )
            return

        if attempt == 1:
            plogger.info("Changelog not produced — retrying reconciliation (attempt 2)")

    plogger.warning(
        f"Spec Reconciler did not produce {changelog} after 2 attempts — continuing.\n"
        f"Future milestone PRDs may reference stale specs. Consider running /spec_reconciler manually."
    )
