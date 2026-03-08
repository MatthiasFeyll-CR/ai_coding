# Context Management Strategy

## Problem

Without structured context, each Ralph iteration wastes tokens exploring docs. With N stories × M docs, the waste compounds across the entire milestone.

## Solution: Three Layers

### Layer 1 — Planning (Context Weight Sizing)

The Strategy Planner computes per-milestone context weight:
- Unique file paths (threshold: >30)
- Doc sections (threshold: >5)
- Story count (threshold: >10)

Over threshold → milestone is split along domain boundaries. Every milestone must fit in Ralph's context window.

### Layer 2 — Generation (Context Bundle)

The PRD Writer (Phase 1) assembles `.ralph/context.md` — a focused bundle containing:

| Source | Extracted Content |
|--------|------------------|
| `docs/02-architecture/` | Relevant tables, endpoints, project paths |
| `docs/03-design/` | Component specs for this milestone's stories |
| `docs/03-ai/` | Agent specs (if applicable) |
| `docs/04-test-architecture/` | Test cases assigned to this milestone |
| `.ralph/archive/*/progress.txt` | Codebase patterns (compressed learnings) |
| Actual codebase | File tree + contents of files stories will modify |

Rules: only referenced content, verbatim (no summarization), fresh per milestone.

### Layer 3 — Consumption (Ralph Reads)

Ralph's read order per iteration:
1. `.ralph/context.md` — primary (pre-assembled)
2. `.ralph/prd.json` — pick next story
3. `.ralph/progress.txt` — patterns + recent learnings
4. `docs/*` — fallback only

No exploration waste. Same specs every iteration. Consistent code.

## Context Validation

Metrics: line count + estimated tokens (lines × 5).

| Condition | Action |
|-----------|--------|
| Lines > max × warn_pct% | Warning logged |
| Lines > max (first time) | Auto-truncate by priority |
| Lines > max (second time) | `ContextOverflowError` (abort) |

Truncation priority (lowest priority removed first):
1. Codebase Snapshot (keeps tree, removes file contents)
2. Codebase Patterns
3. Browser Testing
4. AI Reference
5. Design Reference
6. Architecture Reference
7. Test Specifications
8. Test Infrastructure Setup
9. Quality Checks (highest — never truncated first)

## Bugfix Context Refresh

When QA fails and Ralph enters bugfix mode:
1. Strip stale Codebase Snapshot + Bugfix Context sections
2. Rebuild snapshot from actual files (PRD notes → extract paths, max 200 lines each)
3. Append bugfix context: QA failure summary + git diff stats + fix instructions
