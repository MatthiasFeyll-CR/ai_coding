"""Deterministic reconciliation — catches structural spec drift without AI.

Compares file paths and directory structures mentioned in architecture/design
docs against the actual project tree.  Produces a machine-readable drift
report that supplements (or replaces, on AI failure) the AI reconciler.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ralph_pipeline.log import PipelineLogger


@dataclass
class DriftItem:
    """A single detected drift between specs and reality."""

    category: str  # "file_path" | "directory"
    spec_file: str  # Which spec doc references it
    expected: str  # What the spec says
    actual: str  # What actually exists (or "MISSING")
    severity: str = "info"  # "info" | "warning"


@dataclass
class DriftReport:
    """Result of deterministic reconciliation scan."""

    items: list[DriftItem] = field(default_factory=list)
    scanned_docs: int = 0

    @property
    def has_drift(self) -> bool:
        return len(self.items) > 0

    def summary(self) -> str:
        if not self.items:
            return f"No structural drift detected ({self.scanned_docs} docs scanned)"
        lines = [
            f"Structural drift detected: {len(self.items)} item(s) "
            f"across {self.scanned_docs} docs"
        ]
        for item in self.items:
            lines.append(
                f"  [{item.severity.upper()}] {item.category}: "
                f"'{item.expected}' in {item.spec_file} → {item.actual}"
            )
        return "\n".join(lines)


# Patterns to extract file/directory references from markdown docs
# Matches paths like `src/foo/bar.py`, `./config/settings.ts`, etc.
_PATH_PATTERN = re.compile(
    r"(?:^|\s|`)"  # preceded by whitespace, start, or backtick
    r"((?:\.?/)?(?:src|lib|app|config|tests?|docs?|public|assets|api|backend|frontend|scripts)"
    r"(?:/[\w.\-]+)+)"  # at least one more path segment
    r"(?:`|\s|$|[),])",  # followed by whitespace, end, backtick, etc.
    re.MULTILINE,
)


def _extract_paths_from_doc(content: str) -> set[str]:
    """Extract file/directory path references from a markdown document."""
    paths: set[str] = set()
    for match in _PATH_PATTERN.finditer(content):
        path = match.group(1).strip("`").strip()
        # Normalize leading ./
        if path.startswith("./"):
            path = path[2:]
        paths.add(path)
    return paths


def _scan_doc_for_drift(
    doc_path: Path,
    project_root: Path,
) -> list[DriftItem]:
    """Scan a single spec doc for file paths that don't exist in the project."""
    items: list[DriftItem] = []

    try:
        content = doc_path.read_text()
    except (OSError, UnicodeDecodeError):
        return items

    referenced_paths = _extract_paths_from_doc(content)
    rel_doc = str(doc_path.relative_to(project_root))

    for ref_path in sorted(referenced_paths):
        full_path = project_root / ref_path
        if not full_path.exists():
            # Check if it's a directory reference (no extension)
            category = "file_path" if "." in Path(ref_path).name else "directory"
            items.append(
                DriftItem(
                    category=category,
                    spec_file=rel_doc,
                    expected=ref_path,
                    actual="MISSING",
                    severity="warning",
                )
            )

    return items


def run_deterministic_reconciliation(
    project_root: Path,
    docs_dir: str,
    recon_dir: Path,
    milestone_id: int,
    plogger: PipelineLogger,
) -> DriftReport:
    """Scan spec docs for structural drift against actual project files.

    Checks architecture, design, and integration docs for file path
    references that no longer exist in the project tree.

    Writes results to ``recon_dir/mN-deterministic-drift.md``.
    """
    report = DriftReport()
    docs_root = project_root / docs_dir

    if not docs_root.exists():
        plogger.info("No docs directory found — skipping deterministic reconciliation")
        return report

    # Scan all markdown files in docs/
    doc_files = sorted(docs_root.rglob("*.md"))
    report.scanned_docs = len(doc_files)

    for doc_path in doc_files:
        # Skip reconciliation's own output files
        if "05-reconciliation" in str(doc_path):
            continue
        items = _scan_doc_for_drift(doc_path, project_root)
        report.items.extend(items)

    # Write report
    if report.has_drift:
        recon_dir.mkdir(parents=True, exist_ok=True)
        report_path = recon_dir / f"m{milestone_id}-deterministic-drift.md"
        lines = [
            f"# Deterministic Drift Report — M{milestone_id}",
            "",
            f"Scanned {report.scanned_docs} spec documents.",
            f"Found {len(report.items)} structural drift(s).",
            "",
            "| Severity | Category | Spec File | Expected Path | Status |",
            "|----------|----------|-----------|---------------|--------|",
        ]
        for item in report.items:
            lines.append(
                f"| {item.severity} | {item.category} | {item.spec_file} "
                f"| `{item.expected}` | {item.actual} |"
            )
        lines.append("")
        report_path.write_text("\n".join(lines))
        plogger.warning(report.summary())
    else:
        plogger.info(report.summary())

    return report
