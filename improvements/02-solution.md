# Solution: Context Weight Validated at Execution Time (Issue 02)

## Problem Solved

Context weight was validated only during planning (based on spec documents). By execution time, the actual context bundle was much larger because previous milestones added code and the codebase snapshot didn't exist during planning. The pipeline had no size check — if context.md exceeded the model's context window, late sections (test specs, codebase patterns) got silently truncated.

## Changes

### 1. Execution-time context bundle validation (`context_validator.py`)

New module that measures and validates `.ralph/context.md` after PRD generation.

**Behaviour per milestone:**
- **Warning at 80%** of configured limits (both lines and tokens)
- **Auto-truncate on first exceed** — removes content from lowest-priority sections. Truncation only happens once per milestone.
- **Abort on second exceed** — raises `ContextOverflowError`, aborting the pipeline.

**Section priority (highest → lowest):**
1. Quality Checks (never truncated)
2. Test Infrastructure Setup
3. Test Specifications
4. Architecture Reference
5. Design Reference
6. AI Reference
7. Browser Testing
8. Codebase Patterns (summarised to top 10 bullets)
9. Codebase Snapshot (file contents removed, tree retained)

### 2. Configurable limits (`config.py`)

New `ContextLimitsConfig` in `pipeline-config.json`:

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

### 3. PRD generation integration (`prd_generation.py`)

After PRD generation: validates context bundle size, surfaces milestone-scope `context_weight` warnings, checks for domain-split recommendations.

### 4. PRD Writer SKILL.md updates

- Section priority documentation for truncation awareness
- Inline story context in `prd.json` (`context` object per story with verbatim upstream references)
- Multi-domain detection (Section 8b): generates `.ralph/domain-split-m{N}.md` to pause the pipeline for Strategy Planner re-planning
- Context weight reporting updated with pipeline-enforced limits awareness

### 5. Strategy Planner SKILL.md updates

- Rule 8 strengthened: "one domain per milestone"
- Rule 11 added: domain-split re-planning from PRD Writer recommendations

### 6. Tests — 20 new tests in `test_context_validator.py`

## Files Changed

| File | Change |
|------|--------|
| `src/ralph_pipeline/config.py` | Added `ContextLimitsConfig` + `context_limits` field |
| `src/ralph_pipeline/context_validator.py` | **New** — measurement, truncation, validation |
| `src/ralph_pipeline/phases/prd_generation.py` | Context validation + domain-split detection |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | Section priority, inline context, domain detection |
| `src/ralph_pipeline/data/skills/strategy_planner/SKILL.md` | Domain cohesion + re-planning rules |
| `tests/test_context_validator.py` | **New** — 20 tests |
