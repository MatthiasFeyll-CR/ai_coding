# Issue 04: Context Bundle Assembly Is Unverified — The Most Critical Handoff

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline orchestrates multi-milestone software projects using AI agents. During Phase 1, the PRD Writer AI assembles two artifacts:

1. `tasks/prd-mN.json` — structured user stories
2. `.ralph/context.md` — a **context bundle** that is the single document Ralph reads for all domain knowledge

Ralph (Phase 2) reads context.md first every iteration. It is the **primary source of truth** for architecture decisions, design specs, test specifications, and codebase patterns. If something is missing from context.md, Ralph doesn't know about it.

---

## The Problem

`.ralph/context.md` is assembled by an AI agent (PRD Writer) that reads upstream docs and extracts relevant sections. **No verification exists** that the assembly is correct or complete.

### What context.md should contain

From `prd_writer/SKILL.md`, section on Context Bundle:

1. **Architecture sections** — data model, API design, project structure (with cross-boundary dependencies)
2. **Design specs** — component specs, shared component interfaces
3. **AI specs** — agent definitions, tool schemas (if applicable)
4. **Test specs** — full test case definitions from test-matrix.md for test-first development
5. **Codebase patterns** — from archived progress.txt files
6. **Codebase snapshot** — file tree + existing file contents for files stories will modify
7. **Quality checks** — concrete commands from pipeline-config.json
8. **Test infrastructure setup** — from pipeline-config.json

### What could be missing — and the consequences

| Missing section | Consequence |
|----------------|-------------|
| Architecture/data model | Ralph invents its own schema, diverging from the planned design |
| Design specs | UI components don't match the design system |
| Test specs | Ralph implements without TDD; test coverage analysis later finds MISSING IDs |
| Quality check commands | Ralph can't run tests/lint during implementation; all feedback is deferred to QA |
| Codebase snapshot | Ralph re-explores the codebase from scratch each iteration (token waste) |
| Cross-boundary deps | Ralph breaks interfaces that other milestones depend on |

### Pipeline code — existence check only

In `src/ralph_pipeline/phases/prd_generation.py`:

```python
# Check for context bundle
context_bundle = scripts_dir / "context.md"
if not context_bundle.exists():
    plogger.warning(
        f"PRD Writer did not produce context bundle at {context_bundle}"
    )
    plogger.warning("Ralph will fall back to reading upstream docs directly.")
```

No content check. Not even a basic "does it have section headers?" check.

### The structural problem

The pipeline has **structured knowledge** that should be in context.md:
- `pipeline-config.json` contains exact quality check commands (`gate_checks`, `test_execution`)
- `tasks/prd-mN.json` contains story notes with test IDs
- `docs/04-test-architecture/test-matrix.md` contains test definitions assigned to milestones

But instead of the pipeline injecting these structured elements, it delegates the entire assembly to an AI agent and hopes it got everything right.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/phases/prd_generation.py` | Phase 1 — only checks context.md exists |
| `src/ralph_pipeline/ai/prompts.py` | `prd_generation_prompt()` — tells AI to write context.md |
| `src/ralph_pipeline/data/skills/prd_writer/SKILL.md` | Defines what context.md should contain |
| `src/ralph_pipeline/config.py` | Has `gate_checks`, `test_execution` — structured data that should be in context |
| `src/ralph_pipeline/phases/ralph_execution.py` | Ralph reads whatever context.md contains |

---

## Impact

- **Severity:** Critical — context.md is the single source of truth for the coding agent
- **Failure mode:** Silent — missing sections cause implementation drift, not crashes
- **Frequency:** Every milestone — context is re-assembled each time
- **Blast radius:** Every story Ralph implements is affected by context quality

---

## Questions to Consider

1. Should the pipeline post-validate context.md by checking for required section headers (e.g., `## Architecture`, `## Test Specifications`, `## Quality Checks`)?
2. Should the pipeline **inject** structured sections (quality check commands, test IDs) into context.md after the AI generates the rest, guaranteeing they're present?
3. Should there be a context.md template with required sections that the PRD Writer fills in, rather than free-form generation?
4. Should the pipeline cross-reference: for each test ID in the PRD, verify it appears in context.md?
5. Should missing sections trigger a retry, a warning, or a hard stop?
6. Is there value in splitting context.md into structured YAML/JSON sections vs. keeping it as markdown?
