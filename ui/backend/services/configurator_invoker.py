"""Service to invoke pipeline configurator via Claude Code CLI."""

import json
import logging
import os
import shutil
import signal
import subprocess
from datetime import datetime
from pathlib import Path

from database import db
from dotenv import dotenv_values
from models import InfrastructureBackup, Project, ProjectSetup

log = logging.getLogger("ralph-ui.configurator")

# The prompt sent to Claude to invoke the pipeline_configurator skill
CONFIGURATOR_PROMPT = """\
/pipeline_configurator You are the Pipeline Configurator specialist. Run the pipeline configurator \
skill for this project.

The project is located at: {project_path}

Your task:
1. Generate pipeline-config.json in the project root with milestone \
definitions, gate checks, and paths.
2. Create .ralph/CLAUDE.md with agent instructions tailored to this project.
3. Validate that the generated config is parseable by ralph-pipeline.
4. You are not able to ask questions as this is an automated process. If you feel really unsure about something interrupt the session.

Work directly in the project directory. Create all files needed.
"""

# Registry of active invokers keyed by project_id — used for cancel support
_active_invokers: dict[int, "ConfiguratorInvoker"] = {}


def cancel_configurator(project_id: int) -> bool:
    """Cancel a running configurator for the given project.

    Returns True if a process was cancelled, False if nothing was running.
    """
    invoker = _active_invokers.get(project_id)
    if invoker is None:
        return False
    invoker.cancel()
    return True


class ConfiguratorInvoker:
    """Invokes pipeline configurator via Claude Code CLI and streams output."""

    def __init__(self, project_id, socketio=None, app=None):
        self.project_id = project_id
        self.project = None  # loaded inside app context
        self.socketio = socketio
        self.app = app
        self.setup = None
        self.max_fix_attempts = 3
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self):
        """Signal the running Claude process to terminate."""
        self._cancelled = True
        proc = self._process
        if proc and proc.poll() is None:
            log.info("Cancelling Claude process PID %d", proc.pid)
            try:
                proc.send_signal(signal.SIGTERM)
            except OSError:
                pass

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

        _active_invokers[self.project_id] = self
        try:
            if has_app_context():
                self._run_setup_inner()
            else:
                with self.app.app_context():
                    self._run_setup_inner()
        except Exception as e:
            self._emit("error", "error", f"Setup failed: {e}")
            log.exception("Setup failed for project %d", self.project_id)
        finally:
            _active_invokers.pop(self.project_id, None)

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

    # All env vars required for Azure AI Foundry Claude Code CLI
    _CLAUDE_ENV_KEYS = (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
    )

    def _build_env(self):
        """Build environment dict for Claude CLI subprocess.

        Loads all Azure AI Foundry env vars from the .env file and injects
        them into the subprocess env, overriding any stale shell values.
        """
        env = os.environ.copy()

        # Load .env values explicitly (dotenv_values doesn't touch os.environ)
        dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if dotenv_path.exists():
            dot_vals = dotenv_values(dotenv_path)
            for key in self._CLAUDE_ENV_KEYS:
                if dot_vals.get(key):
                    env[key] = dot_vals[key]

        return env

    def _invoke_configurator(self):
        """Invoke Claude Code CLI and stream output line-by-line.

        Uses ``--output-format stream-json --verbose`` so each stdout line
        is a JSON object that we can parse and relay to the frontend in
        near-real-time via WebSocket.

        Returns True on success, False on failure.
        """
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

        collected_text: list[str] = []
        is_error = False

        try:
            env = self._build_env()

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self.project.root_path,
                env=env,
            )

            log.info("Claude process started (PID %d)", self._process.pid)
            self._emit(
                "configurator",
                "running",
                f"Claude process started (PID {self._process.pid})",
                msg_type="info",
            )

            # Read stdout line-by-line — each line is a JSON object
            for line in iter(self._process.stdout.readline, ""):
                if self._cancelled:
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    # Plain text fallback
                    self._emit("configurator", "running", line, msg_type="output")
                    collected_text.append(line)
                    continue

                self._handle_stream_chunk(chunk, collected_text)

                # Detect terminal error in result
                if chunk.get("type") == "result" and chunk.get("is_error"):
                    is_error = True

            self._process.stdout.close()
            self._process.wait()
            return_code = self._process.returncode

            stderr_output = ""
            if self._process.stderr:
                stderr_output = self._process.stderr.read()
                self._process.stderr.close()

            log.info(
                "Claude process finished (rc=%s, cancelled=%s)",
                return_code,
                self._cancelled,
            )

        except FileNotFoundError:
            self._emit(
                "configurator",
                "error",
                "Claude CLI not found. Install it with: npm install -g @anthropic-ai/claude-code",
            )
            return False
        except Exception as e:
            self._emit("configurator", "error", f"Failed to run Claude: {e}")
            log.exception("Claude invocation failed")
            return False
        finally:
            self._process = None

        # Store collected output
        full_output = "\n".join(collected_text)
        if self.setup:
            self.setup.configurator_output = full_output
            db.session.commit()

        # Handle cancellation
        if self._cancelled:
            self._emit(
                "configurator",
                "error",
                "Configuration cancelled by user",
                msg_type="error",
            )
            return False

        if return_code != 0 or is_error:
            error_detail = full_output[-500:] or stderr_output[:500]
            self._emit(
                "configurator",
                "error",
                f"Claude failed: {error_detail}",
                msg_type="error",
            )
            return False

        return True

    def _handle_stream_chunk(self, chunk: dict, collected: list[str]):
        """Parse one stream-json line and emit appropriate WS events."""
        chunk_type = chunk.get("type", "")

        if chunk_type == "assistant":
            message = chunk.get("message", {})
            content = message.get("content", []) if isinstance(message, dict) else []
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text", "")
                    if text:
                        self._emit(
                            "configurator",
                            "running",
                            text,
                            msg_type="assistant",
                        )
                        collected.append(text)
                    # Tool use blocks
                    tool_name = block.get("name", "")
                    if block.get("type") == "tool_use" and tool_name:
                        tool_input = block.get("input", {})
                        summary = f"Tool: {tool_name}"
                        if isinstance(tool_input, dict):
                            # Show a short summary of the tool input
                            snippet = json.dumps(tool_input, indent=2)
                            if len(snippet) > 300:
                                snippet = snippet[:300] + "…"
                            summary += f"\n{snippet}"
                        self._emit(
                            "configurator",
                            "running",
                            summary,
                            msg_type="tool_use",
                        )
            elif isinstance(content, str) and content:
                self._emit(
                    "configurator",
                    "running",
                    content,
                    msg_type="assistant",
                )
                collected.append(content)

        elif chunk_type == "content_block_delta":
            delta = chunk.get("delta", {})
            text = delta.get("text", "")
            if text:
                self._emit(
                    "configurator",
                    "running",
                    text,
                    msg_type="assistant_delta",
                )
                collected.append(text)

        elif chunk_type == "result":
            result_text = chunk.get("result", "")
            result_is_error = chunk.get("is_error", False)
            if result_text:
                msg_type = "error" if result_is_error else "result"
                status = "error" if result_is_error else "running"
                self._emit(
                    "configurator",
                    status,
                    result_text,
                    msg_type=msg_type,
                )
                collected.append(result_text)

        elif chunk_type == "system":
            # System init — emit as info
            model = chunk.get("model", "")
            if model:
                self._emit(
                    "configurator",
                    "running",
                    f"Model: {model}",
                    msg_type="info",
                )

        else:
            # Other event types — relay text if present
            msg = chunk.get("message", "") or chunk.get("text", "")
            if isinstance(msg, str) and msg:
                self._emit(
                    "configurator",
                    "running",
                    msg,
                    msg_type="info",
                )

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
