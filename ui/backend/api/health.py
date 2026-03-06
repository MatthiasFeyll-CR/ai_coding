"""Health check API endpoints."""

import subprocess

from database import db
from flask import Blueprint, jsonify
from models import RequirementCheck

bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])
def health_check():
    """Basic health check."""
    return jsonify({"status": "ok", "service": "ralph-pipeline-ui"})


@bp.route("/requirements/check", methods=["POST"])
def check_requirements():
    """Check system requirements."""
    checks = []

    # Python
    checks.append(_check_command("python", "python3 --version"))

    # Docker
    checks.append(_check_command("docker", "docker --version"))

    # Docker Compose
    checks.append(_check_command("docker-compose", "docker compose version"))

    # Ralph Pipeline CLI
    checks.append(_check_command("ralph-pipeline", "ralph-pipeline --version"))

    # Claude CLI
    checks.append(_check_command("claude", "claude --version"))

    # Git
    checks.append(_check_command("git", "git --version"))

    # Node.js
    checks.append(_check_command("nodejs", "node --version"))

    # Save results to database
    for check in checks:
        record = RequirementCheck(
            requirement_name=check["name"],
            status=check["status"],
            details=check.get("details"),
        )
        db.session.add(record)

    db.session.commit()

    all_passed = all(c["status"] == "passed" for c in checks)

    return jsonify({"status": "passed" if all_passed else "failed", "checks": checks})


@bp.route("/requirements/status", methods=["GET"])
def get_requirements_status():
    """Get last requirement check results."""
    checks = (
        RequirementCheck.query.order_by(RequirementCheck.checked_at.desc())
        .limit(20)
        .all()
    )
    return jsonify([c.to_dict() for c in checks])


def _check_command(name, command):
    """Check if a command is available."""
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {
                "name": name,
                "status": "passed",
                "details": result.stdout.strip(),
            }
        else:
            return {
                "name": name,
                "status": "failed",
                "details": result.stderr.strip(),
            }
    except FileNotFoundError:
        return {
            "name": name,
            "status": "failed",
            "details": f"{name} not found in PATH",
        }
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "status": "failed",
            "details": "Command timed out",
        }
    except Exception as e:
        return {
            "name": name,
            "status": "failed",
            "details": str(e),
        }
