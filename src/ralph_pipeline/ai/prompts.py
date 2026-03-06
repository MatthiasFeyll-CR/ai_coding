"""Prompt templates — replaces heredocs in pipeline.sh."""

from __future__ import annotations


def prd_generation_prompt(
    skill_content: str,
    milestone_id: int,
    slug: str,
    milestone_doc: str,
    archive_dir: str,
    tasks_dir: str,
    scripts_dir: str,
) -> str:
    """Build the PRD generation prompt. See bash generate_prd()."""
    return f"""{skill_content}

ARGUMENTS: Write PRD for milestone M{milestone_id} ({slug}).

Instructions:
- Read {milestone_doc} and ALL upstream docs (architecture, design, AI, integration docs).
- Read the ACTUAL codebase for ground truth — check what previous milestones actually built.
- Read {archive_dir}/ for learnings from previous milestone runs.
- Write the PRD JSON directly to {tasks_dir}/prd-m{milestone_id}.json (no intermediate markdown PRD — go straight from milestone scope to JSON)
- Write the context bundle to {scripts_dir}/context.md (see Section 8 of your skill instructions)
- Branch name must be: ralph/m{milestone_id}-{slug}
- Follow the exact JSON structure with userStories array, each having: id, title, description, acceptanceCriteria, priority, passes (false), notes."""


def qa_review_prompt(
    skill_content: str,
    milestone_id: int,
    slug: str,
    branch: str,
    prd_path: str,
    progress_path: str,
    test_results: str,
    test_exit_code: int,
    test_command: str,
    coverage_report: str,
    test_arch_ref: str,
    qa_report_path: str,
    prd_json_path: str,
) -> str:
    """Build the QA review prompt. See bash run_qa()."""
    test_results_section = ""
    if test_command:
        test_status = (
            "PASS" if test_exit_code == 0 else f"FAIL (exit code {test_exit_code})"
        )
        test_tail = "\n".join(test_results.splitlines()[-80:]) if test_results else ""
        test_results_section = f"""
TEST EXECUTION RESULTS (run by pipeline before QA):
Command: {test_command}
Result: {test_status}
Output (last 80 lines):
```
{test_tail}
```

IMPORTANT: These test results are the ground truth. If tests fail, the failures are DEFECTS.
Tests verify acceptance criteria from the PRD — do NOT dismiss test failures."""

    coverage_section = ""
    if coverage_report:
        coverage_section = f"""
{coverage_report}
IMPORTANT: Any test ID listed as MISSING above is a DEFECT. Ralph was required to implement these tests.
Include a 'Test Matrix Coverage' section in your QA report with the full FOUND/MISSING breakdown."""

    return f"""{skill_content}

ARGUMENTS: Review milestone M{milestone_id} ({slug}).
Branch: {branch}
PRD: {prd_path}
Progress log: {progress_path}
{test_results_section}
{coverage_section}
{test_arch_ref}
Instructions:
- Read the PRD at {prd_path} and the progress log at {progress_path}
- Read ALL upstream docs (architecture, design, AI, milestones)
- Use the TEST EXECUTION RESULTS above as primary evidence for quality checks
- Use the TEST MATRIX COVERAGE above as primary evidence for test completeness — MISSING tests are DEFECTS
- Run additional quality checks: typecheck, lint, manual code review
- Produce a QA report at {qa_report_path}
- Include a 'Test Matrix Coverage' section showing FOUND/MISSING per test ID
- Include a clear Verdict: PASS or Verdict: FAIL line
- If FAIL: describe exactly what failed, referencing test output and missing test IDs where applicable
- If FAIL and this is not the final cycle: update {prd_json_path} — set passes=false on failing stories and add notes on what needs fixing"""


def test_fix_prompt(
    branch: str,
    test_dir: str,
    test_command: str,
    exit_code: int,
    test_tail: str,
) -> str:
    """Standard test fix prompt (no regressions). See bash run_test_fix_cycle()."""
    return f"""You are fixing test failures on branch {branch}.
Working directory: {test_dir}

The test command `{test_command}` failed with exit code {exit_code}.

Test output (last 100 lines):
```
{test_tail}
```

Instructions:
- Read the failing test files and the source files they test
- Fix the SOURCE CODE to make tests pass — do NOT modify test files unless the test itself has a clear bug (wrong import, typo)
- Tests verify acceptance criteria from the PRD — the tests define correct behavior
- Focus on the actual assertion errors: expected vs received values indicate contract mismatches
- Only fix what is broken — do not refactor or add features
- Commit each fix with message: fix: test failure — <brief description>"""


def regression_fix_prompt(
    milestone: int,
    branch: str,
    test_dir: str,
    test_command: str,
    exit_code: int,
    test_tail: str,
    regression_failures: str,
    current_failures: str,
    merge_diff: str,
    regression_context: str,
) -> str:
    """Regression-aware fix prompt. See bash _build_regression_fix_prompt()."""
    return f"""You are fixing test failures on branch {branch} after merging milestone M{milestone}.
Working directory: {test_dir}

The test command `{test_command}` failed with exit code {exit_code}.

## Failure Classification

**REGRESSION failures** — tests from PREVIOUS milestones that broke after this merge:
```
{regression_failures}
```

**Current milestone failures** — tests from M{milestone}:
```
{current_failures or 'none'}
```

## What changed in this merge (files modified):
```
{merge_diff}
```

## Context from previous milestones whose tests broke:
{regression_context}

## Test output (last 100 lines):
```
{test_tail}
```

## Instructions:
- **REGRESSIONS are the priority.** Previous milestone tests define a contract — they MUST pass.
- Fix SOURCE CODE from milestone M{milestone} to restore compatibility with previous tests.
- Do NOT modify test files from previous milestones. They are contracts, not suggestions.
- You MAY modify M{milestone}'s own test files only if they have a clear bug (wrong import, typo).
- Read the failing test files to understand what behavior they expect.
- Read the source files changed in the merge diff to find what broke the contract.
- Focus on assertion errors: expected vs received values show the exact contract mismatch.
- Only fix what is broken — do not refactor or add features.
- Commit each fix with message: fix: regression — <brief description>"""


def gate_fix_prompt(
    base_branch: str,
    milestone: int,
    slug: str,
    project_root: str,
    gate_errors: str,
) -> str:
    """Gate check fix prompt. See bash merge_and_verify()."""
    return f"""You are fixing build/typecheck errors on branch {base_branch} after merging M{milestone} ({slug}).
Working directory: {project_root}

The following checks failed:

{gate_errors}

Instructions:
- Read the failing files and fix the errors
- Only fix what is broken — do not refactor or add features
- Commit each fix with message: fix: gate check — <brief description>"""


def reconciliation_prompt(
    skill_content: str,
    milestone: int,
    slug: str,
    archive_dir: str,
    qa_dir: str,
    recon_dir: str,
) -> str:
    """Reconciliation prompt. See bash run_reconcile()."""
    return f"""{skill_content}

ARGUMENTS: Reconcile specs after milestone M{milestone} ({slug}).

References:
- Archive: {archive_dir}/m{milestone}-{slug}/
- QA report: {qa_dir}/qa-m{milestone}-{slug}.md

Instructions:
- Read progress file and QA report for M{milestone}
- Compare actual implementation against upstream spec docs
- Auto-apply ALL changes (pipeline trusts QA — no manual approval needed)
- Update spec docs to match reality where implementation deviated
- Record all changes in {recon_dir}/m{milestone}-changes.md"""
