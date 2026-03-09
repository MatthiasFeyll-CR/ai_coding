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
        """Cost data is read from .ralph/state.json, not the DB."""
        pid = linked_project["id"]
        root = linked_project["root_path"]

        # Write cost data into state.json
        ralph_dir = os.path.join(root, ".ralph")
        os.makedirs(ralph_dir, exist_ok=True)
        logs_dir = os.path.join(ralph_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        state = {
            "cost": {
                "sessions": [
                    {
                        "session_id": "sess-1",
                        "phase": "prd",
                        "milestone": 1,
                        "model": "claude-opus-4",
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "cache_creation_tokens": 0,
                        "cache_read_tokens": 200,
                        "cost_usd": 0.05,
                        "invocations": 1,
                    },
                    {
                        "session_id": "sess-2",
                        "phase": "qa",
                        "milestone": 1,
                        "model": "claude-opus-4",
                        "input_tokens": 2000,
                        "output_tokens": 1000,
                        "cache_creation_tokens": 0,
                        "cache_read_tokens": 0,
                        "cost_usd": 0.10,
                        "invocations": 1,
                    },
                    {
                        "session_id": "sess-3",
                        "phase": "prd",
                        "milestone": 2,
                        "model": "claude-opus-4",
                        "input_tokens": 500,
                        "output_tokens": 200,
                        "cache_creation_tokens": 0,
                        "cache_read_tokens": 0,
                        "cost_usd": 0.02,
                        "invocations": 1,
                    },
                ]
            }
        }
        with open(os.path.join(ralph_dir, "state.json"), "w") as f:
            json.dump(state, f)

        # Write matching pipeline.jsonl for timestamps
        with open(os.path.join(logs_dir, "pipeline.jsonl"), "w") as f:
            for s in state["cost"]["sessions"]:
                f.write(
                    json.dumps(
                        {
                            "event": "claude_invocation",
                            "session_id": s["session_id"],
                            "ts": "2026-03-07T14:00:00Z",
                        }
                    )
                    + "\n"
                )

        resp = client.get(f"/api/pipeline/{pid}/tokens")
        data = resp.get_json()

        assert data["total"]["input_tokens"] == 3500
        assert data["total"]["output_tokens"] == 1700
        assert abs(data["total"]["cost_usd"] - 0.17) < 0.001

        assert data["by_milestone"]["1"]["input_tokens"] == 3000
        assert data["by_milestone"]["2"]["input_tokens"] == 500

        # History entries have timestamps from pipeline.jsonl
        assert len(data["history"]) == 3
        assert data["history"][0]["created_at"] == "2026-03-07T14:00:00Z"

    def test_tokens_fallback_to_jsonl(self, client, linked_project, db_session):
        """When state.json has empty sessions, cost data falls back to pipeline.jsonl."""
        pid = linked_project["id"]
        root = linked_project["root_path"]

        ralph_dir = os.path.join(root, ".ralph")
        os.makedirs(ralph_dir, exist_ok=True)
        logs_dir = os.path.join(ralph_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)

        # state.json with empty sessions (as after reinitialization)
        state = {"cost": {"sessions": []}}
        with open(os.path.join(ralph_dir, "state.json"), "w") as f:
            json.dump(state, f)

        # pipeline.jsonl has the actual cost data
        with open(os.path.join(logs_dir, "pipeline.jsonl"), "w") as f:
            f.write(
                json.dumps(
                    {
                        "event": "claude_invocation",
                        "session_id": "sess-p0",
                        "ts": "2026-03-09T01:48:00Z",
                        "phase": "phase0_scaffolding",
                        "milestone": 0,
                        "model": "claude-opus-4-6",
                        "input_tokens": 3,
                        "output_tokens": 192,
                        "cache_creation_tokens": 1219,
                        "cache_read_tokens": 111701,
                        "cost_usd": 7.15,
                    }
                )
                + "\n"
            )

        resp = client.get(f"/api/pipeline/{pid}/tokens")
        data = resp.get_json()

        # Should have picked up data from pipeline.jsonl
        assert data["total"]["invocations"] == 1
        assert data["total"]["input_tokens"] == 3
        assert data["total"]["output_tokens"] == 192
        assert abs(data["total"]["cost_usd"] - 7.15) < 0.01
        assert data["by_phase"]["phase0_scaffolding"]["cost_usd"] > 0
        assert len(data["history"]) == 1
        assert data["history"][0]["created_at"] == "2026-03-09T01:48:00Z"


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
        # 3 milestones: phase 0 (Build Infrastructure) + milestones 1 & 2
        assert len(milestones) == 3
        ids = [m["id"] for m in milestones]
        assert 0 in ids  # phase 0
        assert 1 in ids
        assert 2 in ids
