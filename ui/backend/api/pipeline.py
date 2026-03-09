"""Pipeline control API endpoints."""

import json
import re
from pathlib import Path

from database import db
from flask import Blueprint, jsonify, request
from models import ExecutionLog, Project
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


@bp.route("/<int:project_id>/logfiles", methods=["GET"])
def get_log_files(project_id):
    """List available log files grouped by milestone/phase0 directory.

    Returns a tree: { "phase0": ["scaffolding.log", ...], "m1-foundation": [...], ... }
    """
    project = Project.query.get_or_404(project_id)
    logs_dir = Path(project.root_path) / ".ralph" / "logs"

    if not logs_dir.is_dir():
        return jsonify({"directories": {}})

    directories: dict[str, list[str]] = {}
    for child in sorted(logs_dir.iterdir()):
        if child.is_dir():
            files = sorted(
                f.name for f in child.iterdir() if f.is_file() and f.suffix == ".log"
            )
            if files:
                directories[child.name] = files

    return jsonify({"directories": directories})


@bp.route("/<int:project_id>/logfiles/<path:log_path>", methods=["GET"])
def get_log_file_content(project_id, log_path):
    """Read the content of a specific log file.

    log_path should be e.g. "phase0/scaffolding.log" or "m1-foundation/ralph-iter-1.log".
    Only serves .log files inside .ralph/logs/ for security.
    """
    project = Project.query.get_or_404(project_id)
    logs_dir = Path(project.root_path) / ".ralph" / "logs"
    target = (logs_dir / log_path).resolve()

    # Security: ensure path is inside logs_dir
    if not str(target).startswith(str(logs_dir.resolve())):
        return jsonify({"error": "Invalid path"}), 403

    if not target.is_file() or target.suffix != ".log":
        return jsonify({"error": "Log file not found"}), 404

    try:
        # Read with tail support for large files
        tail = request.args.get("tail", type=int)
        content = target.read_text(errors="replace")
        if tail:
            lines = content.splitlines()
            content = "\n".join(lines[-tail:])
        return jsonify({"path": log_path, "content": content, "size": target.stat().st_size})
    except OSError as e:
        return jsonify({"error": str(e)}), 500


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
    """Get token usage with aggregations by milestone, phase, and model.

    Reads cost data from .ralph/state.json (source of truth written by
    the pipeline CLI) and enriches history entries with timestamps from
    .ralph/logs/pipeline.jsonl.
    """
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / ".ralph" / "state.json"
    log_path = Path(project.root_path) / ".ralph" / "logs" / "pipeline.jsonl"

    # Load state.json cost block
    sessions: list[dict] = []
    if state_path.exists():
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
            sessions = state.get("cost", {}).get("sessions", [])
        except (json.JSONDecodeError, OSError):
            pass

    # Build a session_id → timestamp lookup from pipeline.jsonl
    ts_lookup: dict[str, str] = {}
    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if (
                            entry.get("event") == "claude_invocation"
                            and "session_id" in entry
                            and "ts" in entry
                        ):
                            ts_lookup[entry["session_id"]] = entry["ts"]
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            pass

    # Aggregate from sessions
    _zero_bucket = lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "cost_usd": 0.0,
        "invocations": 0,
    }
    total = _zero_bucket()
    by_milestone: dict[str, dict] = {}
    by_phase: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    history: list[dict] = []

    for idx, s in enumerate(sessions):
        in_tok = s.get("input_tokens", 0)
        out_tok = s.get("output_tokens", 0)
        cache_create = s.get("cache_creation_tokens", 0)
        cache_read = s.get("cache_read_tokens", 0)
        cost = s.get("cost_usd", 0.0)
        invocations = s.get("invocations", 1)
        phase_key = s.get("phase", "unknown")
        model_key = s.get("model", "unknown")
        milestone_key = str(s.get("milestone", ""))
        session_id = s.get("session_id", "")

        # Total
        total["input_tokens"] += in_tok
        total["output_tokens"] += out_tok
        total["cache_creation_tokens"] += cache_create
        total["cache_read_tokens"] += cache_read
        total["cost_usd"] += cost
        total["invocations"] += invocations

        # By milestone
        if milestone_key:
            bm = by_milestone.setdefault(milestone_key, _zero_bucket())
            bm["input_tokens"] += in_tok
            bm["output_tokens"] += out_tok
            bm["cache_creation_tokens"] += cache_create
            bm["cache_read_tokens"] += cache_read
            bm["cost_usd"] += cost
            bm["invocations"] += invocations

        # By phase
        bp_ = by_phase.setdefault(phase_key, _zero_bucket())
        bp_["input_tokens"] += in_tok
        bp_["output_tokens"] += out_tok
        bp_["cache_creation_tokens"] += cache_create
        bp_["cache_read_tokens"] += cache_read
        bp_["cost_usd"] += cost
        bp_["invocations"] += invocations

        # By model
        bmod = by_model.setdefault(model_key, _zero_bucket())
        bmod["input_tokens"] += in_tok
        bmod["output_tokens"] += out_tok
        bmod["cache_creation_tokens"] += cache_create
        bmod["cache_read_tokens"] += cache_read
        bmod["cost_usd"] += cost
        bmod["invocations"] += invocations

        # History entry (matches frontend TokenUsage.history shape)
        created_at = ts_lookup.get(session_id, "")
        history.append(
            {
                "id": idx,
                "project_id": project_id,
                "milestone_id": s.get("milestone"),
                "phase": phase_key,
                "model": model_key,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cache_creation_tokens": cache_create,
                "cache_read_tokens": cache_read,
                "cost_usd": cost,
                "session_id": session_id,
                "created_at": created_at,
            }
        )

    return jsonify(
        {
            "total": total,
            "by_milestone": by_milestone,
            "by_phase": by_phase,
            "by_model": by_model,
            "history": history,
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
                from datetime import datetime, timezone

                phase0["completed_at"] = datetime.fromtimestamp(
                    phase0_path.stat().st_mtime, tz=timezone.utc
                ).isoformat()
        except (json.JSONDecodeError, KeyError):
            pass

    # Use explicit phase0 timestamps from state.json if available
    if state:
        if state.get("phase0_started_at"):
            phase0["started_at"] = state["phase0_started_at"]
        if state.get("phase0_completed_at"):
            phase0["completed_at"] = state["phase0_completed_at"]
        if state.get("phase0_complete"):
            phase0["phase"] = "complete"

        cost = state.get("cost", {})
        by_milestone = cost.get("by_milestone", {})
        if "0" in by_milestone or 0 in by_milestone:
            # Phase 0 has cost data, meaning it started
            if not phase0["started_at"]:
                phase0["started_at"] = phase0.get("completed_at")

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
                if not phase0["started_at"]:
                    phase0["started_at"] = phase0["completed_at"] or "unknown"

    return phase0


@bp.route("/<int:project_id>/overview", methods=["GET"])
def get_overview(project_id):
    """Aggregate overview data for the dashboard overview tab.

    Returns project metadata, progress metrics, cost summary, quality
    metrics, and pipeline running status in a single API call.
    """
    project = Project.query.get_or_404(project_id)
    root = Path(project.root_path)
    state_path = root / ".ralph" / "state.json"
    config_path = Path(project.config_path)

    # ── Load config ──────────────────────────────────────────────────────
    config_data: dict = {}
    config_milestones: list[dict] = []
    models_config: dict = {}
    budget_usd = 0.0
    max_bugfix_cycles = 3
    project_description = ""

    if config_path.exists():
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            project_description = config_data.get("project", {}).get("description", "")
            models_config = config_data.get("models", {})
            budget_usd = config_data.get("cost", {}).get("budget_usd", 0.0)
            max_bugfix_cycles = config_data.get("qa", {}).get("max_bugfix_cycles", 3)
            for m in config_data.get("milestones", []):
                if isinstance(m, dict):
                    config_milestones.append({
                        "id": m.get("id", 0),
                        "name": m.get("name", f"M{m.get('id', '?')}"),
                        "slug": m.get("slug", ""),
                        "stories": m.get("stories", 0),
                    })
                else:
                    config_milestones.append({
                        "id": m,
                        "name": f"Milestone {m}",
                        "slug": f"m{m}",
                        "stories": 0,
                    })
        except (json.JSONDecodeError, OSError):
            pass

    total_milestones = len(config_milestones)
    total_stories = sum(m.get("stories", 0) for m in config_milestones)

    # ── Load state.json ──────────────────────────────────────────────────
    state: dict = {}
    milestone_states: dict[str, dict] = {}
    cost_total = 0.0
    cost_by_milestone: list[dict] = []

    if state_path.exists():
        try:
            with open(state_path) as f:
                state = json.load(f)
            milestone_states = state.get("milestones", {})
            cost_block = state.get("cost", {})
            cost_total = cost_block.get("total_usd", 0.0)

            # Cost by milestone
            for mid_str, cost_val in cost_block.get("by_milestone", {}).items():
                mid = int(mid_str)
                name = next((m["name"] for m in config_milestones if m["id"] == mid), f"M{mid}")
                cost_by_milestone.append({"id": mid, "name": name, "cost_usd": cost_val})
            cost_by_milestone.sort(key=lambda x: x["id"])
        except (json.JSONDecodeError, OSError):
            pass

    # ── Compute progress (including Phase 0) ─────────────────────────────
    completed_milestones = sum(
        1 for ms in milestone_states.values() if ms.get("phase") == "complete"
    )
    failed_milestones = sum(
        1 for ms in milestone_states.values() if ms.get("phase") == "failed"
    )
    current_milestone_id = state.get("current_milestone", 0)
    current_ms = milestone_states.get(str(current_milestone_id), {})
    current_phase = current_ms.get("phase", "pending")
    current_milestone_name = next(
        (m["name"] for m in config_milestones if m["id"] == current_milestone_id),
        f"M{current_milestone_id}",
    )

    # Phase 0 has 3 sub-phases; each milestone has 4 phases
    phase0_sub_phases = 3  # scaffolding, test_infra, lifecycle
    all_phases_count = phase0_sub_phases + total_milestones * 4
    completed_phases = 0

    # Count Phase 0 progress
    phase0_complete = state.get("phase0_complete", False)
    if phase0_complete:
        completed_phases += phase0_sub_phases
    else:
        cost_by_phase = state.get("cost", {}).get("by_phase", {})
        if "phase0_lifecycle" in cost_by_phase:
            completed_phases += 2  # scaffolding + test_infra done
        elif "phase0_test_infra" in cost_by_phase:
            completed_phases += 1  # scaffolding done

    # Count milestone progress
    for ms in milestone_states.values():
        phase = ms.get("phase", "pending")
        if phase == "complete":
            completed_phases += 4
        elif phase == "reconciliation":
            completed_phases += 3
        elif phase == "qa_review":
            completed_phases += 2
        elif phase == "ralph_execution":
            completed_phases += 1

    progress_pct = (completed_phases / all_phases_count * 100) if all_phases_count > 0 else 0

    # Include Phase 0 in milestone counts for overview
    total_milestones_with_phase0 = total_milestones + 1
    completed_milestones_with_phase0 = completed_milestones + (1 if phase0_complete else 0)

    # ── Quality metrics ──────────────────────────────────────────────────
    total_bugfix_cycles = sum(
        ms.get("bugfix_cycle", 0) for ms in milestone_states.values()
    )
    total_test_fix_cycles = sum(
        ms.get("test_fix_cycle", 0) for ms in milestone_states.values()
    )
    milestones_with_bugfixes = [
        {"id": int(mid), "cycles": ms.get("bugfix_cycle", 0)}
        for mid, ms in milestone_states.items()
        if ms.get("bugfix_cycle", 0) > 0
    ]

    # ── Pipeline running status ──────────────────────────────────────────
    running, lock_data = is_pipeline_running(project.root_path)

    # Build per-milestone story counts + completion status
    milestone_details = []
    for m in config_milestones:
        mid = m["id"]
        ms_state = milestone_states.get(str(mid), {})
        milestone_details.append({
            "id": mid,
            "name": m["name"],
            "stories": m.get("stories", 0),
            "completed": ms_state.get("phase") == "complete",
        })

    # Cost by phase from state.json
    cost_by_phase: dict = {}
    if state_path.exists():
        try:
            with open(state_path) as f:
                s2 = json.load(f)
            for ph_key, ph_val in s2.get("cost", {}).get("by_phase", {}).items():
                if isinstance(ph_val, (int, float)):
                    cost_by_phase[ph_key] = ph_val
                elif isinstance(ph_val, dict):
                    cost_by_phase[ph_key] = ph_val.get("cost_usd", 0.0)
        except (json.JSONDecodeError, OSError):
            pass

    return jsonify({
        "project": {
            "name": project.name,
            "description": project_description,
            "root_path": project.root_path,
            "total_milestones": total_milestones_with_phase0,
            "total_stories": total_stories,
            "models": models_config,
            "budget_usd": budget_usd,
            "max_bugfix_cycles": max_bugfix_cycles,
        },
        "progress": {
            "completed_milestones": completed_milestones_with_phase0,
            "failed_milestones": failed_milestones,
            "total_milestones": total_milestones_with_phase0,
            "percentage": round(progress_pct, 1),
            "current_milestone": current_milestone_id,
            "current_milestone_name": current_milestone_name,
            "current_phase": current_phase,
        },
        "cost": {
            "total_usd": cost_total,
            "budget_usd": budget_usd,
            "budget_pct": round(cost_total / budget_usd * 100, 1) if budget_usd > 0 else 0,
            "by_milestone": cost_by_milestone,
            "by_phase": cost_by_phase,
        },
        "quality": {
            "total_bugfix_cycles": total_bugfix_cycles,
            "total_test_fix_cycles": total_test_fix_cycles,
            "milestones_with_bugfixes": milestones_with_bugfixes,
        },
        "pipeline": {
            "running": running,
            "status": project.status,
            "lock": lock_data,
        },
        "milestone_details": milestone_details,
    })


@bp.route("/<int:project_id>/test-analytics", methods=["GET"])
def get_test_analytics(project_id):
    """Aggregate test analytics from pipeline.jsonl, state.json, and QA reports.

    Returns structured data for the Test Analytics dashboard:
    - summary KPIs (total runs, pass rate, fix cycles, avg duration)
    - per-milestone breakdown (test runs, verdicts, bugfix cycles, durations)
    - QA verdict timeline (every test_run and qa_verdict event)
    - enforcement point stats (which phases generate most test failures)
    - failing test files (most frequently failing files across all runs)
    """
    project = Project.query.get_or_404(project_id)
    root = Path(project.root_path)
    state_path = root / ".ralph" / "state.json"
    log_path = root / ".ralph" / "logs" / "pipeline.jsonl"
    qa_dir = root / "docs" / "08-qa"
    config_path = Path(project.config_path)

    # ── Load config for milestone names ──────────────────────────────────
    milestone_names: dict[int, str] = {}
    max_bugfix_cycles = 3
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            for m in cfg.get("milestones", []):
                if isinstance(m, dict):
                    milestone_names[m["id"]] = m.get("name", f"M{m['id']}")
            max_bugfix_cycles = cfg.get("qa", {}).get("max_bugfix_cycles", 3)
        except (json.JSONDecodeError, KeyError):
            pass

    # ── Load state.json for milestone phase data ─────────────────────────
    milestone_states: dict[int, dict] = {}
    if state_path.exists():
        try:
            with open(state_path) as f:
                state = json.load(f)
            for mid_str, ms in state.get("milestones", {}).items():
                mid = int(mid_str)
                milestone_states[mid] = ms
        except (json.JSONDecodeError, OSError):
            pass

    # ── Parse pipeline.jsonl for test_run and qa_verdict events ──────────
    test_runs: list[dict] = []
    qa_verdicts: list[dict] = []
    test_fix_events: list[dict] = []

    if log_path.exists():
        try:
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ev = entry.get("event")
                    if ev == "test_run":
                        test_runs.append(entry)
                    elif ev == "qa_verdict":
                        qa_verdicts.append(entry)
                    elif ev == "claude_invocation" and entry.get("phase") == "test_fix":
                        test_fix_events.append(entry)
        except OSError:
            pass

    # ── Parse QA report files for failing test details ───────────────────
    failing_files: dict[str, int] = {}
    qa_report_details: list[dict] = []

    if qa_dir.exists():
        # Parse test result files for failure details
        for result_file in sorted(qa_dir.glob("test-results-qa-m*.md")):
            content = result_file.read_text()
            # Extract milestone and cycle from filename
            fname_match = re.match(
                r"test-results-qa-m(\d+)-cycle(\d+)\.md", result_file.name
            )
            if not fname_match:
                continue
            mid = int(fname_match.group(1))
            cycle = int(fname_match.group(2))

            passed = "Result: PASS" in content
            exit_code_match = re.search(r"Exit code: (\d+)", content)
            exit_code = int(exit_code_match.group(1)) if exit_code_match else -1

            qa_report_details.append({
                "milestone": mid,
                "cycle": cycle,
                "passed": passed,
                "exit_code": exit_code,
                "file": result_file.name,
            })

            if not passed:
                # Extract FAILED test files from output
                # pytest: FAILED path/to/test.py::test_name
                for m in re.finditer(r"FAILED\s+([^\s:]+\.py)", content):
                    f = m.group(1)
                    failing_files[f] = failing_files.get(f, 0) + 1
                # jest/vitest: FAIL path/to/test.spec.ts
                for m in re.finditer(
                    r"FAIL\s+([^\s]+\.(?:test|spec)\.[jt]sx?)", content
                ):
                    f = m.group(1)
                    failing_files[f] = failing_files.get(f, 0) + 1

    # ── Compute summary KPIs ─────────────────────────────────────────────
    total_test_runs = len(test_runs)
    passed_runs = sum(1 for r in test_runs if r.get("passed"))
    failed_runs = total_test_runs - passed_runs
    pass_rate = (passed_runs / total_test_runs * 100) if total_test_runs > 0 else 0

    total_bugfix_cycles = sum(
        ms.get("bugfix_cycle", 0) for ms in milestone_states.values()
    )
    total_test_fix_cycles = sum(
        ms.get("test_fix_cycle", 0) for ms in milestone_states.values()
    )
    total_fix_cycles = total_bugfix_cycles + total_test_fix_cycles

    durations = [r.get("duration_s", 0) for r in test_runs if r.get("duration_s")]
    avg_duration = sum(durations) / len(durations) if durations else 0
    total_test_time = sum(durations)

    qa_pass_count = sum(1 for v in qa_verdicts if v.get("verdict") == "PASS")
    qa_fail_count = sum(1 for v in qa_verdicts if v.get("verdict") == "FAIL")
    qa_first_pass = 0  # milestones that passed QA on first attempt (cycle 0)
    for v in qa_verdicts:
        if v.get("verdict") == "PASS" and v.get("cycle", 0) == 0:
            qa_first_pass += 1

    # ── Per-milestone breakdown ──────────────────────────────────────────
    milestones_analytics: list[dict] = []
    all_milestone_ids = sorted(
        set(
            list(milestone_states.keys())
            + [r.get("milestone", 0) for r in test_runs]
            + [v.get("milestone", 0) for v in qa_verdicts]
        )
    )

    for mid in all_milestone_ids:
        if mid == 0:
            continue  # Skip phase 0

        ms_state = milestone_states.get(mid, {})
        ms_test_runs = [r for r in test_runs if r.get("milestone") == mid]
        ms_verdicts = [v for v in qa_verdicts if v.get("milestone") == mid]
        ms_passed = sum(1 for r in ms_test_runs if r.get("passed"))
        ms_failed = len(ms_test_runs) - ms_passed
        ms_durations = [r.get("duration_s", 0) for r in ms_test_runs if r.get("duration_s")]

        # Determine final QA outcome
        final_verdict = "pending"
        if ms_verdicts:
            final_verdict = ms_verdicts[-1].get("verdict", "UNKNOWN")

        milestones_analytics.append({
            "id": mid,
            "name": milestone_names.get(mid, f"Milestone {mid}"),
            "phase": ms_state.get("phase", "pending"),
            "bugfix_cycles": ms_state.get("bugfix_cycle", 0),
            "test_fix_cycles": ms_state.get("test_fix_cycle", 0),
            "test_runs": len(ms_test_runs),
            "tests_passed": ms_passed,
            "tests_failed": ms_failed,
            "pass_rate": (ms_passed / len(ms_test_runs) * 100) if ms_test_runs else 0,
            "total_duration_s": sum(ms_durations),
            "avg_duration_s": sum(ms_durations) / len(ms_durations) if ms_durations else 0,
            "qa_verdicts": len(ms_verdicts),
            "final_verdict": final_verdict,
            "first_pass": any(
                v.get("verdict") == "PASS" and v.get("cycle", 0) == 0
                for v in ms_verdicts
            ),
        })

    # ── Enforcement point breakdown ──────────────────────────────────────
    enforcement_points = {
        "qa_review": {"label": "QA Review (Phase 3)", "runs": 0, "passed": 0, "failed": 0},
        "test_fix": {"label": "Test Fix Cycles", "runs": 0, "passed": 0, "failed": 0},
    }
    for r in test_runs:
        phase = r.get("phase", "unknown")
        if phase in enforcement_points:
            enforcement_points[phase]["runs"] += 1
            if r.get("passed"):
                enforcement_points[phase]["passed"] += 1
            else:
                enforcement_points[phase]["failed"] += 1

    # ── Timeline events (for chart) ──────────────────────────────────────
    timeline: list[dict] = []
    for r in test_runs:
        timeline.append({
            "ts": r.get("ts", ""),
            "type": "test_run",
            "milestone": r.get("milestone", 0),
            "cycle": r.get("cycle", 0),
            "passed": r.get("passed", False),
            "duration_s": r.get("duration_s", 0),
        })
    for v in qa_verdicts:
        timeline.append({
            "ts": v.get("ts", ""),
            "type": "qa_verdict",
            "milestone": v.get("milestone", 0),
            "cycle": v.get("cycle", 0),
            "verdict": v.get("verdict", "UNKNOWN"),
        })
    timeline.sort(key=lambda e: e.get("ts", ""))

    # ── Top failing files ────────────────────────────────────────────────
    top_failing = sorted(
        [{"file": f, "failures": c} for f, c in failing_files.items()],
        key=lambda x: x["failures"],
        reverse=True,
    )[:15]

    return jsonify({
        "summary": {
            "total_test_runs": total_test_runs,
            "passed": passed_runs,
            "failed": failed_runs,
            "pass_rate": round(pass_rate, 1),
            "total_fix_cycles": total_fix_cycles,
            "total_bugfix_cycles": total_bugfix_cycles,
            "total_test_fix_cycles": total_test_fix_cycles,
            "avg_duration_s": round(avg_duration, 2),
            "total_test_time_s": round(total_test_time, 2),
            "qa_pass_count": qa_pass_count,
            "qa_fail_count": qa_fail_count,
            "qa_first_pass_count": qa_first_pass,
            "max_bugfix_cycles": max_bugfix_cycles,
        },
        "milestones": milestones_analytics,
        "enforcement_points": list(enforcement_points.values()),
        "timeline": timeline,
        "top_failing_files": top_failing,
        "qa_reports": qa_report_details,
    })
