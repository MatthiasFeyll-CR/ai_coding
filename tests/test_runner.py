"""Tests for the FSM runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.runner import MilestoneRunner
from ralph_pipeline.state import PipelineState

MINIMAL_CONFIG = PipelineConfig(
    project={"name": "Test"},
    milestones=[
        {"id": 1, "slug": "foundation", "name": "Foundation", "stories": 3},
    ],
)


class TestMilestoneRunner:
    def _make_runner(
        self,
        initial_phase: str = "pending",
        tmp_path: Path | None = None,
    ) -> MilestoneRunner:
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        if initial_phase != "pending":
            state.update_phase(1, initial_phase)

        state_file = (tmp_path or Path("/tmp")) / "state.json"

        runner = MilestoneRunner(
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
            project_root=Path("/tmp/project"),
        )
        return runner

    def test_initial_state_pending(self, tmp_path: Path):
        runner = self._make_runner(tmp_path=tmp_path)
        assert runner.state == "pending"

    def test_initial_state_resume(self, tmp_path: Path):
        runner = self._make_runner("ralph_execution", tmp_path=tmp_path)
        assert runner.state == "ralph_execution"

    def test_start_transitions_to_prd(self, tmp_path: Path):
        runner = self._make_runner(tmp_path=tmp_path)
        runner.start()
        assert runner.state == "prd_generation"

    @patch("ralph_pipeline.runner.run_prd_generation")
    @patch("ralph_pipeline.runner.run_ralph_execution")
    @patch("ralph_pipeline.runner.run_qa_review", return_value=True)
    @patch("ralph_pipeline.runner.run_merge_verify")
    @patch("ralph_pipeline.runner.run_reconciliation")
    def test_full_execution_success(
        self, mock_recon, mock_merge, mock_qa, mock_ralph, mock_prd, tmp_path: Path
    ):
        runner = self._make_runner(tmp_path=tmp_path)
        success = runner.execute()
        assert success is True
        assert runner.state == "complete"
        mock_prd.assert_called_once()
        mock_ralph.assert_called_once()
        mock_qa.assert_called_once()
        mock_merge.assert_called_once()
        mock_recon.assert_called_once()

    @patch(
        "ralph_pipeline.runner.run_prd_generation",
        side_effect=Exception("Claude failed"),
    )
    def test_execution_failure(self, mock_prd, tmp_path: Path):
        runner = self._make_runner(tmp_path=tmp_path)
        success = runner.execute()
        assert success is False
        assert runner.state == "failed"

    @patch("ralph_pipeline.runner.run_qa_review", return_value=False)
    @patch("ralph_pipeline.runner.run_ralph_execution")
    @patch("ralph_pipeline.runner.run_prd_generation")
    def test_qa_failure_causes_fail(
        self, mock_prd, mock_ralph, mock_qa, tmp_path: Path
    ):
        runner = self._make_runner(tmp_path=tmp_path)
        success = runner.execute()
        assert success is False
        assert runner.state == "failed"
