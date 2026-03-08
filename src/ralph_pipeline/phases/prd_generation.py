"""Phase 1: PRD Generation — generates PRD JSON and context bundle.

Bash reference: generate_prd() in pipeline.sh lines 1123-1178.
"""

from __future__ import annotations

from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeError, ClaudeRunner
from ralph_pipeline.ai.prompts import prd_generation_prompt
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.context_validator import (ContextOverflowError,
                                              validate_context_bundle)
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.milestone_schema import (MilestoneScopeValidationError,
                                             validate_milestone_scope)
from ralph_pipeline.state import PipelineState
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
    pipeline_state: PipelineState | None = None,
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

    # Structured scope file path for context-weight warnings
    scope_path = milestones_dir / f"milestone-{milestone.id}.json"

    # ── Build drift warning if prior milestones failed reconciliation ──
    drift_warning = ""
    if pipeline_state is not None:
        debt = pipeline_state.reconciliation_debt()
        if debt:
            debt_str = ", ".join(f"M{mid}" for mid in debt)
            drift_warning = (
                f"SPEC DRIFT ADVISORY: Milestones {debt_str} failed spec "
                f"reconciliation. Architecture/design docs may not reflect "
                f"what was actually built in those milestones. Be aware of "
                f"potential drift between spec docs and the codebase — when "
                f"in doubt, verify against actual source files."
            )
            plogger.warning(
                f"PRD generation for M{milestone.id}: injecting drift "
                f"advisory for unreconciled milestones {debt}"
            )

    prompt = prd_generation_prompt(
        skill_content=skill_content,
        milestone_id=milestone.id,
        slug=milestone.slug,
        milestone_doc=milestone_doc,
        archive_dir=str(archive_dir),
        tasks_dir=str(tasks_dir),
        scripts_dir=str(scripts_dir),
        drift_warning=drift_warning,
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
    else:
        # ── Context bundle size validation ────────────────────────────
        try:
            result = validate_context_bundle(
                context_bundle,
                config.context_limits,
                already_truncated=False,
            )
            if result.status == "warned":
                plogger.warning(result.message)
            elif result.status == "truncated":
                plogger.warning(result.message)
            else:
                plogger.info(result.message)
        except ContextOverflowError as e:
            raise PhaseError(str(e)) from e

    # ── Surface milestone-scope context-weight warnings ───────────────
    if scope_path.exists():
        try:
            scope = validate_milestone_scope(scope_path)
            cw = scope.context_weight
            warnings: list[str] = []
            if cw.unique_file_paths > 30:
                warnings.append(
                    f"context_weight.unique_file_paths={cw.unique_file_paths} (>30)"
                )
            if cw.doc_sections > 5:
                warnings.append(f"context_weight.doc_sections={cw.doc_sections} (>5)")
            if cw.estimated_stories > 10:
                warnings.append(
                    f"context_weight.estimated_stories={cw.estimated_stories} (>10)"
                )
            if warnings:
                plogger.warning(
                    f"M{milestone.id} scope weight thresholds exceeded: "
                    + "; ".join(warnings)
                )
        except MilestoneScopeValidationError:
            pass  # Already raised earlier if fatal

    # ── Check for domain-split recommendation ─────────────────────────
    domain_split = scripts_dir / f"domain-split-m{milestone.id}.md"
    if domain_split.exists():
        split_preview = domain_split.read_text()[:500]
        plogger.warning(
            f"PRD Writer detected multi-domain milestone M{milestone.id}. "
            f"Domain split recommendation saved to {domain_split}"
        )
        plogger.warning(
            "Pipeline pausing — re-run the Strategy Planner to split this "
            "milestone, then restart the pipeline."
        )
        raise PhaseError(
            f"M{milestone.id} requires domain split before execution. "
            f"See {domain_split} for details.\n\n{split_preview}"
        )

    plogger.success(f"PRD for M{milestone.id} generated successfully")
