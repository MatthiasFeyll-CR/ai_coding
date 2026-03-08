"""Domain context loading for fix prompts.

Reads .ralph/context.md and extracts high-value sections so that
test-fix, regression-fix, and gate-fix prompts have architectural
awareness instead of operating blind on error output alone.
"""

from __future__ import annotations

import re
from pathlib import Path

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


def _parse_sections(text: str) -> list[tuple[str, int, int]]:
    """Return (section_name, start_line, end_line) for each ``## Section`` header.

    Lines are 0-indexed.  ``end_line`` is exclusive.
    Reuses the same logic as context_validator._parse_sections.
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

    sections = _parse_sections(text)
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
