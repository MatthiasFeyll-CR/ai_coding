"""Rich-based structured logging for the pipeline."""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.state import PipelineState


class PipelineLogger:
    """Structured console output using Rich.
    Shows status panel + severity-tagged messages."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self._milestone_id = 0
        self._milestone_name = ""
        self._phase = ""
        self._total_milestones = 0
        self._elapsed_start = time.monotonic()
        self._project_name = ""
        self._tokens_in = 0
        self._tokens_out = 0
        self._cache_creation = 0
        self._cache_read = 0
        self._cost_usd = 0.0
        self._session_cost_usd = 0.0

    def set_context(
        self,
        milestone_id: int,
        milestone_name: str,
        phase: str,
        total_milestones: int,
        project_name: str = "",
    ) -> None:
        """Update the status panel context."""
        self._milestone_id = milestone_id
        self._milestone_name = milestone_name
        self._phase = phase
        self._total_milestones = total_milestones
        if project_name:
            self._project_name = project_name

    def track_tokens(
        self,
        tokens_in: int,
        tokens_out: int,
        cache_creation: int = 0,
        cache_read: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Accumulate token usage and cost for display in status panel."""
        self._tokens_in += tokens_in
        self._tokens_out += tokens_out
        self._cache_creation += cache_creation
        self._cache_read += cache_read
        self._cost_usd += cost_usd
        self._session_cost_usd += cost_usd

    def reset_session_cost(self) -> None:
        """Reset per-session cost accumulator (call at phase boundaries)."""
        self._session_cost_usd = 0.0

    def _format_tokens(self, count: int) -> str:
        """Format token count for display (e.g., 48000 → ~48K)."""
        if count >= 1000:
            return f"~{count // 1000}K"
        return str(count)

    def _ts(self) -> str:
        from datetime import datetime

        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def _format_cost(usd: float) -> str:
        """Format USD cost for display."""
        if usd < 0.01:
            return f"${usd:.4f}"
        return f"${usd:.2f}"

    def show_status_panel(self) -> None:
        """Render the top-level status panel."""
        elapsed = time.monotonic() - self._elapsed_start
        mins, secs = divmod(int(elapsed), 60)

        phase_map = {
            "prd_generation": ("PRD Generation", "1/4"),
            "ralph_execution": ("Ralph Execution", "2/4"),
            "qa_review": ("QA Review", "3/4"),
            "reconciliation": ("Merge + Reconciliation", "4/4"),
        }
        phase_name, phase_num = phase_map.get(self._phase, (self._phase, ""))

        content = (
            f"  Milestone {self._milestone_id}/{self._total_milestones}: "
            f"{self._milestone_name}\n"
            f"  Phase: {phase_name} ({phase_num})\n"
            f"  Elapsed: {mins}m {secs:02d}s"
        )

        if self._tokens_in > 0 or self._tokens_out > 0:
            content += (
                f"\n  Tokens: {self._format_tokens(self._tokens_in)} in / "
                f"{self._format_tokens(self._tokens_out)} out"
            )
            if self._cache_read > 0 or self._cache_creation > 0:
                content += (
                    f" (cached: {self._format_tokens(self._cache_read)} read"
                    f", {self._format_tokens(self._cache_creation)} created)"
                )

        if self._cost_usd > 0:
            content += (
                f"\n  Cost: {self._format_cost(self._session_cost_usd)} (phase) / "
                f"{self._format_cost(self._cost_usd)} (total)"
            )

        panel = Panel(
            content,
            title=f"Pipeline: {self._project_name}",
            border_style="blue",
        )
        self.console.print(panel)

    def info(self, msg: str) -> None:
        self.console.print(f"[dim][{self._ts()}][/dim] [blue]ℹ[/blue]  {msg}")

    def success(self, msg: str) -> None:
        self.console.print(f"[dim][{self._ts()}][/dim] [green]✓[/green]  {msg}")

    def warning(self, msg: str) -> None:
        self.console.print(f"[dim][{self._ts()}][/dim] [yellow]⚠[/yellow]  {msg}")

    def error(self, msg: str) -> None:
        self.console.print(f"[dim][{self._ts()}][/dim] [red]✗[/red]  {msg}")

    def section(self, title: str) -> None:
        self.console.print(f"\n[bold cyan]{'═' * 60}[/bold cyan]")
        self.console.print(f"[bold cyan]  {title}[/bold cyan]")
        self.console.print(f"[bold cyan]{'═' * 60}[/bold cyan]\n")

    def show_summary(self, state: PipelineState, config: PipelineConfig) -> None:
        """Show completion/interruption summary with milestone status table."""
        elapsed = time.monotonic() - self._elapsed_start
        mins, secs = divmod(int(elapsed), 60)

        # Determine overall status
        all_complete = all(ms.phase == "complete" for ms in state.milestones.values())
        current_ms = state.milestones.get(state.current_milestone)
        if all_complete:
            status_line = "[green]COMPLETE — all milestones finished[/green]"
        elif current_ms:
            status_line = (
                f"[yellow]INTERRUPTED during M{state.current_milestone} "
                f"{current_ms.phase}[/yellow]"
            )
        else:
            status_line = "[yellow]INTERRUPTED[/yellow]"

        # Build milestone table
        table = Table(show_header=False, box=None, padding=(0, 2))
        for m_cfg in config.milestones:
            ms = state.milestones.get(m_cfg.id)
            if not ms:
                continue
            if ms.phase == "complete":
                icon = "[green]✓[/green]"
                status = "complete"
            elif ms.phase == "pending":
                icon = "[dim]○[/dim]"
                status = "pending"
            else:
                icon = "[yellow]◐[/yellow]"
                status = ms.phase
                if ms.bugfix_cycle > 0:
                    status += f" cycle {ms.bugfix_cycle}"
            table.add_row(
                f"  {icon}",
                f"M{m_cfg.id} {m_cfg.name}",
                status,
            )

        content = f"  Status: {status_line}\n"
        if not all_complete:
            content += "  Resume: [cyan]ralph-pipeline run --config pipeline-config.json --resume[/cyan]\n"
        content += f"\n  Total time: {mins}m {secs:02d}s\n  Logs: .ralph/logs/\n"

        # Cost summary
        if state.cost.total_usd > 0:
            content += f"  Total cost: [bold]{self._format_cost(state.cost.total_usd)}[/bold]\n"
            if state.cost.by_milestone:
                parts = [
                    f"M{mid}: {self._format_cost(c)}"
                    for mid, c in sorted(state.cost.by_milestone.items())
                ]
                content += f"  By milestone: {' | '.join(parts)}\n"

        panel = Panel(
            content,
            title="Pipeline Summary",
            border_style="green" if all_complete else "yellow",
        )
        self.console.print(panel)
        self.console.print(table)
        self.console.print()
