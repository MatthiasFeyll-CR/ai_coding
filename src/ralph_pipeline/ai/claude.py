"""Claude subprocess wrapper — retry logic, JSON output parsing, usage logging."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ralph_pipeline.config import RetryConfig
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import is_dry_run
from ralph_pipeline.usage import EventLogger


class ClaudeError(Exception):
    """Raised when Claude subprocess fails after all retries."""

    pass


class CostBudgetExceeded(Exception):
    """Raised when cumulative AI cost exceeds the configured budget."""

    pass


@dataclass
class ClaudeUsage:
    """Parsed token usage and cost from Claude CLI JSON output."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    session_id: str = ""
    duration_api_ms: int = 0
    num_turns: int = 0
    model_used: str = ""


@dataclass
class ClaudeResult:
    output: str
    duration_seconds: float
    attempts: int
    model: str
    log_file: Path
    usage: ClaudeUsage = field(default_factory=ClaudeUsage)


class ClaudeRunner:
    """Runs claude --dangerously-skip-permissions --print --output-format json with retry logic."""

    def __init__(
        self,
        retry_config: RetryConfig,
        usage_logger: EventLogger,
        logger: PipelineLogger,
        env: dict[str, str] | None = None,
        cost_tracker: Any | None = None,
        budget_usd: float = 0.0,
    ):
        self.max_retries = retry_config.max_retries
        self.backoff = retry_config.backoff_seconds
        self.usage = usage_logger
        self.log = logger
        self._env = env  # Claude subprocess environment (AI credentials)
        self._cost_tracker = cost_tracker  # state.CostSummary (optional)
        self._budget_usd = budget_usd  # 0 = no limit

    @staticmethod
    def _parse_json_response(raw: str) -> tuple[str, ClaudeUsage]:
        """Parse Claude CLI --output-format json response.

        Returns (text_output, usage). Falls back gracefully if the
        response isn't valid JSON (e.g. older CLI versions).
        """
        usage = ClaudeUsage()
        try:
            data: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # Not JSON — treat entire output as plain text (backward compat)
            return raw, usage

        # Extract the actual text result
        text = data.get("result", raw)

        # Cost
        usage.cost_usd = float(data.get("total_cost_usd", 0.0))
        usage.session_id = data.get("session_id", "")
        usage.duration_api_ms = int(data.get("duration_api_ms", 0))
        usage.num_turns = int(data.get("num_turns", 0))

        # Token breakdown
        u = data.get("usage", {})
        usage.input_tokens = int(u.get("input_tokens", 0))
        usage.output_tokens = int(u.get("output_tokens", 0))
        usage.cache_creation_tokens = int(u.get("cache_creation_input_tokens", 0))
        usage.cache_read_tokens = int(u.get("cache_read_input_tokens", 0))

        # Model actually used (may differ from requested)
        usage.model_used = data.get("model", "")

        return text, usage

    def run(
        self,
        prompt: str,
        model: str = "",
        phase: str = "unknown",
        milestone: int = 0,
        log_file: Path | None = None,
    ) -> ClaudeResult:
        """Run claude CLI with retry logic.

        Uses --output-format json to get exact token counts and costs.
        Writes the text result to log_file.
        Retries on failure with backoff.
        Logs usage to structured event log.
        """
        if is_dry_run():
            self.log.info(f"[DRY RUN] Would invoke Claude for {phase} (M{milestone})")
            dummy_path = log_file or Path("/dev/null")
            return ClaudeResult(
                output="[dry-run]",
                duration_seconds=0.0,
                attempts=0,
                model=model or "default",
                log_file=dummy_path,
            )

        model_args = ["--model", model] if model else []
        cmd = [
            "claude",
            "--dangerously-skip-permissions",
            "--print",
            "--output-format",
            "json",
        ] + model_args

        if model:
            self.log.info(f"Using model: {model}")

        for attempt in range(1, self.max_retries + 1):
            self.log.info(f"Claude subprocess attempt {attempt}/{self.max_retries}")

            start = time.monotonic()
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=self._env,
                )

                assert proc.stdin is not None
                proc.stdin.write(prompt)
                proc.stdin.close()

                assert proc.stdout is not None
                raw_output = proc.stdout.read()
                proc.wait()

                if proc.returncode == 0:
                    duration = time.monotonic() - start
                    text_output, parsed_usage = self._parse_json_response(
                        raw_output
                    )

                    # Write text result to log file
                    if log_file:
                        log_file.parent.mkdir(parents=True, exist_ok=True)
                        log_file.write_text(text_output)

                    resolved_model = (
                        parsed_usage.model_used or model or "default"
                    )

                    self.usage.log_claude_invocation(
                        phase=phase,
                        model=resolved_model,
                        milestone=milestone,
                        input_tokens=parsed_usage.input_tokens,
                        output_tokens=parsed_usage.output_tokens,
                        cache_creation_tokens=parsed_usage.cache_creation_tokens,
                        cache_read_tokens=parsed_usage.cache_read_tokens,
                        cost_usd=parsed_usage.cost_usd,
                        session_id=parsed_usage.session_id,
                        duration_s=duration,
                        duration_api_s=parsed_usage.duration_api_ms / 1000.0,
                        num_turns=parsed_usage.num_turns,
                        attempts=attempt,
                    )

                    # Record cost into pipeline state tracker
                    if self._cost_tracker is not None:
                        self._cost_tracker.record(
                            cost_usd=parsed_usage.cost_usd,
                            milestone=milestone,
                            phase=phase,
                            model=resolved_model,
                            session_id=parsed_usage.session_id,
                            input_tokens=parsed_usage.input_tokens,
                            output_tokens=parsed_usage.output_tokens,
                            cache_creation_tokens=parsed_usage.cache_creation_tokens,
                            cache_read_tokens=parsed_usage.cache_read_tokens,
                        )

                    # Budget guard
                    if (
                        self._budget_usd > 0
                        and self._cost_tracker is not None
                        and self._cost_tracker.total_usd > self._budget_usd
                    ):
                        raise CostBudgetExceeded(
                            f"AI cost budget exceeded: "
                            f"${self._cost_tracker.total_usd:.2f} > "
                            f"${self._budget_usd:.2f} budget"
                        )

                    return ClaudeResult(
                        output=text_output,
                        duration_seconds=duration,
                        attempts=attempt,
                        model=resolved_model,
                        log_file=log_file or Path("/dev/null"),
                        usage=parsed_usage,
                    )
                else:
                    stderr_text = ""
                    if proc.stderr:
                        stderr_text = proc.stderr.read()
                    self.log.warning(
                        f"Claude exited with code {proc.returncode}"
                        + (f": {stderr_text[:200]}" if stderr_text else "")
                    )
            except CostBudgetExceeded:
                raise  # Don't retry — budget exceeded is fatal
            except Exception as e:
                self.log.warning(f"Claude subprocess failed: {e}")

            if attempt < self.max_retries:
                self.log.info(f"Retrying in {self.backoff}s...")
                time.sleep(self.backoff)

        raise ClaudeError(f"Claude subprocess failed after {self.max_retries} attempts")
