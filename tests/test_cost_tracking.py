"""Tests for AI cost tracking — ClaudeRunner JSON parsing, CostSummary, budget guard."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph_pipeline.ai.claude import ClaudeRunner, CostBudgetExceeded
from ralph_pipeline.config import PipelineConfig, RetryConfig
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.state import CostSummary, PipelineState
from ralph_pipeline.usage import EventLogger

# ─── ClaudeRunner JSON parsing ────────────────────────────────────────────────


class TestClaudeRunnerParseJson:
    """Test _parse_json_response static method."""

    def test_parses_full_json_response(self):
        raw = json.dumps(
            {
                "type": "result",
                "result": "Hello, world!",
                "total_cost_usd": 0.042,
                "session_id": "abc-123",
                "duration_api_ms": 1500,
                "num_turns": 1,
                "model": "claude-sonnet-4-5",
                "usage": {
                    "input_tokens": 500,
                    "output_tokens": 120,
                    "cache_creation_input_tokens": 200,
                    "cache_read_input_tokens": 300,
                },
            }
        )
        text, usage = ClaudeRunner._parse_json_response(raw)

        assert text == "Hello, world!"
        assert usage.cost_usd == pytest.approx(0.042)
        assert usage.session_id == "abc-123"
        assert usage.input_tokens == 500
        assert usage.output_tokens == 120
        assert usage.cache_creation_tokens == 200
        assert usage.cache_read_tokens == 300
        assert usage.duration_api_ms == 1500
        assert usage.num_turns == 1
        assert usage.model_used == "claude-sonnet-4-5"

    def test_parses_minimal_json_response(self):
        raw = json.dumps({"result": "ok"})
        text, usage = ClaudeRunner._parse_json_response(raw)

        assert text == "ok"
        assert usage.cost_usd == 0.0
        assert usage.input_tokens == 0
        assert usage.session_id == ""

    def test_falls_back_on_plain_text(self):
        raw = "This is not JSON, just Claude text output."
        text, usage = ClaudeRunner._parse_json_response(raw)

        assert text == raw
        assert usage.cost_usd == 0.0
        assert usage.input_tokens == 0

    def test_falls_back_on_empty_string(self):
        text, usage = ClaudeRunner._parse_json_response("")
        assert text == ""
        assert usage.cost_usd == 0.0

    def test_handles_missing_usage_block(self):
        raw = json.dumps(
            {
                "result": "output",
                "total_cost_usd": 0.01,
                "session_id": "s1",
            }
        )
        text, usage = ClaudeRunner._parse_json_response(raw)
        assert text == "output"
        assert usage.cost_usd == pytest.approx(0.01)
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0


# ─── CostSummary model ───────────────────────────────────────────────────────


class TestCostSummary:
    def test_record_single_invocation(self):
        cs = CostSummary()
        cs.record(
            cost_usd=0.05,
            milestone=1,
            phase="ralph",
            model="opus",
            session_id="s1",
            input_tokens=1000,
            output_tokens=500,
        )
        assert cs.total_usd == pytest.approx(0.05)
        assert cs.by_milestone[1] == pytest.approx(0.05)
        assert cs.by_phase["ralph"] == pytest.approx(0.05)
        assert cs.by_model["opus"] == pytest.approx(0.05)
        assert len(cs.sessions) == 1
        assert cs.sessions[0].session_id == "s1"
        assert cs.sessions[0].invocations == 1

    def test_record_merges_same_session(self):
        cs = CostSummary()
        cs.record(0.05, 1, "ralph", "opus", "s1", input_tokens=100, output_tokens=50)
        cs.record(0.03, 1, "ralph", "opus", "s1", input_tokens=200, output_tokens=80)

        assert cs.total_usd == pytest.approx(0.08)
        assert len(cs.sessions) == 1
        assert cs.sessions[0].cost_usd == pytest.approx(0.08)
        assert cs.sessions[0].input_tokens == 300
        assert cs.sessions[0].output_tokens == 130
        assert cs.sessions[0].invocations == 2

    def test_record_separates_different_sessions(self):
        cs = CostSummary()
        cs.record(0.05, 1, "prd", "opus", "s1")
        cs.record(0.03, 2, "ralph", "sonnet", "s2")

        assert cs.total_usd == pytest.approx(0.08)
        assert len(cs.sessions) == 2
        assert cs.by_milestone[1] == pytest.approx(0.05)
        assert cs.by_milestone[2] == pytest.approx(0.03)

    def test_record_aggregates_by_phase_and_model(self):
        cs = CostSummary()
        cs.record(0.10, 1, "ralph", "opus", "s1")
        cs.record(0.20, 2, "ralph", "opus", "s2")
        cs.record(0.05, 1, "prd", "sonnet", "s3")

        assert cs.by_phase["ralph"] == pytest.approx(0.30)
        assert cs.by_phase["prd"] == pytest.approx(0.05)
        assert cs.by_model["opus"] == pytest.approx(0.30)
        assert cs.by_model["sonnet"] == pytest.approx(0.05)

    def test_empty_session_id_creates_new_entries(self):
        cs = CostSummary()
        cs.record(0.01, 1, "ralph", "opus", "")
        cs.record(0.02, 1, "ralph", "opus", "")

        # Empty session_id should not merge (each gets a fallback key)
        assert len(cs.sessions) == 2


# ─── CostSummary persistence in PipelineState ────────────────────────────────


class TestCostPersistence:
    def test_cost_survives_save_load(self, tmp_path: Path):
        config = PipelineConfig(
            project={"name": "Test"},
            milestones=[{"id": 1, "slug": "a", "name": "A", "stories": 3}],
        )
        state = PipelineState.initialize(config, "main")
        state.cost.record(
            cost_usd=0.42,
            milestone=1,
            phase="ralph",
            model="opus",
            session_id="test-session-1",
            input_tokens=5000,
            output_tokens=2000,
            cache_creation_tokens=1000,
            cache_read_tokens=3000,
        )

        state_file = tmp_path / "state.json"
        state.save(state_file)

        loaded = PipelineState.load(state_file)
        assert loaded.cost.total_usd == pytest.approx(0.42)
        assert len(loaded.cost.sessions) == 1
        assert loaded.cost.sessions[0].session_id == "test-session-1"
        assert loaded.cost.sessions[0].cache_read_tokens == 3000
        assert loaded.cost.by_model["opus"] == pytest.approx(0.42)

    def test_default_cost_is_empty(self):
        config = PipelineConfig(
            project={"name": "Test"},
            milestones=[{"id": 1, "slug": "a", "name": "A", "stories": 3}],
        )
        state = PipelineState.initialize(config, "main")
        assert state.cost.total_usd == 0.0
        assert state.cost.sessions == []


# ─── CostConfig in PipelineConfig ─────────────────────────────────────────────


class TestCostConfig:
    def test_default_no_budget(self):
        config = PipelineConfig(
            project={"name": "Test"},
            milestones=[{"id": 1, "slug": "a", "name": "A", "stories": 3}],
        )
        assert config.cost.budget_usd == 0.0
        assert config.cost.warn_at_pct == 80.0

    def test_custom_budget_from_json(self, tmp_path: Path):
        data = {
            "project": {"name": "Test"},
            "milestones": [{"id": 1, "slug": "a", "name": "A", "stories": 3}],
            "cost": {"budget_usd": 10.0, "warn_at_pct": 90.0},
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(data))

        config = PipelineConfig.load(config_file)
        assert config.cost.budget_usd == 10.0
        assert config.cost.warn_at_pct == 90.0


# ─── Budget guard in ClaudeRunner ─────────────────────────────────────────────


class TestCostBudgetGuard:
    def _make_runner(
        self,
        budget_usd: float = 0.0,
        cost_tracker: CostSummary | None = None,
    ) -> ClaudeRunner:
        retry = RetryConfig(max_retries=1, backoff_seconds=0)
        runner = ClaudeRunner(
            retry_config=retry,
            usage_logger=MagicMock(spec=EventLogger),
            logger=MagicMock(spec=PipelineLogger),
            cost_tracker=cost_tracker,
            budget_usd=budget_usd,
        )
        return runner

    @patch("ralph_pipeline.ai.claude.subprocess.Popen")
    @patch("ralph_pipeline.ai.claude.is_dry_run", return_value=False)
    def test_budget_exceeded_raises(self, mock_dry, mock_popen):
        """ClaudeRunner should raise CostBudgetExceeded when budget is exceeded."""
        cost_tracker = CostSummary()

        # Simulate a response that costs more than the budget
        json_response = json.dumps(
            {
                "result": "done",
                "total_cost_usd": 15.0,
                "session_id": "s1",
                "usage": {"input_tokens": 1000, "output_tokens": 500},
            }
        )

        proc_mock = MagicMock()
        proc_mock.stdin = MagicMock()
        proc_mock.stdout = MagicMock()
        proc_mock.stdout.read.return_value = json_response
        proc_mock.stderr = MagicMock()
        proc_mock.stderr.read.return_value = ""
        proc_mock.returncode = 0
        proc_mock.wait.return_value = 0
        mock_popen.return_value = proc_mock

        runner = self._make_runner(budget_usd=10.0, cost_tracker=cost_tracker)

        with pytest.raises(CostBudgetExceeded, match="budget"):
            runner.run(prompt="test", phase="ralph", milestone=1)

    @patch("ralph_pipeline.ai.claude.subprocess.Popen")
    @patch("ralph_pipeline.ai.claude.is_dry_run", return_value=False)
    def test_no_budget_no_exception(self, mock_dry, mock_popen):
        """No budget set (0) should never raise CostBudgetExceeded."""
        cost_tracker = CostSummary()

        json_response = json.dumps(
            {
                "result": "done",
                "total_cost_usd": 100.0,
                "session_id": "s1",
                "usage": {"input_tokens": 1000, "output_tokens": 500},
            }
        )

        proc_mock = MagicMock()
        proc_mock.stdin = MagicMock()
        proc_mock.stdout = MagicMock()
        proc_mock.stdout.read.return_value = json_response
        proc_mock.stderr = MagicMock()
        proc_mock.stderr.read.return_value = ""
        proc_mock.returncode = 0
        proc_mock.wait.return_value = 0
        mock_popen.return_value = proc_mock

        runner = self._make_runner(budget_usd=0.0, cost_tracker=cost_tracker)
        result = runner.run(prompt="test", phase="ralph", milestone=1)
        assert result.output == "done"

    @patch("ralph_pipeline.ai.claude.subprocess.Popen")
    @patch("ralph_pipeline.ai.claude.is_dry_run", return_value=False)
    def test_within_budget_succeeds(self, mock_dry, mock_popen):
        """Invocations within budget should succeed normally."""
        cost_tracker = CostSummary()

        json_response = json.dumps(
            {
                "result": "done",
                "total_cost_usd": 2.0,
                "session_id": "s1",
                "usage": {"input_tokens": 1000, "output_tokens": 500},
            }
        )

        proc_mock = MagicMock()
        proc_mock.stdin = MagicMock()
        proc_mock.stdout = MagicMock()
        proc_mock.stdout.read.return_value = json_response
        proc_mock.stderr = MagicMock()
        proc_mock.stderr.read.return_value = ""
        proc_mock.returncode = 0
        proc_mock.wait.return_value = 0
        mock_popen.return_value = proc_mock

        runner = self._make_runner(budget_usd=10.0, cost_tracker=cost_tracker)
        result = runner.run(prompt="test", phase="ralph", milestone=1)
        assert result.output == "done"
        assert result.usage.cost_usd == pytest.approx(2.0)
        assert cost_tracker.total_usd == pytest.approx(2.0)


# ─── EventLogger with real cost fields ───────────────────────────────────────


class TestEventLoggerCostFields:
    def test_log_claude_invocation_fields(self, tmp_path: Path):
        log_path = tmp_path / "pipeline.jsonl"
        logger = EventLogger(log_path)

        logger.log_claude_invocation(
            phase="ralph",
            model="claude-sonnet-4-5",
            milestone=1,
            input_tokens=5000,
            output_tokens=1200,
            cache_creation_tokens=800,
            cache_read_tokens=3000,
            cost_usd=0.042,
            session_id="abc-123",
            duration_s=15.2,
            duration_api_s=12.1,
            num_turns=1,
            attempts=1,
        )

        entry = json.loads(log_path.read_text().strip())
        assert entry["event"] == "claude_invocation"
        assert entry["input_tokens"] == 5000
        assert entry["output_tokens"] == 1200
        assert entry["cache_creation_tokens"] == 800
        assert entry["cache_read_tokens"] == 3000
        assert entry["cost_usd"] == pytest.approx(0.042)
        assert entry["session_id"] == "abc-123"
        assert entry["duration_api_s"] == pytest.approx(12.1)
        assert entry["num_turns"] == 1
        # Verify no legacy estimated fields
        assert "input_chars" not in entry
        assert "input_tokens_est" not in entry


# ─── PipelineLogger cost display ──────────────────────────────────────────────


class TestPipelineLoggerCost:
    def test_track_tokens_with_cost(self):
        from io import StringIO

        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        plogger = PipelineLogger(console=console)

        plogger.track_tokens(5000, 2000, cache_creation=500, cache_read=1000, cost_usd=0.05)
        assert plogger._tokens_in == 5000
        assert plogger._tokens_out == 2000
        assert plogger._cache_creation == 500
        assert plogger._cache_read == 1000
        assert plogger._cost_usd == pytest.approx(0.05)

    def test_status_panel_shows_cost(self):
        from io import StringIO

        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        plogger = PipelineLogger(console=console)

        plogger.set_context(1, "Alpha", "ralph_execution", 2, "TestProject")
        plogger.track_tokens(5000, 2000, cost_usd=0.42)
        plogger.show_status_panel()

        output = console.file.getvalue()
        assert "$0.42" in output

    def test_reset_session_cost(self):
        from io import StringIO

        from rich.console import Console

        console = Console(file=StringIO(), force_terminal=True)
        plogger = PipelineLogger(console=console)

        plogger.track_tokens(1000, 500, cost_usd=0.10)
        assert plogger._session_cost_usd == pytest.approx(0.10)

        plogger.reset_session_cost()
        assert plogger._session_cost_usd == 0.0
        # Total cost is NOT reset
        assert plogger._cost_usd == pytest.approx(0.10)

    def test_format_cost_small(self):
        assert PipelineLogger._format_cost(0.005) == "$0.0050"

    def test_format_cost_normal(self):
        assert PipelineLogger._format_cost(1.23) == "$1.23"
