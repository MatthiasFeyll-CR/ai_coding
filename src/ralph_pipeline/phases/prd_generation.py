"""Phase 1: PRD Generation — generates PRD JSON and context bundle.

Bash reference: generate_prd() in pipeline.sh lines 1123-1178.
"""

from __future__ import annotations

from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeError, ClaudeRunner
from ralph_pipeline.ai.prompts import prd_generation_prompt
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import is_dry_run


class PhaseError(Exception):
    """Raised when a phase fails fatally."""

    pass


def run_prd_generation(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    claude: ClaudeRunner,
    plogger: PipelineLogger,
    project_root: Path,
) -> None:
    """Generate PRD for a milestone.

    - Check if PRD already exists (resume case → skip)
    - Build prompt from PRD Writer skill content + milestone doc path
    - Invoke Claude
    - Verify prd-mN.json was created
    """
    tasks_dir = project_root / config.paths.tasks_dir
    scripts_dir = project_root / config.paths.scripts_dir
    milestones_dir = project_root / config.paths.milestones_dir
    archive_dir = project_root / config.paths.archive_dir
    skills_dir = Path(config.paths.skills_dir).expanduser()

    prd_json = tasks_dir / f"prd-m{milestone.id}.json"

    plogger.info(
        f"Phase 1 (PRD): Generating PRD for M{milestone.id} ({milestone.slug})"
    )

    # Ensure tasks directory exists
    tasks_dir.mkdir(parents=True, exist_ok=True)

    # Skip if PRD already exists (resume case)
    if prd_json.exists():
        plogger.info(f"PRD for M{milestone.id} already exists, skipping")
        return

    if is_dry_run():
        plogger.info(f"[DRY RUN] Would generate PRD for M{milestone.id}")
        return

    # Read skill content
    skill_path = skills_dir / "prd_writer" / "SKILL.md"
    skill_content = ""
    if skill_path.exists():
        skill_content = skill_path.read_text()
    else:
        plogger.warning(f"PRD Writer skill not found at {skill_path}")

    milestone_doc = str(milestones_dir / f"milestone-{milestone.id}.md")

    prompt = prd_generation_prompt(
        skill_content=skill_content,
        milestone_id=milestone.id,
        slug=milestone.slug,
        milestone_doc=milestone_doc,
        archive_dir=str(archive_dir),
        tasks_dir=str(tasks_dir),
        scripts_dir=str(scripts_dir),
    )

    log_dir = project_root / ".ralph" / "logs" / f"m{milestone.id}-{milestone.slug}"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "prd-generation.log"

    # Attempt with retry
    try:
        claude.run(
            prompt,
            model=config.models.prd_generation,
            phase="prd_generation",
            milestone=milestone.id,
            log_file=log_file,
        )
    except ClaudeError:
        plogger.warning(f"PRD generation failed for M{milestone.id}, retrying once...")
        try:
            claude.run(
                prompt,
                model=config.models.prd_generation,
                phase="prd_generation",
                milestone=milestone.id,
                log_file=log_file,
            )
        except ClaudeError as e:
            raise PhaseError(
                f"PRD generation failed for M{milestone.id} after retry"
            ) from e

    if not prd_json.exists():
        raise PhaseError(
            f"PRD generation for M{milestone.id} did not produce {prd_json}"
        )

    # Check for context bundle
    context_bundle = scripts_dir / "context.md"
    if not context_bundle.exists():
        plogger.warning(
            f"PRD Writer did not produce context bundle at {context_bundle}"
        )
        plogger.warning("Ralph will fall back to reading upstream docs directly.")

    plogger.success(f"PRD for M{milestone.id} generated successfully")
