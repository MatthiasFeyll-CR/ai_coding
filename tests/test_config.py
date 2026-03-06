"""Tests for config loading and validation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from ralph_pipeline.config import MilestoneConfig, PipelineConfig

MINIMAL_CONFIG = {
    "project": {"name": "Test Project", "description": "A test"},
    "milestones": [
        {"id": 1, "slug": "foundation", "name": "Foundation", "stories": 5},
        {
            "id": 2,
            "slug": "core",
            "name": "Core Features",
            "stories": 8,
            "dependencies": [1],
        },
    ],
}


def _write_config(data: dict) -> Path:
    """Write config to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestPipelineConfig:
    def test_load_minimal(self):
        path = _write_config(MINIMAL_CONFIG)
        config = PipelineConfig.load(path)
        assert config.project.name == "Test Project"
        assert len(config.milestones) == 2
        assert config.milestones[0].slug == "foundation"
        assert config.milestones[1].dependencies == [1]

    def test_defaults_applied(self):
        path = _write_config(MINIMAL_CONFIG)
        config = PipelineConfig.load(path)
        assert config.paths.scripts_dir == ".ralph"
        assert config.qa.max_bugfix_cycles == 3
        assert config.ralph.max_iterations_multiplier == 3
        assert config.retry.max_retries == 3
        assert config.models.ralph == ""

    def test_missing_dependency(self):
        data = {
            "project": {"name": "Test"},
            "milestones": [
                {"id": 1, "slug": "a", "name": "A", "stories": 1, "dependencies": [99]},
            ],
        }
        path = _write_config(data)
        with pytest.raises(Exception, match="M1 depends on M99"):
            PipelineConfig.load(path)

    def test_circular_dependency(self):
        data = {
            "project": {"name": "Test"},
            "milestones": [
                {"id": 2, "slug": "b", "name": "B", "stories": 1, "dependencies": [1]},
                {"id": 1, "slug": "a", "name": "A", "stories": 1},
            ],
        }
        path = _write_config(data)
        with pytest.raises(Exception, match="comes after it"):
            PipelineConfig.load(path)

    def test_full_config(self):
        data = {
            **MINIMAL_CONFIG,
            "models": {"ralph": "opus", "prd_generation": "sonnet"},
            "qa": {"max_bugfix_cycles": 5},
            "gate_checks": {
                "max_fix_cycles": 2,
                "checks": [
                    {
                        "name": "typecheck",
                        "command": "npm run type-check",
                        "required": True,
                    },
                ],
            },
            "test_execution": {
                "test_command": "pytest",
                "timeout_seconds": 600,
                "max_fix_cycles": 3,
                "services": [
                    {"name": "postgres", "port": 5432, "startup_timeout": 30},
                ],
            },
        }
        path = _write_config(data)
        config = PipelineConfig.load(path)
        assert config.models.ralph == "opus"
        assert config.qa.max_bugfix_cycles == 5
        assert len(config.gate_checks.checks) == 1
        assert config.test_execution.services[0].name == "postgres"

    def test_milestone_config_fields(self):
        m = MilestoneConfig(id=1, slug="test-slug", name="Test", stories=3)
        assert m.id == 1
        assert m.slug == "test-slug"
        assert m.dependencies == []
