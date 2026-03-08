"""Tests for regression analysis."""

from __future__ import annotations

from unittest.mock import MagicMock

from ralph_pipeline.infra.regression import FailedTest, RegressionAnalyzer
from ralph_pipeline.state import PipelineState


class TestRegressionAnalyzer:
    def _make_state(self, test_map: dict | None = None) -> PipelineState:
        state = PipelineState(
            base_branch="main",
            current_milestone=2,
            milestones={},
            test_milestone_map=test_map or {},
        )
        return state

    def test_parse_failing_test_files_pytest(self):
        git = MagicMock()
        state = self._make_state()
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        output = """
=== FAILURES ===
FAILED tests/test_auth.py::test_login_success
FAILED tests/test_api.py::test_create_user
=== short test summary ===
FAILED tests/test_auth.py::test_login_success
"""
        files = analyzer.parse_failing_test_files(output)
        assert "tests/test_auth.py" in files
        assert "tests/test_api.py" in files

    def test_parse_failing_test_files_jest(self):
        git = MagicMock()
        state = self._make_state()
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        output = """
FAIL src/components/Button.test.tsx
  ● Button › renders correctly
"""
        files = analyzer.parse_failing_test_files(output)
        assert "src/components/Button.test.tsx" in files

    def test_classify_regression(self):
        git = MagicMock()
        git.log_first_commit_for_file.return_value = ""
        state = self._make_state({"tests/test_old.py": 1})
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        output = "FAILED tests/test_old.py::test_something"
        failures = analyzer.classify(output, current_milestone=2)
        assert len(failures) == 1
        assert failures[0].classification == "REGRESSION"
        assert failures[0].owner_milestone == 1

    def test_classify_current(self):
        git = MagicMock()
        git.log_first_commit_for_file.return_value = ""
        state = self._make_state({"tests/test_new.py": 2})
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        output = "FAILED tests/test_new.py::test_feature"
        failures = analyzer.classify(output, current_milestone=2)
        assert len(failures) == 1
        assert failures[0].classification == "CURRENT"
        assert failures[0].owner_milestone == 2

    def test_classify_unknown_defaults_to_current(self):
        git = MagicMock()
        git.log_first_commit_for_file.return_value = ""
        git.tags_matching.return_value = []
        state = self._make_state()
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        output = "FAILED tests/test_unknown.py::test_it"
        failures = analyzer.classify(output, current_milestone=3)
        assert len(failures) == 1
        assert failures[0].classification == "CURRENT"
        assert failures[0].owner_milestone == 3

    def test_build_test_map(self):
        git = MagicMock()
        git.diff_names.return_value = [
            "tests/test_login.py",
            "src/auth.py",
            "tests/test_api.py",
        ]
        state = self._make_state()
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        result = analyzer.build_test_map(1)
        assert result["tests/test_login.py"] == 1
        assert result["tests/test_api.py"] == 1
        assert "src/auth.py" not in result

    def test_build_fix_context(self):
        git = MagicMock()
        state = self._make_state()
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        regressions = [
            FailedTest(
                file="tests/test_a.py", owner_milestone=1, classification="REGRESSION"
            ),
            FailedTest(
                file="tests/test_b.py", owner_milestone=1, classification="REGRESSION"
            ),
        ]
        context = analyzer.build_fix_context(regressions, 2)
        assert "M1" in context

    def test_build_fix_context_with_archived_prd(self, tmp_path):
        import json

        git = MagicMock()
        state = self._make_state()
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        # Create an archived PRD
        archive_dir = tmp_path / "archive"
        m1_dir = archive_dir / "m1-foundation"
        m1_dir.mkdir(parents=True)
        prd = {
            "userStories": [
                {
                    "title": "User Login",
                    "acceptanceCriteria": [
                        "Returns JWT token on success",
                        "Returns 401 on bad credentials",
                    ],
                }
            ]
        }
        (m1_dir / "prd.json").write_text(json.dumps(prd))

        regressions = [
            FailedTest(
                file="tests/test_auth.py", owner_milestone=1, classification="REGRESSION"
            ),
        ]
        context = analyzer.build_fix_context(regressions, 2, archive_dir=archive_dir)
        assert "M1" in context
        assert "User Login" in context
        assert "JWT token" in context
        assert "401" in context

    def test_build_fix_context_without_archive_dir(self):
        git = MagicMock()
        state = self._make_state()
        analyzer = RegressionAnalyzer(state, MagicMock(), git)

        regressions = [
            FailedTest(
                file="tests/test_a.py", owner_milestone=1, classification="REGRESSION"
            ),
        ]
        # No archive_dir — should still produce header-only context
        context = analyzer.build_fix_context(regressions, 2, archive_dir=None)
        assert "M1" in context
