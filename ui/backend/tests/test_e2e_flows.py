"""End-to-end flow tests.

Tests complete user journeys from project linking through pipeline execution,
snapshot management, and configuration — exercising the full API surface
as a real frontend client would.
"""

import json
import os
import shutil
import tempfile



class TestLinkToDashboardFlow:
    """
    E2E: Link project → verify it appears in list → fetch dashboard data.
    Simulates: User opens app, links project, sees it in sidebar, clicks it.
    """

    def test_full_link_flow(self, client, sample_project_dir):
        # 1. No projects initially
        resp = client.get("/api/projects")
        assert resp.get_json() == []

        # 2. Link project
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        assert resp.status_code == 201
        project = resp.get_json()
        pid = project["id"]
        assert project["is_setup"] is False
        assert project["status"] == "initialized"

        # 3. Project appears in list
        resp = client.get("/api/projects")
        projects = resp.get_json()
        assert len(projects) == 1
        assert projects[0]["id"] == pid

        # 4. Can fetch project details
        resp = client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == os.path.basename(sample_project_dir)

        # 5. Pre-check returns docs info
        resp = client.post(
            "/api/projects/pre-check",
            json={"project_path": sample_project_dir},
        )
        pre_check = resp.get_json()
        assert pre_check["valid"] is True

        # 6. No state file yet
        resp = client.get(f"/api/projects/{pid}/state")
        assert resp.status_code == 404

        # 7. File tree is readable
        resp = client.get(f"/api/files/{pid}/tree")
        assert resp.status_code == 200
        tree = resp.get_json()
        assert tree["type"] == "directory"

    def test_link_then_configure_flow(self, client, sample_project_dir, monkeypatch):
        """
        Link → not set up → configure → status changes.
        """
        from unittest.mock import MagicMock

        mock_invoker = MagicMock()
        monkeypatch.setattr(
            "services.configurator_invoker.ConfiguratorInvoker",
            lambda project: mock_invoker,
        )

        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        project = resp.get_json()
        assert project["is_setup"] is False

        # Trigger configure
        resp = client.post(f"/api/projects/{project['id']}/configure")
        assert resp.status_code == 202
        assert resp.get_json()["status"] == "configuring"

        # Status is now configuring
        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.get_json()["status"] == "configuring"


class TestSetupToExecutionFlow:
    """
    E2E: Project with config → start pipeline → check logs/tokens → stop.
    """

    def test_pipeline_lifecycle(self, client, sample_project_with_state, monkeypatch):
        from unittest.mock import MagicMock

        mock_runner = MagicMock()
        monkeypatch.setattr(
            "api.pipeline.PipelineRunner",
            lambda project, **kwargs: mock_runner,
        )

        # Link project with config + state
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_state},
        )
        project = resp.get_json()
        pid = project["id"]
        assert project["is_setup"] is True

        # Start pipeline
        resp = client.post(f"/api/pipeline/{pid}/start", json={})
        assert resp.status_code == 200
        mock_runner.start.assert_called_once()

        # Get milestones
        resp = client.get(f"/api/pipeline/{pid}/milestones")
        assert resp.status_code == 200
        milestones = resp.get_json()
        assert len(milestones) == 2

        # Get state
        resp = client.get(f"/api/projects/{pid}/state")
        assert resp.status_code == 200
        assert resp.get_json()["current_milestone"] == 1

        # Get tokens (empty initially)
        resp = client.get(f"/api/pipeline/{pid}/tokens")
        assert resp.get_json()["total"]["input_tokens"] == 0

        # Get logs (empty initially)
        resp = client.get(f"/api/pipeline/{pid}/logs")
        assert resp.get_json() == []

        # Stop pipeline
        resp = client.post(f"/api/pipeline/{pid}/stop")
        assert resp.status_code == 200

        # Status is paused
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["status"] == "paused"


class TestSnapshotRestoreFlow:
    """
    E2E: Create snapshot → modify state → restore → verify original state.
    """

    def test_snapshot_round_trip(self, client, sample_project_with_state):
        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_state},
        )
        pid = resp.get_json()["id"]

        # Take snapshot
        resp = client.post(f"/api/projects/{pid}/snapshots")
        assert resp.status_code == 201
        snap = resp.get_json()
        snap_id = snap["id"]

        # Verify original state
        original_state = json.loads(snap["state_json"])
        assert original_state["current_phase"] == "prd_generation"

        # Modify state on disk
        state_path = os.path.join(sample_project_with_state, ".ralph", "state.json")
        with open(state_path, "w") as f:
            json.dump({"current_phase": "destroyed", "modified": True}, f)

        # Verify modification took
        resp = client.get(f"/api/projects/{pid}/state")
        assert resp.get_json()["current_phase"] == "destroyed"

        # Restore from snapshot
        resp = client.put(f"/api/projects/{pid}/restore/{snap_id}")
        assert resp.status_code == 200

        # Verify restore
        resp = client.get(f"/api/projects/{pid}/state")
        restored = resp.get_json()
        assert restored["current_phase"] == "prd_generation"
        assert "modified" not in restored


class TestModelConfigFlow:
    """
    E2E: Set model config → read back → update → read back.
    """

    def test_model_config_lifecycle(self, client, sample_project_dir):
        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        # Initially empty
        resp = client.get(f"/api/projects/{pid}/models")
        assert resp.get_json() == {}

        # Set models
        resp = client.put(
            f"/api/projects/{pid}/models",
            json={
                "prd": "claude-opus-4",
                "qa": "claude-3-5-sonnet-20241022",
                "ralph": "claude-3-5-haiku",
            },
        )
        assert resp.status_code == 200

        # Read back
        resp = client.get(f"/api/projects/{pid}/models")
        models = resp.get_json()
        assert models["prd"] == "claude-opus-4"
        assert models["qa"] == "claude-3-5-sonnet-20241022"
        assert models["ralph"] == "claude-3-5-haiku"

        # Update one model
        resp = client.put(
            f"/api/projects/{pid}/models",
            json={"prd": "claude-3-5-haiku"},
        )
        assert resp.status_code == 200

        # Verify only prd changed
        resp = client.get(f"/api/projects/{pid}/models")
        models = resp.get_json()
        assert models["prd"] == "claude-3-5-haiku"
        assert models["qa"] == "claude-3-5-sonnet-20241022"


class TestMultiProjectFlow:
    """
    E2E: Multiple projects coexist. Logs, tokens, models are per-project.
    """

    def test_data_isolation(self, client, db_session):
        from models import ExecutionLog, TokenUsage

        dirs = []
        pids = []
        for i in range(2):
            d = tempfile.mkdtemp(prefix=f"ralph_multi_{i}_")
            os.makedirs(os.path.join(d, "docs/01-requirements"), exist_ok=True)
            with open(os.path.join(d, "README.md"), "w") as f:
                f.write(f"# Project {i}\n")
            dirs.append(d)

            resp = client.post("/api/projects", json={"project_path": d})
            pids.append(resp.get_json()["id"])

        # Add logs to project 0 only
        for i in range(3):
            db_session.add(
                ExecutionLog(
                    project_id=pids[0],
                    message=f"p0-log-{i}",
                    log_level="info",
                )
            )
        db_session.add(
            ExecutionLog(
                project_id=pids[1],
                message="p1-log",
                log_level="info",
            )
        )
        db_session.commit()

        # Project 0's logs
        resp = client.get(f"/api/pipeline/{pids[0]}/logs")
        assert len(resp.get_json()) == 3

        # Project 1's logs
        resp = client.get(f"/api/pipeline/{pids[1]}/logs")
        assert len(resp.get_json()) == 1

        # Add tokens to project 1
        db_session.add(
            TokenUsage(
                project_id=pids[1],
                model="claude-opus-4",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.05,
            )
        )
        db_session.commit()

        # Project 0 has no tokens
        resp = client.get(f"/api/pipeline/{pids[0]}/tokens")
        assert resp.get_json()["total"]["input_tokens"] == 0

        # Project 1 has tokens
        resp = client.get(f"/api/pipeline/{pids[1]}/tokens")
        assert resp.get_json()["total"]["input_tokens"] == 1000

        # Deleting project 0 doesn't affect project 1
        client.delete(f"/api/projects/{pids[0]}")
        resp = client.get(f"/api/pipeline/{pids[1]}/logs")
        assert len(resp.get_json()) == 1

        # Cleanup
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)


class TestFileExplorerFlow:
    """E2E: Browse project files and read content."""

    def test_browse_and_read(self, client, sample_project_dir):
        # Create some nested files
        src_dir = os.path.join(sample_project_dir, "src")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "main.py"), "w") as f:
            f.write("print('hello')\n")

        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        pid = resp.get_json()["id"]

        # Get tree
        resp = client.get(f"/api/files/{pid}/tree")
        tree = resp.get_json()
        assert tree["type"] == "directory"

        # Find src in children
        src_node = next(
            (c for c in tree["children"] if c["name"] == "src"), None
        )
        assert src_node is not None
        assert src_node["type"] == "directory"

        # Read file
        resp = client.get(
            f"/api/files/{pid}/read",
            query_string={"path": "src/main.py"},
        )
        assert resp.status_code == 200
        assert "print('hello')" in resp.get_json()["content"]


class TestProjectDeletionCascade:
    """E2E: Deleting a project removes all associated data."""

    def test_cascade(self, client, sample_project_with_state, db_session):
        from models import ExecutionLog, StateSnapshot, TokenUsage

        # Link
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_state},
        )
        pid = resp.get_json()["id"]

        # Create some data
        client.post(f"/api/projects/{pid}/snapshots")
        db_session.add(
            ExecutionLog(project_id=pid, message="test", log_level="info")
        )
        db_session.add(
            TokenUsage(
                project_id=pid,
                model="claude-opus-4",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.01,
            )
        )
        db_session.commit()

        # Verify data exists
        assert StateSnapshot.query.filter_by(project_id=pid).count() == 1
        assert ExecutionLog.query.filter_by(project_id=pid).count() == 1
        assert TokenUsage.query.filter_by(project_id=pid).count() == 1

        # Delete project
        resp = client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 200

        # All associated data is gone
        assert StateSnapshot.query.filter_by(project_id=pid).count() == 0
        assert ExecutionLog.query.filter_by(project_id=pid).count() == 0
        assert TokenUsage.query.filter_by(project_id=pid).count() == 0


class TestIsSetupDynamicFlow:
    """
    E2E: is_setup reflects real disk state, not just DB status.
    """

    def test_is_setup_changes_with_disk(self, client, sample_project_dir):
        # Link — no config, not set up
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        project = resp.get_json()
        pid = project["id"]
        assert project["is_setup"] is False

        # Create pipeline-config.json on disk
        config_path = os.path.join(sample_project_dir, "pipeline-config.json")
        with open(config_path, "w") as f:
            json.dump({"test": True}, f)

        # Re-fetch — now is_setup should be True
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["is_setup"] is True

        # Delete config from disk
        os.unlink(config_path)

        # Re-fetch — back to False
        resp = client.get(f"/api/projects/{pid}")
        assert resp.get_json()["is_setup"] is False


class TestHealthAndRequirementsFlow:
    """E2E: Check health, then system requirements."""

    def test_full_health_flow(self, client):
        # Health check
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

        # Run requirements check
        resp = client.post("/api/requirements/check")
        assert resp.status_code == 200
        checks = resp.get_json()["checks"]
        check_names = [c["name"] for c in checks]
        assert "python" in check_names
        assert "git" in check_names

        # Get cached status
        resp = client.get("/api/requirements/status")
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 5
