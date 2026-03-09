# Issue 01: Milestone Scope Files Are Unstructured — The Planning→Execution Bridge Is Lossy

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline is a Python CLI that orchestrates multi-milestone software projects using AI agents (Claude). The pipeline has three macro-phases:

1. **Specification Phase** (manual) — Requirements → Architecture → Design → Test Architecture
2. **Planning Phase** (manual) — Milestone Planner → Pipeline Configurator
3. **Execution Phase** (automated) — PRD Generation → Ralph Coding → QA → Merge → Reconcile

The **Milestone Planner** (step 5) analyzes all specification docs and produces milestone scope files. The **PRD Writer** (Phase 1 of execution) reads these scope files and generates structured JSON PRDs + context bundles for the Ralph coding agent.

---

## The Problem

Milestone scope files (`docs/05-milestones/milestone-N.md`) are the **only bridge** between planning and execution. They are free-form markdown with no enforced structure.

### What the Milestone Planner produces

The Milestone Planner performs significant analytical work:
- Dependency analysis between features
- Context weight validation (file path count, doc section count, story count)
- Feature-to-milestone mapping with domain cohesion grouping
- Identification of which architecture sections, design specs, and test IDs belong to each milestone

All of this gets serialized as **prose in markdown** — narrative bullets, tables, and references. There is no machine-parseable schema.

### What the PRD Writer consumes

The PRD Writer (invoked as a Claude agent in Phase 1) re-reads **all upstream docs from scratch**, using `milestone-N.md` as a loose guide. The prompt in `src/ralph_pipeline/ai/prompts.py` says:

```python
def prd_generation_prompt(...) -> str:
    return f"""{skill_content}

ARGUMENTS: Write PRD for milestone M{milestone_id} ({slug}).

Instructions:
- Read {milestone_doc} and ALL upstream docs (architecture, design, AI, integration docs).
- Read the ACTUAL codebase for ground truth — check what previous milestones actually built.
- Read {archive_dir}/ for learnings from previous milestone runs.
- Write the PRD JSON directly to {tasks_dir}/prd-m{milestone_id}.json
- Write the context bundle to {scripts_dir}/context.md
...
```

### What gets lost

The Milestone Planner's analytical mappings (which features share data models, which API endpoints are coupled, which doc sections are relevant, which test IDs are assigned) are **embedded as prose**. The PRD Writer AI must **independently re-derive** these same mappings by re-reading all docs.

If the PRD Writer interprets a markdown reference differently than the Milestone Planner intended:
- Spec sections silently vanish from the PRD
- Test IDs get missed
- Architecture references get omitted from the context bundle
- Features get assigned to wrong stories

The failure is **silent** — it only surfaces 2-3 phases later as mysterious QA failures.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/data/skills/milestone_planner/SKILL.md` | Milestone Planner skill — defines milestone scope file format |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | PRD Writer skill — consumes milestone scope files |
| `src/ralph_pipeline/ai/prompts.py` | `prd_generation_prompt()` — the prompt that bridges planning→execution |
| `src/ralph_pipeline/phases/prd_generation.py` | Phase 1 implementation — no structural validation of inputs |
| `src/ralph_pipeline/data/skills/pipeline_configurator/SKILL.md` | Pipeline Configurator — could enforce scope file schema |

### Key code in `src/ralph_pipeline/phases/prd_generation.py`

The PRD generation phase has zero validation of the milestone scope file content:

```python
milestone_doc = str(milestones_dir / f"milestone-{milestone.id}.md")

prompt = prd_generation_prompt(
    skill_content=skill_content,
    milestone_id=milestone.id,
    slug=milestone.slug,
    milestone_doc=milestone_doc,  # Just a path — no content check
    archive_dir=str(archive_dir),
    tasks_dir=str(tasks_dir),
    scripts_dir=str(scripts_dir),
)
```

### Key section in Milestone Planner skill

Phase 4 of `milestone_planner/SKILL.md` defines milestone scope files as:
- Self-contained with features, data model refs, API refs, page/component refs, story outline, acceptance criteria
- Context weight validated (>30 file paths, >5 doc sections, >10 stories triggers warning)

But the format is narrative — no JSON sections, no machine-parseable references.

---

## Impact

- **Severity:** High — this is the primary information funnel between planning and execution
- **Failure mode:** Silent — bad mappings produce bad PRDs which produce bad code which fails at QA
- **Frequency:** Every milestone execution — the PRD Writer re-derives mappings every time
- **Blast radius:** Affects all downstream phases (Ralph coding, QA coverage, context bundle quality)

---

## Questions to Consider

1. Should milestone scope files have a structured JSON/YAML section alongside the markdown narrative?
2. Should the Milestone Planner produce a companion `milestone-N.json` with machine-parseable mappings?
3. Should the PRD Writer prompt include the structured mappings directly instead of relying on the AI to extract them from markdown?
4. How much of the Milestone Planner's analytical work can be preserved in a way the pipeline code (not just the AI) can validate?
5. Does the milestone scope file need a schema that the pipeline validates before starting Phase 1?
