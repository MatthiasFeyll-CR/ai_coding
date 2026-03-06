"""Pipeline control API endpoints."""

import json
from pathlib import Path

from database import db
from flask import Blueprint, jsonify, request
from models import ExecutionLog, Project, TokenUsage
from services.pipeline_runner import PipelineRunner

bp = Blueprint("pipeline", __name__)

# Store active pipeline runners (in-memory)
active_pipelines: dict[int, PipelineRunner] = {}


@bp.route("/<int:project_id>/start", methods=["POST"])
def start_pipeline(project_id):
    """Start pipeline execution."""
    project = Project.query.get_or_404(project_id)

    # Check for lock file
    lock_path = Path(project.root_path) / ".ralph" / "pipeline.lock"
    if lock_path.exists():
        return (
            jsonify({"error": "Pipeline is already running or locked"}),
            409,
        )

    # Get optional milestone parameter
    milestone_id = request.json.get("milestone_id") if request.json else None

    # Create and start runner
    runner = PipelineRunner(project, milestone_id=milestone_id)
    runner.start()

    active_pipelines[project_id] = runner

    # Update project status
    project.status = "running"
    db.session.commit()

    return jsonify({"success": True, "message": "Pipeline started"})


@bp.route("/<int:project_id>/stop", methods=["POST"])
def stop_pipeline(project_id):
    """Stop pipeline execution."""
    project = Project.query.get_or_404(project_id)

    runner = active_pipelines.get(project_id)
    if runner:
        runner.stop()
        del active_pipelines[project_id]

    # Remove lock file
    lock_path = Path(project.root_path) / ".ralph" / "pipeline.lock"
    if lock_path.exists():
        lock_path.unlink()

    project.status = "paused"
    db.session.commit()

    return jsonify({"success": True})


@bp.route("/<int:project_id>/resume", methods=["POST"])
def resume_pipeline(project_id):
    """Resume pipeline from current state."""
    project = Project.query.get_or_404(project_id)

    runner = PipelineRunner(project, resume=True)
    runner.start()

    active_pipelines[project_id] = runner

    project.status = "running"
    db.session.commit()

    return jsonify({"success": True})


@bp.route("/<int:project_id>/logs", methods=["GET"])
def get_logs(project_id):
    """Get execution logs."""
    milestone_id = request.args.get("milestone_id", type=int)
    phase = request.args.get("phase")
    limit = request.args.get("limit", 1000, type=int)

    query = ExecutionLog.query.filter_by(project_id=project_id)

    if milestone_id:
        query = query.filter_by(milestone_id=milestone_id)
    if phase:
        query = query.filter_by(phase=phase)

    logs = query.order_by(ExecutionLog.created_at.desc()).limit(limit).all()
    return jsonify([log.to_dict() for log in logs])


@bp.route("/<int:project_id>/tokens", methods=["GET"])
def get_tokens(project_id):
    """Get token usage."""
    tokens = TokenUsage.query.filter_by(project_id=project_id).all()

    # Aggregate by milestone
    by_milestone: dict = {}
    total = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    for token in tokens:
        total["input_tokens"] += token.input_tokens
        total["output_tokens"] += token.output_tokens
        total["cost_usd"] += token.cost_usd

        if token.milestone_id:
            if token.milestone_id not in by_milestone:
                by_milestone[token.milestone_id] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                }
            by_milestone[token.milestone_id]["input_tokens"] += token.input_tokens
            by_milestone[token.milestone_id]["output_tokens"] += token.output_tokens
            by_milestone[token.milestone_id]["cost_usd"] += token.cost_usd

    return jsonify(
        {
            "total": total,
            "by_milestone": by_milestone,
            "history": [t.to_dict() for t in tokens],
        }
    )


@bp.route("/<int:project_id>/milestones", methods=["GET"])
def get_milestones(project_id):
    """Get milestone status from state."""
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / ".ralph" / "state.json"

    if not state_path.exists():
        return jsonify([])

    with open(state_path, "r") as f:
        state = json.load(f)

    milestones = []
    for m_id, m_state in state.get("milestones", {}).items():
        milestones.append({"id": int(m_id), **m_state})

    return jsonify(milestones)
