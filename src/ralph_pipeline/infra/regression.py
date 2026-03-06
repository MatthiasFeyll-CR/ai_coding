"""Regression analysis — test ownership map, failure classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.state import PipelineState


@dataclass
class FailedTest:
    file: str
    owner_milestone: int
    classification: Literal["REGRESSION", "CURRENT"]


class RegressionAnalyzer:
    """Maps test files to milestones and classifies post-merge failures."""

    def __init__(self, state: PipelineState, project_root: Path, git: GitOps):
        self.test_milestone_map = dict(state.test_milestone_map)
        self.project_root = project_root
        self.git = git

    def build_test_map(self, milestone: int) -> dict[str, int]:
        """Register new test files from git diff after merge."""
        pre_tag = f"pre-m{milestone}-merge"
        try:
            new_files = self.git.diff_names(pre_tag, "HEAD", filter_type="A")
        except Exception:
            return self.test_milestone_map

        test_pattern = re.compile(
            r"(test_|_test\.|\.test\.|\.spec\.|tests/|__tests__/)", re.IGNORECASE
        )
        test_files = [f for f in new_files if test_pattern.search(f)]

        for f in test_files:
            self.test_milestone_map[f] = milestone

        return self.test_milestone_map

    def parse_failing_test_files(self, test_output: str) -> list[str]:
        """Framework-agnostic parser for failing test files."""
        files: set[str] = set()

        # pytest: FAILED path/to/test_file.py::test_name
        for m in re.finditer(r"FAILED\s+([^\s:]+\.py)", test_output):
            files.add(m.group(1))

        # pytest short summary
        for m in re.finditer(r"^([^\s]+\.py)::[\w]+", test_output, re.MULTILINE):
            f = m.group(1)
            if "test" in f.lower():
                files.add(f)

        # pytest ERROR collecting
        for m in re.finditer(
            r"ERROR\s+(?:collecting\s+)?([^\s]+test[^\s]*\.py)", test_output
        ):
            files.add(m.group(1))

        # jest/vitest: FAIL path/to/test.spec.ts
        for m in re.finditer(r"FAIL\s+([^\s]+\.(?:test|spec)\.[jt]sx?)", test_output):
            files.add(m.group(1))

        # jest: at Object.<anonymous> (path/to/test.test.js:line:col)
        for m in re.finditer(
            r"\(([^\s()]+\.(?:test|spec)\.[jt]sx?):\d+:\d+\)", test_output
        ):
            files.add(m.group(1))

        # go test
        for m in re.finditer(r"([^\s]+_test\.go)", test_output):
            files.add(m.group(1))

        # Generic
        for m in re.finditer(
            r"(?:FAIL|ERROR|BROKEN)[^\n]{0,200}?"
            r"([a-zA-Z0-9_./-]*(?:test|spec)[a-zA-Z0-9_./-]*"
            r"\.(?:py|js|ts|jsx|tsx|go|rs|rb))",
            test_output,
            re.IGNORECASE,
        ):
            files.add(m.group(1))

        return sorted(files)

    def lookup_test_milestone(self, test_file: str, current_milestone: int) -> int:
        """Registry first, git tag fallback."""
        # Check registry
        if test_file in self.test_milestone_map:
            return self.test_milestone_map[test_file]

        # Git fallback
        first_commit = self.git.log_first_commit_for_file(test_file)
        if not first_commit:
            return current_milestone

        tags = self.git.tags_matching("m*-complete")
        for tag in tags:
            if self.git.is_ancestor(first_commit, tag):
                # Extract milestone number: m3-complete → 3
                tag_num = tag.lstrip("m").split("-")[0]
                try:
                    return int(tag_num)
                except ValueError:
                    continue

        return current_milestone

    def classify(self, test_output: str, current_milestone: int) -> list[FailedTest]:
        """Parse output → classify each failing file as REGRESSION or CURRENT."""
        failing_files = self.parse_failing_test_files(test_output)
        failures: list[FailedTest] = []

        for f in failing_files:
            owner = self.lookup_test_milestone(f, current_milestone)
            classification: Literal["REGRESSION", "CURRENT"] = (
                "REGRESSION" if owner < current_milestone else "CURRENT"
            )
            failures.append(
                FailedTest(file=f, owner_milestone=owner, classification=classification)
            )

        return failures

    def build_fix_context(
        self, regressions: list[FailedTest], current_milestone: int
    ) -> str:
        """Build regression context string for fix prompt."""
        seen_milestones: set[int] = set()
        context_parts: list[str] = []

        for f in regressions:
            if f.owner_milestone in seen_milestones:
                continue
            seen_milestones.add(f.owner_milestone)

            # Try to read archived PRD
            # This is best-effort; the caller passes config for archive path
            context_parts.append(
                f"### M{f.owner_milestone} — tests from this milestone broke after merge\n"
            )

        return "\n".join(context_parts) if context_parts else ""

    def build_fix_prompt(
        self,
        failures: list[FailedTest],
        current_milestone: int,
        test_output: str,
        config: PipelineConfig,
    ) -> str:
        """Build targeted fix prompt with regression context."""
        from ralph_pipeline.ai.prompts import regression_fix_prompt

        regressions = [f for f in failures if f.classification == "REGRESSION"]
        current = [f for f in failures if f.classification == "CURRENT"]

        reg_str = "\n".join(
            f"{f.file} (from M{f.owner_milestone})" for f in regressions
        )
        cur_str = "\n".join(f.file for f in current)

        merge_diff = self.git.diff_stat(f"pre-m{current_milestone}-merge", "HEAD")
        reg_context = self.build_fix_context(regressions, current_milestone)
        test_tail = "\n".join(test_output.splitlines()[-100:])
        branch = self.git.current_branch()

        return regression_fix_prompt(
            milestone=current_milestone,
            branch=branch,
            test_dir=str(self.project_root),
            test_command=config.test_execution.test_command,
            exit_code=1,
            test_tail=test_tail,
            regression_failures=reg_str,
            current_failures=cur_str,
            merge_diff=merge_diff,
            regression_context=reg_context,
        )
