"""Phase 3: QA Review — runs QA engineer with test results and coverage.

Bash reference: run_qa() in pipeline.sh lines 1404-1524.
"""

from __future__ import annotations

import ast
import json
import logging
import re
import time
from pathlib import Path

_log = logging.getLogger(__name__)

from ralph_pipeline.ai.claude import ClaudeError, ClaudeRunner
from ralph_pipeline.ai.prompts import qa_review_prompt
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.infra.test_runner import TestRunner
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.phases.ralph_execution import run_ralph_bugfix
from ralph_pipeline.subprocess_utils import is_dry_run
from ralph_pipeline.usage import EventLogger


def _extract_verdict(qa_report: Path) -> str:
    """Extract PASS/FAIL verdict from QA report."""
    if not qa_report.exists():
        return "MISSING"
    text = qa_report.read_text()
    if re.search(r"(verdict|result)[:\s*]*\s*pass", text, re.IGNORECASE):
        return "PASS"
    if re.search(r"(verdict|result)[:\s*]*\s*fail", text, re.IGNORECASE):
        return "FAIL"
    return "UNKNOWN"


_TEST_ID_PATTERN = re.compile(
    r"\b(T-[\d.]+|API-[\d.]+|DB-[\d.]+|UI-[\d.]+|"
    r"LOOP-[\d]+|STATE-[\d]+|TIMEOUT-[\d]+|LEAK-[\d]+|"
    r"INTEGRITY-[\d]+|AI-SAFE-[\d]+|SCN-[\d]+|JOURNEY-[\d]+|"
    r"CONC-[\d]+|ERR-[\d]+)\b"
)


def _extract_milestone_test_ids(prd_path: Path) -> list[str]:
    """Extract test IDs from PRD stories.

    Uses a three-tier strategy (highest priority first):
    1. Structured ``testIds`` array per story (deterministic).
    2. Regex extraction from the ``notes`` string (fallback).
    3. Regex extraction from ``context.test_cases`` entries (fallback).

    Bash reference: _extract_milestone_test_ids() lines 1265-1290.
    """
    try:
        prd = json.loads(prd_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    ids: set[str] = set()

    for story in prd.get("userStories", []):
        story_id = story.get("id", "?")

        # --- Tier 1: structured testIds field (preferred) ---
        test_ids_field = story.get("testIds")
        if isinstance(test_ids_field, list):
            for tid in test_ids_field:
                if isinstance(tid, str) and _TEST_ID_PATTERN.fullmatch(tid):
                    ids.add(tid)
                elif isinstance(tid, str):
                    _log.warning(
                        "Story %s: testIds entry %r does not match "
                        "expected ID pattern — skipped",
                        story_id,
                        tid,
                    )
            # If the structured field is present, skip regex fallback for
            # this story — the structured field is authoritative.
            continue

        # --- Tier 2: regex on notes string (fallback) ---
        notes = story.get("notes", "")
        if not isinstance(notes, str):
            _log.warning(
                "Story %s: 'notes' field is %s, expected str — skipped",
                story_id,
                type(notes).__name__,
            )
        else:
            for m in _TEST_ID_PATTERN.finditer(notes):
                ids.add(m.group(1))

        # --- Tier 3: regex on context.test_cases entries ---
        ctx = story.get("context", {})
        if isinstance(ctx, dict):
            for tc in ctx.get("test_cases", []):
                if isinstance(tc, str):
                    for m in _TEST_ID_PATTERN.finditer(tc):
                        ids.add(m.group(1))

    return sorted(ids)


def _load_test_manifest(project_root: Path) -> dict[str, dict]:
    """Load ``.ralph/test-manifest.json`` if it exists.

    Returns a mapping of test-ID → {"file": ..., "function": ...}.
    """
    manifest_path = project_root / ".ralph" / "test-manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text())
        tests = data.get("tests", {})
        if isinstance(tests, dict):
            return tests
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("Failed to read test manifest: %s", exc)
    return {}


def _ast_search_python_tests(test_id: str, search_dir: Path) -> bool:
    """Use Python AST to search for *test_id* in test function names and docstrings.

    Only scans ``test_*.py`` / ``*_test.py`` files under *search_dir*.
    Returns True if any match is found.
    """
    # Build patterns: exact ID and common normalised forms
    normalised = test_id.replace("-", "_").replace(".", "_").lower()
    patterns = {test_id, test_id.lower(), normalised}

    test_files = list(search_dir.rglob("test_*.py")) + list(
        search_dir.rglob("*_test.py")
    )

    for py_file in test_files:
        try:
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name_lower = node.name.lower()
                # Check function name contains the ID
                if any(p in name_lower for p in patterns):
                    return True
                # Check docstring contains the ID
                docstring = ast.get_docstring(node)
                if docstring:
                    doc_lower = docstring.lower()
                    if any(p in doc_lower for p in patterns):
                        return True

    return False


def _find_implemented_test_ids(
    test_ids: list[str], search_dir: Path, project_root: Path | None = None,
) -> list[str]:
    """Search codebase for test ID references.

    Uses a three-tier strategy (first match wins per ID):
    1. Lookup in ``.ralph/test-manifest.json`` (deterministic).
    2. AST-based search in Python test files (structural).
    3. ``grep`` heuristic across all supported languages (fallback).

    Bash reference: _find_implemented_test_ids() lines 1293-1320.
    """
    from ralph_pipeline.subprocess_utils import SubprocessError, run_command

    manifest = _load_test_manifest(project_root or search_dir)
    found: list[str] = []

    for tid in test_ids:
        # --- Tier 1: manifest lookup ---
        if tid in manifest:
            found.append(tid)
            continue

        # --- Tier 2: AST-based Python search ---
        if _ast_search_python_tests(tid, search_dir):
            found.append(tid)
            continue

        # --- Tier 3: grep fallback (all languages) ---
        # Normalize: T-1.2.01 → T_*1_*2_*01
        pattern = tid.replace("-", "_*").replace(".", "_*")
        try:
            result = run_command(
                f"grep -rlE '({re.escape(tid)}|{pattern})' {search_dir} "
                f"--include='*.py' --include='*.js' --include='*.ts' "
                f"--include='*.tsx' --include='*.jsx' --include='*.go' "
                f"--include='*.rs' --include='*.rb' 2>/dev/null | head -1",
                cwd=search_dir,
                check=False,
                shell=True,
                timeout=30,
            )
            if result.stdout and result.stdout.strip():
                found.append(tid)
        except SubprocessError:
            pass

    return found


def _analyze_test_coverage(
    milestone_id: int,
    prd_path: Path,
    project_root: Path,
    docs_dir: Path,
    plogger: PipelineLogger,
) -> str:
    """Analyze test matrix coverage for a milestone.

    Bash reference: analyze_test_matrix_coverage() lines 1335-1400.
    """
    test_matrix = docs_dir / "04-test-architecture" / "test-matrix.md"
    if not test_matrix.exists():
        plogger.info("[coverage] No test matrix found — skipping coverage analysis")
        return ""

    if not prd_path.exists():
        return ""

    plogger.info(f"[coverage] Analyzing test matrix coverage for M{milestone_id}...")

    expected_ids = _extract_milestone_test_ids(prd_path)
    if not expected_ids:
        plogger.info("[coverage] No test IDs found in PRD stories — skipping")
        return "No test matrix IDs referenced in this milestone's PRD stories."

    plogger.info(f"[coverage] Found {len(expected_ids)} test IDs in PRD")

    found_ids = _find_implemented_test_ids(expected_ids, project_root, project_root)
    missing_count = len(expected_ids) - len(found_ids)

    plogger.info(
        f"[coverage] Results: {len(found_ids)}/{len(expected_ids)} implemented "
        f"({missing_count} missing)"
    )

    report = (
        f"TEST MATRIX COVERAGE ANALYSIS (automated by pipeline):\n"
        f"Expected tests: {len(expected_ids)} | Found: {len(found_ids)} | Missing: {missing_count}\n\n"
    )

    if missing_count > 0:
        report += "MISSING TEST IMPLEMENTATIONS (these are DEFECTS):\n"
        found_set = set(found_ids)
        for tid in expected_ids:
            if tid not in found_set:
                report += f"  - {tid} — NOT FOUND in codebase\n"
        report += "\n"

    if found_ids:
        report += "FOUND TEST IMPLEMENTATIONS:\n"
        for tid in found_ids:
            report += f"  - {tid} — found\n"

    return report


def _archive_milestone(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    project_root: Path,
    plogger: PipelineLogger,
) -> None:
    """Archive milestone PRD and progress."""
    archive_dir = project_root / config.paths.archive_dir
    dest = archive_dir / f"m{milestone.id}-{milestone.slug}"
    dest.mkdir(parents=True, exist_ok=True)

    tasks_dir = project_root / config.paths.tasks_dir
    scripts_dir = project_root / config.paths.scripts_dir

    prd = tasks_dir / f"prd-m{milestone.id}.json"
    if prd.exists():
        (dest / "prd.json").write_bytes(prd.read_bytes())

    progress = scripts_dir / "progress.txt"
    if progress.exists():
        (dest / "progress.txt").write_bytes(progress.read_bytes())

    plogger.info(f"Archived M{milestone.id} ({milestone.slug}) → {dest}")


def run_qa_review(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    claude: ClaudeRunner,
    test_runner: TestRunner,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
    event_logger: EventLogger | None = None,
) -> bool:
    """Run QA review with bugfix cycles.

    Returns True if QA passed, False if escalated.
    """
    slug = milestone.slug
    branch = f"ralph/m{milestone.id}-{slug}"
    tasks_dir = project_root / config.paths.tasks_dir
    scripts_dir = project_root / config.paths.scripts_dir
    qa_dir = project_root / config.paths.qa_dir
    docs_dir = project_root / config.paths.docs_dir
    skills_dir = Path(config.paths.skills_dir).expanduser()

    prd_path = tasks_dir / f"prd-m{milestone.id}.json"
    qa_report = Path(qa_dir) / f"qa-m{milestone.id}-{slug}.md"

    plogger.info(f"Phase 3 (QA): M{milestone.id} ({slug})")
    Path(qa_dir).mkdir(parents=True, exist_ok=True)

    log_dir = project_root / ".ralph" / "logs" / f"m{milestone.id}-{slug}"
    log_dir.mkdir(parents=True, exist_ok=True)

    for cycle in range(0, config.qa.max_bugfix_cycles + 1):
        if cycle > 0:
            plogger.info(f"Bugfix cycle {cycle} for M{milestone.id}")
            run_ralph_bugfix(
                milestone,
                config,
                git,
                project_root,
                plogger,
                claude=claude,
                event_logger=event_logger,
                bugfix_cycle=cycle,
                qa_report_path=qa_report,
            )

        plogger.info(f"Running QA for M{milestone.id} (cycle {cycle})...")

        if is_dry_run():
            plogger.info(f"[DRY RUN] Would run QA for M{milestone.id}")
            return True

        # Run test suite before QA
        result = test_runner.run_test_suite(
            f"pre-QA M{milestone.id} cycle {cycle}", tier=2, log_dir=log_dir
        )
        test_runner.store_results(
            result,
            Path(qa_dir) / f"test-results-qa-m{milestone.id}-cycle{cycle}.md",
        )

        # Read skill content
        skill_path = skills_dir / "qa_engineer" / "SKILL.md"
        skill_content = ""
        if skill_path.exists():
            skill_content = skill_path.read_text()

        progress_path = str(scripts_dir / "progress.txt")

        # Coverage analysis
        coverage_report = _analyze_test_coverage(
            milestone.id, prd_path, project_root, Path(docs_dir), plogger
        )

        # Test architecture reference
        test_arch_ref = ""
        test_arch_dir = Path(docs_dir) / "04-test-architecture"
        if test_arch_dir.exists():
            test_arch_ref = (
                f"\nTEST ARCHITECTURE REFERENCE:\n"
                f"- Read {test_arch_dir}/test-matrix.md — verify Ralph wrote the specified tests\n"
                f"- Read {test_arch_dir}/runtime-safety.md — verify safety tests\n"
                f"- The pipeline has already scanned the codebase for test IDs (see TEST MATRIX COVERAGE above)\n"
                f"- Cross-reference the automated scan results with your own code review"
            )

        prompt = qa_review_prompt(
            skill_content=skill_content,
            milestone_id=milestone.id,
            slug=slug,
            branch=branch,
            prd_path=str(prd_path),
            progress_path=progress_path,
            test_results=result.output,
            test_exit_code=result.exit_code,
            test_command=config.test_execution.test_command,
            coverage_report=coverage_report,
            test_arch_ref=test_arch_ref,
            qa_report_path=str(qa_report),
            prd_json_path=str(prd_path),
        )

        try:
            claude.run(
                prompt,
                model=config.models.qa_review,
                phase="qa_review",
                milestone=milestone.id,
                log_file=log_dir / f"qa-review-cycle-{cycle}.log",
            )
        except ClaudeError:
            plogger.warning(f"QA subprocess failed for M{milestone.id}")

        verdict = _extract_verdict(qa_report)
        plogger.info(f"QA verdict for M{milestone.id}: {verdict}")

        if verdict == "PASS":
            _archive_milestone(milestone, config, project_root, plogger)
            return True

        if cycle == config.qa.max_bugfix_cycles:
            plogger.error(
                f"ESCALATION: M{milestone.id} failed QA after "
                f"{config.qa.max_bugfix_cycles} bugfix cycles"
            )
            escalation = Path(qa_dir) / f"escalation-m{milestone.id}-{slug}.md"
            escalation.write_text(
                f"# Escalation Report: M{milestone.id} ({slug})\n\n"
                f"Failed QA after {config.qa.max_bugfix_cycles} bugfix cycles.\n"
                f"Last QA report: {qa_report}\n"
                f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n"
            )
            _archive_milestone(milestone, config, project_root, plogger)
            return False

    return False
