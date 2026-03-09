"""Tests for the Ralph agent loop in ralph_execution.py."""

from __future__ import annotations

import json
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
                                                   _count_remaining,
                                                   _inject_runtime_footer,
                                                   _run_ralph_loop,
                                                   _write_claude_md)


def _make_mock_claude(outputs: list[str]) -> MagicMock:
    """Create a ClaudeRunner mock returning sequential outputs."""
    claude = MagicMock()
    results = [SimpleNamespace(output=o) for o in outputs]
    claude.run.side_effect = results
    return claude


def _write_prd(scripts_dir: Path, stories: list[dict]) -> None:
    """Write a prd.json into scripts_dir for testing."""
    prd = {"userStories": stories}
    (scripts_dir / "prd.json").write_text(json.dumps(prd))


class TestRunRalphLoop:
    def test_completes_when_all_stories_pass(self, tmp_path: Path):
        """COMPLETE + all stories passes=true → returns True on first iteration."""
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")
        _write_prd(scripts, [{"id": "US-001", "passes": True}])

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
    def test_continues_when_stories_remain(self, mock_sleep, tmp_path: Path):
        """COMPLETE but stories remain → continues to next iteration."""
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")
        prd_path = scripts / "prd.json"

        # Start with 2 incomplete stories; after first iteration one passes
        _write_prd(scripts, [
            {"id": "US-001", "passes": False},
            {"id": "US-002", "passes": False},
        ])

        call_count = 0

        def claude_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate Ralph marking one story done
                prd_data = json.loads(prd_path.read_text())
                prd_data["userStories"][0]["passes"] = True
                prd_path.write_text(json.dumps(prd_data))
                return SimpleNamespace(output=f"Story 1 done {COMPLETION_SIGNAL}")
            elif call_count == 2:
                # Simulate Ralph marking second story done
                prd_data = json.loads(prd_path.read_text())
                prd_data["userStories"][1]["passes"] = True
                prd_path.write_text(json.dumps(prd_data))
                return SimpleNamespace(output=f"Story 2 done {COMPLETION_SIGNAL}")
            return SimpleNamespace(output="unexpected")

        claude = MagicMock()
        claude.run.side_effect = claude_side_effect
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
        # Sleep called after first story completion before starting next
        assert mock_sleep.call_count == 1

    @patch("ralph_pipeline.phases.ralph_execution.time.sleep")
    def test_retries_on_no_complete_signal(self, mock_sleep, tmp_path: Path):
        """No COMPLETE signal → retries, then COMPLETE + all pass → done."""
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")
        _write_prd(scripts, [{"id": "US-001", "passes": False}])
        prd_path = scripts / "prd.json"

        def claude_side_effect(*args, **kwargs):
            # First call: no signal (crash/timeout)
            if claude.run.call_count <= 1:
                return SimpleNamespace(output="Still working...")
            # Second call: completes
            prd_data = json.loads(prd_path.read_text())
            prd_data["userStories"][0]["passes"] = True
            prd_path.write_text(json.dumps(prd_data))
            return SimpleNamespace(output=f"All done {COMPLETION_SIGNAL}")

        claude = MagicMock()
        claude.run.side_effect = claude_side_effect
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

    @patch("ralph_pipeline.phases.ralph_execution.time.sleep")
    def test_reaches_max_iterations(self, mock_sleep, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("Do the work.")
        _write_prd(scripts, [{"id": "US-001", "passes": False}])

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
        _write_prd(scripts, [{"id": "US-001", "passes": False}])
        prd_path = scripts / "prd.json"

        def side_effect(*args, **kwargs):
            if claude.run.call_count <= 1:
                raise RuntimeError("timeout")
            prd_data = json.loads(prd_path.read_text())
            prd_data["userStories"][0]["passes"] = True
            prd_path.write_text(json.dumps(prd_data))
            return SimpleNamespace(output=f"ok {COMPLETION_SIGNAL}")

        claude = MagicMock()
        claude.run.side_effect = side_effect
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


class TestCountRemaining:
    def test_all_remaining(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text('{"userStories": [{"passes": false}, {"passes": false}]}')
        assert _count_remaining(prd) == 2

    def test_some_remaining(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text('{"userStories": [{"passes": true}, {"passes": false}]}')
        assert _count_remaining(prd) == 1

    def test_none_remaining(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text('{"userStories": [{"passes": true}, {"passes": true}]}')
        assert _count_remaining(prd) == 0

    def test_missing_file(self, tmp_path: Path):
        assert _count_remaining(tmp_path / "nonexistent.json") == -1

    def test_missing_passes_field(self, tmp_path: Path):
        """Stories without passes field default to False (remaining)."""
        prd = tmp_path / "prd.json"
        prd.write_text('{"userStories": [{"id": "US-001"}]}')
        assert _count_remaining(prd) == 1


class TestWriteClaudeMd:
    def test_writes_per_story_instructions(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        plogger = MagicMock()

        _write_claude_md(scripts, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        assert "One story per session" in content
        assert "COMPLETE" in content
        assert "Repeat from step 1" not in content
        plogger.info.assert_called()

    def test_overwrites_existing(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("old content with Repeat from step 1")
        plogger = MagicMock()

        _write_claude_md(scripts, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        assert "old content" not in content
        assert "One story per session" in content

    def test_permits_prd_passes_modification(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        plogger = MagicMock()

        _write_claude_md(scripts, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        assert "passes" in content.lower()
        assert "prd.json" in content


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
