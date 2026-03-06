"""File browsing API endpoints."""

from pathlib import Path

from flask import Blueprint, jsonify
from models import Project

bp = Blueprint("files", __name__)


@bp.route("/<int:project_id>/tree", methods=["GET"])
def get_file_tree(project_id):
    """Get project file tree."""
    project = Project.query.get_or_404(project_id)
    root = Path(project.root_path)

    if not root.exists():
        return jsonify({"error": "Project path not found"}), 404

    def build_tree(path, depth=0, max_depth=3):
        """Build directory tree recursively."""
        if depth > max_depth:
            return None

        result = {
            "name": path.name,
            "path": str(path.relative_to(root)),
            "type": "directory" if path.is_dir() else "file",
        }

        if path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir()):
                    # Skip hidden dirs and common ignores
                    if child.name.startswith(".") and child.name != ".ralph":
                        continue
                    if child.name in (
                        "node_modules",
                        "__pycache__",
                        ".git",
                        "venv",
                    ):
                        continue

                    child_tree = build_tree(child, depth + 1, max_depth)
                    if child_tree:
                        children.append(child_tree)
            except PermissionError:
                pass
            result["children"] = children

        else:
            result["size"] = path.stat().st_size

        return result

    tree = build_tree(root)
    return jsonify(tree)


@bp.route("/<int:project_id>/read", methods=["GET"])
def read_file(project_id):
    """Read a project file."""
    from flask import request

    project = Project.query.get_or_404(project_id)
    file_path = request.args.get("path")

    if not file_path:
        return jsonify({"error": "path parameter required"}), 400

    full_path = Path(project.root_path) / file_path

    # Security: ensure file is within project root
    try:
        full_path.resolve().relative_to(Path(project.root_path).resolve())
    except ValueError:
        return jsonify({"error": "Access denied"}), 403

    if not full_path.exists():
        return jsonify({"error": "File not found"}), 404

    if not full_path.is_file():
        return jsonify({"error": "Not a file"}), 400

    # Check file size (max 1MB)
    if full_path.stat().st_size > 1_000_000:
        return jsonify({"error": "File too large"}), 413

    try:
        content = full_path.read_text(encoding="utf-8")
        return jsonify(
            {
                "path": file_path,
                "content": content,
                "size": full_path.stat().st_size,
            }
        )
    except UnicodeDecodeError:
        return jsonify({"error": "Binary file not supported"}), 415
