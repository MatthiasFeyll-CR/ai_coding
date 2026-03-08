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
6. Extract PASS/FAIL verdict
7. PASS → archive → proceed | FAIL at max → escalation report

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

## Error Handling

| Phase | Error | Action |
|-------|-------|--------|
| 0 | Scaffolding/infra fails | Retry once → HARD STOP |
| 0 | Lifecycle verification fails | Claude fix ×3 → HARD STOP |
| 1 | PRD generation fails | Retry once → abort milestone |
| 1 | Domain split detected | HARD STOP (re-plan required) |
| 2 | Max iterations reached | Proceed to QA (partial) |
| 3 | QA FAIL after max cycles | Escalation report, continue |
| 4 | Merge conflict | Abort (should not happen) |
| 4 | Reconciliation fails | Retry once → warn + continue |
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
