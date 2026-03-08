"""Tests for the Ralph agent loop in ralph_execution.py."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ralph_pipeline.config import GateCheck, GateChecksConfig
from ralph_pipeline.config import MilestoneConfig as MilestoneConfigModel
from ralph_pipeline.config import (PipelineConfig, ProjectConfig,
                                   TestExecutionConfig, Tier1Config,
                                   Tier1Environment)
from ralph_pipeline.phases.ralph_execution import (COMPLETION_SIGNAL,
                                                   RUNTIME_FOOTER_END,
                                                   RUNTIME_FOOTER_START,
                                                   _build_runtime_footer,
                                                   _check_all_pass,
                                                   _inject_runtime_footer,
                                                   _run_ralph_loop)


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


def _make_config(**overrides) -> PipelineConfig:
    """Create a minimal PipelineConfig for testing."""
    defaults = {
        "project": ProjectConfig(name="TestProject"),
        "milestones": [MilestoneConfigModel(id=1, slug="alpha", name="Alpha", stories=3)],
        "test_execution": TestExecutionConfig(),
        "gate_checks": GateChecksConfig(),
    }
    defaults.update(overrides)
    return PipelineConfig(**defaults)


class TestBuildRuntimeFooter:
    def test_basic_test_command(self):
        config = _make_config(
            test_execution=TestExecutionConfig(test_command="pytest tests/"),
        )
        footer = _build_runtime_footer(config)
        assert "pytest tests/" in footer
        assert "### Test Command" in footer

    def test_tier1_environments(self):
        config = _make_config(
            test_execution=TestExecutionConfig(
                tier1=Tier1Config(
                    environments=[
                        Tier1Environment(
                            name="backend",
                            service="backend",
                            test_command="pytest",
                            build_command="docker compose build backend",
                        ),
                        Tier1Environment(
                            name="frontend",
                            service="frontend",
                            test_command="npm test",
                        ),
                    ]
                )
            ),
        )
        footer = _build_runtime_footer(config)
        assert "### Test Commands (Tier 1)" in footer
        assert "pytest" in footer
        assert "npm test" in footer
        assert "docker compose build backend" in footer
        # Tier 1 takes precedence — no "### Test Command" section
        assert "### Test Command\n" not in footer

    def test_gate_checks(self):
        config = _make_config(
            gate_checks=GateChecksConfig(
                checks=[
                    GateCheck(name="lint", command="ruff check ."),
                    GateCheck(name="types", command="mypy src/", required=False),
                ]
            ),
        )
        footer = _build_runtime_footer(config)
        assert "### Gate Checks" in footer
        assert "ruff check ." in footer
        assert "mypy src/" in footer
        assert "# optional" in footer
        assert "# lint" in footer

    def test_setup_teardown(self):
        config = _make_config(
            test_execution=TestExecutionConfig(
                test_command="pytest",
                setup_command="docker compose up -d",
                teardown_command="docker compose down",
            ),
        )
        footer = _build_runtime_footer(config)
        assert "docker compose up -d" in footer
        assert "docker compose down" in footer
        assert "# clean slate" in footer
        assert "# start dependency services" in footer

    def test_integration_test_command(self):
        config = _make_config(
            test_execution=TestExecutionConfig(
                test_command="pytest tests/unit",
                integration_test_command="pytest tests/integration",
            ),
        )
        footer = _build_runtime_footer(config)
        assert "### Integration Test Command" in footer
        assert "pytest tests/integration" in footer

    def test_empty_config(self):
        config = _make_config()
        footer = _build_runtime_footer(config)
        assert "No test or gate check commands configured." in footer

    def test_build_command_included(self):
        config = _make_config(
            test_execution=TestExecutionConfig(
                test_command="pytest",
                build_command="pip install -e .",
            ),
        )
        footer = _build_runtime_footer(config)
        assert "pip install -e ." in footer
        assert "pytest" in footer


class TestInjectRuntimeFooter:
    def test_injects_footer_into_claude_md(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("# CLAUDE.md\n\nDo the work.")

        config = _make_config(
            test_execution=TestExecutionConfig(test_command="pytest tests/"),
        )
        plogger = MagicMock()

        _inject_runtime_footer(scripts, config, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        assert "# CLAUDE.md" in content
        assert "Do the work." in content
        assert "pytest tests/" in content
        assert RUNTIME_FOOTER_START.strip() in content
        assert RUNTIME_FOOTER_END.strip() in content
        plogger.info.assert_called()

    def test_idempotent_reinjection(self, tmp_path: Path):
        """Running inject twice doesn't duplicate the footer."""
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        original = "# CLAUDE.md\n\nDo the work."
        (scripts / "CLAUDE.md").write_text(original)

        config = _make_config(
            test_execution=TestExecutionConfig(test_command="pytest tests/"),
        )
        plogger = MagicMock()

        _inject_runtime_footer(scripts, config, plogger)
        first_content = (scripts / "CLAUDE.md").read_text()

        _inject_runtime_footer(scripts, config, plogger)
        second_content = (scripts / "CLAUDE.md").read_text()

        assert first_content == second_content
        # Only one footer marker
        assert second_content.count(RUNTIME_FOOTER_START.strip()) == 1

    def test_updates_when_config_changes(self, tmp_path: Path):
        """If config changes between runs, footer reflects the new config."""
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("# CLAUDE.md\n\nDo the work.")

        config1 = _make_config(
            test_execution=TestExecutionConfig(test_command="pytest tests/"),
        )
        plogger = MagicMock()
        _inject_runtime_footer(scripts, config1, plogger)

        config2 = _make_config(
            test_execution=TestExecutionConfig(test_command="npm test"),
        )
        _inject_runtime_footer(scripts, config2, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        assert "npm test" in content
        assert "pytest tests/" not in content

    def test_noop_when_claude_md_missing(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        # No CLAUDE.md

        config = _make_config()
        plogger = MagicMock()

        _inject_runtime_footer(scripts, config, plogger)
        # Should not crash, and no file created
        assert not (scripts / "CLAUDE.md").exists()

    def test_preserves_original_content(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        original = "# CLAUDE.md\n\n## Task Workflow\n\n1. Read prd.json\n2. Implement\n3. Test\n\n## Stop Condition\n\n<promise>COMPLETE</promise>"
        (scripts / "CLAUDE.md").write_text(original)

        config = _make_config(
            test_execution=TestExecutionConfig(test_command="pytest"),
            gate_checks=GateChecksConfig(
                checks=[GateCheck(name="lint", command="ruff check .")]
            ),
        )
        plogger = MagicMock()

        _inject_runtime_footer(scripts, config, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        # Original content preserved
        assert "## Task Workflow" in content
        assert "## Stop Condition" in content
        assert "<promise>COMPLETE</promise>" in content
        # Footer appended
        assert "pytest" in content
        assert "ruff check ." in content
