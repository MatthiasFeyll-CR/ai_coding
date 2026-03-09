"""Tests for Phase 0: Infrastructure Bootstrap."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.phases.phase0_bootstrap import Phase0Error, run_phase0_bootstrap
from ralph_pipeline.state import PipelineState

MINIMAL_CONFIG = PipelineConfig(
    project={"name": "Test"},
    milestones=[
        {"id": 1, "slug": "foundation", "name": "Foundation", "stories": 3},
    ],
)


def _config_with_infra(**overrides) -> PipelineConfig:
    """Create config with test_infrastructure populated."""
    data = MINIMAL_CONFIG.model_dump()
    data["test_infrastructure"] = {
        "compose_file": "docker-compose.test.yml",
        "services": [
            {
                "name": "postgres",
                "image": "postgres:16",
                "port": 5432,
                "environment": {"POSTGRES_PASSWORD": "postgres"},
                "readiness": "pg_isready -U postgres",
            }
        ],
        "runtimes": [
            {
                "name": "backend",
                "base_image": "python:3.12",
                "test_framework": "pytest",
                "test_cmd": "pytest tests/ -v",
            }
        ],
    }
    data.update(overrides)
    return PipelineConfig(**data)


def _config_with_scaffolding(**overrides) -> PipelineConfig:
    """Create config with scaffolding populated."""
    data = MINIMAL_CONFIG.model_dump()
    data["scaffolding"] = {
        "enabled": True,
        "project_structure_doc": "docs/02-architecture/project-structure.md",
        "tech_stack_doc": "docs/02-architecture/tech-stack.md",
    }
    data.update(overrides)
    return PipelineConfig(**data)


def _config_with_both() -> PipelineConfig:
    """Create config with both scaffolding and test_infrastructure."""
    data = MINIMAL_CONFIG.model_dump()
    data["scaffolding"] = {
        "enabled": True,
        "project_structure_doc": "docs/02-architecture/project-structure.md",
    }
    data["test_infrastructure"] = {
        "compose_file": "docker-compose.test.yml",
        "services": [
            {"name": "redis", "image": "redis:7", "port": 6379}
        ],
        "runtimes": [
            {"name": "api", "test_cmd": "pytest tests/ -v"}
        ],
    }
    return PipelineConfig(**data)


class TestPhase0ConfigModels:
    """Test that Phase 0 config models parse correctly."""

    def test_test_infrastructure_optional(self):
        """test_infrastructure defaults to None."""
        assert MINIMAL_CONFIG.test_infrastructure is None

    def test_scaffolding_optional(self):
        """scaffolding defaults to None."""
        assert MINIMAL_CONFIG.scaffolding is None

    def test_test_infrastructure_parsing(self):
        config = _config_with_infra()
        assert config.test_infrastructure is not None
        assert len(config.test_infrastructure.services) == 1
        assert config.test_infrastructure.services[0].name == "postgres"
        assert config.test_infrastructure.services[0].port == 5432
        assert len(config.test_infrastructure.runtimes) == 1
        assert config.test_infrastructure.runtimes[0].test_cmd == "pytest tests/ -v"

    def test_scaffolding_parsing(self):
        config = _config_with_scaffolding()
        assert config.scaffolding is not None
        assert config.scaffolding.enabled is True
        assert "project-structure.md" in config.scaffolding.project_structure_doc

    def test_infra_timeouts_defaults(self):
        config = _config_with_infra()
        assert config.test_infrastructure is not None
        assert config.test_infrastructure.timeouts.setup_seconds == 120
        assert config.test_infrastructure.timeouts.build_seconds == 300
        assert config.test_infrastructure.timeouts.test_seconds == 300


class TestPhase0State:
    """Test phase0_complete state tracking."""

    def test_phase0_complete_defaults_false(self):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        assert state.phase0_complete is False

    def test_phase0_complete_persists(self, tmp_path: Path):
        state = PipelineState.initialize(MINIMAL_CONFIG, "main")
        state.phase0_complete = True
        state_file = tmp_path / "state.json"
        state.save(state_file)

        loaded = PipelineState.load(state_file)
        assert loaded.phase0_complete is True


class TestPhase0Bootstrap:
    """Test run_phase0_bootstrap orchestration."""

    def _make_claude(self) -> MagicMock:
        mock = MagicMock()
        mock.run.return_value = MagicMock(output="ok", attempts=1)
        return mock

    def _make_plogger(self) -> MagicMock:
        return MagicMock()

    def test_skips_when_no_infra_or_scaffolding(self, tmp_path: Path):
        """Phase 0 is a no-op when neither section is configured."""
        config = MINIMAL_CONFIG
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)
        claude.run.assert_not_called()

    def test_scaffolding_only(self, tmp_path: Path):
        """Phase 0 runs scaffolding when only scaffolding is configured."""
        config = _config_with_scaffolding()
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

        # Scaffolding invokes Claude once
        assert claude.run.call_count == 1
        call_kwargs = claude.run.call_args
        assert call_kwargs[1]["phase"] == "phase0_scaffolding"

    def test_infra_full_lifecycle(self, tmp_path: Path):
        """Phase 0 runs all 4 steps with test_infrastructure."""
        config = _config_with_infra()
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        # Create artifacts that Phase 0 expects
        compose_path = tmp_path / "docker-compose.test.yml"
        compose_path.write_text("version: '3'\nservices:\n  postgres:\n    image: postgres:16\n")

        verification = {
            "verified": True,
            "compose_file": "docker-compose.test.yml",
            "steps": {
                "build": "pass",
                "setup": "pass",
                "health": "pass",
                "smoke": "pass",
                "teardown": "pass",
            },
            "test_commands": {"backend": "pytest tests/ -v"},
        }
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        (ralph_dir / "phase0-verification.json").write_text(json.dumps(verification))

        run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

        # Claude called 3 times: test_infra, lifecycle, (no scaffolding)
        assert claude.run.call_count == 2
        phases = [c[1]["phase"] for c in claude.run.call_args_list]
        assert "phase0_test_infra" in phases
        assert "phase0_lifecycle" in phases

        # Config was written back
        updated = json.loads(config_path.read_text())
        assert "test_infrastructure" not in updated
        assert updated["test_execution"]["setup_command"].startswith("docker compose")
        assert updated["test_execution"]["test_command"] == "pytest tests/ -v"

    def test_infra_and_scaffolding(self, tmp_path: Path):
        """Phase 0 runs both scaffolding and infra when both configured."""
        config = _config_with_both()
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        # Create artifacts
        (tmp_path / "docker-compose.test.yml").write_text("version: '3'\n")
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        (ralph_dir / "phase0-verification.json").write_text(
            json.dumps({
                "verified": True,
                "compose_file": "docker-compose.test.yml",
                "steps": {"build": "pass", "setup": "pass", "health": "pass", "smoke": "pass", "teardown": "pass"},
                "test_commands": {"api": "pytest tests/ -v"},
            })
        )

        run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

        # Claude called 3 times: scaffolding + test_infra + lifecycle
        assert claude.run.call_count == 3
        phases = [c[1]["phase"] for c in claude.run.call_args_list]
        assert "phase0_scaffolding" in phases
        assert "phase0_test_infra" in phases
        assert "phase0_lifecycle" in phases

    def test_compose_not_generated_raises(self, tmp_path: Path):
        """Phase 0 raises when Claude doesn't produce compose file."""
        config = _config_with_infra()
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        with pytest.raises(Phase0Error, match="compose file"):
            run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

    def test_lifecycle_verification_fails(self, tmp_path: Path):
        """Phase 0 raises when lifecycle verification reports failure."""
        config = _config_with_infra()
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        (tmp_path / "docker-compose.test.yml").write_text("version: '3'\n")
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        (ralph_dir / "phase0-verification.json").write_text(
            json.dumps({
                "verified": False,
                "steps": {"build": "pass", "setup": "fail"},
            })
        )

        with pytest.raises(Phase0Error, match="verification failed"):
            run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

    def test_verification_report_missing_raises(self, tmp_path: Path):
        """Phase 0 raises when Claude doesn't produce verification report."""
        config = _config_with_infra()
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        (tmp_path / "docker-compose.test.yml").write_text("version: '3'\n")

        with pytest.raises(Phase0Error, match="verification"):
            run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

    def test_scaffolding_claude_failure_raises(self, tmp_path: Path):
        """Phase 0 raises when Claude fails during scaffolding."""
        from ralph_pipeline.ai.claude import ClaudeError

        config = _config_with_scaffolding()
        claude = self._make_claude()
        claude.run.side_effect = ClaudeError("Claude failed")
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        with pytest.raises(Phase0Error, match="scaffolding failed"):
            run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

    def test_write_back_populates_services(self, tmp_path: Path):
        """Write-back generates health check services from infra services."""
        config = _config_with_infra()
        claude = self._make_claude()
        plogger = self._make_plogger()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        (tmp_path / "docker-compose.test.yml").write_text("version: '3'\n")
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir(parents=True, exist_ok=True)
        (ralph_dir / "phase0-verification.json").write_text(
            json.dumps({
                "verified": True,
                "compose_file": "docker-compose.test.yml",
                "steps": {"build": "pass", "setup": "pass", "health": "pass", "smoke": "pass", "teardown": "pass"},
                "test_commands": {"backend": "pytest tests/ -v"},
            })
        )

        run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)

        updated = json.loads(config_path.read_text())
        services = updated["test_execution"]["services"]
        assert len(services) == 1
        assert services[0]["name"] == "postgres"
        assert services[0]["port"] == 5432
        # ready_command should NOT be written — readiness probes are for Docker
        # healthchecks inside containers, not host-side commands
        assert "ready_command" not in services[0]


class TestPhase0DryRun:
    """Test that Phase 0 respects dry-run mode."""

    @patch("ralph_pipeline.phases.phase0_bootstrap.is_dry_run", return_value=True)
    def test_dry_run_skips_claude(self, mock_dry, tmp_path: Path):
        config = _config_with_both()
        claude = MagicMock()
        plogger = MagicMock()
        config_path = tmp_path / "pipeline-config.json"
        config_path.write_text(config.model_dump_json(indent=2))

        run_phase0_bootstrap(config, claude, plogger, tmp_path, config_path)
        claude.run.assert_not_called()
