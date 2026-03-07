"""Pipeline state persistence + FSM state definitions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from ralph_pipeline.config import PipelineConfig


class SessionCost(BaseModel):
    """Cost record for a single Claude CLI session."""

    session_id: str
    phase: str
    milestone: int
    model: str
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    invocations: int = 0


class CostSummary(BaseModel):
    """Aggregated cost tracking across the entire pipeline run."""

    total_usd: float = 0.0
    by_milestone: dict[int, float] = {}
    by_phase: dict[str, float] = {}
    by_model: dict[str, float] = {}
    sessions: list[SessionCost] = []

    def record(
        self,
        cost_usd: float,
        milestone: int,
        phase: str,
        model: str,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> None:
        """Record a single invocation's cost into all aggregations."""
        self.total_usd += cost_usd
        self.by_milestone[milestone] = self.by_milestone.get(milestone, 0.0) + cost_usd
        self.by_phase[phase] = self.by_phase.get(phase, 0.0) + cost_usd
        self.by_model[model] = self.by_model.get(model, 0.0) + cost_usd

        # Merge into existing session or create new entry
        existing = next(
            (s for s in self.sessions if s.session_id == session_id and session_id),
            None,
        )
        if existing:
            existing.cost_usd += cost_usd
            existing.input_tokens += input_tokens
            existing.output_tokens += output_tokens
            existing.cache_creation_tokens += cache_creation_tokens
            existing.cache_read_tokens += cache_read_tokens
            existing.invocations += 1
        else:
            self.sessions.append(
                SessionCost(
                    session_id=session_id or f"{phase}-m{milestone}",
                    phase=phase,
                    milestone=milestone,
                    model=model,
                    cost_usd=cost_usd,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    cache_read_tokens=cache_read_tokens,
                    invocations=1,
                )
            )


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
    cost: CostSummary = CostSummary()
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
