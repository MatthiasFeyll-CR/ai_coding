"""Projects API endpoints."""

import json
import os
from pathlib import Path

from database import db
from flask import Blueprint, jsonify, request
from models import ModelConfig, Project, StateSnapshot
from sqlalchemy.exc import IntegrityError

bp = Blueprint("projects", __name__)


@bp.route("", methods=["GET"])
def list_projects():
    """List all projects sorted by last activity."""
    projects = Project.query.order_by(Project.last_run_at.desc().nullsfirst()).all()
    return jsonify([p.to_dict() for p in projects])


@bp.route("", methods=["POST"])
def create_project():
    """Create/link a new project. Does not require pipeline-config.json."""
    data = request.json
    project_path = data.get("project_path")

    if not project_path:
        return jsonify({"error": "project_path is required"}), 400

    # Validate path exists
    if not os.path.exists(project_path):
        return jsonify({"error": "Project path does not exist"}), 400

    # Extract project name from path
    project_name = data.get("name") or Path(project_path).name

    # Config path (may not exist yet – created by configurator later)
    config_path = os.path.join(project_path, "pipeline-config.json")

    try:
        project = Project(
            name=project_name,
            root_path=project_path,
            config_path=config_path,
            status="initialized",
        )
        db.session.add(project)
        db.session.commit()

        return jsonify(project.to_dict()), 201
    except IntegrityError:
        db.session.rollback()
        # Project with this path already exists – return it instead of erroring
        existing = Project.query.filter_by(root_path=project_path).first()
        if existing:
            return jsonify(existing.to_dict()), 200
        return jsonify({"error": "Project already exists"}), 409


@bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id):
    """Get project details."""
    project = Project.query.get_or_404(project_id)
    return jsonify(project.to_dict())


@bp.route("/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    """Delete a project."""
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return jsonify({"success": True})


@bp.route("/pre-check", methods=["POST"])
def pre_check_project():
    """Pre-check project for required documentation."""
    data = request.json
    project_path = Path(data.get("project_path"))

    if not project_path.exists():
        return jsonify({"error": "Path does not exist"}), 400

    # Check required docs folders
    required_docs = [
        "docs/01-requirements",
        "docs/02-architecture",
        "docs/03-design",
        "docs/04-test-architecture",
        "docs/05-milestones",
    ]

    docs_check = {}
    all_valid = True

    for doc_path in required_docs:
        full_path = project_path / doc_path
        exists = full_path.exists()
        has_handover = (full_path / "handover.json").exists() if exists else False

        docs_check[doc_path] = {"exists": exists, "has_handover": has_handover}

        if not exists:
            all_valid = False

    # Check for existing infrastructure files
    infra_files = [
        "docker-compose.yml",
        "docker-compose.test.yml",
        "pipeline-config.json",
    ]

    existing_infra = []
    for file in infra_files:
        file_path = project_path / file
        if file_path.exists():
            existing_infra.append(
                {
                    "file": file,
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime,
                }
            )

    return jsonify(
        {
            "valid": all_valid,
            "docs_structure": docs_check,
            "existing_infrastructure": existing_infra,
            "project_name": project_path.name,
        }
    )


@bp.route("/setup", methods=["POST"])
def setup_project():
    """Start automated project setup."""
    data = request.json
    project_path = data.get("project_path")

    # Create project record
    project_name = Path(project_path).name
    config_path = os.path.join(project_path, "pipeline-config.json")

    project = Project(
        name=project_name,
        root_path=project_path,
        config_path=config_path,
        status="configuring",
    )
    db.session.add(project)
    db.session.commit()

    # Invoke configurator in background
    from threading import Thread

    from services.configurator_invoker import ConfiguratorInvoker

    configurator = ConfiguratorInvoker(project)
    thread = Thread(target=configurator.run_setup)
    thread.daemon = True
    thread.start()

    return (
        jsonify({"project_id": project.id, "status": "setup_started"}),
        202,
    )


@bp.route("/<int:project_id>/configure", methods=["POST"])
def configure_project(project_id):
    """Invoke the pipeline configurator skill via Claude to set up
    the test environment, architecture, and pipeline-config.json."""
    project = Project.query.get_or_404(project_id)

    # Don't re-configure if already running
    if project.status == "configuring":
        return jsonify({"error": "Configuration already in progress"}), 409

    project.status = "configuring"
    db.session.commit()

    # Invoke configurator in background
    from threading import Thread

    from services.configurator_invoker import ConfiguratorInvoker

    configurator = ConfiguratorInvoker(project)
    thread = Thread(target=configurator.run_setup)
    thread.daemon = True
    thread.start()

    return (
        jsonify({"project_id": project.id, "status": "configuring"}),
        202,
    )


@bp.route("/<int:project_id>/config", methods=["GET"])
def get_config(project_id):
    """Get pipeline configuration."""
    project = Project.query.get_or_404(project_id)

    try:
        with open(project.config_path, "r") as f:
            config = json.load(f)
        return jsonify(config)
    except FileNotFoundError:
        return jsonify({"error": "Config file not found"}), 404


@bp.route("/<int:project_id>/state", methods=["GET"])
def get_state(project_id):
    """Get current pipeline state."""
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / ".ralph" / "state.json"

    if not state_path.exists():
        return jsonify({"message": "No state file found"}), 404

    try:
        with open(state_path, "r") as f:
            state = json.load(f)
        return jsonify(state)
    except FileNotFoundError:
        return jsonify({"error": "State file not found"}), 404


@bp.route("/<int:project_id>/snapshots", methods=["GET"])
def list_snapshots(project_id):
    """List state snapshots."""
    snapshots = (
        StateSnapshot.query.filter_by(project_id=project_id)
        .order_by(StateSnapshot.created_at.desc())
        .limit(10)
        .all()
    )
    return jsonify([s.to_dict() for s in snapshots])


@bp.route("/<int:project_id>/snapshots", methods=["POST"])
def create_snapshot(project_id):
    """Create manual snapshot."""
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / ".ralph" / "state.json"

    if not state_path.exists():
        return jsonify({"error": "No state file to snapshot"}), 404

    with open(state_path, "r") as f:
        state_json = f.read()

    snapshot = StateSnapshot(
        project_id=project_id,
        state_json=state_json,
        snapshot_type="manual",
    )
    db.session.add(snapshot)
    db.session.commit()

    return jsonify(snapshot.to_dict()), 201


@bp.route("/<int:project_id>/restore/<int:snapshot_id>", methods=["PUT"])
def restore_snapshot(project_id, snapshot_id):
    """Restore state from snapshot."""
    project = Project.query.get_or_404(project_id)
    snapshot = StateSnapshot.query.filter_by(
        id=snapshot_id, project_id=project_id
    ).first_or_404()

    # Write state back to file
    state_path = Path(project.root_path) / ".ralph" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with open(state_path, "w") as f:
        f.write(snapshot.state_json)

    return jsonify({"success": True})


@bp.route("/<int:project_id>/models", methods=["GET"])
def get_models(project_id):
    """Get model configuration."""
    configs = ModelConfig.query.filter_by(project_id=project_id).all()
    return jsonify({c.phase: c.model for c in configs})


@bp.route("/<int:project_id>/models", methods=["PUT"])
def update_models(project_id):
    """Update model configuration."""
    Project.query.get_or_404(project_id)
    data = request.json

    for phase, model in data.items():
        config = ModelConfig.query.filter_by(project_id=project_id, phase=phase).first()
        if config:
            config.model = model
        else:
            config = ModelConfig(project_id=project_id, phase=phase, model=model)
            db.session.add(config)

    db.session.commit()
    return jsonify({"success": True})


@bp.route("/models/available", methods=["GET"])
def list_available_models():
    """List available models."""
    models = [
        "claude-opus-4",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku",
    ]
    return jsonify(models)
    return jsonify(models)
