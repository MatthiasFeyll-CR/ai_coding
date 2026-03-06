"""ConfiguratorInvoker service tests.

Tests the infrastructure setup flow including backup, validation loop,
auto-fix attempts, and status transitions as specified in the UI handoff doc.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_invoker(app, project, db):
    """Helper: create a ConfiguratorInvoker with app + mock socketio."""
    from services.configurator_invoker import ConfiguratorInvoker

    mock_socketio = MagicMock()
    invoker = ConfiguratorInvoker(project.id, socketio=mock_socketio, app=app)
    # Pre-set project for tests that call internal methods directly
    invoker.project = project
    return invoker


class TestConfiguratorInvokerInit:
    """Test ConfiguratorInvoker construction."""

    def test_default_init(self, app, sample_project_dir):
        """Invoker initialises with project and max 3 fix attempts."""
        from models import Project
        from services.configurator_invoker import ConfiguratorInvoker

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = ConfiguratorInvoker(project.id)
            assert invoker.project_id == project.id
            assert invoker.max_fix_attempts == 3
            assert invoker.setup is None


class TestBackupInfrastructure:
    """Test infrastructure file backup."""

    def test_backs_up_existing_files(self, app, sample_project_dir):
        """_backup_infrastructure should copy existing infra files."""
        from models import InfrastructureBackup, Project
        from services.configurator_invoker import ConfiguratorInvoker

        with app.app_context():
            from database import db

            # Create files to backup
            for f in ["docker-compose.yml", "pipeline-config.json"]:
                with open(os.path.join(sample_project_dir, f), "w") as fh:
                    fh.write(f"# {f}")

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = ConfiguratorInvoker(project.id)
            invoker.project = project
            invoker._backup_infrastructure()

            backup = InfrastructureBackup.query.filter_by(project_id=project.id).first()
            assert backup is not None
            backed_up = json.loads(backup.files_backed_up)
            assert "docker-compose.yml" in backed_up
            assert "pipeline-config.json" in backed_up
            assert Path(backup.backup_path).exists()

    def test_no_files_to_backup(self, app, sample_project_dir):
        """_backup_infrastructure should handle no existing files gracefully."""
        from models import InfrastructureBackup, Project
        from services.configurator_invoker import ConfiguratorInvoker

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = ConfiguratorInvoker(project.id)
            invoker.project = project
            invoker._backup_infrastructure()

            backup = InfrastructureBackup.query.filter_by(project_id=project.id).first()
            assert backup is not None
            backed_up = json.loads(backup.files_backed_up)
            assert backed_up == []


class TestRunSetupFlow:
    """Test the full setup flow with mocked externals."""

    def test_successful_setup_config_created(self, app, sample_project_dir):
        """Setup succeeds when configurator creates config file → status=complete."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            config_path = os.path.join(sample_project_dir, "pipeline-config.json")
            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=config_path,
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = _make_invoker(app, project, db)

            def fake_invoke():
                # Simulate configurator creating the config file
                with open(config_path, "w") as f:
                    json.dump({"milestones": []}, f)
                return True

            with patch.object(invoker, "_backup_infrastructure"):
                with patch.object(
                    invoker, "_invoke_configurator", side_effect=fake_invoke
                ):
                    invoker.run_setup()

            setup = ProjectSetup.query.filter_by(project_id=project.id).first()
            assert setup is not None
            assert setup.status == "complete"
            assert setup.progress == 100
            assert setup.completed_at is not None
            project = db.session.get(Project, project.id)
            assert project.status == "ready"

    def test_successful_setup_via_validation(self, app, sample_project_dir):
        """Setup succeeds via validation when config file not found → status=complete."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = _make_invoker(app, project, db)

            with patch.object(invoker, "_backup_infrastructure"):
                with patch.object(invoker, "_invoke_configurator", return_value=True):
                    with patch.object(
                        invoker,
                        "_validate_environment",
                        return_value={"status": "passed"},
                    ):
                        invoker.run_setup()

            setup = ProjectSetup.query.filter_by(project_id=project.id).first()
            assert setup is not None
            assert setup.status == "complete"
            assert setup.progress == 100
            project = db.session.get(Project, project.id)
            assert project.status == "ready"

    def test_setup_fails_after_max_fix_attempts(self, app, sample_project_dir):
        """Setup fails after 3 fix attempts → status=intervention."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = _make_invoker(app, project, db)

            with patch.object(invoker, "_backup_infrastructure"):
                with patch.object(invoker, "_invoke_configurator", return_value=True):
                    with patch.object(
                        invoker,
                        "_validate_environment",
                        return_value={"status": "failed", "errors": ["bad env"]},
                    ):
                        with patch.object(invoker, "_auto_fix"):
                            invoker.run_setup()

            setup = ProjectSetup.query.filter_by(project_id=project.id).first()
            assert setup is not None
            assert setup.status == "intervention"
            assert setup.current_step == "manual_intervention_required"
            project = db.session.get(Project, project.id)
            assert project.status == "error"

    def test_setup_succeeds_after_one_fix(self, app, sample_project_dir):
        """Setup fails first validation but succeeds on second → status=complete."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = _make_invoker(app, project, db)
            validation_results = [
                {"status": "failed", "errors": ["missing docker"]},
                {"status": "passed"},
            ]

            with patch.object(invoker, "_backup_infrastructure"):
                with patch.object(invoker, "_invoke_configurator", return_value=True):
                    with patch.object(
                        invoker,
                        "_validate_environment",
                        side_effect=validation_results,
                    ):
                        with patch.object(invoker, "_auto_fix"):
                            invoker.run_setup()

            setup = ProjectSetup.query.filter_by(project_id=project.id).first()
            assert setup.status == "complete"
            project = db.session.get(Project, project.id)
            assert project.status == "ready"

    def test_setup_exception_sets_failed(self, app, sample_project_dir):
        """Exception during setup → status=failed, project=error."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = _make_invoker(app, project, db)

            with patch.object(
                invoker,
                "_backup_infrastructure",
                side_effect=Exception("disk full"),
            ):
                invoker.run_setup()

            setup = ProjectSetup.query.filter_by(project_id=project.id).first()
            assert setup.status == "failed"
            project = db.session.get(Project, project.id)
            assert project.status == "error"

    def test_auto_fix_attempts_counter(self, app, sample_project_dir):
        """auto_fix_attempts should increment on each fix attempt."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = _make_invoker(app, project, db)

            with patch.object(invoker, "_backup_infrastructure"):
                with patch.object(invoker, "_invoke_configurator", return_value=True):
                    with patch.object(
                        invoker,
                        "_validate_environment",
                        return_value={"status": "failed"},
                    ):
                        with patch.object(invoker, "_auto_fix"):
                            invoker.run_setup()

            setup = ProjectSetup.query.filter_by(project_id=project.id).first()
            # Should have attempted 2 fixes (max_attempts-1 because last attempt doesn't fix)
            assert setup.auto_fix_attempts == 2

    def test_configurator_failure_stops_setup(self, app, sample_project_dir):
        """When _invoke_configurator returns False, setup should stop with error."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            invoker = _make_invoker(app, project, db)

            with patch.object(invoker, "_backup_infrastructure"):
                with patch.object(invoker, "_invoke_configurator", return_value=False):
                    invoker.run_setup()

            setup = ProjectSetup.query.filter_by(project_id=project.id).first()
            assert setup.status == "failed"
            project = db.session.get(Project, project.id)
            assert project.status == "error"


class TestInvokeConfigurator:
    """Test the _invoke_configurator subprocess call."""

    def _make_mock_popen(self, stdout_lines, returncode=0, stderr_text=""):
        """Create a mock Popen process with line-by-line stdout iteration."""
        mock_proc = MagicMock()
        # readline() returns each line, then "" to signal EOF
        mock_proc.stdout.readline = MagicMock(
            side_effect=[line + "\n" for line in stdout_lines] + [""]
        )
        mock_proc.stdout.close = MagicMock()
        mock_proc.stderr.read = MagicMock(return_value=stderr_text)
        mock_proc.stderr.close = MagicMock()
        mock_proc.wait = MagicMock()
        mock_proc.returncode = returncode
        mock_proc.pid = 12345
        mock_proc.poll = MagicMock(return_value=None)
        return mock_proc

    def test_calls_claude_command(self, app, sample_project_dir):
        """_invoke_configurator should call the claude CLI via Popen."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            setup = ProjectSetup(
                project_id=project.id,
                status="configuring",
                current_step="pipeline_configurator",
            )
            db.session.add(setup)
            db.session.commit()

            invoker = _make_invoker(app, project, db)
            invoker.setup = setup

            # Simulate stream-json output lines
            stdout_lines = [
                json.dumps({"type": "system", "model": "claude-opus-4-6"}),
                json.dumps({"type": "result", "result": "Done", "is_error": False}),
            ]
            mock_proc = self._make_mock_popen(stdout_lines, returncode=0)

            with patch(
                "services.configurator_invoker.subprocess.Popen",
                return_value=mock_proc,
            ) as mock_popen:
                with patch.object(
                    invoker, "_build_env", return_value=os.environ.copy()
                ):
                    result = invoker._invoke_configurator()

                mock_popen.assert_called_once()
                cmd = mock_popen.call_args[0][0]
                assert "claude" in cmd
                assert "-p" in cmd
                assert "--output-format" in cmd
                assert "stream-json" in cmd
                assert result is True

    def test_returns_false_on_failure(self, app, sample_project_dir):
        """_invoke_configurator should return False on non-zero exit."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            setup = ProjectSetup(
                project_id=project.id,
                status="configuring",
                current_step="pipeline_configurator",
            )
            db.session.add(setup)
            db.session.commit()

            invoker = _make_invoker(app, project, db)
            invoker.setup = setup

            stdout_lines = [
                json.dumps({"type": "result", "result": "Error!", "is_error": True}),
            ]
            mock_proc = self._make_mock_popen(
                stdout_lines, returncode=1, stderr_text="Error!"
            )

            with patch(
                "services.configurator_invoker.subprocess.Popen",
                return_value=mock_proc,
            ):
                with patch.object(
                    invoker, "_build_env", return_value=os.environ.copy()
                ):
                    result = invoker._invoke_configurator()
                    assert result is False

    def test_returns_false_on_file_not_found(self, app, sample_project_dir):
        """_invoke_configurator should return False if claude CLI not found."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            setup = ProjectSetup(
                project_id=project.id,
                status="configuring",
                current_step="pipeline_configurator",
            )
            db.session.add(setup)
            db.session.commit()

            invoker = _make_invoker(app, project, db)
            invoker.setup = setup

            with patch(
                "services.configurator_invoker.subprocess.Popen",
                side_effect=FileNotFoundError,
            ):
                with patch.object(
                    invoker, "_build_env", return_value=os.environ.copy()
                ):
                    result = invoker._invoke_configurator()
                    assert result is False

    def test_cancel_stops_reading(self, app, sample_project_dir):
        """_invoke_configurator should stop reading when cancelled."""
        from models import Project, ProjectSetup

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            setup = ProjectSetup(
                project_id=project.id,
                status="configuring",
                current_step="pipeline_configurator",
            )
            db.session.add(setup)
            db.session.commit()

            invoker = _make_invoker(app, project, db)
            invoker.setup = setup

            # Simulate many lines, but cancel after first
            stdout_lines = [
                json.dumps({"type": "system", "model": "claude-opus-4-6"}),
                json.dumps(
                    {"type": "assistant", "message": {"content": [{"text": "Hello"}]}}
                ),
            ]
            mock_proc = self._make_mock_popen(stdout_lines, returncode=0)

            def set_cancelled_on_second_read():
                """After first readline, set _cancelled to True."""
                calls = mock_proc.stdout.readline.call_count
                if calls >= 1:
                    invoker._cancelled = True

            orig_readline = mock_proc.stdout.readline.side_effect
            call_idx = [0]

            def readline_with_cancel():
                if call_idx[0] < len(stdout_lines):
                    result = stdout_lines[call_idx[0]] + "\n"
                    call_idx[0] += 1
                    if call_idx[0] >= 1:
                        invoker._cancelled = True
                    return result
                return ""

            mock_proc.stdout.readline = MagicMock(side_effect=readline_with_cancel)
            mock_proc.poll = MagicMock(return_value=None)

            with patch(
                "services.configurator_invoker.subprocess.Popen",
                return_value=mock_proc,
            ):
                with patch.object(
                    invoker, "_build_env", return_value=os.environ.copy()
                ):
                    result = invoker._invoke_configurator()
                    assert result is False  # cancelled → returns False


class TestValidateEnvironment:
    """Test _validate_environment subprocess call."""

    def test_returns_validation_result(self, app, sample_project_dir):
        """_validate_environment should return parsed JSON result."""
        from models import Project, ProjectSetup
        from services.configurator_invoker import ConfiguratorInvoker

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            setup = ProjectSetup(
                project_id=project.id,
                status="validating",
                current_step="test_environment_validation",
            )
            db.session.add(setup)
            db.session.commit()

            invoker = ConfiguratorInvoker(project.id)
            invoker.project = project
            invoker.setup = setup

            validation_output = {"status": "passed", "checks": []}
            with patch("services.configurator_invoker.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=json.dumps(validation_output),
                    stderr="",
                )

                result = invoker._validate_environment()

            assert result["status"] == "passed"

    def test_returns_failed_on_invalid_json(self, app, sample_project_dir):
        """_validate_environment should return failed status on JSON parse error."""
        from models import Project, ProjectSetup
        from services.configurator_invoker import ConfiguratorInvoker

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="configuring",
            )
            db.session.add(project)
            db.session.commit()

            setup = ProjectSetup(
                project_id=project.id,
                status="validating",
                current_step="test_environment_validation",
            )
            db.session.add(setup)
            db.session.commit()

            invoker = ConfiguratorInvoker(project.id)
            invoker.project = project
            invoker.setup = setup

            with patch("services.configurator_invoker.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stdout="not json",
                    stderr="",
                )

                result = invoker._validate_environment()

            assert result["status"] == "failed"
