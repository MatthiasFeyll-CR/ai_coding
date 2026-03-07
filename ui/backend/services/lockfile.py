"""Lock file utilities for the UI backend.

Mirrors the logic in ``ralph_pipeline.lockfile`` but is a standalone
module so the UI backend does not depend on the CLI package at runtime.
"""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from typing import Optional


def _lock_path(project_root: str | Path) -> Path:
    return Path(project_root) / ".ralph" / "pipeline.lock"


def is_pid_alive(pid: int) -> bool:
    """Return True if *pid* refers to a running process."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_lock(project_root: str | Path) -> Optional[dict]:
    """Read the lock file and return its contents, or *None*."""
    lp = _lock_path(project_root)
    if not lp.exists():
        return None
    try:
        return json.loads(lp.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def is_pipeline_running(project_root: str | Path) -> tuple[bool, Optional[dict]]:
    """Check whether a pipeline process is alive.

    Returns ``(alive, lock_data)``.
    """
    data = read_lock(project_root)
    if data is None:
        return False, None
    pid = data.get("pid")
    if pid is None or not is_pid_alive(int(pid)):
        return False, None
    return True, data


def kill_pipeline(project_root: str | Path) -> bool:
    """Send SIGTERM to the PID in the lock file.

    Returns True if a signal was sent.  Removes the lock file afterwards.
    """
    running, data = is_pipeline_running(project_root)
    if not running:
        release_lock(project_root)
        return False
    pid = int(data["pid"])  # type: ignore[index]
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    # Note: the lock file is removed by the pipeline process's signal/atexit
    # handler.  We give it a moment, but do NOT force-delete it ourselves so
    # the process can shut down cleanly.  If the caller needs to ensure the
    # lock is gone they can poll is_pipeline_running().
    return True


def release_lock(project_root: str | Path) -> None:
    """Remove the lock file if it exists."""
    lp = _lock_path(project_root)
    try:
        lp.unlink()
    except FileNotFoundError:
        pass
