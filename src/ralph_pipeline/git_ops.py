"""Git operations — all git commands in one place."""

from __future__ import annotations

import logging
from pathlib import Path

from ralph_pipeline.subprocess_utils import SubprocessError, run_command

logger = logging.getLogger(__name__)


class GitError(Exception):
    pass


class MergeConflictError(GitError):
    pass


class GitOps:
    """All git operations in one place. Replaces inline git commands in pipeline.sh."""

    def __init__(self, project_root: Path):
        self.root = project_root

    def _run(self, *args: str, check: bool = True) -> str:
        """Run a git command and return stdout."""
        cmd = ["git"] + list(args)
        try:
            result = run_command(cmd, cwd=self.root, check=check, timeout=60)
            return (result.stdout or "").strip()
        except SubprocessError as e:
            raise GitError(f"Git command failed: {' '.join(args)}: {e}") from e

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def checkout(self, branch: str, create: bool = False) -> None:
        if create:
            self._run("checkout", "-b", branch)
        else:
            self._run("checkout", branch)

    def merge(self, source_branch: str, no_ff: bool = True, message: str = "") -> None:
        args = ["merge", source_branch]
        if no_ff:
            args.append("--no-ff")
        if message:
            args.extend(["-m", message])
        try:
            self._run(*args)
        except GitError as e:
            self._run("merge", "--abort", check=False)
            raise MergeConflictError(f"Merge conflict merging {source_branch}") from e

    def tag(self, name: str) -> None:
        self._run("tag", name, check=False)

    def delete_branch(self, branch: str) -> None:
        self._run("branch", "-d", branch, check=False)

    def has_uncommitted_changes(self) -> bool:
        # Check tracked changes
        result = run_command(
            ["git", "diff", "--quiet", "HEAD"],
            cwd=self.root,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            return True
        # Check untracked files
        result = run_command(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=self.root,
            check=False,
            timeout=30,
        )
        return bool((result.stdout or "").strip())

    def commit_all(self, message: str) -> None:
        """Stage all and commit. No-op if tree is clean."""
        if not self.has_uncommitted_changes():
            return
        self._run("add", "-A")
        self._run("commit", "-m", message, check=False)
        logger.info("Committed: %s", message)

    def diff_stat(self, from_ref: str, to_ref: str, max_lines: int = 40) -> str:
        output = self._run("diff", f"{from_ref}..{to_ref}", "--stat", check=False)
        lines = output.splitlines()
        if len(lines) > max_lines:
            return (
                "\n".join(lines[:max_lines])
                + f"\n... ({len(lines) - max_lines} more lines)"
            )
        return output

    def diff_names(
        self, from_ref: str, to_ref: str, filter_type: str = "A"
    ) -> list[str]:
        output = self._run(
            "diff",
            "--name-only",
            f"--diff-filter={filter_type}",
            from_ref,
            to_ref,
            check=False,
        )
        return [f for f in output.splitlines() if f.strip()]

    def tag_exists(self, name: str) -> bool:
        try:
            self._run("rev-parse", "--verify", name)
            return True
        except GitError:
            return False

    def branch_exists(self, name: str) -> bool:
        try:
            self._run("rev-parse", "--verify", name)
            return True
        except GitError:
            return False

    def merge_dry_run(self, source_branch: str) -> bool:
        """Returns True if merge would succeed without conflicts."""
        try:
            self._run("merge", "--no-commit", "--no-ff", source_branch)
            self._run("merge", "--abort", check=False)
            return True
        except GitError:
            self._run("merge", "--abort", check=False)
            return False

    def log_first_commit_for_file(self, file_path: str) -> str:
        """Returns the oldest commit hash that introduced a file."""
        output = self._run(
            "log",
            "--diff-filter=A",
            "--format=%H",
            "--",
            file_path,
            check=False,
        )
        lines = output.splitlines()
        return lines[-1] if lines else ""

    def is_ancestor(self, commit: str, ref: str) -> bool:
        try:
            run_command(
                ["git", "merge-base", "--is-ancestor", commit, ref],
                cwd=self.root,
                check=True,
                timeout=30,
            )
            return True
        except SubprocessError:
            return False

    def tags_matching(self, pattern: str) -> list[str]:
        output = self._run("tag", "-l", pattern, "--sort=version:refname", check=False)
        return [t for t in output.splitlines() if t.strip()]

    def dirty_files(self, max_files: int = 20) -> list[str]:
        """Return list of dirty file paths (for error messages)."""
        result = run_command(
            ["git", "status", "--short"],
            cwd=self.root,
            check=False,
            timeout=30,
        )
        lines = (result.stdout or "").strip().splitlines()
        return lines[:max_files]
