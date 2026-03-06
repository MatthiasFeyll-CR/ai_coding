# Test Strategy — Full Lifecycle

How tests are designed, written, and enforced across the pipeline.

---

## Test Flow Through the Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  TEST LIFECYCLE — FROM SPEC TO ENFORCEMENT                      │
│                                                                 │
│  SPECIFICATION PHASE                                            │
│                                                                 │
│  [4b] Test Architect                                            │
│    │  Produces: test-plan.md, test-matrix.md, test-fixtures.md, │
│    │  integration-scenarios.md, runtime-safety.md               │
│    │                                                            │
│    ▼                                                            │
│  EXECUTION PHASE (automated per milestone)                      │
│                                                                 │
│  [Phase 1] PRD Writer                                           │
│    │  Embeds test IDs + definitions into story Notes             │
│    │  Bundles test specs into .ralph/context.md                  │
│    │                                                            │
│    ▼                                                            │
│  [Phase 2] Ralph — Test-First Story Loop                        │
│    │  Per story: writes tests → verifies fail → implements      │
│    │                                                            │
│    ▼                                                            │
│  [Phase 3] QA Engineer                                          │
│    │  Pipeline runs analyze_test_coverage() → FOUND/MISSING     │
│    │  QA reviews coverage report + code quality                 │
│    │                                                            │
│    ▼                                                            │
│  [Phase 4] Merge + Verify                                       │
│    │  Registers test ownership: build_test_milestone_map()      │
│    │  Runs full test suite. On fail → regression analysis:      │
│    │  ├─ REGRESSION (prev M) → targeted fix with merge diff    │
│    │  └─ CURRENT (this M) → standard fix prompt                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Test Authoring: Test-First vs Implement-First

```
┌─────────────────────────────────────────────────────────────────┐
│  STORY ITERATION — TEST AUTHORING DECISION                      │
│                                                                 │
│       ┌──────────────────────────────────┐                      │
│       │  Pick story from prd.json        │                      │
│       └──────────────┬───────────────────┘                      │
│                      ▼                                          │
│       ┌──────────────────────────────────┐                      │
│       │  Story notes contain "Testing:"  │                      │
│       │  references to test-matrix IDs?  │                      │
│       └──────┬───────────────┬───────────┘                      │
│              │               │                                  │
│             YES             NO                                  │
│              │               │                                  │
│              ▼               ▼                                  │
│  ┌───────────────────┐ ┌───────────────────┐                    │
│  │  TEST-FIRST (TDD) │ │  IMPLEMENT-FIRST  │                    │
│  │  Write tests      │ │  Implement feature│                    │
│  │  Verify FAIL      │ │  Write tests      │                    │
│  │  Implement        │ │  Run quality checks│                    │
│  │  Verify PASS      │ └───────────────────┘                    │
│  │  Quality checks   │                                          │
│  └───────────────────┘  Used for: scaffolding, config,          │
│                         stories without test-matrix entries      │
│  Used for: stories with                                         │
│  T-X.X, API-X, DB-X, UI-X,                                     │
│  LOOP-X, STATE-X test IDs                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Two-Tier Testing

```
┌─────────────────────────────────────────────────────────────────┐
│  TWO-TIER TESTING                                               │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  TIER 1 — Dev Test Containers (per story, ~30×/milestone) │  │
│  │  Docker containers with bind-mounted source code          │  │
│  │  Fresh containers + volumes per run (clean state)         │  │
│  │  Image rebuild: only when dependency files change (hash)  │  │
│  │  On fail: Ralph fixes inline, retries before committing   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                          ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  TIER 2 — Full Rebuild (post-merge, ~3×/milestone)        │  │
│  │  All images rebuilt --no-cache + fresh services            │  │
│  │  Catches stale builds, contract mismatches                │  │
│  │  On fail: Claude fix cycle, HARD STOP if exhausted        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Both tiers use real services (DB, Redis, etc.) — no mocks.    │
│  Hash-based rebuild: tracks dependency file checksums in        │
│  .ralph/.test-image-hashes to skip unnecessary image rebuilds. │
└─────────────────────────────────────────────────────────────────┘
```

---

## Test Enforcement Points

```
┌─────────────────────────────────────────────────────────────────┐
│  TEST ENFORCEMENT POINTS                                        │
│                                                                 │
│   Phase  Point              Tier   Blocking?  Command           │
│   ────── ────────────────── ────── ────────── ──────────────── │
│   2      Per-story checks   T1     Yes*       test_command      │
│   2      Post-Ralph run     T2     No         test_command      │
│   3      Pre-QA run         T2     No         test_command      │
│   4      Post-merge tests   T2     YES        test_command      │
│   4      Integration tests  T2     YES        integration_cmd   │
│   4      Gate checks        —      YES        gate_checks[]     │
│                                                                 │
│   * Ralph self-fixes inline before committing                   │
│                                                                 │
│   Post-merge (Phase 4) runs THREE different command types:      │
│   D = test_command     (unit/contract tests)                    │
│   E = integration_cmd  (cross-service/E2E — if configured)     │
│   F = gate_checks[]    (lint, typecheck, docker build)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Regression Analysis

```
┌─────────────────────────────────────────────────────────────────┐
│  REGRESSION ANALYSIS (Phase 4 — post-merge)                     │
│                                                                 │
│  Tests fail after merge                                         │
│       │                                                         │
│       ▼                                                         │
│  Parse failing test files from output                           │
│  Look up milestone owner (state.json registry → git fallback)   │
│  Classify: REGRESSION (prev M) vs CURRENT (this M)             │
│       │                                                         │
│       ├─ Regressions found → TARGETED PROMPT:                   │
│       │  ├─ Classification summary                              │
│       │  ├─ git diff pre-mN-merge..HEAD                         │
│       │  ├─ Archived PRD context for broken milestones          │
│       │  └─ Constraint: fix M(N) code, never prev tests         │
│       │                                                         │
│       └─ No regressions → STANDARD PROMPT:                      │
│          └─ Test output + constraint: fix source, not tests      │
│       │                                                         │
│       ▼                                                         │
│  Claude modifies source → commit → re-run tests                 │
│  ├─ PASS → continue      └─ FAIL → retry → HARD STOP           │
│                                                                 │
│  Test ownership tracking:                                       │
│  ├─ build_test_milestone_map() records {file: milestone}        │
│  │   in .ralph/state.json after each merge                      │
│  └─ Enables REGRESSION vs CURRENT classification                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Test Fix Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│  TEST FIX PHILOSOPHY                                            │
│                                                                 │
│  RULE: Tests are contracts. Fix SOURCE CODE, not tests.         │
│                                                                 │
│  Previous milestone tests:                                      │
│  ├─ NEVER modified                                              │
│  ├─ Treated as regression contracts                             │
│  └─ If they break → current milestone's code is wrong           │
│                                                                 │
│  Current milestone tests:                                       │
│  ├─ Written test-first from test-matrix specs                   │
│  ├─ Modified only if the test itself has a clear bug            │
│  └─ Implementation must satisfy them, not the other way around  │
│                                                                 │
│  Results stored: docs/08-qa/ (audit trail for every run)        │
└─────────────────────────────────────────────────────────────────┘
```
