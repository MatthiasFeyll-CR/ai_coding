"""Phase 2: Ralph Execution — runs Ralph agent for story-by-story coding.

Bash reference: run_ralph() in pipeline.sh lines 1182-1232
                run_ralph_bugfix() lines 1236-1252.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.infra.test_runner import TestRunner
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import is_dry_run, run_command


def _check_all_pass(prd_path: Path) -> bool:
    """Check if all stories in PRD have passes=true."""
    try:
        data = json.loads(prd_path.read_text())
        stories = data.get("userStories", [])
        if not stories:
            return False
        return all(s.get("passes", False) for s in stories)
    except (json.JSONDecodeError, FileNotFoundError):
        return False


def run_ralph_execution(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    git: GitOps,
    test_runner: TestRunner,
    plogger: PipelineLogger,
    project_root: Path,
) -> None:
    """Run Ralph agent for a milestone.

    - Create symlink to PRD
    - Initialize progress.txt
    - Commit dirty tree, create/checkout branch
    - Invoke ralph.sh
    - Run light test suite (log only)
    """
    scripts_dir = project_root / config.paths.scripts_dir
    tasks_dir = project_root / config.paths.tasks_dir
    qa_dir = project_root / config.paths.qa_dir

    slug = milestone.slug
    stories = milestone.stories
    max_iter = stories * config.ralph.max_iterations_multiplier
    branch = f"ralph/m{milestone.id}-{slug}"
    prd_src = tasks_dir / f"prd-m{milestone.id}.json"

    plogger.info(
        f"Phase 2 (Ralph): M{milestone.id} ({slug}), branch={branch}, max_iter={max_iter}"
    )

    if is_dry_run():
        plogger.info(f"[DRY RUN] Would run Ralph for M{milestone.id}")
        return

    # Set up Ralph workspace
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Create symlink: .ralph/prd.json → tasks/prd-mN.json
    prd_link = scripts_dir / "prd.json"
    if prd_link.exists() or prd_link.is_symlink():
        prd_link.unlink()
    # Compute relative path from scripts_dir to prd_src
    try:
        rel_path = os.path.relpath(prd_src, scripts_dir)
        prd_link.symlink_to(rel_path)
    except (ValueError, OSError):
        prd_link.symlink_to(prd_src)

    # Initialize progress.txt
    progress = scripts_dir / "progress.txt"
    progress.write_text(f"# Ralph Progress Log\nStarted: M{milestone.id} {slug}\n---\n")

    # Commit dirty tree
    git.commit_all(f"chore: pipeline artifacts before M{milestone.id}")

    # Create or checkout milestone branch
    if git.branch_exists(branch):
        git.checkout(branch)
    else:
        git.checkout(branch, create=True)

    # Run ralph.sh
    ralph_sh = scripts_dir / "ralph.sh"
    if not ralph_sh.exists():
        plogger.warning(f"ralph.sh not found at {ralph_sh} — skipping Ralph execution")
        return

    ralph_model_args = []
    if config.models.ralph:
        ralph_model_args = ["--model", config.models.ralph]

    cmd = ["bash", str(ralph_sh)] + ralph_model_args + [str(max_iter)]

    log_dir = project_root / ".ralph" / "logs" / f"m{milestone.id}-{slug}"
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        run_command(
            cmd,
            cwd=project_root,
            timeout=0,  # No timeout for Ralph
            check=False,
            stream_to=log_dir / "ralph-iter-1.log",
        )
    except Exception as e:
        plogger.warning(f"Ralph execution had issues: {e}")

    if _check_all_pass(prd_src):
        plogger.success(f"Ralph: M{milestone.id} ALL PASS")
    else:
        plogger.warning(
            f"Ralph: M{milestone.id} completed with some stories still failing"
        )

    # Light test run after Ralph — log results for QA but don't block
    qa_dir_path = Path(qa_dir)
    qa_dir_path.mkdir(parents=True, exist_ok=True)

    if config.test_execution.tier1.environments:
        result = test_runner.run_tier1_tests(
            f"post-ralph M{milestone.id}", log_dir=log_dir
        )
    else:
        result = test_runner.run_test_suite(
            f"post-ralph M{milestone.id}", tier=2, log_dir=log_dir
        )

    test_runner.store_results(
        result,
        qa_dir_path / f"test-results-post-ralph-m{milestone.id}.md",
    )


def run_ralph_bugfix(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    git: GitOps,
    project_root: Path,
    plogger: PipelineLogger,
) -> None:
    """Re-run Ralph in bugfix mode (shorter iteration count).

    Bash reference: run_ralph_bugfix() lines 1236-1252.
    """
    scripts_dir = project_root / config.paths.scripts_dir
    slug = milestone.slug
    stories = milestone.stories
    max_iter = stories * 2
    branch = f"ralph/m{milestone.id}-{slug}"

    plogger.info(f"Ralph bugfix: M{milestone.id} ({slug}), max_iter={max_iter}")

    git.checkout(branch)

    # Re-link PRD
    prd_link = scripts_dir / "prd.json"
    prd_src = project_root / config.paths.tasks_dir / f"prd-m{milestone.id}.json"
    if prd_link.exists() or prd_link.is_symlink():
        prd_link.unlink()
    try:
        rel_path = os.path.relpath(prd_src, scripts_dir)
        prd_link.symlink_to(rel_path)
    except (ValueError, OSError):
        prd_link.symlink_to(prd_src)

    ralph_sh = scripts_dir / "ralph.sh"
    if not ralph_sh.exists():
        plogger.warning("ralph.sh not found — skipping bugfix")
        return

    ralph_model_args = []
    if config.models.ralph:
        ralph_model_args = ["--model", config.models.ralph]

    cmd = ["bash", str(ralph_sh)] + ralph_model_args + [str(max_iter)]

    try:
        run_command(cmd, cwd=project_root, timeout=0, check=False)
    except Exception as e:
        plogger.warning(f"Ralph bugfix had issues: {e}")
