# Pipeline Workflow — Global Overview

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                        SPECIFICATION PHASE                          │
  │                 (Manual — user invokes each skill)                  │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  [1] Requirements Engineer        /requirements_engineering         │
  │      docs/01-requirements/                                          │
  │      8-phase elicitation → handover.json                            │
  │                          │                                          │
  │                          ▼                                          │
  │  [2] Software Architect           /software_architect               │
  │      docs/02-architecture/                                          │
  │      Tech stack → data model → API → project structure → tests      │
  │                          │                                          │
  │              ┌───────────┼───────────┐                              │
  │              ▼                       ▼                              │
  │  [3a] UI/UX Designer     [3b] AI Engineer        (parallel)         │
  │       /ui_ux_designer          /ai_engineer                         │
  │       docs/03-design/          docs/03-ai/                          │
  │              │                       │                              │
  │              └───────────┬───────────┘                              │
  │                          ▼                                          │
  │  [3c] Arch+AI Integrator         /arch_ai_integrator                │
  │       docs/03-integration/                                          │
  │                          │                                          │
  │                          ▼                                          │
  │  [4] Spec QA                         /spec_qa                       │
  │      docs/04-spec-qa/                                               │
  │      Verdict: PASS / CONDITIONAL PASS / FAIL                        │
  │                          │                                          │
  │                          ▼                                          │
  │  [4b] Test Architect                /test_architect                 │
  │       docs/04-test-architecture/                                    │
  │       Test plan → test matrix → fixtures → integration → runtime    │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                         PLANNING PHASE                              │
  │               (Manual — user invokes each skill)                    │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  [5] Strategy Planner               /strategy_planner               │
  │      docs/05-milestones/                                            │
  │      Dependency analysis → milestone scope files → handoff          │
  │                          │                                          │
  │                          ▼                                          │
  │  [6] Pipeline Configurator          /pipeline_configurator          │
  │      pipeline-config.json + .ralph/CLAUDE.md                        │
  │      Translates strategy into machine-readable config               │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                        EXECUTION PHASE                              │
  │            (Automated — ralph-pipeline orchestrates)                │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  ralph-pipeline run --config pipeline-config.json                   │
  │                                                                     │
  │  Iterates through milestones sequentially, each runs 5 phases:      │
  │  PRD + Context Bundle → Ralph Coding → QA Review →                  │
  │  Merge+Verify → Reconcile                                           │
  │                                                                     │
  │  Skills invoked: /prd_writer, /qa_engineer, /spec_reconciler        │
  │  State persisted at .ralph/state.json after each phase transition   │
  │                                                                     │
  │  See: docs/diagrams/execution-phase.md for detailed breakdown       │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       RELEASE PHASE                                 │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  [8] Release Engineer                /release_engineer              │
  │      docs/09-release/                                               │
  │      (after all milestones complete)                                │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘

    Utilities:  /pipeline_dashboard — unified status overview at any time

  ┌─────────────────────────────────────────────────────────────────────┐
  │                        HANDOVER FLOW                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  Every step produces a JSON handover file with:                     │
  │  - from/to fields, files_produced list, next_commands               │
  │                                                                     │
  │  docs/01-requirements/handover.json                                 │
  │    → docs/02-architecture/handover.json                             │
  │      → docs/03-design/handover.json     (parallel)                  │
  │      → docs/03-ai/handover.json         (parallel)                  │
  │        → docs/03-integration/handover.json                          │
  │          → docs/04-spec-qa/handover.json                            │
  │            → docs/04-test-architecture/handover.json                │
  │              → docs/05-milestones/handover.json                     │
  │                → .ralph/handover.json                               │
  │                  → ralph-pipeline runs autonomously                 │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```
