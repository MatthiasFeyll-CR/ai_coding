"""Integration tests for the Projects API.

Tests the full request → DB → response cycle for every projects endpoint.
"""

import json
import os



class TestCreateProject:
    """POST /api/projects"""

    def test_link_project_success(self, client, sample_project_dir):
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == os.path.basename(sample_project_dir)
        assert data["root_path"] == sample_project_dir
        assert data["status"] == "initialized"
        assert "id" in data

    def test_link_project_custom_name(self, client, sample_project_dir):
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir, "name": "My Project"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["name"] == "My Project"

    def test_link_project_no_path(self, client):
        resp = client.post("/api/projects", json={})
        assert resp.status_code == 400
        assert "project_path is required" in resp.get_json()["error"]

    def test_link_project_invalid_path(self, client):
        resp = client.post(
            "/api/projects",
            json={"project_path": "/nonexistent/path/that/does/not/exist"},
        )
        assert resp.status_code == 400

    def test_link_project_without_config_succeeds(self, client, sample_project_dir):
        """Core test: linking a project does NOT require pipeline-config.json."""
        config_path = os.path.join(sample_project_dir, "pipeline-config.json")
        assert not os.path.exists(config_path)

        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        assert resp.status_code == 201
        assert resp.get_json()["is_setup"] is False

    def test_link_project_with_config_is_setup(self, client, sample_project_with_config):
        resp = client.post(
            "/api/projects",
            json={"project_path": sample_project_with_config},
        )
        assert resp.status_code == 201
        assert resp.get_json()["is_setup"] is True

    def test_link_duplicate_returns_existing(self, client, sample_project_dir):
        """Linking the same path twice returns the existing project (not an error)."""
        resp1 = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        assert resp1.status_code == 201
        id1 = resp1.get_json()["id"]

        resp2 = client.post(
            "/api/projects",
            json={"project_path": sample_project_dir},
        )
        assert resp2.status_code == 200
        assert resp2.get_json()["id"] == id1


class TestListProjects:
    """GET /api/projects"""

    def test_list_empty(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_after_create(self, client, linked_project):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["id"] == linked_project["id"]

    def test_list_multiple_projects(self, client, sample_project_dir):
        import tempfile

        dirs = [sample_project_dir]
        for _ in range(2):
            d = tempfile.mkdtemp(prefix="ralph_test_")
            dirs.append(d)
            client.post("/api/projects", json={"project_path": d})

        # Original one
        client.post("/api/projects", json={"project_path": sample_project_dir})

        resp = client.get("/api/projects")
        assert len(resp.get_json()) == 3

        # Cleanup
        import shutil

        for d in dirs[1:]:
            shutil.rmtree(d, ignore_errors=True)


class TestGetProject:
    """GET /api/projects/<id>"""

    def test_get_existing(self, client, linked_project):
        resp = client.get(f"/api/projects/{linked_project['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == linked_project["name"]

    def test_get_nonexistent(self, client):
        resp = client.get("/api/projects/99999")
        assert resp.status_code == 404


class TestDeleteProject:
    """DELETE /api/projects/<id>"""

    def test_delete(self, client, linked_project):
        project_id = linked_project["id"]
        resp = client.delete(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # Verify it's gone
        resp = client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/projects/99999")
        assert resp.status_code == 404


class TestPreCheck:
    """POST /api/projects/pre-check"""

    def test_pre_check_valid_project(self, client, sample_project_dir):
        resp = client.post(
            "/api/projects/pre-check",
            json={"project_path": sample_project_dir},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert "docs/01-requirements" in data["docs_structure"]
        assert data["docs_structure"]["docs/01-requirements"]["exists"] is True

    def test_pre_check_missing_docs(self, client):
        import tempfile

        tmpdir = tempfile.mkdtemp()
        resp = client.post(
            "/api/projects/pre-check",
            json={"project_path": tmpdir},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is False
        for doc_info in data["docs_structure"].values():
            assert doc_info["exists"] is False

        import shutil

        shutil.rmtree(tmpdir)

    def test_pre_check_nonexistent_path(self, client):
        resp = client.post(
            "/api/projects/pre-check",
            json={"project_path": "/nonexistent"},
        )
        assert resp.status_code == 400

    def test_pre_check_detects_infrastructure_files(self, client, sample_project_with_config):
        resp = client.post(
            "/api/projects/pre-check",
            json={"project_path": sample_project_with_config},
        )
        data = resp.get_json()
        infra_files = [f["file"] for f in data["existing_infrastructure"]]
        assert "pipeline-config.json" in infra_files


class TestGetConfig:
    """GET /api/projects/<id>/config"""

    def test_get_config_exists(self, client, linked_project_with_config):
        project_id = linked_project_with_config["id"]
        resp = client.get(f"/api/projects/{project_id}/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "project_name" in data

    def test_get_config_missing(self, client, linked_project):
        resp = client.get(f"/api/projects/{linked_project['id']}/config")
        assert resp.status_code == 404


class TestGetState:
    """GET /api/projects/<id>/state"""

    def test_get_state_exists(self, client, linked_project_with_state):
        resp = client.get(
            f"/api/projects/{linked_project_with_state['id']}/state"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current_phase"] == "prd_generation"
        assert data["current_milestone"] == 1

    def test_get_state_missing(self, client, linked_project):
        resp = client.get(f"/api/projects/{linked_project['id']}/state")
        assert resp.status_code == 404


class TestSnapshots:
    """Snapshot CRUD: POST/GET /api/projects/<id>/snapshots, PUT restore."""

    def test_create_snapshot(self, client, linked_project_with_state):
        pid = linked_project_with_state["id"]
        resp = client.post(f"/api/projects/{pid}/snapshots")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["snapshot_type"] == "manual"
        assert data["project_id"] == pid

    def test_list_snapshots_empty(self, client, linked_project):
        resp = client.get(f"/api/projects/{linked_project['id']}/snapshots")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_snapshots_after_create(self, client, linked_project_with_state):
        pid = linked_project_with_state["id"]
        client.post(f"/api/projects/{pid}/snapshots")
        client.post(f"/api/projects/{pid}/snapshots")

        resp = client.get(f"/api/projects/{pid}/snapshots")
        assert len(resp.get_json()) == 2

    def test_restore_snapshot(self, client, linked_project_with_state):
        pid = linked_project_with_state["id"]
        # Create snapshot
        snap_resp = client.post(f"/api/projects/{pid}/snapshots")
        snap_id = snap_resp.get_json()["id"]

        # Modify state on disk
        project_path = linked_project_with_state["root_path"]
        state_path = os.path.join(project_path, ".ralph", "state.json")
        with open(state_path, "w") as f:
            json.dump({"modified": True}, f)

        # Restore
        resp = client.put(f"/api/projects/{pid}/restore/{snap_id}")
        assert resp.status_code == 200

        # Verify state was restored
        with open(state_path) as f:
            restored = json.load(f)
        assert "current_phase" in restored

    def test_create_snapshot_no_state(self, client, linked_project):
        resp = client.post(f"/api/projects/{linked_project['id']}/snapshots")
        assert resp.status_code == 404


class TestModelConfig:
    """Model configuration: GET/PUT /api/projects/<id>/models"""

    def test_get_models_empty(self, client, linked_project):
        resp = client.get(f"/api/projects/{linked_project['id']}/models")
        assert resp.status_code == 200
        assert resp.get_json() == {}

    def test_update_and_get_models(self, client, linked_project):
        pid = linked_project["id"]
        models = {"prd": "claude-opus-4", "qa": "claude-3-5-sonnet-20241022"}

        resp = client.put(f"/api/projects/{pid}/models", json=models)
        assert resp.status_code == 200

        resp = client.get(f"/api/projects/{pid}/models")
        data = resp.get_json()
        assert data["prd"] == "claude-opus-4"
        assert data["qa"] == "claude-3-5-sonnet-20241022"

    def test_update_model_overwrites(self, client, linked_project):
        pid = linked_project["id"]
        client.put(f"/api/projects/{pid}/models", json={"prd": "claude-opus-4"})
        client.put(
            f"/api/projects/{pid}/models",
            json={"prd": "claude-3-5-haiku"},
        )

        resp = client.get(f"/api/projects/{pid}/models")
        assert resp.get_json()["prd"] == "claude-3-5-haiku"

    def test_list_available_models(self, client):
        resp = client.get("/api/projects/models/available")
        assert resp.status_code == 200
        models = resp.get_json()
        assert isinstance(models, list)
        assert "claude-opus-4" in models


class TestConfigureProject:
    """POST /api/projects/<id>/configure"""

    def test_configure_changes_status(self, client, linked_project, monkeypatch):
        """Configure endpoint sets status to 'configuring' and returns 202."""
        # Mock ConfiguratorInvoker so no subprocess is spawned
        from unittest.mock import MagicMock

        mock_invoker = MagicMock()
        monkeypatch.setattr(
            "services.configurator_invoker.ConfiguratorInvoker",
            lambda project: mock_invoker,
        )

        pid = linked_project["id"]
        resp = client.post(f"/api/projects/{pid}/configure")
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["status"] == "configuring"

        # Verify status is updated in DB
        resp2 = client.get(f"/api/projects/{pid}")
        assert resp2.get_json()["status"] == "configuring"

    def test_configure_already_configuring(self, client, linked_project, monkeypatch, db_session):
        """Cannot re-configure while already configuring."""
        from models import Project

        project = Project.query.get(linked_project["id"])
        project.status = "configuring"
        db_session.commit()

        resp = client.post(f"/api/projects/{linked_project['id']}/configure")
        assert resp.status_code == 409

    def test_configure_nonexistent_project(self, client):
        resp = client.post("/api/projects/99999/configure")
        assert resp.status_code == 404
