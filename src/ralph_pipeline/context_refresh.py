"""Context management for .ralph/context.md.

Provides:
- Bugfix-cycle context refresh (stale snapshot replacement + bugfix section).
- Domain context extraction for fix prompts (architecture, design, test specs).
- Type/lint config loading for gate fix prompts.
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
    regression_context: str = "",
) -> None:
    """Refresh context.md before a bugfix cycle.

    1. Strip the stale Codebase Snapshot section.
    2. Strip any previous Bugfix Context section.
    3. Regenerate the Codebase Snapshot from PRD file paths.
    4. Append a Bugfix Context section with QA summary, diff stats,
       and regression classification (if available).

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

    # Include regression classification if available
    if regression_context:
        bugfix_ctx += "\n" + regression_context + "\n"

    content += bugfix_ctx

    context_md.write_text(content)
    plogger.info("context.md refreshed with current codebase snapshot and bugfix context")


# ── Domain context extraction for fix prompts ────────────────────────────

# Sections to extract from context.md for fix prompts, in priority order.
_FIX_RELEVANT_SECTIONS = [
    "Architecture Reference",
    "Design Reference",
    "Test Specifications",
    "Codebase Patterns",
    "Quality Checks",
]

# Common type-config filenames to look for when fixing gate errors.
_TYPE_CONFIG_FILES = [
    "tsconfig.json",
    "pyproject.toml",
    "setup.cfg",
    ".eslintrc.json",
    ".eslintrc.js",
    "tslint.json",
    "mypy.ini",
    ".mypy.ini",
]


def _parse_context_sections(text: str) -> list[tuple[str, int, int]]:
    """Return (section_name, start_line, end_line) for each ``## Section`` header.

    Lines are 0-indexed.  ``end_line`` is exclusive.
    """
    lines = text.splitlines()
    sections: list[tuple[str, int, int]] = []
    header_re = re.compile(r"^##\s+(.+)")

    for i, line in enumerate(lines):
        m = header_re.match(line)
        if m:
            name = m.group(1).strip()
            if sections:
                prev_name, prev_start, _ = sections[-1]
                sections[-1] = (prev_name, prev_start, i)
            sections.append((name, i, len(lines)))
    return sections


def load_domain_context(project_root: str | Path, max_lines: int = 800) -> str:
    """Load relevant domain context sections from .ralph/context.md.

    Extracts Architecture Reference, Design Reference, Test Specifications,
    Codebase Patterns, and Quality Checks — truncated to *max_lines* total.

    Returns an empty string if context.md doesn't exist or has no
    relevant sections.
    """
    context_path = Path(project_root) / ".ralph" / "context.md"
    if not context_path.exists():
        return ""

    try:
        text = context_path.read_text()
    except OSError:
        return ""

    if not text.strip():
        return ""

    sections = _parse_context_sections(text)
    all_lines = text.splitlines()

    extracted: list[str] = []
    remaining = max_lines

    for section_name in _FIX_RELEVANT_SECTIONS:
        if remaining <= 0:
            break
        for name, start, end in sections:
            if name == section_name:
                section_lines = all_lines[start:end]
                if len(section_lines) > remaining:
                    section_lines = section_lines[:remaining]
                    section_lines.append(
                        f"<!-- truncated: {name} exceeded fix context budget -->"
                    )
                extracted.extend(section_lines)
                remaining -= len(section_lines)
                break

    return "\n".join(extracted) if extracted else ""


def load_type_config(project_root: str | Path) -> str:
    """Load type/lint configuration files for gate fix context.

    Searches for common config files (tsconfig.json, pyproject.toml, etc.)
    and returns their contents concatenated with file headers.

    Returns an empty string if no config files are found.
    """
    root = Path(project_root)
    parts: list[str] = []

    for filename in _TYPE_CONFIG_FILES:
        config_path = root / filename
        if config_path.exists():
            try:
                content = config_path.read_text()
                # Skip very large config files (> 200 lines)
                if len(content.splitlines()) > 200:
                    parts.append(
                        f"### {filename}\n"
                        f"*(file too large — {len(content.splitlines())} lines, omitted)*\n"
                    )
                else:
                    parts.append(f"### {filename}\n```\n{content}\n```\n")
            except OSError:
                continue

    return "\n".join(parts) if parts else ""
