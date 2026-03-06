"""Single choke point for all subprocess calls."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level dry-run flag — set by the CLI before any execution begins.
_dry_run: bool = False


class SubprocessError(Exception):
    """Raised when a subprocess call fails."""

    def __init__(
        self, message: str, cmd: str | list[str], exit_code: int, output: str = ""
    ):
        super().__init__(message)
        self.cmd = cmd
        self.exit_code = exit_code
        self.output = output


def set_dry_run(enabled: bool) -> None:
    """Set the global dry-run mode for all subprocess calls."""
    global _dry_run
    _dry_run = enabled


def is_dry_run() -> bool:
    return _dry_run


def run_command(
    cmd: str | list[str],
    cwd: Path,
    timeout: int = 300,
    capture: bool = True,
    stream_to: Optional[Path] = None,
    env: Optional[dict] = None,
    check: bool = True,
    shell: bool = False,
) -> subprocess.CompletedProcess:
    """Single choke point for all subprocess calls.

    - Supports dry-run mode (log command, don't execute)
    - Logs command + duration
    - Streams output to file if stream_to is set
    - Raises SubprocessError with structured info on failure when check=True
    """
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)

    if _dry_run:
        logger.info("[DRY RUN] Would run: %s (cwd=%s)", cmd_str, cwd)
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="[dry-run]", stderr=""
        )

    logger.debug("Running: %s (cwd=%s, timeout=%ds)", cmd_str, cwd, timeout)
    start = time.monotonic()

    try:
        if stream_to:
            stream_to.parent.mkdir(parents=True, exist_ok=True)
            with open(stream_to, "w") as f:
                result = subprocess.run(
                    cmd,
                    cwd=str(cwd),
                    timeout=timeout if timeout > 0 else None,
                    capture_output=False,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    shell=shell if isinstance(cmd, str) else False,
                )
            # Re-read the output for the result
            result.stdout = stream_to.read_text()
            result.stderr = ""
        elif capture:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                timeout=timeout if timeout > 0 else None,
                capture_output=True,
                text=True,
                env=env,
                shell=shell if isinstance(cmd, str) else False,
            )
        else:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                timeout=timeout if timeout > 0 else None,
                text=True,
                env=env,
                shell=shell if isinstance(cmd, str) else False,
            )
    except subprocess.TimeoutExpired as e:
        duration = time.monotonic() - start
        logger.warning("Command timed out after %.1fs: %s", duration, cmd_str)
        raise SubprocessError(
            f"Command timed out after {timeout}s: {cmd_str}",
            cmd=cmd,
            exit_code=124,
            output=str(e.stdout or ""),
        ) from e

    duration = time.monotonic() - start
    logger.debug(
        "Command completed in %.1fs (exit=%d): %s", duration, result.returncode, cmd_str
    )

    if check and result.returncode != 0:
        raise SubprocessError(
            f"Command failed (exit={result.returncode}): {cmd_str}",
            cmd=cmd,
            exit_code=result.returncode,
            output=result.stdout or result.stderr or "",
        )

    return result
