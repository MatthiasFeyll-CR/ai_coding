"""Bugfix-cycle context refresh for .ralph/context.md.

When QA fails and the pipeline enters a bugfix cycle, the Codebase Snapshot
section of context.md is stale — it reflects the pre-Phase-2 state, not the
code Ralph wrote.  This module surgically refreshes that section and appends
a Bugfix Context section with QA failure summaries and a change overview.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.log import PipelineLogger

# ── Constants ────────────────────────────────────────────────────────────

_SNAPSHOT_HEADER = "## Codebase Snapshot"
_BUGFIX_HEADER = "## Bugfix Context"
_MAX_FILE_LINES = 200


# ── PRD file-path extraction ─────────────────────────────────────────────


def _extract_file_paths_from_prd(prd_path: Path) -> list[str]:
    """Extract file paths from PRD story ``Files:`` fields.

    Parses the ``notes`` string of each story, looking for lines that start
    with ``Files:`` and extracting comma-separated file paths.
    """
    try:
        data = json.loads(prd_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    paths: set[str] = set()
    files_re = re.compile(r"^Files:\s*(.+)", re.MULTILINE)

    for story in data.get("userStories", []):
        notes = story.get("notes", "")
        if not isinstance(notes, str):
            continue
        for m in files_re.finditer(notes):
            raw = m.group(1)
            for segment in raw.split(","):
                cleaned = segment.strip().strip("`").strip()
                if cleaned:
                    paths.add(cleaned)

    return sorted(paths)


# ── Snapshot regeneration ────────────────────────────────────────────────


def _build_file_tree(project_root: Path, max_depth: int = 3) -> str:
    """Build a project file tree string (top N levels), ignoring common junk."""
    ignore = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist",
        ".egg-info", ".tox", "htmlcov",
    }
    lines: list[str] = []

    def _walk(current: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return
        dirs = [e for e in entries if e.is_dir() and e.name not in ignore
                and not e.name.endswith(".egg-info")]
        files = [e for e in entries if e.is_file()]

        for f in files:
            lines.append(f"{prefix}{f.name}")
        for d in dirs:
            lines.append(f"{prefix}{d.name}/")
            _walk(d, prefix + "  ", depth + 1)

    _walk(project_root, "", 1)
    return "\n".join(lines)


def _snapshot_file(file_path: Path, project_root: Path) -> str:
    """Return a snapshot entry for a single file."""
    rel = file_path.relative_to(project_root) if file_path.is_absolute() else file_path
    if not file_path.exists():
        return f"### {rel} (to be created)\n*File does not exist yet.*\n"

    try:
        content = file_path.read_text()
    except (OSError, UnicodeDecodeError):
        return f"### {rel} (exists)\n*Unable to read file contents.*\n"

    file_lines = content.splitlines()
    if len(file_lines) > _MAX_FILE_LINES:
        truncated = "\n".join(file_lines[:_MAX_FILE_LINES])
        return (
            f"### {rel} (exists — first {_MAX_FILE_LINES} of {len(file_lines)} lines)\n"
            f"```\n{truncated}\n```\n"
            f"*(truncated — {len(file_lines) - _MAX_FILE_LINES} lines omitted)*\n"
        )

    return f"### {rel} (exists)\n```\n{content}\n```\n"


def _build_codebase_snapshot(
    project_root: Path, file_paths: list[str]
) -> str:
    """Build a fresh Codebase Snapshot section from file paths."""
    parts: list[str] = [_SNAPSHOT_HEADER, ""]

    # File tree
    parts.append("### File Tree")
    parts.append("```")
    parts.append(_build_file_tree(project_root))
    parts.append("```")
    parts.append("")

    # Individual file snapshots
    for fp in file_paths:
        resolved = project_root / fp
        parts.append(_snapshot_file(resolved, project_root))

    return "\n".join(parts)


# ── QA summary extraction ───────────────────────────────────────────────


def _summarise_qa_report(qa_report_path: Path, max_lines: int = 30) -> str:
    """Extract a summary from the QA report.

    Returns the first ``max_lines`` non-empty lines, plus the verdict line.
    """
    if not qa_report_path.exists():
        return "No QA report available."

    text = qa_report_path.read_text()
    lines = [line for line in text.splitlines() if line.strip()]

    # Find verdict line
    verdict_line = ""
    for line in lines:
        if re.search(r"(verdict|result)[:\s*]*\s*(pass|fail)", line, re.IGNORECASE):
            verdict_line = line
            break

    summary_lines = lines[:max_lines]
    if verdict_line and verdict_line not in summary_lines:
        summary_lines.append("...")
        summary_lines.append(verdict_line)

    if len(lines) > max_lines:
        summary_lines.append(f"*(... {len(lines) - max_lines} more lines in full report)*")

    return "\n".join(summary_lines)


# ── Bugfix context section ───────────────────────────────────────────────


def _build_bugfix_context(
    milestone_id: int,
    cycle: int,
    qa_report_path: Path,
    git: GitOps,
    branch: str,
) -> str:
    """Build the ``## Bugfix Context`` section appended during bugfix cycles."""
    parts: list[str] = [
        _BUGFIX_HEADER,
        "",
        f"> Auto-generated by pipeline before bugfix cycle {cycle}.",
        f"> Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        "",
        "### QA Failure Summary",
        "",
        _summarise_qa_report(qa_report_path),
        "",
        "### Changes Since Phase 2 Start",
        "",
        "Files modified/added by Ralph during Phase 2 implementation:",
        "",
        "```",
    ]

    try:
        diff_stat = git.diff_stat("main", branch)
        parts.append(diff_stat if diff_stat.strip() else "(no diff available)")
    except Exception:
        parts.append("(unable to compute diff)")

    parts.extend([
        "```",
        "",
        "### Instructions",
        "",
        "- The **Codebase Snapshot** above has been refreshed to reflect the current file state.",
        "- Consult `progress.txt` for per-story implementation details from Phase 2.",
        "- Focus on the **QA failure notes** in the PRD (`passes: false` stories).",
        "- Trust the **actual codebase** if anything in context.md seems inconsistent.",
        "",
    ])

    return "\n".join(parts)


# ── Section replacement helpers ──────────────────────────────────────────


def _remove_section(text: str, header: str) -> str:
    """Remove a ``## Section`` and all content up to the next ``## `` header."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(header):
            skipping = True
            continue
        if skipping and re.match(r"^## ", stripped):
            skipping = False
        if not skipping:
            out.append(line)

    return "".join(out)


# ── Main entry point ─────────────────────────────────────────────────────


def refresh_context_for_bugfix(
    project_root: Path,
    config: PipelineConfig,
    milestone_id: int,
    cycle: int,
    git: GitOps,
    plogger: PipelineLogger,
    qa_report_path: Path | None = None,
) -> None:
    """Refresh context.md before a bugfix cycle.

    1. Strip the stale Codebase Snapshot section.
    2. Strip any previous Bugfix Context section.
    3. Regenerate the Codebase Snapshot from PRD file paths.
    4. Append a Bugfix Context section with QA summary and diff stats.

    All other sections (Architecture, Design, Tests, Quality Checks, etc.)
    are left untouched.
    """
    scripts_dir = project_root / config.paths.scripts_dir
    tasks_dir = project_root / config.paths.tasks_dir
    context_md = scripts_dir / "context.md"

    if not context_md.exists():
        plogger.warning("context.md not found — skipping bugfix context refresh")
        return

    milestone_cfg = None
    for m in config.milestones:
        if m.id == milestone_id:
            milestone_cfg = m
            break
    slug = milestone_cfg.slug if milestone_cfg else "unknown"
    branch = f"ralph/m{milestone_id}-{slug}"

    # Read PRD to get file paths
    prd_path = tasks_dir / f"prd-m{milestone_id}.json"
    file_paths = _extract_file_paths_from_prd(prd_path)

    plogger.info(
        f"Refreshing context.md for bugfix cycle {cycle} "
        f"({len(file_paths)} files from PRD)"
    )

    # Read and strip stale sections
    content = context_md.read_text()
    content = _remove_section(content, _SNAPSHOT_HEADER)
    content = _remove_section(content, _BUGFIX_HEADER)

    # Ensure trailing newline before appending
    content = content.rstrip("\n") + "\n\n"

    # Regenerate snapshot
    snapshot = _build_codebase_snapshot(project_root, file_paths)
    content += snapshot + "\n\n"

    # Append bugfix context
    qa_path = qa_report_path
    if qa_path is None:
        qa_dir = project_root / config.paths.qa_dir
        qa_path = qa_dir / f"qa-m{milestone_id}-{slug}.md"

    bugfix_ctx = _build_bugfix_context(
        milestone_id=milestone_id,
        cycle=cycle,
        qa_report_path=qa_path,
        git=git,
        branch=branch,
    )
    content += bugfix_ctx

    context_md.write_text(content)
    plogger.info("context.md refreshed with current codebase snapshot and bugfix context")
