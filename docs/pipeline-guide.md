# Ralph Pipeline — Reference Guide

## Overview

Ralph Pipeline is a Python CLI framework that orchestrates multi-milestone software projects using Claude AI agents. It drives each milestone through a structured phase lifecycle — from PRD generation to code implementation, quality assurance, and spec reconciliation — fully autonomously.

## Configuration

Everything starts with `pipeline-config.json`:

```json
{
  "project": { "name": "MyApp", "description": "..." },
  "milestones": [
    { "id": 1, "slug": "foundation", "name": "Foundation", "stories": 3 },
    { "id": 2, "slug": "core", "name": "Core", "stories": 5, "dependencies": [1] }
  ],
  "models": {
    "ralph": "claude-sonnet",
    "prd_generation": "claude-opus",
    "qa_review": "claude-opus",
    "reconciliation": "claude-sonnet"
  },
  "test_execution": {
    "test_command": "npm test",
    "services": [{ "name": "postgres", "type": "tcp", "host": "localhost", "port": 5432 }]
  },
  "gate_checks": {
    "checks": [
      { "name": "lint", "command": "npm run lint" },
      { "name": "typecheck", "command": "npm run typecheck" }
    ]
  },
  "cost": { "budget_usd": 50.0, "warn_at_pct": 80 },
  "context_limits": { "max_lines": 3000, "max_tokens": 15000, "warn_pct": 80 }
}
```

Milestones are validated at load time: no missing dependencies, no circular dependencies, correct ordering.

## Phase Lifecycle

Every milestone passes through these phases, managed by a finite state machine (`transitions` library):

```
pending → prd_generation → ralph_execution → qa_review → reconciliation → complete
```

> Bugfix cycles run *inside* Phase 3 (`run_qa_review()`), not as FSM transitions. On QA FAIL, Ralph bugfix mode is triggered internally, then QA re-runs. Up to `max_bugfix_cycles` iterations.

### Phase 0 — Infrastructure Bootstrap (runs once)

Converts declarative `test_infrastructure` and `scaffolding` specs into concrete infrastructure. Generates Docker Compose files, verifies the lifecycle (build → setup → health → smoke → teardown), and writes concrete `test_execution` commands back into the config. Consumed sections are removed after bootstrap.

### Phase 1 — PRD Generation

Invokes the PRD Writer skill to produce `tasks/prd-mN.json` and `.ralph/context.md`. The context bundle contains milestone-scoped architecture, design, test specs, codebase patterns from prior milestones, and a codebase snapshot. Context is validated against size limits (truncation by priority if exceeded).

### Phase 2 — Ralph Execution

Creates feature branch `ralph/mN-slug`, injects runtime footer (test commands, gate checks) into `CLAUDE.md`, then runs an iterative Claude coding loop. Iteration budget: `stories × max_iterations_multiplier`. Loops until `<promise>COMPLETE</promise>` signal or budget exhaustion. No tests are run at the end of this phase — testing is deferred entirely to Phase 3.

### Phase 3 — QA Review (blocking)

Runs full test suite (Tier 2), executes configured gate checks (typecheck, lint, etc.), analyzes test coverage against PRD test IDs (3-tier extraction + 3-tier finding), invokes QA Engineer skill. Two mechanistic hard gates ensure safety: (1) non-zero test exit code overrides any AI PASS verdict, and (2) failed required gate checks override any AI PASS verdict. On FAIL verdict, triggers bugfix cycle: classifies failures as REGRESSION vs CURRENT, refreshes context with current codebase snapshot + QA summary + regression context, re-runs Ralph in bugfix mode, then re-runs QA. Up to `max_bugfix_cycles` iterations. On exhaustion, writes escalation report and **the pipeline halts** — the milestone is marked as failed, guaranteeing that no milestone proceeds to merge without passing QA.

### Phase 4 — Merge + Reconciliation

Merges feature branch into base (`--no-ff`), registers test ownership for regression tracking, tags `mN-complete`. Runs both deterministic drift detection (path references vs actual tree) and AI-powered spec reconciliation. Merge failures are **fatal** (pipeline halts). Reconciliation failures are non-fatal (warn and continue); controlled by the `reconciliation.blocking` config option which gates the *next* milestone.

## Working Directory

```
.ralph/
├── state.json              # FSM state, cost tracking, test ownership
├── pipeline.lock           # PID-based lock preventing concurrent runs
├── prd.json                # Symlink to active PRD
├── context.md              # Context bundle for current milestone
├── progress.txt            # Ralph agent progress tracking
├── CLAUDE.md               # Agent instructions with runtime footer
├── logs/pipeline.jsonl     # Structured event log
├── .test-image-hashes      # Docker image rebuild tracking
└── archive/<slug>/         # Archived PRDs + progress per completed milestone
```

## CLI Reference

```bash
ralph-pipeline run --config pipeline-config.json              # Full run
ralph-pipeline run --config pipeline-config.json --resume     # Resume from interruption
ralph-pipeline run --config pipeline-config.json --milestone 2 # Start at milestone 2
ralph-pipeline run --config pipeline-config.json --dry-run     # Trace without executing
ralph-pipeline install-skills                                  # Install skills to ~/.claude/skills/
ralph-pipeline validate-infra --config pipeline-config.json    # Validate test infra
```

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11+ (pip package) |
| Config | Pydantic 2.0+ (15+ typed models) |
| State Machine | `transitions` 0.9+ |
| Terminal UI | `rich` 13.0+ |
| AI Agent | Claude CLI (`--print --output-format json`) |
| VCS | Git (branch-per-milestone) |
| Test Infra | Docker Compose (two-tier) |

## Key Modules

| Module | Purpose |
|--------|---------|
| `cli.py` | Entry point, orchestration, signal handling |
| `config.py` | Pydantic configuration schema (15+ models) |
| `state.py` | Pipeline state persistence + cost tracking |
| `runner.py` | FSM milestone runner with `transitions` |
| `git_ops.py` | Git operations (branches, merges, tags) |
| `ai/claude.py` | Claude subprocess wrapper with retry + cost tracking |
| `ai/prompts.py` | 10 prompt templates as Python functions |
| `ai/env.py` | `.ai.env` credential loading + validation |
| `infra/health.py` | TCP health checks for services |
| `infra/test_infra.py` | Docker container lifecycle (hash-based rebuild) |
| `infra/test_runner.py` | Test execution + AI fix cycles |
| `infra/regression.py` | Test ownership + regression classification |
| `phases/phase0_bootstrap.py` | Infrastructure bootstrap |
| `phases/prd_generation.py` | PRD + context bundle generation |
| `phases/ralph_execution.py` | Iterative Ralph coding loop |
| `phases/qa_review.py` | QA review + bugfix cycles |
| `phases/reconciliation.py` | Merge + spec reconciliation |
| `phases/deterministic_recon.py` | Structural drift detection |

## Skills

14 bundled Claude skills, installed via `ralph-pipeline install-skills`:

| Skill | Phase | Invocation |
|-------|-------|-----------|
| Requirements Engineering | Specification | Manual |
| Software Architect | Specification | Manual |
| UI/UX Designer | Specification | Manual |
| AI Engineer | Specification | Manual |
| Arch+AI Integrator | Specification | Manual |
| Spec QA | Specification | Manual |
| Test Architect | Specification | Manual |
| Milestone Planner | Planning | Manual |
| Pipeline Configurator | Planning | Manual |
| PRD Writer | Phase 1 | Automated |
| QA Engineer | Phase 3 | Automated |
| Spec Reconciler | Phase 4 | Automated |
| Release Engineer | Post-Pipeline | Manual |
| Pipeline Dashboard | Utility | Manual |
