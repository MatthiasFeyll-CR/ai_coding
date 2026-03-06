# Ralph Pipeline — AI Agent Reference

## What Is This

Ralph Pipeline is a Python CLI framework that orchestrates multi-milestone software projects using AI agents. It takes a project configuration, breaks work into milestones, and drives each milestone through a structured 5-phase lifecycle — from requirements generation to code implementation, quality assurance, integration, and spec reconciliation.

The pipeline manages git branches, test infrastructure, AI agent invocations (Claude), and state persistence. It is designed to run autonomously end-to-end, producing production-ready code for each milestone with full test coverage and gate checks.

## How It Works

### Configuration

Everything starts with `pipeline-config.json` at the project root:

```json
{
  "project": { "name": "MyApp", "description": "Application description" },
  "milestones": [
    { "id": 1, "slug": "foundation", "name": "Foundation", "stories": 3 },
    { "id": 2, "slug": "core", "name": "Core Features", "stories": 5, "dependencies": [1] }
  ],
  "test_execution": {
    "test_command": "npm test",
    "services": [
      { "name": "postgres", "type": "tcp", "host": "localhost", "port": 5432 }
    ]
  },
  "gate_checks": {
    "checks": [
      { "name": "lint", "command": "npm run lint" },
      { "name": "typecheck", "command": "npm run typecheck" }
    ]
  }
}
```

The config defines milestones in execution order, with optional dependencies between them. Each milestone specifies a slug (used for branch naming) and number of user stories.

### The 5-Phase Lifecycle

Every milestone passes through these phases sequentially, managed by a finite state machine:

```
pending → prd_generation → ralph_execution → qa_review → merge_verify → reconciliation → complete
                                ↑                |
                                └── qa_needs_fix ┘
```

**Phase 1 — PRD Generation**
Generates a Product Requirements Document (`tasks/prd-mN.json`) and a context bundle (`.ralph/context.md`). The PRD contains structured stories with test specifications. Previous milestone archives inform codebase patterns.

**Phase 2 — Ralph Execution**
Creates a feature branch (`ralph/mN-slug`), then runs the Ralph agent loop — an iterative Claude session that implements each story from the PRD. Ralph reads the PRD and context, writes code, and runs light tests after each iteration. The agent loops until it signals completion or hits the iteration limit.

**Phase 3 — QA Review**
Runs the full test suite, analyzes test coverage against the PRD's test matrix, and invokes a QA reviewer agent. The reviewer issues a PASS or FAIL verdict. On FAIL, the pipeline loops back to Phase 2 for a bugfix cycle (up to `qa.max_bugfix_cycles` times). On PASS, the milestone is archived and proceeds.

**Phase 4 — Merge & Verify**
Merges the feature branch into the base branch (`--no-ff`), runs post-merge tests with regression analysis (distinguishing regressions from current-milestone failures), executes integration tests, and runs all configured gate checks (lint, typecheck, etc.). Failed gate checks trigger AI-assisted fix cycles. On success, the milestone is tagged `mN-complete` and the feature branch is deleted.

**Phase 5 — Reconciliation**
Invokes the Spec Reconciler agent to update project documentation (specs, changelogs) to reflect what was actually built vs. what was planned. This phase is non-fatal — reconciliation failures are logged as warnings but don't block the pipeline.

### Directory Structure

The pipeline uses `.ralph/` in the project root for all working state:

```
.ralph/
├── state.json              # FSM state — current phase per milestone
├── prd.json                # Active PRD for current milestone
├── context.md              # Context bundle for current milestone
├── progress.txt            # Ralph agent progress tracking
├── logs/
│   └── pipeline.jsonl      # Structured event log (usage, phases, tests)
└── archive/
    └── <milestone-slug>/   # Archived PRDs and progress per completed milestone
        ├── prd.json
        └── progress.txt
```

### State Persistence & Resume

Pipeline state is persisted to `.ralph/state.json` after every phase transition. If the pipeline is interrupted (Ctrl+C, crash, timeout), it can be resumed:

```bash
ralph-pipeline run --config pipeline-config.json --resume
```

Resume skips completed milestones and restarts the current milestone from its last saved phase.

### Test Infrastructure

The pipeline manages two tiers of test infrastructure:

- **Tier 2 (Simple):** Direct test commands (`test_command`), optional build step, service health checks via configured `services` array
- **Tier 1 (Docker):** Docker Compose environments with image hash tracking, automatic rebuild detection, structured health check polling

Services are verified via TCP connectivity checks with configurable timeouts before tests run.

### Regression Analysis

After merging a milestone, the pipeline distinguishes between:
- **REGRESSION:** A test owned by a previously-completed milestone now fails → high priority, blocks pipeline
- **CURRENT:** A test introduced by the current milestone fails → normal fix cycle

Test ownership is tracked in `state.json` via `test_milestone_map`, built by scanning git history for when test files were first committed.

## CLI Reference

```bash
# Run full pipeline
ralph-pipeline run --config pipeline-config.json

# Dry run (no commands executed, traces full flow)
ralph-pipeline run --config pipeline-config.json --dry-run

# Resume interrupted pipeline
ralph-pipeline run --config pipeline-config.json --resume

# Start from specific milestone
ralph-pipeline run --config pipeline-config.json --milestone 2

# Install bundled skills to ~/.claude/skills/
ralph-pipeline install-skills

# Validate test infrastructure lifecycle
ralph-pipeline validate-infra --config pipeline-config.json
```

## Technical Stack

- **Python 3.11+** — pip-installable package
- **Pydantic** — typed config validation with dependency graph checking
- **transitions** — FSM library for milestone state management
- **Rich** — structured terminal UI with status panels and formatted output
- **Claude** — AI agent invocations via `claude --print` subprocess calls with retry and streaming

## Key Modules

| Module | Purpose |
|---|---|
| `config.py` | 15 Pydantic models defining the full configuration schema |
| `state.py` | Pipeline state persistence — milestone phases, timestamps, test ownership |
| `runner.py` | FSM driving one milestone through 5 phases with transition callbacks |
| `cli.py` | CLI entry point — argument parsing, service initialization, signal handling |
| `git_ops.py` | All git operations — branches, merges, tags, conflict detection |
| `subprocess_utils.py` | Single choke point for all subprocess calls, dry-run mode |
| `ai/claude.py` | Claude subprocess wrapper with retry, streaming, usage logging |
| `ai/prompts.py` | All prompt templates as Python functions |
| `infra/health.py` | TCP health checks for test dependency services |
| `infra/test_infra.py` | Docker test infrastructure lifecycle management |
| `infra/test_runner.py` | Test execution engine with AI-assisted fix cycles |
| `infra/regression.py` | Post-merge failure classification (regression vs current) |
| `phases/*.py` | One module per pipeline phase with the core execution logic |
| `data/ralph.sh` | The Ralph agent loop script (iterative Claude coding sessions) |
| `data/skills/` | 14 bundled Claude skills for each pipeline role |

## Skills

The pipeline bundles 14 specialized Claude skills, each defining a role in the development workflow:

| Skill | Role |
|---|---|
| `requirements_engineering` | Elicits and structures project requirements |
| `software_architect` | Designs system architecture from requirements |
| `ai_engineer` | Designs AI/ML integration patterns |
| `arch_ai_integrator` | Validates architecture–AI alignment |
| `spec_qa` | Reviews specifications for completeness |
| `test_architect` | Designs test strategy and coverage matrix |
| `strategy_planner` | Plans milestone breakdown and execution strategy |
| `pipeline_configurator` | Generates pipeline-config.json and CLAUDE.md |
| `prd_writer` | Generates structured PRDs per milestone |
| `qa_engineer` | Reviews implementation quality and test coverage |
| `spec_reconciler` | Reconciles specs with actual implementation |
| `release_engineer` | Manages release packaging and deployment |
| `pipeline_dashboard` | Provides project status overview |
| `ui_ux_designer` | Designs UI components with design system intelligence |

Skills are installed to `~/.claude/skills/` via `ralph-pipeline install-skills` and are invoked by the pipeline at the appropriate phases.
