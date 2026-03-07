"""Pipeline lock file management.

The lock file (`<project_root>/.ralph/pipeline.lock`) prevents concurrent
pipeline executions on the same project.  It stores the PID and metadata
so that any observer (UI, another CLI invocation, …) can determine whether
a pipeline process is still alive.
"""

from __future__ import annotations

import json
import os
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class LockfileError(RuntimeError):
    """Raised when a live pipeline process already holds the lock."""


def _lock_path(project_root: Path) -> Path:
    return project_root / ".ralph" / "pipeline.lock"


def _is_pid_alive(pid: int) -> bool:
    """Return True if *pid* refers to a running process."""
    try:
        os.kill(pid, 0)  # signal 0 = existence check, no signal sent
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't own it — still alive.
        return True


def read_lock(project_root: Path) -> Optional[dict]:
    """Read and return the lock file contents, or *None* if absent."""
    lp = _lock_path(project_root)
    if not lp.exists():
        return None
    try:
        return json.loads(lp.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def is_pipeline_running(project_root: Path) -> tuple[bool, Optional[dict]]:
    """Check whether a pipeline process is alive for *project_root*.

    Returns ``(alive, lock_data)``.  If the lock file exists but the
    PID is dead the file is considered orphaned and ``(False, None)``
    is returned.
    """
    data = read_lock(project_root)
    if data is None:
        return False, None
    pid = data.get("pid")
    if pid is None or not _is_pid_alive(int(pid)):
        return False, None
    return True, data


def acquire(project_root: Path, *, source: str = "cli") -> Path:
    """Create the lock file.  Raises `LockfileError` if already held.

    The lock contains:
    * ``pid``         – current process PID
    * ``started_at``  – ISO-8601 UTC timestamp
    * ``source``      – ``"cli"`` or ``"ui"``
    """
    running, data = is_pipeline_running(project_root)
    if running:
        pid = data["pid"]  # type: ignore[index]
        raise LockfileError(
            f"Another pipeline process is already running (PID {pid}). "
            "Stop it first or wait for it to finish."
        )

    lp = _lock_path(project_root)
    lp.parent.mkdir(parents=True, exist_ok=True)

    lock_data = {
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
    }
    lp.write_text(json.dumps(lock_data, indent=2))
    return lp


def release(project_root: Path) -> None:
    """Remove the lock file if it exists."""
    lp = _lock_path(project_root)
    try:
        lp.unlink()
    except FileNotFoundError:
        pass


def kill_holder(project_root: Path) -> bool:
    """Send SIGTERM to the PID in the lock file.

    Returns True if a signal was sent, False if no live process was found.
    Removes the lock file afterwards.
    """
    running, data = is_pipeline_running(project_root)
    if not running:
        # Orphaned or missing — just clean up.
        release(project_root)
        return False

    pid = int(data["pid"])  # type: ignore[index]
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    release(project_root)
    return True
