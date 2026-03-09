# Solution 2: Pipeline-Executor Alignment — Context Weight at Execution Time

> **Purpose:** Handover document for a future AI session working on the pipeline-executor (`ralph_execution.py`, `runner.py`, and the Ralph coding agent itself). Summarises all changes from Issue 02 that the executor must be aware of.

---

## What Changed and Why

Context weight was previously validated only at planning time. By execution, the actual context bundle (`.ralph/context.md`) was much larger due to accumulated codebase snapshots and code from prior milestones. The pipeline had no size check — oversized bundles caused silent quality degradation.

Now, the pipeline validates and optionally truncates the context bundle **after PRD generation, before Ralph execution begins**.

---

## Changes That Affect the Executor

### 1. Context bundle may now be truncated before Ralph sees it

**File:** `src/ralph_pipeline/context_validator.py` (new module)

After PRD generation, `prd_generation.py` calls `validate_context_bundle()`. If the bundle exceeds configured limits, the validator **truncates it in-place** before the executor phase starts. This means:

- **Codebase Snapshot** sections may have file contents replaced with `*(file contents omitted — see actual file)*`. The file tree is preserved.
- **Codebase Patterns** sections may be summarised to the first 10 bullet points.
- Lower-priority sections may be cut to header + first 5 lines with a truncation marker: `<!-- [context-validator] section truncated to fit context limits -->`.

**Section priority (highest = kept, lowest = truncated first):**
1. Quality Checks *(never truncated)*
2. Test Infrastructure Setup
3. Test Specifications
4. Architecture Reference
5. Design Reference
6. AI Reference
7. Browser Testing
8. Codebase Patterns
9. Codebase Snapshot

**Executor impact:** Ralph may receive a context.md where some sections are summarised or truncated. The executor should NOT treat truncation markers as errors. Ralph should refer to actual source files when a section says "file contents omitted".

### 2. Pipeline may abort before reaching the executor

If the context bundle exceeds limits **and** truncation cannot bring it under the threshold, `prd_generation.py` raises `PhaseError` (wrapping `ContextOverflowError`). The milestone FSM transitions to `failed` state. The executor phase never runs.

**Executor impact:** No action needed — the executor simply won't be called. But if the executor is ever extended to re-validate context mid-iteration (e.g., after bugfix cycles that append to context.md), it should import and use `validate_context_bundle` from `context_validator.py`.

### 3. Domain-split may halt the pipeline before execution

If the PRD Writer detects a multi-domain milestone, it produces `.ralph/domain-split-m{N}.md`. The pipeline raises `PhaseError` with a message to re-run Milestone Planner. The executor never runs.

**Executor impact:** None for now. If future work adds domain-split detection at the executor level (e.g., Ralph identifies domain mixing during coding), it should write to the same `.ralph/domain-split-m{N}.md` path for consistency.

### 4. PRD JSON now contains per-story context

**File:** `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` (Section 5 — "Inline Story Context")

Each user story in `prd-m{N}.json` may now include a `context` object:

```json
{
  "id": "US-M3-001",
  "title": "...",
  "context": {
    "data_model": ["users table (id, email, role)", "sessions table (id, user_id, token)"],
    "api_endpoints": ["POST /api/auth/login", "DELETE /api/auth/logout"],
    "components": ["LoginForm.tsx", "AuthProvider.tsx"],
    "test_cases": ["login with valid credentials", "reject expired session"],
    "ai_specs": [],
    "existing_code": ["src/auth/middleware.py#L10-L45"]
  },
  "acceptanceCriteria": ["..."]
}
```

**Executor impact:** Ralph's CLAUDE.md template or prompt assembly should surface these per-story `context` fields so the agent has focused references even if context.md was truncated. The `context` field is optional — older PRDs won't have it.

### 5. Configurable limits in pipeline-config.json

**File:** `src/ralph_pipeline/config.py` — new `ContextLimitsConfig` model

```json
{
  "context_limits": {
    "max_lines": 3000,
    "max_tokens": 15000,
    "warn_pct": 80.0,
    "tokens_per_line": 4.5
  }
}
```

Defaults apply if omitted. The executor can read these limits via `config.context_limits` if it needs to perform its own size checks (e.g., validating CLAUDE.md total size).

### 6. Milestone scope JSON has context_weight metrics

**File:** `src/ralph_pipeline/milestone_schema.py`

Structured scope files (`docs/05-milestones/milestone-N.json`) include `context_weight` with:
- `unique_file_paths` — number of unique source files touched
- `doc_sections` — number of spec doc sections referenced
- `estimated_stories` — story count

The pipeline logs warnings when these exceed thresholds (>30 files, >5 doc sections, >10 stories). The executor doesn't use these directly, but they provide useful diagnostics if a milestone is running slowly or producing poor results.

---

## File Reference

| File | Status | Executor Relevance |
|------|--------|--------------------|
| `src/ralph_pipeline/context_validator.py` | **New** | Import `validate_context_bundle` if executor needs mid-run validation |
| `src/ralph_pipeline/config.py` | Modified | `config.context_limits` available for executor-side checks |
| `src/ralph_pipeline/phases/prd_generation.py` | Modified | Runs validation before executor — executor receives pre-validated bundle |
| `src/ralph_pipeline/milestone_schema.py` | Existing | `context_weight` metrics available via `validate_milestone_scope()` |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | Modified | PRD Writer now produces inline `context` per story in prd.json |
| `src/ralph_pipeline/data/skills/milestone_planner/SKILL.md` | Modified | Stronger domain-cohesion rule reduces multi-domain milestones |
| `tests/test_context_validator.py` | **New** | 20 tests covering all validation paths |

---

## Recommended Executor Alignment Tasks

1. **Surface per-story `context` in CLAUDE.md.** When assembling the Ralph prompt, extract `context` from each PRD story and include it alongside the acceptance criteria. This ensures Ralph has focused references even after bundle truncation.

2. **Handle truncation markers gracefully.** If Ralph encounters `<!-- [context-validator] section truncated -->` or `*(file contents omitted — see actual file)*` in context.md, it should read the actual source file rather than assuming the content is missing.

3. **Consider mid-iteration validation.** After QA bugfix cycles that regenerate context, call `validate_context_bundle(bundle_path, config.context_limits, already_truncated=True)` to catch growth. On `ContextOverflowError`, transition to failed state.

4. **Log context metrics.** At the start of `run_ralph_execution()`, call `measure_bundle()` and log the line/token counts for observability. This helps diagnose quality issues without needing to inspect the bundle manually.
