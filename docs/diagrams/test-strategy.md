# Test Strategy

## Test Lifecycle

Tests flow from specification through implementation to enforcement:

1. **Test Architect** (spec phase) → test plan, test matrix, fixtures, integration scenarios
2. **PRD Writer** (Phase 1) → embeds test IDs into story notes, bundles specs into context
3. **Ralph** (Phase 2) → test-first story loop: write tests → verify fail → implement → verify pass
4. **QA Engineer** (Phase 3) → coverage analysis (FOUND/MISSING), code quality review
5. **Merge** (Phase 4) → register test ownership for future regression detection

## Two-Tier Infrastructure

### Tier 1 — Dev Containers
- Docker containers with bind-mounted source
- Per-story execution (~30×/milestone)
- Hash-based rebuild: MD5 of dependency files, stored in `.ralph/.test-image-hashes`
- On fail: Ralph fixes inline before committing

### Tier 2 — Full Rebuild
- Force teardown → build (no cache) → setup → health → test
- QA phase (~3×/milestone)
- Catches stale builds and contract mismatches
- On fail: Claude fix cycle → escalation

Both tiers use real services (DB, Redis, etc.) — no mocks.

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

## Test Fix Philosophy

- **Tests are contracts** — fix SOURCE CODE, not tests
- **Previous milestone tests**: NEVER modified, treated as regression contracts
- **Current milestone tests**: modified only if test itself has a clear bug
- **Domain context injection**: fix prompts include architecture, design, test specs
- **Results archived**: all test results stored in `docs/08-qa/` for audit trail

## Enforcement Points

| Phase | Point | Tier | Blocking |
|-------|-------|------|----------|
| 2 | Per-story checks | T1 | Yes (Ralph self-fixes) |
| 2 | Post-Ralph run | T2 | No (logged only) |
| 3 | Pre-QA run | T2 | No (fed to QA reviewer) |
