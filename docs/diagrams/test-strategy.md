# Test Strategy

## Test Lifecycle

Tests flow from specification through implementation to enforcement:

1. **Test Architect** (spec phase) → test plan, test matrix, fixtures, integration scenarios
2. **PRD Writer** (Phase 1) → embeds test IDs into story notes, bundles specs into context
3. **Ralph** (Phase 2) → test-first story loop: write tests → verify fail → implement → verify pass (advisory — pipeline does not enforce test execution during Phase 2)
4. **QA Engineer** (Phase 3) → coverage analysis (FOUND/MISSING), code quality review
5. **Merge** (Phase 4) → register test ownership for future regression detection

## Two-Tier Infrastructure

### Tier 1 — Dev Containers
- Docker containers with bind-mounted source
- Hash-based rebuild: MD5 of dependency files, stored in `.ralph/.test-image-hashes`
- Available for Ralph to run during Phase 2 via CLAUDE.md instructions (not enforced by pipeline)
- Pipeline support: `TestRunner.run_tier1_tests()` exists but is not called in the main execution path

### Tier 2 — Full Rebuild
- Force teardown → build (no cache) → setup → health → test
- Runs once per QA cycle in Phase 3 (1 initial + up to `max_bugfix_cycles` retries)
- Catches stale builds and contract mismatches
- On fail: triggers bugfix cycle (Ralph bugfix → re-test → re-QA)

Both tiers use real services (DB, Redis, etc.) — no mocks.

> **Note:** The pipeline does NOT run tests during Phase 2. Test execution is entirely deferred to Phase 3 (QA Review). Ralph is instructed to run tests via CLAUDE.md's runtime footer, but this is advisory — the pipeline does not verify that Ralph actually ran them.

## Test Coverage Analysis (Phase 3)

### Extracting Expected Test IDs
3-tier priority per story:
1. Structured `testIds` array (deterministic — preferred)
2. Regex on `notes` string (fallback)
3. Regex on `context.test_cases` entries (fallback)

Recognized patterns: `T-N.N`, `API-N.N`, `DB-N.N`, `UI-N.N`, `LOOP-N`, `STATE-N`, `TIMEOUT-N`, `LEAK-N`, `INTEGRITY-N`, `AI-SAFE-N`, `SCN-N`, `JOURNEY-N`, `CONC-N`, `ERR-N`

### Finding Implemented Tests
3-tier strategy per ID:
1. `.ralph/test-manifest.json` lookup (deterministic)
2. Python AST: scan function names + docstrings (normalized: `T-1.2.01` → `t_1_2_01`)
3. `grep` across `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.go`, `.rs`, `.rb`

## Regression Analysis

After each merge, `build_test_map()` scans git diff for newly added test files → stores `{test_file: milestone_id}` in state.

When tests fail in a future milestone's QA:
1. Parse failing files (pytest, jest, vitest, Go patterns)
2. Lookup milestone owner: registry → git tag fallback
3. Classify: **REGRESSION** (owner < current) vs **CURRENT**
4. Regressions get targeted prompt: classification + merge diff + archived acceptance criteria
5. Current failures get standard fix prompt

> **Design note:** Regression analysis is wired into the QA bugfix path. When tests fail in `run_qa_review()`, failing tests are classified as REGRESSION (owned by prior milestone) vs CURRENT using `RegressionAnalyzer`. Regression context — including archived acceptance criteria and merge diffs from the regressed milestone — is injected into the bugfix context for targeted fix instructions.

## Test Fix Philosophy

- **Tests are contracts** — fix SOURCE CODE, not tests
- **Previous milestone tests**: NEVER modified, treated as regression contracts
- **Current milestone tests**: modified only if test itself has a clear bug
- **Domain context injection**: fix prompts include architecture, design, test specs
- **Results archived**: all test results stored in `docs/08-qa/` for audit trail

## Enforcement Points

| Phase | Point | Tier | Blocking | Mechanism |
|-------|-------|------|----------|-----------|
| 2 | Per-story checks | T1 | Advisory | Ralph is instructed via CLAUDE.md; pipeline does not enforce |
| 3 | QA test run | T2 | Yes | Test exit code is a **hard gate** — overrides AI PASS verdict if tests failed |
| 3 | Gate checks | — | Yes (if required) | `_run_gate_checks()` executes configured checks; required failures override AI verdict |

> **Design note:** The AI-generated QA report is still produced for diagnostic value (code quality review, coverage analysis, recommendations). However, the pipeline enforces two mechanistic hard gates that **cannot be overridden by the AI**: (1) non-zero test exit code → FAIL, and (2) failed required gate checks → FAIL. The AI verdict is only trusted when both hard gates pass.
