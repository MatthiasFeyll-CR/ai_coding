"""Pipeline execution service."""

import json
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from database import db
from models import ExecutionLog


class PipelineRunner:
    """Manages pipeline execution as a subprocess."""

    def __init__(self, project, milestone_id=None, resume=False):
        self.project = project
        self.milestone_id = milestone_id
        self.resume = resume
        self.process = None
        self.thread = None
        self.running = False

    def start(self):
        """Start pipeline in background thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run_pipeline)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """Stop the pipeline."""
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def _run_pipeline(self):
        """Run pipeline subprocess and stream output."""
        # Create lock file
        lock_path = Path(self.project.root_path) / ".ralph" / "pipeline.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        lock_data = {
            "pid": os.getpid(),
            "started_at": datetime.utcnow().isoformat(),
            "project_id": self.project.id,
            "source": "ui",
        }

        with open(lock_path, "w") as f:
            json.dump(lock_data, f)

        try:
            # Build command
            cmd = [
                "ralph-pipeline",
                "run",
                "--config",
                self.project.config_path,
            ]

            if self.resume:
                cmd.append("--resume")
            elif self.milestone_id:
                cmd.extend(["--milestone", str(self.milestone_id)])

            # Run subprocess
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self.project.root_path,
            )

            # Stream output
            for line in self.process.stdout:
                if not self.running:
                    break

                # Log to database
                log = ExecutionLog(
                    project_id=self.project.id,
                    message=line.strip(),
                    log_level="info",
                )
                db.session.add(log)
                db.session.commit()

                # Emit via WebSocket
                from api.websocket import emit_log
                from app import socketio

                emit_log(
                    socketio,
                    self.project.id,
                    {
                        "project_id": self.project.id,
                        "message": line.strip(),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            # Wait for completion
            self.process.wait()

            # Update project status
            if self.process.returncode == 0:
                self.project.status = "success"
            else:
                self.project.status = "error"

            self.project.last_run_at = datetime.utcnow()
            db.session.commit()

        finally:
            # Remove lock file
            if lock_path.exists():
                lock_path.unlink()

            self.running = False
