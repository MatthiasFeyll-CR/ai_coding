"""Phase 2: Ralph Execution — iterative Claude agent loop for coding.

Replaces the former ralph.sh bash script with a pure Python implementation.
Each iteration feeds CLAUDE.md to Claude Code (--print mode) and checks for
the <promise>COMPLETE</promise> completion signal.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeRunner
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.infra.test_runner import TestRunner
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import is_dry_run
from ralph_pipeline.usage import EventLogger

COMPLETION_SIGNAL = "<promise>COMPLETE</promise>"


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


def _setup_workspace(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    git: GitOps,
    plogger: PipelineLogger,
    project_root: Path,
) -> tuple[Path, Path, str]:
    """Prepare the Ralph workspace: symlink PRD, init progress, create branch.

    Returns (scripts_dir, prd_src, branch).
    """
    scripts_dir = project_root / config.paths.scripts_dir
    tasks_dir = project_root / config.paths.tasks_dir
    slug = milestone.slug
    branch = f"ralph/m{milestone.id}-{slug}"
    prd_src = tasks_dir / f"prd-m{milestone.id}.json"

    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Create symlink: .ralph/prd.json → tasks/prd-mN.json
    prd_link = scripts_dir / "prd.json"
    if prd_link.exists() or prd_link.is_symlink():
        prd_link.unlink()
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

    return scripts_dir, prd_src, branch


def _run_ralph_loop(
    claude: ClaudeRunner,
    scripts_dir: Path,
    log_dir: Path,
    max_iterations: int,
    model: str,
    milestone_id: int,
    plogger: PipelineLogger,
    event_logger: EventLogger,
) -> bool:
    """Run the iterative Ralph agent loop.

    Each iteration:
      1. Reads CLAUDE.md from scripts_dir as the prompt
      2. Invokes Claude Code (--print mode) via ClaudeRunner
      3. Checks output for COMPLETE signal
      4. Logs iteration results

    Returns True if Ralph signaled completion, False if max iterations reached.
    """
    claude_md = scripts_dir / "CLAUDE.md"
    if not claude_md.exists():
        plogger.warning(
            f"CLAUDE.md not found at {claude_md} — Ralph has no instructions to execute"
        )
        return False

    log_dir.mkdir(parents=True, exist_ok=True)

    plogger.info(f"Starting Ralph loop — max {max_iterations} iterations")

    for iteration in range(1, max_iterations + 1):
        plogger.info(f"Ralph iteration {iteration}/{max_iterations}")

        prompt = claude_md.read_text()
        iter_log = log_dir / f"ralph-iter-{iteration}.log"

        start = time.monotonic()
        try:
            result = claude.run(
                prompt=prompt,
                model=model,
                phase="ralph",
                milestone=milestone_id,
                log_file=iter_log,
            )
            output = result.output
        except Exception as e:
            plogger.warning(f"Ralph iteration {iteration} failed: {e}")
            output = ""

        duration = time.monotonic() - start

        # Check for completion signal
        if COMPLETION_SIGNAL in output:
            plogger.success(
                f"Ralph completed at iteration {iteration}/{max_iterations} "
                f"({duration:.0f}s)"
            )
            return True

        plogger.info(f"Iteration {iteration} complete ({duration:.0f}s). Continuing...")
        time.sleep(2)

    plogger.warning(
        f"Ralph reached max iterations ({max_iterations}) without completing"
    )
    return False


def run_ralph_execution(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    git: GitOps,
    test_runner: TestRunner,
    plogger: PipelineLogger,
    project_root: Path,
    claude: ClaudeRunner | None = None,
    event_logger: EventLogger | None = None,
) -> None:
    """Run Ralph agent for a milestone.

    - Set up workspace (PRD symlink, progress, branch)
    - Run iterative Claude agent loop
    - Run light test suite (log only)
    """
    slug = milestone.slug
    max_iter = milestone.stories * config.ralph.max_iterations_multiplier

    plogger.info(f"Phase 2 (Ralph): M{milestone.id} ({slug}), max_iter={max_iter}")

    if is_dry_run():
        plogger.info(f"[DRY RUN] Would run Ralph for M{milestone.id}")
        return

    scripts_dir, prd_src, branch = _setup_workspace(
        milestone, config, git, plogger, project_root
    )

    log_dir = project_root / ".ralph" / "logs" / f"m{milestone.id}-{slug}"

    # Run the Ralph agent loop
    if claude is not None:
        _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts_dir,
            log_dir=log_dir,
            max_iterations=max_iter,
            model=config.models.ralph,
            milestone_id=milestone.id,
            plogger=plogger,
            event_logger=event_logger or EventLogger(log_dir / "pipeline.jsonl"),
        )
    else:
        plogger.warning("No ClaudeRunner provided — skipping Ralph execution")

    if _check_all_pass(prd_src):
        plogger.success(f"Ralph: M{milestone.id} ALL PASS")
    else:
        plogger.warning(
            f"Ralph: M{milestone.id} completed with some stories still failing"
        )

    # Light test run after Ralph — log results for QA but don't block
    qa_dir = project_root / config.paths.qa_dir
    qa_dir.mkdir(parents=True, exist_ok=True)

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
        qa_dir / f"test-results-post-ralph-m{milestone.id}.md",
    )


def run_ralph_bugfix(
    milestone: MilestoneConfig,
    config: PipelineConfig,
    git: GitOps,
    project_root: Path,
    plogger: PipelineLogger,
    claude: ClaudeRunner | None = None,
    event_logger: EventLogger | None = None,
) -> None:
    """Re-run Ralph in bugfix mode (shorter iteration count)."""
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

    log_dir = project_root / ".ralph" / "logs" / f"m{milestone.id}-{slug}"

    if claude is not None:
        _run_ralph_loop(
            claude=claude,
            scripts_dir=scripts_dir,
            log_dir=log_dir,
            max_iterations=max_iter,
            model=config.models.ralph,
            milestone_id=milestone.id,
            plogger=plogger,
            event_logger=event_logger or EventLogger(log_dir / "pipeline.jsonl"),
        )
    else:
        plogger.warning("No ClaudeRunner provided — skipping bugfix")
