"""Tests for reconciliation drift tracking and semi-blocking behaviour."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ralph_pipeline.config import PipelineConfig, ReconciliationConfig
from ralph_pipeline.phases.deterministic_recon import (
    DriftItem, DriftReport, _extract_paths_from_doc,
    run_deterministic_reconciliation)
from ralph_pipeline.phases.reconciliation import _run_spec_reconciliation
from ralph_pipeline.runner import MilestoneRunner
from ralph_pipeline.state import MilestoneState, PipelineState

MINIMAL_CONFIG = PipelineConfig(
    project={"name": "Test"},
    milestones=[
        {"id": 1, "slug": "alpha", "name": "Alpha", "stories": 2},
        {"id": 2, "slug": "beta", "name": "Beta", "stories": 3, "dependencies": [1]},
    ],
)


# ─── MilestoneState reconciliation_status ──────────────────────────────────────


class TestReconciliationStatus:
    def test_default_is_none(self):
        ms = MilestoneState(id=1)
        assert ms.reconciliation_status is None

    def test_set_success(self):
        ms = MilestoneState(id=1)
        ms.reconciliation_status = "success"
        assert ms.reconciliation_status == "success"

    def test_set_failed(self):
        ms = MilestoneState(id=1)
        ms.reconciliation_status = "failed"
        assert ms.reconciliation_status == "failed"

    def test_persists_through_save_load(self, tmp_path: Path):
        config = PipelineConfig(**{
            "project": {"name": "Test"},
            "milestones": [
                {"id": 1, "slug": "a", "name": "A", "stories": 3},
            ],
        })
        state = PipelineState.initialize(config, "main")
        state.milestones[1].reconciliation_status = "failed"

        state_file = tmp_path / "state.json"
        state.save(state_file)

        loaded = PipelineState.load(state_file)
        assert loaded.milestones[1].reconciliation_status == "failed"


# ─── PipelineState.reconciliation_debt ─────────────────────────────────────────


class TestReconciliationDebt:
    def test_no_debt_initially(self):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        assert state.reconciliation_debt() == []

    def test_debt_after_failure(self):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        state.milestones[1].reconciliation_status = "failed"
        assert state.reconciliation_debt() == [1]

    def test_no_debt_after_success(self):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        state.milestones[1].reconciliation_status = "success"
        assert state.reconciliation_debt() == []

    def test_multiple_debts(self):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        state.milestones[1].reconciliation_status = "failed"
        state.milestones[2].reconciliation_status = "failed"
        assert state.reconciliation_debt() == [1, 2]

    def test_mixed_statuses(self):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        state.milestones[1].reconciliation_status = "success"
        state.milestones[2].reconciliation_status = "failed"
        assert state.reconciliation_debt() == [2]

    def test_none_status_not_counted_as_debt(self):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        # None = not yet attempted, not debt
        assert state.reconciliation_debt() == []


# ─── ReconciliationConfig ─────────────────────────────────────────────────────


class TestReconciliationConfig:
    def test_default_blocking_true(self):
        config = ReconciliationConfig()
        assert config.blocking is True

    def test_pipeline_config_default(self):
        assert MINIMAL_CONFIG.reconciliation.blocking is True

    def test_override_blocking_false(self):
        config = PipelineConfig(
            project={"name": "Test"},
            milestones=[{"id": 1, "slug": "a", "name": "A", "stories": 1}],
            reconciliation={"blocking": False},
        )
        assert config.reconciliation.blocking is False


# ─── _run_spec_reconciliation returns bool ─────────────────────────────────────


class TestSpecReconciliationReturnValue:
    def test_returns_true_on_changelog_produced(self, tmp_path: Path):
        """When the changelog file is created, returns True."""
        config = MINIMAL_CONFIG
        milestone = config.milestones[0]

        claude = MagicMock()
        git = MagicMock()
        plogger = MagicMock()

        # Simulate Claude creating the changelog file
        recon_dir = tmp_path / config.paths.reconciliation_dir
        recon_dir.mkdir(parents=True)
        changelog = recon_dir / f"m{milestone.id}-changes.md"

        def create_changelog(*a, **kw):
            changelog.write_text("# Changes\n- Updated API docs")

        claude.run.side_effect = create_changelog

        with patch(
            "ralph_pipeline.phases.reconciliation.run_deterministic_reconciliation"
        ):
            result = _run_spec_reconciliation(
                milestone=milestone,
                config=config,
                claude=claude,
                git=git,
                plogger=plogger,
                project_root=tmp_path,
            )

        assert result is True
        plogger.success.assert_called_once()

    def test_returns_false_when_no_changelog(self, tmp_path: Path):
        """When no changelog is produced after 2 attempts, returns False."""
        config = MINIMAL_CONFIG
        milestone = config.milestones[0]

        claude = MagicMock()
        git = MagicMock()
        plogger = MagicMock()

        # Claude doesn't create the changelog file
        with patch(
            "ralph_pipeline.phases.reconciliation.run_deterministic_reconciliation"
        ):
            result = _run_spec_reconciliation(
                milestone=milestone,
                config=config,
                claude=claude,
                git=git,
                plogger=plogger,
                project_root=tmp_path,
            )

        assert result is False
        # Should have warning about stale specs
        assert any(
            "did not produce" in str(call)
            for call in plogger.warning.call_args_list
        )


# ─── Runner records reconciliation outcome ─────────────────────────────────────


class TestRunnerReconciliationTracking:
    def _make_runner(self, tmp_path: Path) -> MilestoneRunner:
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        state_file = tmp_path / "state.json"

        return MilestoneRunner(
            milestone=MINIMAL_CONFIG.milestones[0],
            config=MINIMAL_CONFIG,
            pipeline_state=state,
            state_file=state_file,
            claude=MagicMock(),
            git=MagicMock(),
            test_runner=MagicMock(),
            infra=MagicMock(),
            regression_analyzer=MagicMock(),
            plogger=MagicMock(),
            event_logger=MagicMock(),
            project_root=tmp_path,
        )

    @patch("ralph_pipeline.runner.run_prd_generation")
    @patch("ralph_pipeline.runner.run_ralph_execution")
    @patch("ralph_pipeline.runner.run_qa_review", return_value=True)
    @patch("ralph_pipeline.runner.run_reconciliation", return_value=True)
    def test_records_success(
        self, mock_recon, mock_qa, mock_ralph, mock_prd, tmp_path: Path
    ):
        runner = self._make_runner(tmp_path)
        runner.execute()
        ms = runner.pipeline_state.milestones[1]
        assert ms.reconciliation_status == "success"

    @patch("ralph_pipeline.runner.run_prd_generation")
    @patch("ralph_pipeline.runner.run_ralph_execution")
    @patch("ralph_pipeline.runner.run_qa_review", return_value=True)
    @patch("ralph_pipeline.runner.run_reconciliation", return_value=False)
    def test_records_failure(
        self, mock_recon, mock_qa, mock_ralph, mock_prd, tmp_path: Path
    ):
        runner = self._make_runner(tmp_path)
        runner.execute()
        ms = runner.pipeline_state.milestones[1]
        assert ms.reconciliation_status == "failed"

    @patch("ralph_pipeline.runner.run_prd_generation")
    @patch("ralph_pipeline.runner.run_ralph_execution")
    @patch("ralph_pipeline.runner.run_qa_review", return_value=True)
    @patch("ralph_pipeline.runner.run_reconciliation", return_value=False)
    def test_warns_on_debt(
        self, mock_recon, mock_qa, mock_ralph, mock_prd, tmp_path: Path
    ):
        runner = self._make_runner(tmp_path)
        runner.execute()
        # Should have logged a warning about reconciliation debt
        assert any(
            "Reconciliation debt" in str(call)
            for call in runner.plogger.warning.call_args_list
        )


# ─── PRD prompt drift warning ─────────────────────────────────────────────────


class TestPRDDriftWarning:
    def test_prompt_includes_drift_warning(self):
        from ralph_pipeline.ai.prompts import prd_generation_prompt

        result = prd_generation_prompt(
            skill_content="SKILL",
            milestone_id=3,
            slug="gamma",
            milestone_doc="docs/milestone-3.md",
            archive_dir=".ralph/archive",
            tasks_dir="tasks",
            scripts_dir=".ralph",
            drift_warning="SPEC DRIFT ADVISORY: Milestones M1, M2 failed...",
        )
        assert "SPEC DRIFT ADVISORY" in result
        assert "M1, M2" in result

    def test_prompt_no_warning_when_empty(self):
        from ralph_pipeline.ai.prompts import prd_generation_prompt

        result = prd_generation_prompt(
            skill_content="SKILL",
            milestone_id=1,
            slug="alpha",
            milestone_doc="docs/milestone-1.md",
            archive_dir=".ralph/archive",
            tasks_dir="tasks",
            scripts_dir=".ralph",
            drift_warning="",
        )
        assert "SPEC DRIFT ADVISORY" not in result

    def test_prompt_backward_compatible_without_kwarg(self):
        from ralph_pipeline.ai.prompts import prd_generation_prompt

        result = prd_generation_prompt(
            skill_content="SKILL",
            milestone_id=1,
            slug="alpha",
            milestone_doc="docs/milestone-1.md",
            archive_dir=".ralph/archive",
            tasks_dir="tasks",
            scripts_dir=".ralph",
        )
        assert "SPEC DRIFT ADVISORY" not in result
        assert "M1" in result


# ─── Deterministic reconciliation ──────────────────────────────────────────────


class TestExtractPaths:
    def test_extracts_src_paths(self):
        content = "The main module is at `src/app/main.py` and tests in `tests/test_main.py`."
        paths = _extract_paths_from_doc(content)
        assert "src/app/main.py" in paths
        assert "tests/test_main.py" in paths

    def test_extracts_dotslash_paths(self):
        content = "See `./src/config/settings.ts` for details."
        paths = _extract_paths_from_doc(content)
        assert "src/config/settings.ts" in paths

    def test_ignores_non_project_paths(self):
        content = "Install with `pip install foo`."
        paths = _extract_paths_from_doc(content)
        assert len(paths) == 0

    def test_extracts_directory_references(self):
        content = "Place files in src/components/ui for the UI layer."
        paths = _extract_paths_from_doc(content)
        assert "src/components/ui" in paths


class TestDriftReport:
    def test_empty_report(self):
        report = DriftReport()
        assert not report.has_drift
        assert "No structural drift" in report.summary()

    def test_report_with_items(self):
        report = DriftReport(
            items=[
                DriftItem(
                    category="file_path",
                    spec_file="docs/arch.md",
                    expected="src/old.py",
                    actual="MISSING",
                )
            ],
            scanned_docs=5,
        )
        assert report.has_drift
        assert "1 item(s)" in report.summary()


class TestDeterministicReconciliation:
    def test_scan_finds_missing_paths(self, tmp_path: Path):
        # Create a docs dir with a doc referencing a non-existent file
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "architecture.md").write_text(
            "The API is at `src/api/routes.py` and the database module at `src/db/models.py`."
        )

        recon_dir = tmp_path / "docs" / "05-reconciliation"
        plogger = MagicMock()

        report = run_deterministic_reconciliation(
            project_root=tmp_path,
            docs_dir="docs",
            recon_dir=recon_dir,
            milestone_id=1,
            plogger=plogger,
        )

        assert report.has_drift
        assert len(report.items) == 2
        assert recon_dir.exists()
        assert (recon_dir / "m1-deterministic-drift.md").exists()

    def test_scan_no_drift_when_files_exist(self, tmp_path: Path):
        # Create a doc referencing files that actually exist
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "architecture.md").write_text(
            "The main module is at `src/app/main.py`."
        )
        # Create the referenced file
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / "src" / "app" / "main.py").write_text("# main")

        recon_dir = tmp_path / "docs" / "05-reconciliation"
        plogger = MagicMock()

        report = run_deterministic_reconciliation(
            project_root=tmp_path,
            docs_dir="docs",
            recon_dir=recon_dir,
            milestone_id=1,
            plogger=plogger,
        )

        assert not report.has_drift
        plogger.info.assert_called()

    def test_scan_skips_reconciliation_dir(self, tmp_path: Path):
        # Docs in the reconciliation dir itself should be skipped
        docs_dir = tmp_path / "docs"
        recon_dir = docs_dir / "05-reconciliation"
        recon_dir.mkdir(parents=True)
        (recon_dir / "m1-changes.md").write_text(
            "Referenced `src/nonexistent/file.py` which doesn't exist."
        )

        plogger = MagicMock()
        report = run_deterministic_reconciliation(
            project_root=tmp_path,
            docs_dir="docs",
            recon_dir=recon_dir,
            milestone_id=2,
            plogger=plogger,
        )

        assert not report.has_drift

    def test_no_docs_dir(self, tmp_path: Path):
        plogger = MagicMock()
        report = run_deterministic_reconciliation(
            project_root=tmp_path,
            docs_dir="docs",
            recon_dir=tmp_path / "recon",
            milestone_id=1,
            plogger=plogger,
        )
        assert not report.has_drift
        assert report.scanned_docs == 0
