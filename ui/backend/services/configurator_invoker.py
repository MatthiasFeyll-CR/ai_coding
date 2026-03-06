"""Service to invoke pipeline configurator via Claude Code CLI."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from database import db
from models import InfrastructureBackup, Project, ProjectSetup

# The prompt sent to Claude to invoke the pipeline_configurator skill
CONFIGURATOR_PROMPT = """\
/pipeline_configurator You are the Pipeline Configurator specialist. Run the pipeline configurator \
skill for this project.

The project is located at: {project_path}

Your task:
1. Read the project's docs/ folder structure (docs/01-requirements, \
docs/02-architecture, docs/03-design, docs/04-test-architecture, \
docs/05-milestones).
2. Generate pipeline-config.json in the project root with milestone \
definitions, gate checks, and paths.
3. Create .ralph/CLAUDE.md with agent instructions tailored to this project.
4. Validate that the generated config is parseable by ralph-pipeline.

Work directly in the project directory. Create all files needed.
"""


class ConfiguratorInvoker:
    """Invokes pipeline configurator via Claude Code CLI and streams output."""

    def __init__(self, project_id, socketio=None, app=None):
        self.project_id = project_id
        self.project = None  # loaded inside app context
        self.socketio = socketio
        self.app = app
        self.setup = None
        self.max_fix_attempts = 3

    def _emit(self, step, status, message, msg_type="progress"):
        """Emit a setup_progress event via WebSocket."""
        data = {
            "step": step,
            "status": status,
            "message": message,
            "type": msg_type,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if self.socketio:
            self.socketio.emit(
                "setup_progress",
                data,
                room=f"project_{self.project_id}",
            )

    def run_setup(self):
        """Run the full setup process."""
        from flask import has_app_context

        try:
            if has_app_context():
                self._run_setup_inner()
            else:
                with self.app.app_context():
                    self._run_setup_inner()
        except Exception as e:
            self._emit("error", "error", f"Setup failed: {e}")
            print(f"Setup failed: {e}")

    def _run_setup_inner(self):
        """Inner setup logic (runs inside app context)."""
        # Re-query project inside this thread's app context
        self.project = db.session.get(Project, self.project_id)
        if not self.project:
            self._emit("error", "error", f"Project {self.project_id} not found")
            return

        try:
            # Create setup record
            self.setup = ProjectSetup(
                project_id=self.project_id,
                status="checking",
                current_step="pre-check",
                progress=10,
            )
            db.session.add(self.setup)
            db.session.commit()

            self._emit("pre-check", "running", "Starting pre-check…")

            # Step 1: Backup existing files
            self._backup_infrastructure()
            self._emit("backup", "running", "Backed up existing infrastructure files")

            # Step 2: Invoke configurator via Claude CLI
            self.setup.status = "configuring"
            self.setup.current_step = "pipeline_configurator"
            self.setup.progress = 30
            db.session.commit()

            self._emit(
                "configurator", "running", "Spawning Claude Code for configuration…"
            )
            success = self._invoke_configurator()

            if not success:
                self.setup.status = "failed"
                self.project.status = "error"
                db.session.commit()
                self._emit("configurator", "error", "Claude configurator failed")
                return

            # Step 3: Validate
            self.setup.status = "validating"
            self.setup.current_step = "validation"
            self.setup.progress = 70
            db.session.commit()
            self._emit("validation", "running", "Validating generated configuration…")

            # Check if pipeline-config.json was created
            config_path = Path(self.project.config_path)
            if config_path.exists():
                self.setup.status = "complete"
                self.setup.progress = 100
                self.setup.completed_at = datetime.utcnow()
                self.project.status = "ready"
                db.session.commit()
                self._emit(
                    "complete",
                    "complete",
                    "Pipeline configuration generated successfully!",
                )
                return

            # Config not created — try validation loop
            for attempt in range(self.max_fix_attempts):
                validation_result = self._validate_environment()

                if validation_result.get("status") == "passed":
                    self.setup.status = "complete"
                    self.setup.progress = 100
                    self.setup.completed_at = datetime.utcnow()
                    self.project.status = "ready"
                    db.session.commit()
                    self._emit("complete", "complete", "Configuration complete!")
                    return

                if attempt < self.max_fix_attempts - 1:
                    self.setup.status = "fixing"
                    self.setup.auto_fix_attempts = attempt + 1
                    db.session.commit()
                    self._emit(
                        "fix",
                        "running",
                        f"Auto-fix attempt {attempt + 1}/{self.max_fix_attempts - 1}…",
                    )
                    self._auto_fix(validation_result)

            # Failed after max attempts
            self.setup.status = "intervention"
            self.setup.current_step = "manual_intervention_required"
            self.setup.progress = 80
            self.project.status = "error"
            db.session.commit()
            self._emit(
                "intervention",
                "error",
                "Configuration needs manual intervention",
            )
        except Exception:
            # Handle exceptions while still inside app context
            if self.setup:
                self.setup.status = "failed"
            self.project.status = "error"
            db.session.commit()
            raise

    def _backup_infrastructure(self):
        """Backup existing docker-compose files."""
        project_path = Path(self.project.root_path)
        backup_dir = (
            project_path
            / ".ralph"
            / "backup"
            / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        backup_dir.mkdir(parents=True, exist_ok=True)

        files_to_backup = [
            "docker-compose.yml",
            "docker-compose.test.yml",
            "pipeline-config.json",
        ]

        backed_up = []
        for file in files_to_backup:
            src = project_path / file
            if src.exists():
                dst = backup_dir / file
                shutil.copy2(src, dst)
                backed_up.append(file)

        backup = InfrastructureBackup(
            project_id=self.project.id,
            backup_path=str(backup_dir),
            files_backed_up=json.dumps(backed_up),
        )
        db.session.add(backup)
        db.session.commit()

    def _invoke_configurator(self):
        """Invoke Claude Code CLI.

        Uses simple subprocess.run for maximum compatibility.
        Returns True on success, False on failure.
        """
        import os

        prompt = CONFIGURATOR_PROMPT.format(project_path=self.project.root_path)

        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]

        self._emit(
            "configurator",
            "running",
            "Running Claude CLI (this may take a few minutes)...",
            msg_type="info",
        )

        try:
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                cwd=self.project.root_path,
                start_new_session=True,
                env=os.environ.copy(),
                timeout=600,  # 10 minute timeout
            )

            # Store output
            if self.setup:
                self.setup.configurator_output = result.stdout[:50000]
                db.session.commit()

            if result.returncode != 0:
                self._emit(
                    "configurator",
                    "error",
                    f"Claude exited with code {result.returncode}: {result.stderr[:500]}",
                )
                return False

            self._emit(
                "configurator",
                "running",
                "Claude CLI completed successfully",
                msg_type="info",
            )
            return True

        except FileNotFoundError:
            self._emit(
                "configurator",
                "error",
                "Claude CLI not found. Install it with: npm install -g @anthropic-ai/claude-code",
            )
            return False
        except subprocess.TimeoutExpired:
            self._emit(
                "configurator",
                "error",
                "Claude CLI timed out after 10 minutes",
            )
            return False
        except Exception as e:
            self._emit("configurator", "error", f"Failed to run Claude: {e}")
            return False

    def _validate_environment(self):
        """Run validation command."""
        cmd = [
            "ralph-pipeline",
            "validate-test-env",
            "--config",
            self.project.config_path,
            "--output",
            "json",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            validation_result = json.loads(result.stdout)
            self.setup.validation_report = json.dumps(validation_result)
            db.session.commit()

            return validation_result
        except (json.JSONDecodeError, Exception) as e:
            return {
                "status": "failed",
                "error": str(e),
            }

    def _auto_fix(self, validation_result):
        """Attempt to auto-fix validation errors."""
        # Re-invoke configurator with validation context
        self._invoke_configurator()
