"""Tests for PRD schema and iteration budget recalculation (Issue 08 fix)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from ralph_pipeline.config import (MilestoneConfig, PipelineConfig,
                                   ProjectConfig, RalphConfig)
from ralph_pipeline.phases.ralph_execution import (_get_prd_story_count,
                                                   _resolve_iteration_budget)
from ralph_pipeline.prd_schema import PRD, PRDLoadError

# ── PRD schema tests ──────────────────────────────────────────────────────────


class TestPRDSchema:
    def test_load_valid_prd(self, tmp_path: Path):
        prd_data = {
            "project": "TestProject",
            "branchName": "ralph/m1-alpha",
            "description": "Test milestone",
            "userStories": [
                {
                    "id": "US-001",
                    "title": "First story",
                    "description": "As a user...",
                    "acceptanceCriteria": ["Criterion 1"],
                    "priority": 1,
                    "passes": False,
                },
                {
                    "id": "US-002",
                    "title": "Second story",
                    "passes": True,
                },
            ],
        }
        prd_file = tmp_path / "prd-m1.json"
        prd_file.write_text(json.dumps(prd_data))

        prd = PRD.load(prd_file)
        assert prd.project == "TestProject"
        assert prd.story_count == 2
        assert prd.pending_story_count == 1
        assert prd.userStories[0].id == "US-001"
        assert prd.userStories[1].passes is True

    def test_load_minimal_prd(self, tmp_path: Path):
        """PRD with only userStories should load fine."""
        prd_data = {
            "userStories": [
                {"id": "US-001", "title": "Only story"},
            ],
        }
        prd_file = tmp_path / "prd.json"
        prd_file.write_text(json.dumps(prd_data))

        prd = PRD.load(prd_file)
        assert prd.story_count == 1
        assert prd.project == ""

    def test_load_empty_stories(self, tmp_path: Path):
        prd_file = tmp_path / "prd.json"
        prd_file.write_text('{"userStories": []}')

        prd = PRD.load(prd_file)
        assert prd.story_count == 0
        assert prd.pending_story_count == 0

    def test_load_missing_file_raises(self, tmp_path: Path):
        try:
            PRD.load(tmp_path / "nonexistent.json")
            assert False, "Should have raised PRDLoadError"
        except PRDLoadError as e:
            assert "not found" in str(e)

    def test_load_invalid_json_raises(self, tmp_path: Path):
        prd_file = tmp_path / "prd.json"
        prd_file.write_text("{invalid json")

        try:
            PRD.load(prd_file)
            assert False, "Should have raised PRDLoadError"
        except PRDLoadError as e:
            assert "Invalid JSON" in str(e)

    def test_story_context_parsed(self, tmp_path: Path):
        prd_data = {
            "userStories": [
                {
                    "id": "US-001",
                    "title": "Story with context",
                    "context": {
                        "data_model": ["CREATE TABLE users"],
                        "api_endpoints": ["POST /api/users"],
                        "test_cases": ["T-1.1.01"],
                    },
                }
            ],
        }
        prd_file = tmp_path / "prd.json"
        prd_file.write_text(json.dumps(prd_data))

        prd = PRD.load(prd_file)
        ctx = prd.userStories[0].context
        assert ctx is not None
        assert ctx.data_model == ["CREATE TABLE users"]
        assert ctx.api_endpoints == ["POST /api/users"]

    def test_bugfix_prd_format(self, tmp_path: Path):
        """The QA engineer's bugfix PRD format should also parse correctly."""
        prd_data = {
            "project": "TestProject",
            "branchName": "ralph/m1-alpha-bugfix-1",
            "description": "Bugfix cycle 1",
            "userStories": [
                {
                    "id": "BF-001",
                    "title": "Fix: DEF-001",
                    "description": "Fix defect DEF-001",
                    "acceptanceCriteria": ["Bug is fixed"],
                    "priority": 1,
                    "passes": False,
                    "notes": "Defect: DEF-001. File: src/app.py.",
                },
                {
                    "id": "BF-002",
                    "title": "Fix: DEF-002",
                    "passes": False,
                },
            ],
        }
        prd_file = tmp_path / "prd.json"
        prd_file.write_text(json.dumps(prd_data))

        prd = PRD.load(prd_file)
        assert prd.story_count == 2
        assert prd.pending_story_count == 2

    def test_extra_fields_ignored(self, tmp_path: Path):
        """Unknown fields in the PRD should not cause validation failures."""
        prd_data = {
            "userStories": [{"id": "US-001", "title": "Story", "customField": 42}],
            "extraTopLevel": "ignored",
        }
        prd_file = tmp_path / "prd.json"
        prd_file.write_text(json.dumps(prd_data))

        prd = PRD.load(prd_file)
        assert prd.story_count == 1


# ── _get_prd_story_count tests ────────────────────────────────────────────────


class TestGetPrdStoryCount:
    def test_returns_count_from_valid_prd(self, tmp_path: Path):
        prd_data = {
            "userStories": [
                {"id": "US-001", "title": "S1"},
                {"id": "US-002", "title": "S2"},
                {"id": "US-003", "title": "S3"},
            ]
        }
        prd_file = tmp_path / "prd.json"
        prd_file.write_text(json.dumps(prd_data))

        plogger = MagicMock()
        assert _get_prd_story_count(prd_file, plogger) == 3
        plogger.warning.assert_not_called()

    def test_returns_none_for_missing_file(self, tmp_path: Path):
        plogger = MagicMock()
        result = _get_prd_story_count(tmp_path / "missing.json", plogger)
        assert result is None
        plogger.warning.assert_called_once()

    def test_returns_none_for_invalid_json(self, tmp_path: Path):
        prd_file = tmp_path / "prd.json"
        prd_file.write_text("not json")

        plogger = MagicMock()
        result = _get_prd_story_count(prd_file, plogger)
        assert result is None
        plogger.warning.assert_called_once()


# ── _resolve_iteration_budget tests ───────────────────────────────────────────


def _make_config(**overrides) -> PipelineConfig:
    defaults = {
        "project": ProjectConfig(name="TestProject"),
        "milestones": [MilestoneConfig(id=1, slug="alpha", name="Alpha", stories=5)],
    }
    defaults.update(overrides)
    return PipelineConfig(**defaults)


class TestResolveIterationBudget:
    def test_uses_prd_count_when_available(self, tmp_path: Path):
        """When PRD exists, iteration budget uses its story count."""
        config = _make_config()
        milestone = config.milestones[0]  # stories=5

        # PRD has 8 stories → budget = 8 * 3 = 24
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        prd_data = {
            "userStories": [{"id": f"US-{i}", "title": f"S{i}"} for i in range(8)]
        }
        (tasks_dir / "prd-m1.json").write_text(json.dumps(prd_data))

        plogger = MagicMock()
        budget = _resolve_iteration_budget(milestone, config, tmp_path, plogger)

        assert budget == 24  # 8 stories * 3 multiplier

    def test_falls_back_to_config_when_no_prd(self, tmp_path: Path):
        """When PRD doesn't exist, falls back to config.stories."""
        config = _make_config()
        milestone = config.milestones[0]  # stories=5

        plogger = MagicMock()
        budget = _resolve_iteration_budget(milestone, config, tmp_path, plogger)

        assert budget == 15  # 5 stories * 3 multiplier

    def test_emits_warning_on_drift(self, tmp_path: Path):
        """When PRD story count differs from config, a deprecation warning is emitted."""
        config = _make_config()
        milestone = config.milestones[0]  # stories=5

        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        prd_data = {
            "userStories": [{"id": f"US-{i}", "title": f"S{i}"} for i in range(8)]
        }
        (tasks_dir / "prd-m1.json").write_text(json.dumps(prd_data))

        plogger = MagicMock()
        _resolve_iteration_budget(milestone, config, tmp_path, plogger)

        # Should have warned about drift
        plogger.warning.assert_called_once()
        warning_msg = plogger.warning.call_args[0][0]
        assert "drift" in warning_msg.lower()
        assert "5" in warning_msg  # configured count
        assert "8" in warning_msg  # PRD count
        assert "advisory" in warning_msg.lower()

    def test_no_warning_when_counts_match(self, tmp_path: Path):
        """No warning when PRD count matches config."""
        config = _make_config()
        milestone = config.milestones[0]  # stories=5

        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        prd_data = {
            "userStories": [{"id": f"US-{i}", "title": f"S{i}"} for i in range(5)]
        }
        (tasks_dir / "prd-m1.json").write_text(json.dumps(prd_data))

        plogger = MagicMock()
        budget = _resolve_iteration_budget(milestone, config, tmp_path, plogger)

        assert budget == 15  # 5 * 3
        plogger.warning.assert_not_called()

    def test_custom_multiplier_override(self, tmp_path: Path):
        """Bugfix mode uses multiplier=2 override."""
        config = _make_config()
        milestone = config.milestones[0]  # stories=5

        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        prd_data = {
            "userStories": [{"id": f"US-{i}", "title": f"S{i}"} for i in range(4)]
        }
        (tasks_dir / "prd-m1.json").write_text(json.dumps(prd_data))

        plogger = MagicMock()
        budget = _resolve_iteration_budget(
            milestone, config, tmp_path, plogger, multiplier=2
        )

        assert budget == 8  # 4 stories * 2 multiplier

    def test_uses_config_multiplier_by_default(self, tmp_path: Path):
        """If no multiplier override, uses config.ralph.max_iterations_multiplier."""
        config = _make_config(ralph=RalphConfig(max_iterations_multiplier=4))
        milestone = config.milestones[0]  # stories=5

        plogger = MagicMock()
        budget = _resolve_iteration_budget(milestone, config, tmp_path, plogger)

        assert budget == 20  # 5 stories * 4 multiplier (no PRD, fallback)

    def test_prd_with_zero_stories_uses_prd_count(self, tmp_path: Path):
        """Even with 0 stories in PRD, we use PRD count (0) not config count."""
        config = _make_config()
        milestone = config.milestones[0]  # stories=5

        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        prd_data = {"userStories": []}
        (tasks_dir / "prd-m1.json").write_text(json.dumps(prd_data))

        plogger = MagicMock()
        budget = _resolve_iteration_budget(milestone, config, tmp_path, plogger)

        assert budget == 0  # 0 stories * 3 multiplier

    def test_milestone_id_in_prd_path(self, tmp_path: Path):
        """Correctly maps milestone ID to prd-mN.json filename."""
        config = _make_config(
            milestones=[
                MilestoneConfig(id=3, slug="gamma", name="Gamma", stories=2),
            ]
        )
        milestone = config.milestones[0]

        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        prd_data = {
            "userStories": [
                {"id": "US-001", "title": "S1"},
                {"id": "US-002", "title": "S2"},
                {"id": "US-003", "title": "S3"},
            ]
        }
        (tasks_dir / "prd-m3.json").write_text(json.dumps(prd_data))

        plogger = MagicMock()
        budget = _resolve_iteration_budget(milestone, config, tmp_path, plogger)

        assert budget == 9  # 3 stories from PRD * 3 multiplier
