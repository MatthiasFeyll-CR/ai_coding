# Pipeline Workflow — End-to-End

The pipeline operates in four macro-phases. The specification and planning phases are driven manually by invoking Claude skills. The execution phase runs autonomously via `ralph-pipeline run`. The release phase is manual post-completion.

## Specification Phase (Manual)

Each skill produces a `handover.json` consumed by the next:

1. **Requirements Engineering** → `docs/01-requirements/` — 8-phase structured elicitation
2. **Software Architect** → `docs/02-architecture/` — Tech stack, data model, API, project structure, testing
3. **UI/UX Designer** → `docs/03-design/` — Design system, wireframes, components *(parallel with 3b)*
4. **AI Engineer** → `docs/03-ai/` — Agent architecture, prompts, tool schemas *(parallel with 3a)*
5. **Arch+AI Integrator** → `docs/03-integration/` — Reconciles architecture + AI docs
6. **Spec QA** → `docs/04-spec-qa/` — Quality gate: PASS / CONDITIONAL / FAIL
7. **Test Architect** → `docs/04-test-architecture/` — Test plan, matrix, fixtures, integration scenarios

## Planning Phase (Manual)

1. **Milestone Planner** → `docs/05-milestones/` — Milestone scope files with context-weight validation
2. **Pipeline Configurator** → `pipeline-config.json` + `.ralph/CLAUDE.md` — Machine-readable config with declarative infrastructure specs

## Execution Phase (Automated)

```
ralph-pipeline run --config pipeline-config.json

Phase 0: Bootstrap (once)
  Scaffolding → Test infra → Lifecycle verification → Config write-back

For each milestone (sequential):
  Phase 1: PRD Generation + Context Bundle
  Phase 2: Ralph Coding Loop (iterative Claude sessions)
  Phase 3: QA Review + Bugfix Cycles (up to max_bugfix_cycles)
  Phase 4: Merge + Test Ownership + Spec Reconciliation

State saved after every phase transition → resumable from any point
```

## Release Phase (Manual)

**Release Engineer** → `docs/09-release/` — Deployment documentation after all milestones complete.

**Pipeline Dashboard** — Utility skill for status overview at any time.

## Handover Chain

```
docs/01-requirements/handover.json
  → docs/02-architecture/handover.json
    → docs/03-design/handover.json     (parallel)
    → docs/03-ai/handover.json         (parallel)
      → docs/03-integration/handover.json
        → docs/04-spec-qa/handover.json
          → docs/04-test-architecture/handover.json
            → docs/05-milestones/handover.json
              → .ralph/handover.json
                → ralph-pipeline runs autonomously
```
