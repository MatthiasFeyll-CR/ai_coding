# Execution Phase — Pipeline Architecture

```
ralph-pipeline run --config pipeline-config.json
CLI: --resume | --milestone N | --dry-run
```

---

## Phase 0: Infrastructure Bootstrap

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 0: INFRASTRUCTURE BOOTSTRAP         (runs once)          │
│                                                                 │
│  Triggered: before milestone loop, if test_infrastructure       │
│  or scaffolding sections exist in pipeline-config.json          │
│                                                                 │
│  Step 1 — Scaffolding (Claude invocation):                      │
│  ├─ Read scaffolding.project_structure_doc                      │
│  ├─ Create all project directories                              │
│  ├─ If framework_boilerplate: generate framework init files     │
│  │   (Django manage.py+settings, React vite.config, etc.)       │
│  └─ Commit: "chore: project scaffolding from architecture spec" │
│                                                                 │
│  Step 2 — Test Infrastructure (Claude invocation):              │
│  ├─ Read test_infrastructure declarative spec                   │
│  ├─ Generate docker-compose.test.yml from services + runtimes   │
│  ├─ Generate Dockerfile.test-* for each runtime                 │
│  └─ Commit: "chore: test infrastructure from declarative spec"  │
│                                                                 │
│  Step 3 — Lifecycle Verification:                               │
│  ├─ Build test images (--no-cache)                              │
│  ├─ Start dependency services, verify readiness                 │
│  ├─ Run smoke test per runtime (e.g., pytest --collect-only)    │
│  ├─ Teardown, verify clean shutdown                             │
│  └─ If failure: Claude fix loop (max 3), then HARD STOP         │
│                                                                 │
│  Step 4 — Write Concrete Commands:                              │
│  ├─ Generate test_execution section in pipeline-config.json     │
│  │   (setup, teardown, test, build commands — both tiers)       │
│  ├─ Remove test_infrastructure section (consumed)               │
│  ├─ Remove scaffolding section (consumed)                       │
│  └─ Save updated config                                        │
│                                                                 │
│  State: phase0_complete = true in .ralph/state.json             │
│  Resume: if phase0_complete, skip Phase 0                       │
└─────────────────────────────────────────────────────────────────┘
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
│                          ┌────────────────▼────┐                 │
│                          │ Phase 4             │                 │
│                          │ Merge+Reconcile     │                 │
│                          └─────────┬───────────┘                 │
│                                │                                │
│                                ▼                                │
│                          save state → next milestone             │
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

## Phase 4: Merge + Reconciliation

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: MERGE + RECONCILIATION                                │
│                                                                 │
│  The pipeline uses a single linear coding agent, so the         │
│  feature branch diverges from base at a point where nothing     │
│  else changes.  The merge is trivial and the merged code is     │
│  identical to what QA validated.  No post-merge verification.   │
│                                                                 │
│  Step 1 — Merge:                                                │
│  ├─ Commit any dirty pipeline artifacts                         │
│  ├─ Checkout base branch                                        │
│  ├─ Tag: pre-mN-merge (rollback point)                          │
│  └─ git merge ralph/mN-slug --no-ff into base                   │
│                                                                 │
│  Step 2 — Register Test Ownership:                              │
│  └─ build_test_milestone_map(N) — record {file: milestone}      │
│     in .ralph/state.json (for future milestone QA)              │
│                                                                 │
│  Step 3 — Tag + Cleanup:                                        │
│  ├─ git tag mN-complete                                         │
│  └─ Delete milestone branch                                     │
│                                                                 │
│  Step 4 — Spec Reconciliation:              /spec_reconciler    │
│  ├─ Collect deviations from progress.txt + QA report            │
│  ├─ Update upstream docs (requirements, architecture, design)   │
│  └─ Output: docs/05-reconciliation/mN-changes.md               │
│                                                                 │
│  On merge conflict: abort (should not happen in linear flow)    │
│  On reconciliation failure: retry once, then warn and continue  │
│  (non-fatal — stale specs degrade future PRDs but don't block)  │
│                                                                 │
│  Commit spec changes so next milestone sees up-to-date specs.   │
└─────────────────────────────────────────────────────────────────┘
```
│                                                                 │
│  Step 6 — Tag + Cleanup:                                        │
│  ├─ git tag mN-complete                                         │
│  └─ Delete milestone branch                                     │
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
│  │   └─ phase0_complete: bool      (Phase 0 bootstrap status)  │
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
│  0      Scaffolding generation fail  Retry once, HARD STOP     │
│  0      Test infra generation fail   Retry once, HARD STOP     │
│  0      Lifecycle verification fail  Claude fix ×3, HARD STOP  │
│  1      PRD generation fails         Retry once, abort          │
│  2      Ralph max iterations         Proceed to QA (partial)    │
│  3      QA FAIL after max cycles     Escalation report, cont.   │
│  4      Merge conflict               Abort (should not happen)  │
│  4      Reconciliation fails         Retry once, warn+continue  │
│  *      Claude subprocess crash      Retry × max_retries        │
│  *      Infra build/setup fails      Skip tests, return error   │
│                                                                 │
│  Resume: ralph-pipeline run --config ... --resume               │
│  State is saved after every FSM transition.                     │
└─────────────────────────────────────────────────────────────────┘
```
