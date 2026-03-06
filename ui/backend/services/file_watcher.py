"""File system watcher for .ralph/ changes."""

import json
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class RalphFileHandler(FileSystemEventHandler):
    """Handler for .ralph/ file changes."""

    def __init__(self, project_id, socketio):
        self.project_id = project_id
        self.socketio = socketio
        self.last_state_emit = 0
        self.debounce_interval = 0.1  # 100ms

    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Debounce rapid changes
        now = time.time()
        if now - self.last_state_emit < self.debounce_interval:
            return

        # Handle state.json changes
        if file_path.name == "state.json":
            self._emit_state_change(file_path)
            self.last_state_emit = now

        # Handle progress.txt changes
        elif file_path.name == "progress.txt":
            self._emit_progress_update(file_path)

        # Handle pipeline.jsonl log changes
        elif file_path.name == "pipeline.jsonl":
            self._emit_new_logs(file_path)

    def _emit_state_change(self, state_path):
        """Emit state change event."""
        try:
            with open(state_path, "r") as f:
                state = json.load(f)

            from api.websocket import emit_state_change

            emit_state_change(
                self.socketio,
                self.project_id,
                {"project_id": self.project_id, "state": state},
            )
        except Exception as e:
            print(f"Error emitting state change: {e}")

    def _emit_progress_update(self, progress_path):
        """Emit progress update."""
        try:
            with open(progress_path, "r") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()

                    from api.websocket import emit_log

                    emit_log(
                        self.socketio,
                        self.project_id,
                        {
                            "project_id": self.project_id,
                            "message": last_line,
                            "timestamp": time.time(),
                        },
                    )
        except Exception as e:
            print(f"Error emitting progress: {e}")

    def _emit_new_logs(self, log_path):
        """Emit new log entries."""
        # Parse JSONL and emit new entries
        pass


class FileWatcher:
    """Watches .ralph/ directory for changes."""

    def __init__(self, project, socketio):
        self.project = project
        self.socketio = socketio
        self.observer = None

    def start(self):
        """Start watching."""
        ralph_path = Path(self.project.root_path) / ".ralph"
        ralph_path.mkdir(parents=True, exist_ok=True)

        handler = RalphFileHandler(self.project.id, self.socketio)
        self.observer = Observer()
        self.observer.schedule(handler, str(ralph_path), recursive=True)
        self.observer.start()

    def stop(self):
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
