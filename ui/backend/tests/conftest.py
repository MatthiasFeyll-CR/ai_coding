"""Shared test fixtures for the backend test suite."""

import json
import os
import shutil
import sys
import tempfile

import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def app():
    """Create a test Flask application with an in-memory SQLite database."""
    from app import app as _app
    from database import db

    _app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret",
        }
    )
    # Disable eventlet async mode for tests
    with _app.app_context():
        db.create_all()
        yield _app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def _clear_active_pipelines():
    """Clear the active_pipelines dict between tests to avoid cross-test contamination."""
    from api.pipeline import active_pipelines

    active_pipelines.clear()
    yield
    active_pipelines.clear()


@pytest.fixture()
def db_session(app):
    """Database session for direct model access."""
    from database import db

    with app.app_context():
        yield db.session


@pytest.fixture()
def sample_project_dir():
    """Create a temporary directory that looks like a valid project."""
    tmpdir = tempfile.mkdtemp(prefix="ralph_test_project_")

    # Create docs structure
    for folder in [
        "docs/01-requirements",
        "docs/02-architecture",
        "docs/03-design",
        "docs/04-test-architecture",
        "docs/05-milestones",
        ".ralph",
    ]:
        os.makedirs(os.path.join(tmpdir, folder), exist_ok=True)

    # Create handover files
    for folder in [
        "docs/01-requirements",
        "docs/02-architecture",
        "docs/03-design",
        "docs/04-test-architecture",
        "docs/05-milestones",
    ]:
        with open(os.path.join(tmpdir, folder, "handover.json"), "w") as f:
            json.dump({"status": "complete"}, f)

    # Create some realistic project files
    with open(os.path.join(tmpdir, "README.md"), "w") as f:
        f.write("# Test Project\n")

    yield tmpdir

    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture()
def sample_project_with_config(sample_project_dir):
    """Project directory that also has a pipeline-config.json."""
    config = {
        "project_name": os.path.basename(sample_project_dir),
        "milestones": [1, 2, 3],
        "models": {"prd": "claude-opus-4"},
    }
    with open(os.path.join(sample_project_dir, "pipeline-config.json"), "w") as f:
        json.dump(config, f)

    return sample_project_dir


@pytest.fixture()
def sample_project_with_state(sample_project_with_config):
    """Project directory with a .ralph/state.json file."""
    state = {
        "base_branch": "main",
        "current_milestone": 1,
        "current_phase": "prd_generation",
        "status": "running",
        "milestones": {
            "1": {
                "id": 1,
                "phase": "prd_generation",
                "bugfix_cycle": 0,
                "test_fix_cycle": 0,
                "started_at": "2026-03-01T00:00:00",
                "completed_at": None,
            },
            "2": {
                "id": 2,
                "phase": "waiting",
                "bugfix_cycle": 0,
                "test_fix_cycle": 0,
                "started_at": None,
                "completed_at": None,
            },
        },
        "test_milestone_map": {},
        "timestamp": "2026-03-06T12:00:00",
    }
    state_path = os.path.join(sample_project_with_config, ".ralph", "state.json")
    with open(state_path, "w") as f:
        json.dump(state, f)

    return sample_project_with_config


@pytest.fixture()
def linked_project(client, sample_project_dir):
    """Create and return a linked project via the API."""
    resp = client.post(
        "/api/projects",
        json={"project_path": sample_project_dir},
        content_type="application/json",
    )
    assert resp.status_code in (200, 201)
    return resp.get_json()


@pytest.fixture()
def linked_project_with_config(client, sample_project_with_config):
    """Create and return a linked project that has pipeline-config.json."""
    resp = client.post(
        "/api/projects",
        json={"project_path": sample_project_with_config},
        content_type="application/json",
    )
    assert resp.status_code in (200, 201)
    return resp.get_json()


@pytest.fixture()
def linked_project_with_state(client, sample_project_with_state):
    """Create and return a linked project with state.json."""
    resp = client.post(
        "/api/projects",
        json={"project_path": sample_project_with_state},
        content_type="application/json",
    )
    assert resp.status_code in (200, 201)
    return resp.get_json()
