"""Execution-time context bundle validation and truncation.

Validates .ralph/context.md after PRD generation to prevent silent
context-window overflow that degrades Ralph's code quality.

Behaviour per milestone iteration:
  1. Warn at ``warn_pct`` % of limits.
  2. On first exceed → auto-truncate low-priority sections.
  3. On second exceed (after truncation already applied) → abort.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ralph_pipeline.config import ContextLimitsConfig


class ContextOverflowError(Exception):
    """Raised when the context bundle exceeds limits after truncation was already applied."""

    pass


# ── Section priority (highest = kept, lowest = truncated first) ──────────
# Order matters: index 0 = highest priority (never truncated).
# NOTE: Quality commands are NOT in context.md — they are injected at
# runtime into CLAUDE.md footer from pipeline-config.json (single source
# of truth).
SECTION_PRIORITY = [
    "Test Infrastructure Setup",
    "Test Specifications",
    "Architecture Reference",
    "Design Reference",
    "AI Reference",
    "Browser Testing",
    "Codebase Patterns",
    "Codebase Snapshot",
]


@dataclass
class ContextMetrics:
    """Measured size of the context bundle."""

    lines: int
    tokens_est: int  # lines × tokens_per_line
    path: Path

    # per-section line counts (section_name → line_count)
    section_sizes: dict[str, int] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Outcome of context bundle validation."""

    status: str  # "ok" | "warned" | "truncated" | "abort"
    metrics: ContextMetrics
    message: str = ""
    truncated_sections: list[str] = field(default_factory=list)


# ── Measurement ──────────────────────────────────────────────────────────


def _parse_sections(text: str) -> list[tuple[str, int, int]]:
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
            # Close the previous section
            if sections:
                prev_name, prev_start, _ = sections[-1]
                sections[-1] = (prev_name, prev_start, i)
            sections.append((name, i, len(lines)))
    return sections


def measure_bundle(path: Path, tokens_per_line: float = 4.5) -> ContextMetrics:
    """Measure the context bundle and return metrics."""
    text = path.read_text()
    lines = text.splitlines()
    line_count = len(lines)

    sections = _parse_sections(text)
    section_sizes = {}
    for name, start, end in sections:
        section_sizes[name] = end - start

    return ContextMetrics(
        lines=line_count,
        tokens_est=int(line_count * tokens_per_line),
        path=path,
        section_sizes=section_sizes,
    )


# ── Truncation ───────────────────────────────────────────────────────────

_TRUNCATION_MARKER = (
    "\n<!-- [context-validator] section truncated to fit context limits -->\n"
)

_SNAPSHOT_SUMMARY_HEADER = (
    "<!-- Summarised by context-validator: file contents omitted, tree retained -->"
)


def _summarise_snapshot_section(section_text: str) -> str:
    """Keep the file-tree block but replace individual file contents with a note."""
    out_lines: list[str] = []
    in_file_block = False
    in_code_fence = False
    kept_tree = False

    for line in section_text.splitlines():
        # Detect code fences
        if line.strip().startswith("```"):
            if in_code_fence:
                in_code_fence = False
                if in_file_block:
                    in_file_block = False
                    continue  # drop closing fence of file content
                out_lines.append(line)
                continue
            else:
                in_code_fence = True
                if not kept_tree and "File Tree" not in "".join(out_lines[-3:]):
                    pass  # keep first code block (likely tree)

        # Keep the tree section and headers
        if line.startswith("### File Tree") or line.startswith("## Codebase Snapshot"):
            out_lines.append(line)
            kept_tree = False  # reset for tree detection
            continue

        # Keep file path headers but replace contents
        if line.startswith("### ") and ("exists" in line or "to be created" in line):
            out_lines.append(line)
            if "exists" in line:
                out_lines.append("*(file contents omitted — see actual file)*")
            in_file_block = True
            continue

        if in_file_block:
            continue  # Skip file contents

        out_lines.append(line)

    return "\n".join(out_lines)


def _summarise_patterns_section(section_text: str) -> str:
    """Collapse codebase patterns to a compact bullet list."""
    lines = section_text.splitlines()
    header = lines[0] if lines else ""
    bullets = [line for line in lines[1:] if line.strip().startswith("- ")]
    # Keep first 10 bullets, summarise rest
    if len(bullets) > 10:
        kept = bullets[:10]
        return (
            header
            + "\n"
            + "\n".join(kept)
            + f"\n- *(… {len(bullets) - 10} more patterns omitted)*\n"
        )
    return section_text


def truncate_bundle(
    path: Path,
    limits: ContextLimitsConfig,
) -> list[str]:
    """Truncate low-priority sections in-place to bring the bundle under limits.

    Returns list of truncated section names.
    """
    text = path.read_text()
    lines_list = text.splitlines()
    sections = _parse_sections(text)

    # Build a name → (start, end) index map
    sec_map: dict[str, tuple[int, int]] = {
        name: (start, end) for name, start, end in sections
    }

    truncated: list[str] = []

    # Iterate from lowest priority to highest
    for sec_name in reversed(SECTION_PRIORITY):
        # Find the matching section (may have extra text like "(from previous milestones)")
        matched_key = None
        for key in sec_map:
            if sec_name.lower() in key.lower():
                matched_key = key
                break
        if matched_key is None:
            continue

        start, end = sec_map[matched_key]
        section_text = "\n".join(lines_list[start:end])

        if "Codebase Snapshot" in matched_key:
            replacement = (
                lines_list[start]
                + "\n"
                + _SNAPSHOT_SUMMARY_HEADER
                + "\n"
                + _summarise_snapshot_section(section_text)
            )
        elif "Codebase Patterns" in matched_key:
            replacement = _summarise_patterns_section(section_text)
        else:
            # Generic: keep header + first 5 lines, add truncation marker
            keep = lines_list[start : min(start + 6, end)]
            replacement = "\n".join(keep) + _TRUNCATION_MARKER

        replacement_lines = replacement.splitlines()
        lines_list[start:end] = replacement_lines
        truncated.append(matched_key)

        # Recompute — offsets shifted
        new_count = len(lines_list)
        est_tokens = int(new_count * limits.tokens_per_line)

        if new_count <= limits.max_lines and est_tokens <= limits.max_tokens:
            break

    # Write the truncated file
    path.write_text("\n".join(lines_list))
    return truncated


# ── Main validation entry point ──────────────────────────────────────────


def validate_context_bundle(
    bundle_path: Path,
    limits: ContextLimitsConfig,
    already_truncated: bool = False,
) -> ValidationResult:
    """Validate the context bundle against configured limits.

    Args:
        bundle_path: Path to .ralph/context.md
        limits: Configured size limits.
        already_truncated: True if truncation was already applied in this
            milestone iteration (second exceed → abort).

    Returns:
        ValidationResult with status and metrics.

    Raises:
        ContextOverflowError: If the bundle still exceeds limits after a
            prior truncation pass.
    """
    if not bundle_path.exists():
        return ValidationResult(
            status="missing",
            metrics=ContextMetrics(lines=0, tokens_est=0, path=bundle_path),
            message="Context bundle not found",
        )

    metrics = measure_bundle(bundle_path, limits.tokens_per_line)

    warn_lines = int(limits.max_lines * limits.warn_pct / 100)
    warn_tokens = int(limits.max_tokens * limits.warn_pct / 100)

    lines_exceeded = metrics.lines > limits.max_lines
    tokens_exceeded = metrics.tokens_est > limits.max_tokens
    exceeded = lines_exceeded or tokens_exceeded

    lines_warned = metrics.lines > warn_lines
    tokens_warned = metrics.tokens_est > warn_tokens
    warned = lines_warned or tokens_warned

    if exceeded:
        if already_truncated:
            msg = (
                f"Context bundle still exceeds limits after truncation "
                f"({metrics.lines} lines / ~{metrics.tokens_est} tokens). "
                f"Limits: {limits.max_lines} lines / {limits.max_tokens} tokens. "
                f"Milestone must be split — aborting."
            )
            raise ContextOverflowError(msg)

        # First exceed → truncate
        truncated_sections = truncate_bundle(bundle_path, limits)
        new_metrics = measure_bundle(bundle_path, limits.tokens_per_line)

        # Check if truncation brought it under limits
        still_over = (
            new_metrics.lines > limits.max_lines
            or new_metrics.tokens_est > limits.max_tokens
        )
        if still_over:
            msg = (
                f"Context bundle still exceeds limits after truncation "
                f"({new_metrics.lines} lines / ~{new_metrics.tokens_est} tokens). "
                f"Limits: {limits.max_lines} lines / {limits.max_tokens} tokens. "
                f"Milestone must be split — aborting."
            )
            raise ContextOverflowError(msg)

        return ValidationResult(
            status="truncated",
            metrics=new_metrics,
            message=(
                f"Context bundle truncated: {metrics.lines}→{new_metrics.lines} lines, "
                f"~{metrics.tokens_est}→~{new_metrics.tokens_est} tokens. "
                f"Sections truncated: {', '.join(truncated_sections)}"
            ),
            truncated_sections=truncated_sections,
        )

    if warned:
        return ValidationResult(
            status="warned",
            metrics=metrics,
            message=(
                f"Context bundle approaching limits: "
                f"{metrics.lines}/{limits.max_lines} lines "
                f"(~{metrics.tokens_est}/{limits.max_tokens} tokens). "
                f"Threshold: {limits.warn_pct}%"
            ),
        )

    return ValidationResult(
        status="ok",
        metrics=metrics,
        message=(
            f"Context bundle OK: {metrics.lines} lines, "
            f"~{metrics.tokens_est} tokens"
        ),
    )
