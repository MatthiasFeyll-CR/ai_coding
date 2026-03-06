"""Tests for the Ralph agent loop in ralph_execution.py."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ralph_pipeline.phases.ralph_execution import (
    COMPLETION_SIGNAL,
    _check_all_pass,
    _run_ralph_loop,
)


def _make_mock_claude(outputs: list[str]) -> MagicMock:
    """Create a ClaudeRunner mock returning sequential outputs."""
    claude = MagicMock()
    results = [SimpleNamespace(output=o) for o in outputs]
    claude.run.side_effect = results
    return claude


class TestRunRalphLoop:
    def test_completes_on_first_iteration(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")

        log_dir = tmp_path / "logs"
        claude = _make_mock_claude([f"Done. {COMPLETION_SIGNAL}"])
        plogger = MagicMock()
        event_logger = MagicMock()

        result = _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts,
            log_dir=log_dir,
            max_iterations=5,
            model="claude-sonnet-4-5",
            milestone_id=1,
            plogger=plogger,
            event_logger=event_logger,
        )

        assert result is True
        assert claude.run.call_count == 1
        plogger.success.assert_called_once()

    @patch("ralph_pipeline.phases.ralph_execution.time.sleep")
    def test_completes_on_third_iteration(self, mock_sleep, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")

        claude = _make_mock_claude(
            [
                "Still working...",
                "More work...",
                f"All done {COMPLETION_SIGNAL}",
            ]
        )
        plogger = MagicMock()

        result = _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts,
            log_dir=tmp_path / "logs",
            max_iterations=5,
            model="test",
            milestone_id=1,
            plogger=plogger,
            event_logger=MagicMock(),
        )

        assert result is True
        assert claude.run.call_count == 3
        # Sleep called between iterations (not after completion)
        assert mock_sleep.call_count == 2

    @patch("ralph_pipeline.phases.ralph_execution.time.sleep")
    def test_reaches_max_iterations(self, mock_sleep, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")

        claude = _make_mock_claude(["nope"] * 3)
        plogger = MagicMock()

        result = _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts,
            log_dir=tmp_path / "logs",
            max_iterations=3,
            model="test",
            milestone_id=1,
            plogger=plogger,
            event_logger=MagicMock(),
        )

        assert result is False
        assert claude.run.call_count == 3
        plogger.warning.assert_called()

    def test_missing_claude_md(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        # No CLAUDE.md file

        claude = MagicMock()
        plogger = MagicMock()

        result = _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts,
            log_dir=tmp_path / "logs",
            max_iterations=5,
            model="test",
            milestone_id=1,
            plogger=plogger,
            event_logger=MagicMock(),
        )

        assert result is False
        claude.run.assert_not_called()
        plogger.warning.assert_called()

    @patch("ralph_pipeline.phases.ralph_execution.time.sleep")
    def test_handles_claude_exception(self, mock_sleep, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")

        claude = MagicMock()
        claude.run.side_effect = [
            RuntimeError("timeout"),
            SimpleNamespace(output=f"ok {COMPLETION_SIGNAL}"),
        ]
        plogger = MagicMock()

        result = _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts,
            log_dir=tmp_path / "logs",
            max_iterations=5,
            model="test",
            milestone_id=1,
            plogger=plogger,
            event_logger=MagicMock(),
        )

        assert result is True
        assert claude.run.call_count == 2


class TestCheckAllPass:
    def test_all_pass(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text('{"userStories": [{"passes": true}, {"passes": true}]}')
        assert _check_all_pass(prd) is True

    def test_some_failing(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text('{"userStories": [{"passes": true}, {"passes": false}]}')
        assert _check_all_pass(prd) is False

    def test_missing_file(self, tmp_path: Path):
        assert _check_all_pass(tmp_path / "nonexistent.json") is False

    def test_empty_stories(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text('{"userStories": []}')
        assert _check_all_pass(prd) is False
