"""Structured JSON event logger — writes to .ralph/logs/pipeline.jsonl."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class EventLogger:
    """Writes structured JSON events to .ralph/logs/pipeline.jsonl."""

    def __init__(self, log_path: Path):
        self.path = log_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **data: object) -> None:
        """Write a single event line."""
        entry = {"ts": datetime.utcnow().isoformat() + "Z", "event": event, **data}
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def log_phase_start(self, milestone: int, phase: str, **extra: object) -> None:
        self.emit("phase_start", milestone=milestone, phase=phase, **extra)

    def log_phase_complete(
        self, milestone: int, phase: str, duration_s: float, **extra: object
    ) -> None:
        self.emit(
            "phase_complete",
            milestone=milestone,
            phase=phase,
            duration_s=duration_s,
            **extra,
        )

    def log_infra_ready(self, service: str, port: int, wait_s: float) -> None:
        self.emit("infra_ready", service=service, port=port, wait_s=wait_s)

    def log_test_complete(
        self, tier: int, passed: bool, failures: int = 0, total: int = 0
    ) -> None:
        self.emit(
            "test_complete", tier=tier, passed=passed, failures=failures, total=total
        )

    def log_claude_invocation(
        self,
        phase: str,
        model: str,
        milestone: int,
        input_chars: int,
        output_chars: int,
        duration_s: float,
        attempts: int,
    ) -> None:
        self.emit(
            "claude_invocation",
            phase=phase,
            model=model,
            milestone=milestone,
            input_chars=input_chars,
            output_chars=output_chars,
            input_tokens_est=input_chars // 4,
            output_tokens_est=output_chars // 4,
            duration_s=duration_s,
            attempts=attempts,
        )

    def log_qa_verdict(
        self, milestone: int, verdict: str, failing_stories: list[str] | None = None
    ) -> None:
        self.emit(
            "qa_verdict",
            milestone=milestone,
            verdict=verdict,
            failing_stories=failing_stories or [],
        )
