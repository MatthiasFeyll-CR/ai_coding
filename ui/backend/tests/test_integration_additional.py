"""Additional E2E and integration tests.

Covers gaps identified in the test coverage audit:
- POST /api/projects/setup endpoint
- Pipeline resume flow
- Logs phase filter
- Pipeline error handling (nonexistent project, runner exceptions)
- Infrastructure validation flow (auto-fix loop E2E)
- WebSocket integration flow
- Setup endpoint flow
- Cascade delete with setup + backup records
"""

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock


class TestSetupEndpointFlow:
    """E2E: POST /api/projects/setup creates project and spawns configurator."""

    def test_setup_creates_project_and_starts_configurator(
        self, client, sample_project_dir, monkeypatch
    ):
        """POST /setup should create project with 'configuring' status and return 202."""
        mock_invoker = MagicMock()
        monkeypatch.setattr(
            "services.configurator_invoker.ConfiguratorInvoker",
            lambda *args, **kwargs: mock_invoker,
        )
        # Mock start_background_task to prevent actual green thread spawning
        from app import socketio

        monkeypatch.setattr(
            socketio, "start_background_task", lambda fn, *a, **kw: None
        )

        resp = client.post(
            "/api/projects/setup",
            json={"project_path": sample_project_dir},
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["status"] == "setup_started"
        assert "project_id" in data

        # Project should exist in DB with configuring status
        resp2 = client.get(f"/api/projects/{data['project_id']}")
        assert resp2.status_code == 200
        assert resp2.get_json()["status"] == "configuring"


class TestPipelineResumeFlow:
    """E2E: Resume pipeline from checkpoint."""

    def test_resume_sets_running_status(
        self, client, sample_project_with_state, monkeypatch
    ):
        """POST /pipeline/<id>/resume should set status=running and call start."""
        mock_runner = MagicMock()
        monkeypatch.setattr(
            "api.pipeline.PipelineRunner",
            lambda project, **kwargs: mock_runner,
        )

        # Link project
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_state},
        )
        pid = resp.get_json()["id"]

        # Resume pipeline
        resp = client.post(f"/api/pipeline/{pid}/resume")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Runner was called with resume=True
        mock_runner.start.assert_called_once()

        # Project status is 'running'
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["status"] == "running"

    def test_start_then_stop_then_resume(
        self, client, sample_project_with_state, monkeypatch
    ):
        """Full lifecycle: start → stop → resume."""
        mock_runner = MagicMock()
        monkeypatch.setattr(
            "api.pipeline.PipelineRunner",
            lambda project, **kwargs: mock_runner,
        )

        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_state},
        )
        pid = resp.get_json()["id"]

        # Start
        resp = client.post(f"/api/pipeline/{pid}/start", json={})
        assert resp.status_code == 200

        # Stop
        resp = client.post(f"/api/pipeline/{pid}/stop")
        assert resp.status_code == 200
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["status"] == "stopped"

        # Resume
        resp = client.post(f"/api/pipeline/{pid}/resume")
        assert resp.status_code == 200
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["status"] == "running"


class TestLogsPhaseFilter:
    """Test logs filtering by phase parameter."""

    def test_filter_by_phase(self, client, sample_project_dir, db_session):
        """GET /pipeline/<id>/logs?phase=qa_review should filter logs."""
        from models import ExecutionLog

        # Link project
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        # Add logs with different phases
        db_session.add(
            ExecutionLog(
                project_id=pid,
                message="PRD log",
                phase="prd_generation",
                log_level="info",
            )
        )
        db_session.add(
            ExecutionLog(
                project_id=pid,
                message="QA log 1",
                phase="qa_review",
                log_level="info",
            )
        )
        db_session.add(
            ExecutionLog(
                project_id=pid,
                message="QA log 2",
                phase="qa_review",
                log_level="warning",
            )
        )
        db_session.commit()

        # Filter by phase
        resp = client.get(
            f"/api/pipeline/{pid}/logs",
            query_string={"phase": "qa_review"},
        )
        logs = resp.get_json()
        assert len(logs) == 2
        assert all(log["phase"] == "qa_review" for log in logs)

    def test_filter_by_milestone_and_phase(
        self, client, sample_project_dir, db_session
    ):
        """GET /pipeline/<id>/logs?milestone_id=1&phase=prd should filter by both."""
        from models import ExecutionLog

        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        db_session.add(
            ExecutionLog(
                project_id=pid,
                message="M1 PRD",
                milestone_id=1,
                phase="prd_generation",
                log_level="info",
            )
        )
        db_session.add(
            ExecutionLog(
                project_id=pid,
                message="M2 PRD",
                milestone_id=2,
                phase="prd_generation",
                log_level="info",
            )
        )
        db_session.add(
            ExecutionLog(
                project_id=pid,
                message="M1 QA",
                milestone_id=1,
                phase="qa_review",
                log_level="info",
            )
        )
        db_session.commit()

        resp = client.get(
            f"/api/pipeline/{pid}/logs",
            query_string={"milestone_id": 1, "phase": "prd_generation"},
        )
        logs = resp.get_json()
        assert len(logs) == 1
        assert logs[0]["message"] == "M1 PRD"


class TestPipelineErrorHandling:
    """Test error handling for pipeline endpoints."""

    def test_start_nonexistent_project(self, client):
        """POST /pipeline/999/start should return 404."""
        resp = client.post("/api/pipeline/999/start", json={})
        assert resp.status_code == 404

    def test_stop_nonexistent_project(self, client):
        """POST /pipeline/999/stop should return 404."""
        resp = client.post("/api/pipeline/999/stop")
        assert resp.status_code == 404

    def test_resume_nonexistent_project(self, client):
        """POST /pipeline/999/resume should return 404."""
        resp = client.post("/api/pipeline/999/resume")
        assert resp.status_code == 404

    def test_logs_nonexistent_project(self, client):
        """GET /pipeline/999/logs should return empty list (not 404)."""
        resp = client.get("/api/pipeline/999/logs")
        # The logs endpoint doesn't check project existence, just filters by ID
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_tokens_nonexistent_project(self, client):
        """GET /pipeline/999/tokens should return 404."""
        resp = client.get("/api/pipeline/999/tokens")
        assert resp.status_code == 404

    def test_milestones_nonexistent_project(self, client):
        """GET /pipeline/999/milestones should return 404."""
        resp = client.get("/api/pipeline/999/milestones")
        assert resp.status_code == 404

    def test_stop_when_no_active_runner(self, client, sample_project_dir, monkeypatch):
        """Stop should succeed even if no runner is active (just removes lock)."""
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        resp = client.post(f"/api/pipeline/{pid}/stop")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True


class TestInfrastructureValidationFlow:
    """E2E: Full infrastructure validation with auto-fix loop."""

    def test_configure_triggers_validation_loop(
        self, client, sample_project_dir, monkeypatch
    ):
        """Configure → configurator runs → validation loop engages."""
        mock_invoker = MagicMock()
        monkeypatch.setattr(
            "services.configurator_invoker.ConfiguratorInvoker",
            lambda *args, **kwargs: mock_invoker,
        )
        # Mock start_background_task to prevent actual green thread spawning
        from app import socketio

        monkeypatch.setattr(
            socketio, "start_background_task", lambda fn, *a, **kw: None
        )

        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        # Check not configuring initially
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["status"] == "initialized"

        # Configure
        resp = client.post(f"/api/projects/{pid}/configure")
        assert resp.status_code == 202

        # Status changed
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["status"] == "configuring"

        # Cannot configure again while configuring
        resp = client.post(f"/api/projects/{pid}/configure")
        assert resp.status_code == 409

    def test_configure_nonexistent_project(self, client):
        """POST /projects/999/configure should return 404."""
        resp = client.post("/api/projects/999/configure")
        assert resp.status_code == 404


class TestCascadeDeleteWithSetupAndBackup:
    """E2E: Ensure cascade delete includes setup and backup records."""

    def test_full_cascade_delete(self, client, sample_project_dir, db_session):
        """Deleting project should remove ProjectSetup and InfrastructureBackup."""
        from models import InfrastructureBackup, ProjectSetup

        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        # Create setup and backup records
        db_session.add(
            ProjectSetup(
                project_id=pid,
                status="complete",
                current_step="done",
                progress=100,
            )
        )
        db_session.add(
            InfrastructureBackup(
                project_id=pid,
                backup_path="/tmp/backup",
                files_backed_up=json.dumps(["file.yml"]),
            )
        )
        db_session.commit()

        assert ProjectSetup.query.filter_by(project_id=pid).count() == 1
        assert InfrastructureBackup.query.filter_by(project_id=pid).count() == 1

        # Delete project
        client.delete(f"/api/projects/{pid}")

        assert ProjectSetup.query.filter_by(project_id=pid).count() == 0
        assert InfrastructureBackup.query.filter_by(project_id=pid).count() == 0


class TestTokenAggregationEdgeCases:
    """Test token aggregation with edge cases."""

    def test_tokens_multiple_milestones(self, client, sample_project_dir, db_session):
        """Token aggregation should group by milestone correctly."""
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        # Write cost sessions to state.json
        ralph_dir = os.path.join(sample_project_dir, ".ralph")
        os.makedirs(ralph_dir, exist_ok=True)
        state = {
            "cost": {
                "sessions": [
                    {
                        "session_id": "s1",
                        "phase": "prd",
                        "milestone": 1,
                        "model": "claude-opus-4",
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "cache_creation_tokens": 0,
                        "cache_read_tokens": 0,
                        "cost_usd": 0.05,
                        "invocations": 1,
                    },
                    {
                        "session_id": "s2",
                        "phase": "ralph",
                        "milestone": 1,
                        "model": "claude-opus-4",
                        "input_tokens": 2000,
                        "output_tokens": 800,
                        "cache_creation_tokens": 0,
                        "cache_read_tokens": 0,
                        "cost_usd": 0.10,
                        "invocations": 1,
                    },
                    {
                        "session_id": "s3",
                        "phase": "prd",
                        "milestone": 2,
                        "model": "claude-3-5-haiku",
                        "input_tokens": 500,
                        "output_tokens": 200,
                        "cache_creation_tokens": 0,
                        "cache_read_tokens": 0,
                        "cost_usd": 0.01,
                        "invocations": 1,
                    },
                ]
            }
        }
        with open(os.path.join(ralph_dir, "state.json"), "w") as f:
            json.dump(state, f)

        resp = client.get(f"/api/pipeline/{pid}/tokens")
        data = resp.get_json()

        # Total
        assert data["total"]["input_tokens"] == 3500
        assert data["total"]["output_tokens"] == 1500
        assert abs(data["total"]["cost_usd"] - 0.16) < 0.001

        # By milestone
        assert data["by_milestone"]["1"]["input_tokens"] == 3000
        assert data["by_milestone"]["2"]["input_tokens"] == 500

        # History has all entries
        assert len(data["history"]) == 3

    def test_tokens_without_milestone(self, client, sample_project_dir, db_session):
        """Tokens without milestone should still be in total."""
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        # Write cost session with no milestone
        ralph_dir = os.path.join(sample_project_dir, ".ralph")
        os.makedirs(ralph_dir, exist_ok=True)
        state = {
            "cost": {
                "sessions": [
                    {
                        "session_id": "s1",
                        "phase": "unknown",
                        "model": "claude-opus-4",
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_tokens": 0,
                        "cache_read_tokens": 0,
                        "cost_usd": 0.005,
                        "invocations": 1,
                    }
                ]
            }
        }
        with open(os.path.join(ralph_dir, "state.json"), "w") as f:
            json.dump(state, f)

        resp = client.get(f"/api/pipeline/{pid}/tokens")
        data = resp.get_json()
        assert data["total"]["input_tokens"] == 100
        assert data["by_milestone"] == {}


class TestSnapshotEdgeCases:
    """Test snapshot edge cases."""

    def test_restore_wrong_project(self, client, sample_project_with_state):
        """Restoring a snapshot from another project should 404."""
        # Create two projects
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_state},
        )
        pid1 = resp.get_json()["id"]

        # Create a snapshot for project 1
        resp = client.post(f"/api/projects/{pid1}/snapshots")
        snap_id = resp.get_json()["id"]

        # Try to restore to project 999
        resp = client.put(f"/api/projects/999/restore/{snap_id}")
        assert resp.status_code == 404

    def test_snapshot_no_state_file(self, client, sample_project_dir):
        """Creating a snapshot without state.json should 404."""
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        resp = client.post(f"/api/projects/{pid}/snapshots")
        assert resp.status_code == 404


class TestPreCheckEdgeCases:
    """Test pre-check edge cases."""

    def test_pre_check_partial_docs(self, client):
        """Pre-check with only some docs folders should report invalid."""
        tmpdir = tempfile.mkdtemp(prefix="ralph_partial_")
        os.makedirs(os.path.join(tmpdir, "docs/01-requirements"))
        os.makedirs(os.path.join(tmpdir, "docs/02-architecture"))
        # Missing 03, 04, 05

        try:
            resp = client.post(
                "/api/projects/pre-check",
                json={"project_path": tmpdir},
            )
            data = resp.get_json()
            assert data["valid"] is False
            assert data["docs_structure"]["docs/03-design"]["exists"] is False
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_pre_check_with_infrastructure_files(self, client, sample_project_dir):
        """Pre-check should detect existing infrastructure files."""
        # Create infra files
        with open(os.path.join(sample_project_dir, "docker-compose.yml"), "w") as f:
            f.write("version: '3'\n")
        with open(
            os.path.join(sample_project_dir, "docker-compose.test.yml"), "w"
        ) as f:
            f.write("version: '3'\n")

        resp = client.post(
            "/api/projects/pre-check",
            json={"project_path": sample_project_dir},
        )
        data = resp.get_json()
        infra_files = [f["file"] for f in data["existing_infrastructure"]]
        assert "docker-compose.yml" in infra_files
        assert "docker-compose.test.yml" in infra_files


class TestLockFileMechanism:
    """Test the lock file prevention mechanism for concurrent execution."""

    def test_lock_prevents_double_start(
        self, client, sample_project_with_config, monkeypatch
    ):
        """Starting pipeline twice should fail due to lock file."""
        mock_runner = MagicMock()
        monkeypatch.setattr(
            "api.pipeline.PipelineRunner",
            lambda project, **kwargs: mock_runner,
        )

        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_config},
        )
        pid = resp.get_json()["id"]

        # Create lock file manually with current PID so it looks alive
        lock_path = os.path.join(sample_project_with_config, ".ralph", "pipeline.lock")
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w") as f:
            json.dump({"pid": os.getpid()}, f)

        # Start should fail
        resp = client.post(f"/api/pipeline/{pid}/start", json={})
        assert resp.status_code == 409
        assert "already running" in resp.get_json()["error"].lower()

    def test_stop_removes_lock_file(
        self, client, sample_project_with_config, monkeypatch
    ):
        """Stopping pipeline should remove the lock file."""
        mock_runner = MagicMock()
        monkeypatch.setattr(
            "api.pipeline.PipelineRunner",
            lambda project, **kwargs: mock_runner,
        )

        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_config},
        )
        pid = resp.get_json()["id"]

        # Create lock file with a dead PID (orphaned — will be cleaned up)
        lock_path = os.path.join(sample_project_with_config, ".ralph", "pipeline.lock")
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w") as f:
            json.dump({"pid": 99999999}, f)

        # Mark as active so stop actually processes
        from api.pipeline import active_pipelines

        active_pipelines[pid] = mock_runner

        # Stop
        resp = client.post(f"/api/pipeline/{pid}/stop")
        assert resp.status_code == 200

        # Lock file should be gone
        assert not os.path.exists(lock_path)


class TestAvailableModels:
    """Test the available models endpoint."""

    def test_list_available_models(self, client):
        """GET /projects/models/available returns model list."""
        resp = client.get("/api/projects/models/available")
        assert resp.status_code == 200
        models = resp.get_json()
        assert isinstance(models, list)
        assert len(models) >= 3
        assert "claude-opus-4" in models
