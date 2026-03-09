# Issue 02: Context Weight Validated at Planning Time, Never at Execution Time

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline orchestrates multi-milestone software projects using AI agents. Each milestone goes through: PRD Generation → Ralph Coding → QA → Merge → Reconcile.

The **Milestone Planner** (planning phase) sizes milestones to fit within the AI agent's context window. The **PRD Writer** (execution Phase 1) then assembles a **context bundle** (`.ralph/context.md`) — the single document Ralph reads for all domain knowledge during coding.

---

## The Problem

Context weight is validated **only during planning**, based on spec documents. By execution time, the actual context is much larger because:

1. **Previous milestones added code.** The context bundle includes a codebase snapshot (file tree + contents of files stories will modify). This grows with every milestone.
2. **The codebase snapshot didn't exist during planning.** The Milestone Planner's weight calculation only counts spec references, not actual code.
3. **The warning is non-blocking.** The PRD Writer skill says "warn if bundle > ~1500 lines" but the pipeline code does **nothing** with this warning.

### Milestone Planner's validation (planning time)

From `milestone_planner/SKILL.md`, Phase 4:
- Context weight thresholds: >30 unique file paths, >5 doc sections, >10 stories → split warning
- This only counts references in spec documents — it cannot know how much code will exist after prior milestones run

### PRD Writer's context assembly (execution time)

From `prd_writer/SKILL.md`, the context bundle includes:
1. Architecture sections
2. Design specs
3. AI specs
4. Test specs (full test case definitions)
5. **Codebase patterns from archived progress files**
6. **Codebase snapshot (file tree + existing file contents)**
7. Quality checks from pipeline-config.json
8. Test infrastructure setup

Items 5 and 6 grow with every milestone. By milestone 4-5, the codebase snapshot alone can exceed the planned weight.

### Pipeline code — no size validation

In `src/ralph_pipeline/phases/prd_generation.py`, the only check on context.md is:

```python
# Check for context bundle
context_bundle = scripts_dir / "context.md"
if not context_bundle.exists():
    plogger.warning(
        f"PRD Writer did not produce context bundle at {context_bundle}"
    )
    plogger.warning("Ralph will fall back to reading upstream docs directly.")
```

No size check. No line count. No token estimation. If context.md is 5000 lines, the pipeline proceeds silently.

### What happens when context overflows

Ralph reads context.md first every iteration (`ralph_execution.py` line 96-103):
```python
claude_md = scripts_dir / "CLAUDE.md"
# ...
prompt = claude_md.read_text()
```

CLAUDE.md tells Ralph to read context.md. If context.md exceeds the effective context window, late-appearing sections (typically test specs and codebase patterns — the most actionable parts) get truncated or ignored by the model.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/data/skills/milestone_planner/SKILL.md` | Defines context weight thresholds (spec-time only) |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | Assembles context.md with 1500-line warning |
| `src/ralph_pipeline/phases/prd_generation.py` | Phase 1 — only checks existence, not size |
| `src/ralph_pipeline/phases/ralph_execution.py` | Phase 2 — feeds context to Ralph with no size guard |
| `src/ralph_pipeline/config.py` | No context weight config options exist |

---

## Impact

- **Severity:** High — context overflow silently degrades code quality across all stories in a milestone
- **Failure mode:** Silent — large context causes the model to miss specs at the tail of the document
- **Frequency:** Increases with later milestones as codebase grows
- **Blast radius:** Affects every story Ralph implements in the overflowed milestone

---

## Questions to Consider

1. Should the pipeline validate context.md size after PRD generation and abort/warn if it exceeds a threshold?
2. Should there be a configurable `max_context_lines` in `pipeline-config.json`?
3. Should the PRD Writer be instructed to prioritize certain sections over others when the bundle is large (e.g., test specs > codebase snapshot)?
4. Should the codebase snapshot be truncated to only files directly referenced by stories, with a summary for everything else?
5. Should the pipeline estimate token count (not just line count) using a simple heuristic (lines × avg_tokens_per_line)?
6. Could context.md be split into multiple documents with Ralph reading only what's needed per story?
