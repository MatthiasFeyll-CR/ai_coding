"""Pipeline state persistence + FSM state definitions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from ralph_pipeline.config import PipelineConfig


class MilestoneState(BaseModel):
    """State for a single milestone."""

    id: int
    phase: str = "pending"
    bugfix_cycle: int = 0
    test_fix_cycle: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class PipelineState(BaseModel):
    """Full pipeline state — persisted to .ralph/state.json."""

    base_branch: str
    current_milestone: int
    milestones: dict[int, MilestoneState] = {}
    test_milestone_map: dict[str, int] = {}
    phase0_complete: bool = False
    phase0_started_at: Optional[str] = None
    phase0_completed_at: Optional[str] = None
    timestamp: str = ""

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path) -> PipelineState:
        return cls.model_validate_json(path.read_text())

    @classmethod
    def initialize(cls, config: PipelineConfig, base_branch: str) -> PipelineState:
        """Create initial state from config."""
        milestones = {m.id: MilestoneState(id=m.id) for m in config.milestones}
        first_id = config.milestones[0].id
        return cls(
            base_branch=base_branch,
            current_milestone=first_id,
            milestones=milestones,
        )

    def update_phase(self, milestone_id: int, phase: str) -> None:
        """Update phase for a milestone and persist timestamp."""
        ms = self.milestones[milestone_id]
        ms.phase = phase
        if phase != "pending" and ms.started_at is None:
            ms.started_at = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        if phase == "complete":
            ms.completed_at = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
