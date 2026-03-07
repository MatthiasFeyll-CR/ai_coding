"""Integration tests for the Pipeline API.

Tests pipeline control, logs, tokens, and milestones endpoints.
"""

import json
import os


class TestStartPipeline:
    """POST /api/pipeline/<id>/start"""

    def test_start_pipeline_no_lock(self, client, linked_project_with_config, monkeypatch):
        from unittest.mock import MagicMock

        mock_runner = MagicMock()
        monkeypatch.setattr(
            "api.pipeline.PipelineRunner",
            lambda project, **kwargs: mock_runner,
        )

        pid = linked_project_with_config["id"]
        resp = client.post(f"/api/pipeline/{pid}/start", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        mock_runner.start.assert_called_once()

    def test_start_pipeline_with_lock(self, client, linked_project_with_config, monkeypatch):
        """If lock file exists with a live PID, start should return 409."""
        project_path = linked_project_with_config["root_path"]
        lock_path = os.path.join(project_path, ".ralph", "pipeline.lock")
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        # Use current PID so is_pid_alive returns True
        with open(lock_path, "w") as f:
            json.dump({"pid": os.getpid()}, f)

        pid = linked_project_with_config["id"]
        resp = client.post(f"/api/pipeline/{pid}/start", json={})
        assert resp.status_code == 409

        os.unlink(lock_path)

    def test_start_with_milestone_id(self, client, linked_project_with_config, monkeypatch):

        captured_kwargs = {}

        class MockRunner:
            def __init__(self, project, **kwargs):
                captured_kwargs.update(kwargs)

            def start(self):
                pass

        monkeypatch.setattr("api.pipeline.PipelineRunner", MockRunner)

        pid = linked_project_with_config["id"]
        resp = client.post(
            f"/api/pipeline/{pid}/start",
            json={"milestone_id": 3},
        )
        assert resp.status_code == 200
        assert captured_kwargs.get("milestone_id") == 3


class TestStopPipeline:
    """POST /api/pipeline/<id>/stop"""

    def test_stop_pipeline(self, client, linked_project):
        pid = linked_project["id"]
        resp = client.post(f"/api/pipeline/{pid}/stop")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Verify status changes to stopped
        project = client.get(f"/api/projects/{pid}").get_json()
        assert project["status"] == "stopped"

    def test_stop_removes_lock(self, client, linked_project):
        project_path = linked_project["root_path"]
        lock_path = os.path.join(project_path, ".ralph", "pipeline.lock")
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w") as f:
            f.write("locked")

        pid = linked_project["id"]
        client.post(f"/api/pipeline/{pid}/stop")
        assert not os.path.exists(lock_path)


class TestResumePipeline:
    """POST /api/pipeline/<id>/resume"""

    def test_resume(self, client, linked_project, monkeypatch):

        captured = {}

        class MockRunner:
            def __init__(self, project, **kwargs):
                captured["resume"] = kwargs.get("resume")

            def start(self):
                pass

        monkeypatch.setattr("api.pipeline.PipelineRunner", MockRunner)

        pid = linked_project["id"]
        resp = client.post(f"/api/pipeline/{pid}/resume")
        assert resp.status_code == 200
        assert captured["resume"] is True


class TestGetLogs:
    """GET /api/pipeline/<id>/logs"""

    def test_get_logs_empty(self, client, linked_project):
        resp = client.get(f"/api/pipeline/{linked_project['id']}/logs")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_get_logs_with_data(self, client, linked_project, db_session):
        from models import ExecutionLog

        pid = linked_project["id"]
        for i in range(5):
            db_session.add(
                ExecutionLog(
                    project_id=pid,
                    milestone_id=1,
                    phase="prd",
                    log_level="info",
                    message=f"Log {i}",
                )
            )
        db_session.commit()

        resp = client.get(f"/api/pipeline/{pid}/logs")
        assert len(resp.get_json()) == 5

    def test_get_logs_filtered_by_milestone(self, client, linked_project, db_session):
        from models import ExecutionLog

        pid = linked_project["id"]
        for m_id in [1, 1, 2]:
            db_session.add(
                ExecutionLog(
                    project_id=pid,
                    milestone_id=m_id,
                    message=f"M{m_id}",
                    log_level="info",
                )
            )
        db_session.commit()

        resp = client.get(f"/api/pipeline/{pid}/logs?milestone_id=1")
        assert len(resp.get_json()) == 2

    def test_get_logs_limit(self, client, linked_project, db_session):
        from models import ExecutionLog

        pid = linked_project["id"]
        for i in range(10):
            db_session.add(
                ExecutionLog(project_id=pid, message=f"Log {i}", log_level="info")
            )
        db_session.commit()

        resp = client.get(f"/api/pipeline/{pid}/logs?limit=3")
        assert len(resp.get_json()) == 3


class TestGetTokens:
    """GET /api/pipeline/<id>/tokens"""

    def test_tokens_empty(self, client, linked_project):
        resp = client.get(f"/api/pipeline/{linked_project['id']}/tokens")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"]["input_tokens"] == 0
        assert data["total"]["cost_usd"] == 0.0

    def test_tokens_aggregation(self, client, linked_project, db_session):
        from models import TokenUsage

        pid = linked_project["id"]
        db_session.add(
            TokenUsage(
                project_id=pid,
                milestone_id=1,
                phase="prd",
                model="claude-opus-4",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.05,
            )
        )
        db_session.add(
            TokenUsage(
                project_id=pid,
                milestone_id=1,
                phase="qa",
                model="claude-opus-4",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.10,
            )
        )
        db_session.add(
            TokenUsage(
                project_id=pid,
                milestone_id=2,
                phase="prd",
                model="claude-opus-4",
                input_tokens=500,
                output_tokens=200,
                cost_usd=0.02,
            )
        )
        db_session.commit()

        resp = client.get(f"/api/pipeline/{pid}/tokens")
        data = resp.get_json()

        assert data["total"]["input_tokens"] == 3500
        assert data["total"]["output_tokens"] == 1700
        assert abs(data["total"]["cost_usd"] - 0.17) < 0.001

        assert data["by_milestone"][str(1)]["input_tokens"] == 3000
        assert data["by_milestone"][str(2)]["input_tokens"] == 500


class TestGetMilestones:
    """GET /api/pipeline/<id>/milestones"""

    def test_milestones_no_state(self, client, linked_project):
        resp = client.get(f"/api/pipeline/{linked_project['id']}/milestones")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "milestones" in data
        assert "max_bugfix_cycles" in data

    def test_milestones_with_state(self, client, linked_project_with_state):
        resp = client.get(
            f"/api/pipeline/{linked_project_with_state['id']}/milestones"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        milestones = data["milestones"]
        assert len(milestones) == 2
        ids = [m["id"] for m in milestones]
        assert 1 in ids
        assert 2 in ids
