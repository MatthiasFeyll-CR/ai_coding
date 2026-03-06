"""Claude subprocess wrapper — retry logic, streaming, usage logging."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ralph_pipeline.config import RetryConfig
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import is_dry_run
from ralph_pipeline.usage import EventLogger


class ClaudeError(Exception):
    """Raised when Claude subprocess fails after all retries."""

    pass


@dataclass
class ClaudeResult:
    output: str
    duration_seconds: float
    attempts: int
    model: str
    log_file: Path


class ClaudeRunner:
    """Runs claude --dangerously-skip-permissions --print with retry logic."""

    def __init__(
        self,
        retry_config: RetryConfig,
        usage_logger: EventLogger,
        logger: PipelineLogger,
    ):
        self.max_retries = retry_config.max_retries
        self.backoff = retry_config.backoff_seconds
        self.usage = usage_logger
        self.log = logger

    def run(
        self,
        prompt: str,
        model: str = "",
        phase: str = "unknown",
        milestone: int = 0,
        log_file: Path | None = None,
    ) -> ClaudeResult:
        """Run claude CLI with retry logic.

        Streams stdout to log_file in real time.
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
        cmd = ["claude", "--dangerously-skip-permissions", "--print"] + model_args

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
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                assert proc.stdin is not None
                proc.stdin.write(prompt)
                proc.stdin.close()

                output_lines: list[str] = []
                log_fh = None
                try:
                    if log_file:
                        log_file.parent.mkdir(parents=True, exist_ok=True)
                        log_fh = open(log_file, "w")

                    assert proc.stdout is not None
                    for line in proc.stdout:
                        if log_fh:
                            log_fh.write(line)
                            log_fh.flush()
                        output_lines.append(line)
                finally:
                    if log_fh:
                        log_fh.close()

                proc.wait()
                output = "".join(output_lines)

                if proc.returncode == 0:
                    duration = time.monotonic() - start
                    self.usage.log_claude_invocation(
                        phase=phase,
                        model=model or "default",
                        milestone=milestone,
                        input_chars=len(prompt),
                        output_chars=len(output),
                        duration_s=duration,
                        attempts=attempt,
                    )
                    return ClaudeResult(
                        output=output,
                        duration_seconds=duration,
                        attempts=attempt,
                        model=model or "default",
                        log_file=log_file or Path("/dev/null"),
                    )
                else:
                    self.log.warning(f"Claude exited with code {proc.returncode}")
            except Exception as e:
                self.log.warning(f"Claude subprocess failed: {e}")

            if attempt < self.max_retries:
                self.log.info(f"Retrying in {self.backoff}s...")
                time.sleep(self.backoff)

        raise ClaudeError(f"Claude subprocess failed after {self.max_retries} attempts")
