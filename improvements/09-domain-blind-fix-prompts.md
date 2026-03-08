# Issue 09: Fix Prompts (Test + Gate) Are Domain-Blind

## Instructions for AI

You are a professional AI engineer reviewing a pipeline orchestration system. Your role:

1. **Understand** the problem described below fully. Ask clarifying questions if anything is unclear.
2. **Recommend** concrete improvements with trade-offs. Discuss alternatives.
3. **Do NOT implement** anything until the user explicitly says to proceed.
4. **Ask questions** about edge cases, scope, and priorities before proposing solutions.

Read the referenced files to get full context before making recommendations.

---

## System Overview

Ralph Pipeline has automated fix cycles at two points:

1. **Phase 4 — Post-merge test fixes:** When tests fail after merging a milestone branch, Claude is invoked to fix the code. There are two prompt variants:
   - `test_fix_prompt` — standard failures (no regression)
   - `regression_fix_prompt` — failures in previous milestone tests

2. **Phase 4 — Gate check fixes:** When lint/typecheck/build checks fail, Claude is invoked via `gate_fix_prompt` to fix the code.

These fix prompts receive **error output only** — no domain context from the project's architecture, design, or PRD.

---

## The Problem

### Standard test fix prompt

From `src/ralph_pipeline/ai/prompts.py`:

```python
def test_fix_prompt(branch, test_dir, test_command, exit_code, test_tail) -> str:
    return f"""You are fixing test failures on branch {branch}.
Working directory: {test_dir}

The test command `{test_command}` failed with exit code {exit_code}.

Test output (last 100 lines):
```
{test_tail}
```

Instructions:
- Read the failing test files and the source files they test
- Fix the SOURCE CODE to make tests pass — do NOT modify test files
- Focus on the actual assertion errors: expected vs received values
- Only fix what is broken — do not refactor or add features
- Commit each fix with message: fix: test failure — <brief description>"""
```

**What's available:** Branch name, test output, error messages.
**What's missing:** Architecture constraints, data model specs, API contracts, design specs, PRD context, context.md.

### Regression fix prompt — better but still limited

```python
def regression_fix_prompt(..., merge_diff, regression_context) -> str:
    # Includes:
    # - Failure classification (REGRESSION vs CURRENT)
    # - merge diff (files changed)
    # - archived PRD context for broken milestones
    # - constraint: never modify prev milestone tests
```

The regression prompt is noticeably richer — it includes archived PRD context and the merge diff. But it still lacks:
- Architecture docs (data model, API contracts)
- Design specs
- The current milestone's context.md
- Test specifications from test-matrix.md

### Gate fix prompt — minimal

```python
def gate_fix_prompt(base_branch, milestone, slug, project_root, gate_errors) -> str:
    return f"""You are fixing build/typecheck errors on branch {base_branch}...
{gate_errors}
Instructions:
- Read the failing files and fix the errors
- Only fix what is broken — do not refactor or add features"""
```

**Only error output.** No architecture docs, no type definitions, no API specs.

### Why domain blindness matters

Pattern-matching on error messages works for simple cases (typos, missing imports). But post-merge failures often involve **structural mismatches**:

- A type changed in milestone N that milestone N-1's tests expect
- An API response shape differs from what the test asserts
- A database schema migration is needed but the fix agent doesn't know the data model
- A design constraint (e.g., "this endpoint must return paginated results") is violated

Without domain context, Claude can only fix **syntactic errors**. For **semantic errors** (wrong behavior, wrong types, wrong API contracts), it guesses — potentially making the architecture worse.

---

## Affected Files

| File | Role |
|------|------|
| `src/ralph_pipeline/ai/prompts.py` | `test_fix_prompt()`, `regression_fix_prompt()`, `gate_fix_prompt()` |
| `src/ralph_pipeline/infra/test_runner.py` | Invokes fix prompts during test fix cycles |
| `src/ralph_pipeline/phases/merge_verify.py` | Invokes gate fix prompts; orchestrates fix cycles |
| `src/ralph_pipeline/infra/regression.py` | Builds regression context for `regression_fix_prompt` |

### Fix cycle invocation in test_runner.py

The test runner calls claude with the fix prompt. Check this file to see how the prompt is assembled and what data flows into it.

### Fix cycle invocation in merge_verify.py

```python
prompt = gate_fix_prompt(
    base_branch=base_branch,
    milestone=milestone.id,
    slug=slug,
    project_root=str(project_root),
    gate_errors=gate_errors,  # Just error text — no domain context
)
claude.run(prompt, model=config.models.gate_fix, ...)
```

---

## Impact

- **Severity:** Medium — most test failures ARE simple and can be fixed from error output alone; structural failures are the minority but cause the most damage
- **Failure mode:** Two modes: (1) Claude makes a bad fix that compiles but violates architecture → passes gate, breaks next milestone; (2) Claude can't fix → HARD STOP after max cycles
- **Frequency:** Every post-merge test failure and gate failure
- **Blast radius:** Bad fixes degrade codebase quality for all subsequent milestones

---

## Questions to Consider

1. Should fix prompts include a summary of relevant architecture docs (data model, API contracts)?
2. Should fix prompts include the current milestone's context.md (or a subset of it)?
3. Would including the full context.md in fix prompts exceed context window limits? Should it be a condensed version?
4. Should the regression fix prompt serve as the template for all fix prompts (it already includes more context)?
5. Should gate fix prompts specifically include type definitions and API schemas when fixing typecheck errors?
6. Is there a risk that adding domain context to fix prompts causes Claude to over-fix (refactor instead of minimal fix)?
7. Should fix prompts have access to the PRD to understand WHAT the code is supposed to do?
