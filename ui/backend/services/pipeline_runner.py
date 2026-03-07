"""Pipeline execution service."""

import subprocess
import threading
from datetime import datetime, timezone

from database import db
from models import ExecutionLog, Project


class PipelineRunner:
    """Manages pipeline execution as a subprocess.

    Lock file management is handled by the ``ralph-pipeline`` CLI itself.
    This service only spawns the subprocess and streams its output.
    """

    def __init__(self, project, milestone_id=None, resume=False):
        # Eagerly capture scalar values while the ORM object is still
        # bound to a session so they can be used safely in a background thread.
        self.project_id = project.id
        self.root_path = project.root_path
        self.config_path = project.config_path
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
        from app import app

        try:
            # Build command
            cmd = [
                "ralph-pipeline",
                "run",
                "--config",
                self.config_path,
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
                cwd=self.root_path,
            )

            # Stream output — use an app context so db.session works
            with app.app_context():
                for line in self.process.stdout:
                    if not self.running:
                        break

                    # Log to database
                    log = ExecutionLog(
                        project_id=self.project_id,
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
                        self.project_id,
                        {
                            "project_id": self.project_id,
                            "message": line.strip(),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                # Wait for completion
                self.process.wait()

                # Update project status
                project = db.session.get(Project, self.project_id)
                if project:
                    if self.process.returncode == 0:
                        project.status = "success"
                    else:
                        project.status = "error"
                    project.last_run_at = datetime.now(timezone.utc)
                    db.session.commit()

        finally:
            self.running = False
