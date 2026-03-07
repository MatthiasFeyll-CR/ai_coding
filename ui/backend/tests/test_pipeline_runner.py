"""PipelineRunner service tests.

Tests the PipelineRunner class including lock file management,
subprocess lifecycle, log streaming, and status updates.
"""

import os
from unittest.mock import MagicMock, patch


class TestPipelineRunnerInit:
    """Test PipelineRunner construction."""

    def test_default_init(self, app, sample_project_with_config):
        """Runner initialises with correct defaults."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)
            assert runner.project_id == project.id
            assert runner.milestone_id is None
            assert runner.resume is False
            assert runner.process is None
            assert runner.thread is None
            assert runner.running is False

    def test_init_with_milestone(self, app, sample_project_with_config):
        """Runner accepts milestone_id parameter."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project, milestone_id=2)
            assert runner.milestone_id == 2

    def test_init_with_resume(self, app, sample_project_with_config):
        """Runner accepts resume parameter."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project, resume=True)
            assert runner.resume is True


class TestPipelineRunnerStart:
    """Test start() spawns a daemon thread."""

    def test_start_creates_thread(self, app, sample_project_with_config):
        """start() should create and start a daemon thread."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)

            with patch.object(runner, "_run_pipeline"):
                runner.start()
                assert runner.running is True
                assert runner.thread is not None
                assert runner.thread.daemon is True
                runner.thread.join(timeout=1)


class TestPipelineRunnerStop:
    """Test stop() terminates the subprocess."""

    def test_stop_sets_running_false(self, app, sample_project_with_config):
        """stop() should set running to False."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)
            runner.running = True
            runner.process = None  # no subprocess to terminate

            runner.stop()
            assert runner.running is False

    def test_stop_terminates_process(self, app, sample_project_with_config):
        """stop() should call terminate on the subprocess."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)
            runner.running = True
            mock_proc = MagicMock()
            runner.process = mock_proc

            runner.stop()

            mock_proc.terminate.assert_called_once()
            mock_proc.wait.assert_called_once_with(timeout=5)

    def test_stop_kills_on_timeout(self, app, sample_project_with_config):
        """stop() should kill the process if terminate times out."""
        import subprocess

        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)
            runner.running = True
            mock_proc = MagicMock()
            mock_proc.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
            runner.process = mock_proc

            runner.stop()

            mock_proc.kill.assert_called_once()


class TestPipelineRunnerRunPipeline:
    """Test _run_pipeline() subprocess management."""

    def test_spawns_subprocess(self, app, sample_project_with_config):
        """_run_pipeline should spawn a subprocess."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)

            # Mock subprocess to avoid actually running
            with patch("services.pipeline_runner.subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.stdout = []  # no output
                mock_proc.returncode = 0
                mock_proc.wait.return_value = 0
                mock_popen.return_value = mock_proc

                runner._run_pipeline()

            mock_popen.assert_called_once()

    def test_builds_command_with_resume(self, app, sample_project_with_config):
        """_run_pipeline should add --resume flag when resume=True."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project, resume=True)

            with patch("services.pipeline_runner.subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.stdout = []
                mock_proc.returncode = 0
                mock_popen.return_value = mock_proc

                runner._run_pipeline()

                call_args = mock_popen.call_args
                cmd = call_args[0][0]
                assert "--resume" in cmd

    def test_builds_command_with_milestone(self, app, sample_project_with_config):
        """_run_pipeline should add --milestone flag when milestone_id is set."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project, milestone_id=3)

            with patch("services.pipeline_runner.subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.stdout = []
                mock_proc.returncode = 0
                mock_popen.return_value = mock_proc

                runner._run_pipeline()

                call_args = mock_popen.call_args
                cmd = call_args[0][0]
                assert "--milestone" in cmd
                assert "3" in cmd

    def test_sets_success_status_on_zero_exit(self, app, sample_project_with_config):
        """Project status should be 'success' when subprocess returns 0."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="running",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)

            with patch("services.pipeline_runner.subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.stdout = []
                mock_proc.returncode = 0
                mock_popen.return_value = mock_proc

                runner._run_pipeline()

            db.session.refresh(project)
            assert project.status == "success"

    def test_sets_error_status_on_nonzero_exit(self, app, sample_project_with_config):
        """Project status should be 'error' when subprocess returns non-zero."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="running",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)

            with patch("services.pipeline_runner.subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.stdout = []
                mock_proc.returncode = 1
                mock_popen.return_value = mock_proc

                runner._run_pipeline()

            db.session.refresh(project)
            assert project.status == "error"

    def test_handles_exception_gracefully(self, app, sample_project_with_config):
        """Runner should set running=False even if an exception occurs."""
        from models import Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="running",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)

            with patch("services.pipeline_runner.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = OSError("cannot start process")

                try:
                    runner._run_pipeline()
                except OSError:
                    pass

            assert runner.running is False

    def test_logs_output_to_database(self, app, sample_project_with_config):
        """Each line of subprocess output should be logged to the database."""
        from models import ExecutionLog, Project
        from services.pipeline_runner import PipelineRunner

        with app.app_context():
            from database import db

            project = Project(
                name="test",
                root_path=sample_project_with_config,
                config_path=os.path.join(
                    sample_project_with_config, "pipeline-config.json"
                ),
                status="running",
            )
            db.session.add(project)
            db.session.commit()

            runner = PipelineRunner(project)
            runner.running = True  # Needed for the output loop

            with patch("services.pipeline_runner.subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.stdout = iter(["Line 1\n", "Line 2\n", "Line 3\n"])
                mock_proc.returncode = 0
                mock_proc.wait.return_value = 0
                mock_popen.return_value = mock_proc

                # Mock the lazy WebSocket imports inside the for loop
                mock_socketio = MagicMock()
                with patch("api.websocket.emit_log"):
                    with patch("app.socketio", mock_socketio):
                        runner._run_pipeline()

            logs = ExecutionLog.query.filter_by(project_id=project.id).all()
            assert len(logs) == 3
            messages = {log.message for log in logs}
            assert "Line 1" in messages
            assert "Line 2" in messages
            assert "Line 3" in messages
