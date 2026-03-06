"""Tests for pipeline state persistence."""

from __future__ import annotations

from pathlib import Path

from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.state import MilestoneState, PipelineState

MINIMAL_CONFIG = {
    "project": {"name": "Test"},
    "milestones": [
        {"id": 1, "slug": "a", "name": "A", "stories": 3},
        {"id": 2, "slug": "b", "name": "B", "stories": 5, "dependencies": [1]},
    ],
}


class TestPipelineState:
    def test_initialize(self):
        config = PipelineConfig(**MINIMAL_CONFIG)
        state = PipelineState.initialize(config, "main")
        assert state.base_branch == "main"
        assert state.current_milestone == 1
        assert 1 in state.milestones
        assert 2 in state.milestones
        assert state.milestones[1].phase == "pending"

    def test_save_and_load(self, tmp_path: Path):
        config = PipelineConfig(**MINIMAL_CONFIG)
        state = PipelineState.initialize(config, "main")
        state.update_phase(1, "prd_generation")

        state_file = tmp_path / ".ralph" / "state.json"
        state.save(state_file)

        loaded = PipelineState.load(state_file)
        assert loaded.base_branch == "main"
        assert loaded.milestones[1].phase == "prd_generation"
        assert loaded.timestamp != ""

    def test_update_phase(self):
        config = PipelineConfig(**MINIMAL_CONFIG)
        state = PipelineState.initialize(config, "main")

        state.update_phase(1, "ralph_execution")
        assert state.milestones[1].phase == "ralph_execution"
        assert state.milestones[1].started_at is not None

        state.update_phase(1, "complete")
        assert state.milestones[1].completed_at is not None

    def test_test_milestone_map(self, tmp_path: Path):
        config = PipelineConfig(**MINIMAL_CONFIG)
        state = PipelineState.initialize(config, "main")
        state.test_milestone_map = {"tests/test_a.py": 1, "tests/test_b.py": 2}

        state_file = tmp_path / "state.json"
        state.save(state_file)

        loaded = PipelineState.load(state_file)
        assert loaded.test_milestone_map["tests/test_a.py"] == 1

    def test_milestone_state_defaults(self):
        ms = MilestoneState(id=1)
        assert ms.phase == "pending"
        assert ms.bugfix_cycle == 0
        assert ms.test_fix_cycle == 0
        assert ms.started_at is None
        assert ms.completed_at is None
