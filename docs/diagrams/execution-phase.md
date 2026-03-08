# Execution Phase — Detailed Breakdown

## Phase 0: Infrastructure Bootstrap

Runs once before the milestone loop. Triggered if `test_infrastructure` or `scaffolding` sections exist in the config.

| Step | Action | Output |
|------|--------|--------|
| 1. Scaffolding | Claude creates project directories + framework boilerplate | Committed to base branch |
| 2. Test Infra | Claude generates `docker-compose.test.yml` + Dockerfiles | Committed to base branch |
| 3. Verification | Build → setup → health → smoke → teardown cycle | `.ralph/phase0-verification.json` |
| 4. Config Write-Back | Generate concrete `test_execution` commands, remove consumed sections | Updated `pipeline-config.json` |

On verification failure: Claude fix loop (max 3 attempts) → HARD STOP.
Resume: skipped if `state.phase0.phase0_complete == true`.

## Main Loop (FSM)

```
FOR each milestone (sequential, dependency order):
  Phase 1 → Phase 2 → Phase 3 → Phase 4
  State saved after each transition
  Signal handlers: SIGINT/SIGTERM → persist + teardown
```

## Phase 1: PRD Generation

- Checks if `tasks/prd-mN.json` exists (resume → skip)
- Reads PRD Writer skill, milestone scope, archive learnings
- Injects drift warning if prior reconciliation failed
- Validates context bundle size
- Detects domain-split recommendations → halt if found

Outputs: `tasks/prd-mN.json`, `.ralph/context.md`

## Phase 2: Ralph Execution

### Workspace Setup
- Symlink `.ralph/prd.json` → `tasks/prd-mN.json`
- Initialize `progress.txt` (Implementation Log, Codebase Patterns, Deviations)
- Create/checkout feature branch `ralph/mN-slug`

### Runtime Footer Injection
Appends to `CLAUDE.md`: test commands (Tier 1/2), integration tests, gate checks. Idempotent (strips previous footer first).

### Agent Loop
- Budget: `effective_stories × max_iterations_multiplier`
- Each iteration: read `CLAUDE.md` as prompt → invoke Claude → check for `<promise>COMPLETE</promise>`
- 2-second delay between iterations
- No tests run post-completion — testing is deferred to Phase 3 (QA)

### Bugfix Mode
- Triggered by QA FAIL
- Shorter budget (multiplier=2)
- Refreshes context with current codebase + QA summary
- Injects bugfix notice into `CLAUDE.md`

## Phase 3: QA Review

For each cycle (0 to `max_bugfix_cycles`):
1. If cycle > 0: run Ralph bugfix first
2. Run full test suite (Tier 2)
3. Analyze test coverage:
   - Extract expected IDs: structured `testIds` → regex on `notes` → regex on `context.test_cases`
   - Find implemented IDs: `test-manifest.json` → Python AST → grep
4. Build QA prompt with skill, results, coverage, test architecture
5. Invoke Claude QA Engineer
6. Extract PASS/FAIL verdict from AI-generated report via regex
7. PASS → archive → proceed | FAIL at max → escalation report

> **Design notes:**
> - The AI verdict is extracted via `_extract_verdict()` regex, but **hard gates override it**: if the test exit code is non-zero or required gate checks fail, a PASS verdict is mechanistically overridden to FAIL. The AI report is still generated for diagnostic value.
> - Gate checks (typecheck, lint, etc.) from `pipeline-config.json` are now executed by `_run_gate_checks()` before the verdict is finalized.
> - Regression analysis classifies test failures as REGRESSION (owned by prior milestone) vs CURRENT before bugfix cycles. Regression context (archived acceptance criteria, merge diffs) is injected into the bugfix context.
> - Bugfix cycles run inside `run_qa_review()`. On resume, the bugfix cycle counter restarts from 0.

## Phase 4: Merge + Reconciliation

### Merge
1. Commit dirty artifacts
2. Checkout base, tag `pre-mN-merge`
3. Merge `--no-ff`
4. Register test ownership via `build_test_map()`
5. Tag `mN-complete`, delete feature branch

### Reconciliation
1. **Deterministic**: Scan doc path references vs actual file tree → drift report
2. **AI-powered**: Claude with Spec Reconciler skill → update upstream docs
3. Retry once if changelog not produced
4. Non-fatal: failures tracked as reconciliation debt

> **Design notes:**
> - The reconciliation prompt classifies changes by autonomy level: SMALL TECHNICAL (auto-apply), FEATURE DESIGN and LARGE TECHNICAL (apply but flag for review). This aligns with the Spec Reconciler skill's own autonomy classification.
> - **Docs-only guard**: After each reconciliation attempt, the pipeline checks `git diff` for any modified files outside `docs/` and `.ralph/`. If violations are found, all uncommitted changes are reverted (`git checkout . && git clean -fd`) and the pipeline hard-exits with `ReconciliationScopeViolation`.
> - No post-merge tests are run — the assumption is that the merged code is byte-identical to what QA validated. Reconciliation can only commit documentation changes to the base branch.

## Error Handling

| Phase | Error | Action |
|-------|-------|--------|
| 0 | Scaffolding/infra fails | Retry once → HARD STOP |
| 0 | Lifecycle verification fails | Claude fix ×3 → HARD STOP |
| 1 | PRD generation fails | Retry once → abort milestone |
| 1 | Domain split detected | HARD STOP (re-plan required) |
| 2 | Max iterations reached | Proceed to QA (partial) |
| 3 | QA FAIL after max cycles | Escalation report, milestone FAILS |
| 3 | Test exit code != 0 | Hard gate: overrides AI PASS verdict to FAIL |
| 4 | Merge conflict | Abort (should not happen) |
| 4 | Reconciliation fails | Retry once → warn + continue |
| 4 | Scope violation (non-docs files modified) | Revert all changes → HARD STOP |
| * | Claude crash | Retry × max_retries |
| * | Cost budget exceeded | Fatal, no retry |
| * | SIGINT/SIGTERM | Persist state → teardown → exit |

## State & Artifacts

| Artifact | Location |
|----------|----------|
| FSM state | `.ralph/state.json` |
| Event log | `.ralph/logs/pipeline.jsonl` |
| Active PRD | `.ralph/prd.json` (symlink to `tasks/prd-mN.json`) |
| Context bundle | `.ralph/context.md` |
| Progress | `.ralph/progress.txt` |
| QA reports | `docs/08-qa/qa-mN-slug.md` |
| Test results | `docs/08-qa/test-results-*.md` |
| Reconciliation | `docs/05-reconciliation/mN-changes.md` |
| Drift report | `docs/05-reconciliation/mN-deterministic-drift.md` |
| Git tags | `pre-mN-merge`, `mN-complete` |
| Archive | `.ralph/archive/<slug>/prd.json`, `progress.txt` |

## Known Limitations & Risks

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| 1 | ~~CRITICAL~~ | ~~QA verdict is AI-determined, not test-exit-code~~ | **RESOLVED** — test exit code hard gate overrides AI verdict |
| 2 | CRITICAL | Phase 2 runs zero tests; Ralph self-grades via `<promise>COMPLETE</promise>` | **By design** — Phase 2 defers all testing to Phase 3 (see Phase 2 design rationale below) |
| 3 | ~~CRITICAL~~ | ~~Gate checks are prompt suggestions, never executed~~ | **RESOLVED** — `_run_gate_checks()` now executes all configured gate checks |
| 4 | ~~SEVERE~~ | ~~Reconciliation prompt overrides skill autonomy~~ | **RESOLVED** — prompt now classifies by autonomy level, flags non-trivial changes |
| 5 | ~~SEVERE~~ | ~~FSM `qa_needs_fix` transition is dead code~~ | **RESOLVED** — dead transition removed |
| 6 | ~~SEVERE~~ | ~~`run_test_fix_cycle()` never called; regression analysis not wired~~ | **RESOLVED** — regression classification wired into QA bugfix path |
| 7 | ~~MODERATE~~ | ~~Test/gate commands in 3 places (config, CLAUDE.md footer, context.md)~~ | **RESOLVED** — quality commands removed from context.md; config → CLAUDE.md footer is single path |
| 8 | MODERATE | Cross-milestone patterns depend on Ralph writing to `progress.txt` | No enforcement of pattern recording |
| 9 | ~~MINOR~~ | ~~Resume checks phantom `merge_verify` state~~ | **RESOLVED** — dead code removed |
| 10 | ~~MINOR~~ | ~~`cli.py:main()` has 6 duplicate `sys.exit(0)` calls~~ | **RESOLVED** — duplicates removed |

## Phase 2 Design Rationale — No Pipeline-Enforced Tests

Phase 2 intentionally does not run tests at the pipeline level. This is a deliberate architectural decision:

1. **Separation of concerns**: Phase 2 is the *coding* phase. Phase 3 is the *verification* phase. Mixing them would couple Ralph's iteration budget to test infrastructure availability.
2. **Tier 2 full-rebuild guarantee**: Phase 3 runs Tier 2 tests (force teardown → clean build → test), catching stale builds and contract mismatches that incremental testing during Phase 2 would miss.
3. **Advisory testing via CLAUDE.md**: Ralph is *instructed* to run Tier 1 tests via the CLAUDE.md runtime footer. The pipeline does not enforce this, but Claude agents typically follow these instructions. Any failures Ralph misses are caught by Phase 3.
4. **Bugfix cycle safety**: When Phase 3 fails, the bugfix cycle refreshes context with the full QA report and current codebase snapshot, giving Ralph targeted fix instructions rather than iterating blindly.
