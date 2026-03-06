"""Tests for prompt assembly."""

from __future__ import annotations

from ralph_pipeline.ai.prompts import (
    gate_fix_prompt,
    prd_generation_prompt,
    qa_review_prompt,
    reconciliation_prompt,
    regression_fix_prompt,
    test_fix_prompt,
)


class TestPrompts:
    def test_prd_generation_prompt(self):
        result = prd_generation_prompt(
            skill_content="SKILL INSTRUCTIONS",
            milestone_id=1,
            slug="foundation",
            milestone_doc="docs/05-milestones/m1-foundation.md",
            archive_dir=".ralph/archive",
            tasks_dir="tasks",
            scripts_dir=".ralph",
        )
        assert "SKILL INSTRUCTIONS" in result
        assert "M1" in result
        assert "foundation" in result
        assert "prd-m1.json" in result

    def test_qa_review_prompt(self):
        result = qa_review_prompt(
            skill_content="QA SKILL",
            milestone_id=2,
            slug="core",
            branch="ralph/m2-core",
            prd_path="tasks/prd-m2.json",
            progress_path=".ralph/progress.txt",
            test_results="3 passed, 1 failed",
            test_exit_code=1,
            test_command="pytest",
            coverage_report="Coverage: 80%",
            test_arch_ref="See test-matrix.md",
            qa_report_path="docs/08-qa/qa-m2-core.md",
            prd_json_path="tasks/prd-m2.json",
        )
        assert "QA SKILL" in result
        assert "M2" in result
        assert "FAIL" in result
        assert "Coverage: 80%" in result

    def test_test_fix_prompt(self):
        result = test_fix_prompt(
            branch="ralph/m1-foundation",
            test_dir="/project",
            test_command="pytest",
            exit_code=1,
            test_tail="AssertionError: expected 1 got 2",
        )
        assert "ralph/m1-foundation" in result
        assert "pytest" in result
        assert "AssertionError" in result

    def test_regression_fix_prompt(self):
        result = regression_fix_prompt(
            milestone=2,
            branch="main",
            test_dir="/project",
            test_command="pytest",
            exit_code=1,
            test_tail="test_auth FAILED",
            regression_failures="tests/test_auth.py (from M1)",
            current_failures="tests/test_new.py",
            merge_diff="src/auth.py | 10 ++++----",
            regression_context="### M1 — tests broke",
        )
        assert "REGRESSION" in result
        assert "M2" in result
        assert "test_auth" in result

    def test_gate_fix_prompt(self):
        result = gate_fix_prompt(
            base_branch="main",
            milestone=1,
            slug="foundation",
            project_root="/project",
            gate_errors="=== typecheck FAILED ===\nTS2304: Cannot find name",
        )
        assert "main" in result
        assert "typecheck" in result

    def test_reconciliation_prompt(self):
        result = reconciliation_prompt(
            skill_content="RECONCILE SKILL",
            milestone=1,
            slug="foundation",
            archive_dir=".ralph/archive",
            qa_dir="docs/08-qa",
            recon_dir="docs/05-reconciliation",
        )
        assert "RECONCILE SKILL" in result
        assert "M1" in result
        assert "foundation" in result
