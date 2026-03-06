# Execution Phase — Pipeline Architecture

```
ralph-pipeline run --config pipeline-config.json
CLI: --resume | --milestone N | --dry-run
```

---

## Main Loop

```
┌─────────────────────────────────────────────────────────────────┐
│  PIPELINE MAIN LOOP (FSM via transitions library)               │
│                                                                 │
│  PipelineConfig.load(pipeline-config.json)                      │
│  State persisted → .ralph/state.json                            │
│                                                                 │
│  FOR each milestone (sequential, dependency order):             │
│                                                                 │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐                 │
│    │ Phase 1  │───►│ Phase 2  │───►│ Phase 3  │                 │
│    │ PRD Gen  │    │ Ralph    │    │ QA+Bugfix│                 │
│    └──────────┘    └──────────┘    └─────┬────┘                 │
│                                          │                      │
│         ┌──────────┐    ┌────────────────▼────┐                 │
│         │ Phase 5  │◄───│ Phase 4             │                 │
│         │ Reconcile│    │ Merge+Verify        │                 │
│         └─────┬────┘    │ (tests + gates)     │                 │
│               │         └─────────────────────┘                 │
│               ▼                                                 │
│         save state → next milestone                             │
│                                                                 │
│  ► Signal handlers: SIGINT/SIGTERM → persist state + teardown   │
│  ► Resume: ralph-pipeline run --config ... --resume             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: PRD Generation + Context Bundle

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: PRD GENERATION + CONTEXT BUNDLE       /prd_writer     │
│                                                                 │
│  Inputs:                                                        │
│  ├─ docs/05-milestones/milestone-N.md  (scope file)             │
│  ├─ ALL upstream docs + actual codebase (ground truth)          │
│  └─ .ralph/archive/ (learnings from prior milestones)           │
│                                                                 │
│  Outputs:                                                       │
│  ├─ tasks/prd-mN.json           (Ralph-consumable JSON)        │
│  └─ .ralph/context.md           (context bundle for Ralph)     │
│                                                                 │
│  Context bundle contains:                                       │
│  ├─ Codebase Patterns from archived progress.txt                │
│  ├─ Relevant upstream doc sections (architecture, design, AI)   │
│  ├─ Test specifications for this milestone's stories            │
│  └─ Codebase snapshot (file tree + contents of referenced files)│
│                                                                 │
│  Key: PRDs written per-milestone, not upfront.                  │
│  Each PRD sees the real codebase from all previous milestones.  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 2: Ralph Execution

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: RALPH EXECUTION                          ralph.sh     │
│                                                                 │
│  Branch from HEAD → ralph/mN-slug                               │
│  Ralph sees the full codebase from all previous milestones.     │
│                                                                 │
│  max_iterations = stories × iterations_multiplier               │
│                                                                 │
│  Loop: read context.md → pick story → implement → test → commit │
│  Stuck detection: 3 consecutive failures → skip story           │
│                                                                 │
│  Terminal states: ALL_PASS | STUCK | MAX_ITERATIONS             │
│                                                                 │
│  Post-Ralph: run_test_suite — LIGHT mode (log only)             │
│    Results → docs/08-qa/test-results-post-ralph-mN.md           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 3: QA + Bugfix Cycles

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: QA + BUGFIX CYCLES                    /qa_engineer    │
│                                                                 │
│  Step 1: run_test_suite → results injected into QA prompt       │
│  Step 2: analyze_test_coverage (FOUND/MISSING per test ID)      │
│                                                                 │
│  QA review checks:                                              │
│  ├─ Acceptance criteria (story-by-story)                        │
│  ├─ Test matrix coverage (pipeline-scanned + manual review)     │
│  ├─ Test results (ground truth from step 1)                     │
│  ├─ Quality gates (typecheck, lint, build)                      │
│  └─ Security + performance review                               │
│                                                                 │
│  Verdict:                                                       │
│         ┌────────┐          ┌──────┐                            │
│         │  PASS  │          │ FAIL │                             │
│         └───┬────┘          └──┬───┘                            │
│             │                  │                                 │
│             │          QA writes bugfix prd.json                 │
│             │          Re-run Ralph (bugfix mode)                │
│             │          Re-run QA (cycle 2, 3...)                 │
│             │          cycle > max → ESCALATE                   │
│             │                  │                                 │
│             ▼                  ▼                                 │
│       Proceed to merge   Proceed (best effort)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 4: Merge + Verify

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: MERGE + VERIFY                                        │
│                                                                 │
│  Step 1 — Merge:                                                │
│  ├─ Tag: pre-mN-merge (rollback point)                          │
│  ├─ Dry-run conflict check                                      │
│  └─ git merge ralph/mN-slug --no-ff into base                   │
│                                                                 │
│  Step 2 — Register Test Ownership:                              │
│  └─ build_test_milestone_map(N) — record {file: milestone}      │
│     in .ralph/state.json                                        │
│                                                                 │
│  Step 3 — Post-Merge Tests (regression-aware):                  │
│  ┌───────────────────────────────────────────────────────┐      │
│  │  On failure → REGRESSION ANALYSIS:                    │      │
│  │  ├─ Parse failing test files from output              │      │
│  │  ├─ Classify: REGRESSION (prev M) vs CURRENT (this M)│      │
│  │  ├─ Regressions → targeted prompt with merge diff     │      │
│  │  │   + archived PRD + constraint: never modify prev   │      │
│  │  │   milestone tests (they are contracts)              │      │
│  │  └─ No regressions → standard fix prompt              │      │
│  │  On exhaust: HARD STOP — manual fix required          │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                 │
│  Step 4 — Integration Tests (if configured):                    │
│  └─ Same regression-aware fix cycle. HARD STOP on exhaust.      │
│                                                                 │
│  Step 5 — Config-driven Gate Checks:                            │
│  ├─ Lint, typecheck, docker build (condition-gated)             │
│  └─ On failure: Claude fix loop, HARD STOP if still failing     │
│                                                                 │
│  Step 6 — Tag + Cleanup:                                        │
│  ├─ git tag mN-complete                                         │
│  └─ Delete milestone branch                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 5: Spec Reconciliation

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5: SPEC RECONCILIATION                /spec_reconciler   │
│                                                                 │
│  ├─ Collect deviations from progress.txt + QA report            │
│  ├─ Update upstream docs (requirements, architecture, design)   │
│  └─ Output: docs/05-reconciliation/mN-changes.md               │
│                                                                 │
│  On failure: retry once, then warn and continue                 │
│  (non-fatal — stale specs degrade future PRDs but don't block)  │
│                                                                 │
│  Commit spec changes so next milestone sees up-to-date specs.   │
└─────────────────────────────────────────────────────────────────┘
```

---

## State & Artifacts

```
┌─────────────────────────────────────────────────────────────────┐
│  STATE & ARTIFACTS                                              │
│                                                                 │
│  State:                                                         │
│  ├─ .ralph/state.json              (FSM state per milestone)    │
│  └─ .ralph/logs/pipeline.jsonl     (structured event log)       │
│                                                                 │
│  Per-Milestone:                                                 │
│  ├─ tasks/prd-mN.json              (Ralph-consumable PRD)      │
│  ├─ .ralph/prd.json                (active PRD)                │
│  ├─ .ralph/context.md              (context bundle)            │
│  ├─ .ralph/progress.txt            (Ralph execution log)       │
│  ├─ docs/08-qa/qa-mN-slug.md       (QA report)                │
│  ├─ docs/08-qa/test-results-*.md    (test results per phase)   │
│  ├─ docs/05-reconciliation/mN-changes.md                        │
│  └─ git tags: pre-mN-merge, mN-complete                        │
│                                                                 │
│  Archive (after QA pass):                                       │
│  ├─ .ralph/archive/<slug>/prd.json                             │
│  └─ .ralph/archive/<slug>/progress.txt                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Error Handling

```
┌─────────────────────────────────────────────────────────────────┐
│  ERROR HANDLING                                                 │
│                                                                 │
│  Phase  Error                        Action                     │
│  ────── ──────────────────────────── ────────────────────────── │
│  1      PRD generation fails         Retry once, abort          │
│  2      Ralph max iterations         Proceed to QA (partial)    │
│  3      QA FAIL after max cycles     Escalation report, cont.   │
│  4      Post-merge tests fail        Auto-fix ×5, HARD STOP    │
│  4      Integration tests fail       Auto-fix ×5, HARD STOP    │
│  4      Gate check fail              Claude fix ×3, HARD STOP  │
│  4      Merge conflict               Abort (should not happen)  │
│  5      Reconciliation fails         Retry once, warn+continue  │
│  *      Claude subprocess crash      Retry × max_retries        │
│  *      Infra build/setup fails      Skip tests, return error   │
│                                                                 │
│  Resume: ralph-pipeline run --config ... --resume               │
│  State is saved after every FSM transition.                     │
└─────────────────────────────────────────────────────────────────┘
```
