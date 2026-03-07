"""Pipeline control API endpoints."""

import json
from pathlib import Path

from database import db
from flask import Blueprint, jsonify, request
from models import ExecutionLog, Project, TokenUsage
from services.lockfile import is_pipeline_running, kill_pipeline, release_lock
from services.pipeline_runner import PipelineRunner

bp = Blueprint("pipeline", __name__)

# Store active pipeline runners spawned by *this* UI process (in-memory).
# This is only used to track subprocesses the UI itself launched so it
# can terminate them on stop.  It is NOT the source of truth for whether
# a pipeline is running — the lock file is.
active_pipelines: dict[int, PipelineRunner] = {}


@bp.route("/<int:project_id>/start", methods=["POST"])
def start_pipeline(project_id):
    """Start pipeline execution."""
    project = Project.query.get_or_404(project_id)

    # Check lock file + PID liveness
    running, lock_data = is_pipeline_running(project.root_path)
    if running:
        return (
            jsonify(
                {
                    "error": "Pipeline is already running",
                    "pid": lock_data.get("pid"),
                    "started_at": lock_data.get("started_at"),
                    "source": lock_data.get("source"),
                }
            ),
            409,
        )

    # Orphaned lock file — clean it up
    release_lock(project.root_path)

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
    """Stop pipeline execution.

    If the pipeline was started by this UI process we terminate the
    subprocess directly.  Otherwise we send SIGTERM to the PID
    recorded in the lock file.
    """
    project = Project.query.get_or_404(project_id)

    # 1. Try local in-memory runner first
    runner = active_pipelines.pop(project_id, None)
    if runner:
        runner.stop()

    # 2. Fallback: kill via lock file PID (works for externally-started pipelines)
    killed = kill_pipeline(project.root_path)

    project.status = "stopped"
    db.session.commit()

    return jsonify({"success": True, "killed": killed or runner is not None})


@bp.route("/<int:project_id>/resume", methods=["POST"])
def resume_pipeline(project_id):
    """Resume pipeline from current state."""
    project = Project.query.get_or_404(project_id)

    # Check lock file
    running, lock_data = is_pipeline_running(project.root_path)
    if running:
        return (
            jsonify(
                {
                    "error": "Pipeline is already running",
                    "pid": lock_data.get("pid"),
                }
            ),
            409,
        )
    release_lock(project.root_path)

    runner = PipelineRunner(project, resume=True)
    runner.start()

    active_pipelines[project_id] = runner

    project.status = "running"
    db.session.commit()

    return jsonify({"success": True})


@bp.route("/<int:project_id>/status", methods=["GET"])
def pipeline_status(project_id):
    """Return pipeline run status derived exclusively from the lock file.

    This works regardless of whether the pipeline was started by the UI,
    the CLI, or any other mechanism.
    """
    project = Project.query.get_or_404(project_id)
    running, lock_data = is_pipeline_running(project.root_path)

    return jsonify(
        {
            "running": running,
            "lock": lock_data,
        }
    )


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
    """Get token usage with aggregations by milestone, phase, and model."""
    tokens = TokenUsage.query.filter_by(project_id=project_id).all()

    # Aggregation accumulators
    by_milestone: dict = {}
    by_phase: dict = {}
    by_model: dict = {}
    total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "cost_usd": 0.0,
        "invocations": 0,
    }

    for token in tokens:
        total["input_tokens"] += token.input_tokens
        total["output_tokens"] += token.output_tokens
        total["cache_creation_tokens"] += token.cache_creation_tokens or 0
        total["cache_read_tokens"] += token.cache_read_tokens or 0
        total["cost_usd"] += token.cost_usd
        total["invocations"] += 1

        # By milestone
        if token.milestone_id:
            if token.milestone_id not in by_milestone:
                by_milestone[token.milestone_id] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 0,
                    "cost_usd": 0.0,
                    "invocations": 0,
                }
            by_milestone[token.milestone_id]["input_tokens"] += token.input_tokens
            by_milestone[token.milestone_id]["output_tokens"] += token.output_tokens
            by_milestone[token.milestone_id]["cache_creation_tokens"] += (
                token.cache_creation_tokens or 0
            )
            by_milestone[token.milestone_id]["cache_read_tokens"] += (
                token.cache_read_tokens or 0
            )
            by_milestone[token.milestone_id]["cost_usd"] += token.cost_usd
            by_milestone[token.milestone_id]["invocations"] += 1

        # By phase
        phase_key = token.phase or "unknown"
        if phase_key not in by_phase:
            by_phase[phase_key] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "invocations": 0,
            }
        by_phase[phase_key]["input_tokens"] += token.input_tokens
        by_phase[phase_key]["output_tokens"] += token.output_tokens
        by_phase[phase_key]["cost_usd"] += token.cost_usd
        by_phase[phase_key]["invocations"] += 1

        # By model
        model_key = token.model or "unknown"
        if model_key not in by_model:
            by_model[model_key] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "invocations": 0,
            }
        by_model[model_key]["input_tokens"] += token.input_tokens
        by_model[model_key]["output_tokens"] += token.output_tokens
        by_model[model_key]["cost_usd"] += token.cost_usd
        by_model[model_key]["invocations"] += 1

    return jsonify(
        {
            "total": total,
            "by_milestone": by_milestone,
            "by_phase": by_phase,
            "by_model": by_model,
            "history": [t.to_dict() for t in tokens],
        }
    )


@bp.route("/<int:project_id>/milestones", methods=["GET"])
def get_milestones(project_id):
    """Get milestone status enriched with config data (name, slug)."""
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / ".ralph" / "state.json"
    config_path = Path(project.config_path)
    phase0_path = Path(project.root_path) / ".ralph" / "phase0-verification.json"

    # Load config for milestone names/slugs and qa settings
    config_milestones = {}
    max_bugfix_cycles = 3  # default
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            for m in config.get("milestones", []):
                # milestones can be plain ints or dicts with id/name/slug
                if isinstance(m, int):
                    m_id = m
                    m_data = {}
                else:
                    m_id = m["id"]
                    m_data = m
                config_milestones[m_id] = {
                    "name": m_data.get("name", f"Milestone {m_id}"),
                    "slug": m_data.get("slug", f"m{m_id}"),
                    "stories": m_data.get("stories", 0),
                    "dependencies": m_data.get("dependencies", []),
                }
            max_bugfix_cycles = config.get("qa", {}).get("max_bugfix_cycles", 3)
        except (json.JSONDecodeError, KeyError):
            pass

    # Determine Phase 0 status from state.json cost data and phase0-verification.json
    phase0_entry = _build_phase0_entry(state_path, phase0_path)

    if not state_path.exists():
        # Return config-only milestones if no state yet
        milestones = [phase0_entry]
        for m_id, m_info in sorted(config_milestones.items()):
            milestones.append(
                {
                    "id": m_id,
                    "name": m_info["name"],
                    "slug": m_info["slug"],
                    "stories": m_info["stories"],
                    "dependencies": m_info["dependencies"],
                    "phase": "pending",
                    "bugfix_cycle": 0,
                    "test_fix_cycle": 0,
                    "started_at": None,
                    "completed_at": None,
                }
            )
        return jsonify(
            {"milestones": milestones, "max_bugfix_cycles": max_bugfix_cycles}
        )

    with open(state_path, "r") as f:
        state = json.load(f)

    # Update phase0 entry with state data if available
    phase0_entry = _build_phase0_entry(state_path, phase0_path, state)

    milestones = [phase0_entry]
    for m_id, m_state in state.get("milestones", {}).items():
        int_id = int(m_id)
        cfg = config_milestones.get(int_id, {})
        milestones.append(
            {
                "id": int_id,
                "name": cfg.get("name", f"Milestone {int_id}"),
                "slug": cfg.get("slug", f"m{int_id}"),
                "stories": cfg.get("stories", 0),
                "dependencies": cfg.get("dependencies", []),
                **m_state,
            }
        )

    # Sort by id (phase 0 comes first)
    milestones.sort(key=lambda m: m["id"])

    return jsonify({"milestones": milestones, "max_bugfix_cycles": max_bugfix_cycles})


def _build_phase0_entry(state_path, phase0_path, state=None):
    """Build Phase 0 (Build Infrastructure) milestone entry."""
    phase0 = {
        "id": 0,
        "name": "Build Infrastructure",
        "slug": "phase0",
        "stories": 0,
        "dependencies": [],
        "phase": "pending",
        "bugfix_cycle": 0,
        "test_fix_cycle": 0,
        "started_at": None,
        "completed_at": None,
    }

    # Check if phase0-verification.json exists and indicates completion
    if phase0_path.exists():
        try:
            with open(phase0_path, "r") as f:
                verification = json.load(f)
            if verification.get("verified"):
                phase0["phase"] = "complete"
                phase0["completed_at"] = phase0_path.stat().st_mtime
                # Convert to ISO format
                from datetime import datetime, timezone

                phase0["completed_at"] = datetime.fromtimestamp(
                    phase0_path.stat().st_mtime, tz=timezone.utc
                ).isoformat()
        except (json.JSONDecodeError, KeyError):
            pass

    # Check state.json cost data for phase0 activity to determine started_at
    if state:
        cost = state.get("cost", {})
        by_milestone = cost.get("by_milestone", {})
        if "0" in by_milestone or 0 in by_milestone:
            # Phase 0 has cost data, meaning it started
            sessions = cost.get("sessions", [])
            phase0_sessions = [s for s in sessions if s.get("milestone") == 0]
            if phase0_sessions:
                # Use the earliest session as started_at (approximate)
                phase0["started_at"] = phase0_sessions[0].get("session_id", "")
                # We don't have a direct timestamp but we know it ran
                phase0["started_at"] = phase0.get("completed_at")  # approximate

            # Determine current sub-phase if not complete
            if phase0["phase"] != "complete":
                by_phase = cost.get("by_phase", {})
                if "phase0_lifecycle" in by_phase:
                    phase0["phase"] = "phase0_lifecycle"
                elif "phase0_test_infra" in by_phase:
                    phase0["phase"] = "phase0_test_infra"
                elif "phase0_scaffolding" in by_phase:
                    phase0["phase"] = "phase0_scaffolding"
                else:
                    phase0["phase"] = "phase0_scaffolding"
                phase0["started_at"] = phase0["completed_at"] or "unknown"

    return phase0
