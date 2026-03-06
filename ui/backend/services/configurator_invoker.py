"""Service to invoke pipeline configurator."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from database import db
from models import InfrastructureBackup, ProjectSetup


class ConfiguratorInvoker:
    """Invokes pipeline configurator and handles validation loop."""

    def __init__(self, project):
        self.project = project
        self.setup = None
        self.max_fix_attempts = 3

    def run_setup(self):
        """Run the full setup process."""
        try:
            # Create setup record
            self.setup = ProjectSetup(
                project_id=self.project.id,
                status="checking",
                current_step="pre-check",
                progress=10,
            )
            db.session.add(self.setup)
            db.session.commit()

            # Step 1: Backup existing files
            self._backup_infrastructure()

            # Step 2: Invoke configurator
            self.setup.status = "configuring"
            self.setup.current_step = "pipeline_configurator"
            self.setup.progress = 30
            db.session.commit()

            self._invoke_configurator()

            # Step 3: Validate
            self.setup.status = "validating"
            self.setup.current_step = "test_environment_validation"
            self.setup.progress = 60
            db.session.commit()

            for attempt in range(self.max_fix_attempts):
                validation_result = self._validate_environment()

                if validation_result.get("status") == "passed":
                    # Success!
                    self.setup.status = "complete"
                    self.setup.progress = 100
                    self.setup.completed_at = datetime.utcnow()
                    self.project.status = "ready"
                    db.session.commit()
                    return

                # Auto-fix
                if attempt < self.max_fix_attempts - 1:
                    self.setup.status = "fixing"
                    self.setup.auto_fix_attempts = attempt + 1
                    db.session.commit()

                    self._auto_fix(validation_result)

            # Failed after max attempts
            self.setup.status = "intervention"
            self.setup.current_step = "manual_intervention_required"
            self.setup.progress = 80
            self.project.status = "error"
            db.session.commit()

        except Exception as e:
            if self.setup:
                self.setup.status = "failed"
            self.project.status = "error"
            db.session.commit()
            print(f"Setup failed: {e}")

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
        """Invoke pipeline configurator skill."""
        cmd = [
            "claude",
            "/pipeline_configurator",
            "--project",
            self.project.root_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project.root_path,
        )

        self.setup.configurator_output = result.stdout
        db.session.commit()

        if result.returncode != 0:
            raise Exception(f"Configurator failed: {result.stderr}")

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
