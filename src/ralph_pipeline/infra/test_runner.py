"""Test execution engine — run tests, fix cycles, store results."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeRunner
from ralph_pipeline.config import TestExecutionConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.infra.test_infra import InfraError, TestInfraManager
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import SubprocessError, run_command


@dataclass
class TestResult:
    """Structured test result."""

    passed: bool
    exit_code: int
    output: str
    duration_seconds: float
    label: str
    tier: int
    log_file: Path


class TestRunner:
    """Runs tests and manages fix cycles."""

    def __init__(
        self,
        config: TestExecutionConfig,
        infra: TestInfraManager,
        claude: ClaudeRunner,
        plogger: PipelineLogger,
        project_root: Path,
        git: GitOps,
    ):
        self.config = config
        self.infra = infra
        self.claude = claude
        self.log = plogger
        self.project_root = project_root
        self.git = git

    def run_test_suite(
        self,
        label: str,
        tier: int = 2,
        test_command: str | None = None,
        log_dir: Path | None = None,
    ) -> TestResult:
        """Run test command, capture output, return structured result."""
        cmd = test_command or self.config.test_command
        if not cmd:
            self.log.info(f"[{label}] No test command configured — skipping")
            return TestResult(
                passed=True,
                exit_code=0,
                output="",
                duration_seconds=0.0,
                label=label,
                tier=tier,
                log_file=Path("/dev/null"),
            )

        # Check condition
        if self.config.condition:
            try:
                result = run_command(
                    self.config.condition,
                    cwd=self.project_root,
                    check=False,
                    shell=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    self.log.info(f"[{label}] Test condition not met — skipping")
                    return TestResult(
                        passed=True,
                        exit_code=0,
                        output="",
                        duration_seconds=0.0,
                        label=label,
                        tier=tier,
                        log_file=Path("/dev/null"),
                    )
            except SubprocessError:
                pass

        # Ensure infra is ready for Tier 2
        if tier == 2 and self.config.setup_command:
            try:
                self.infra.ensure_tier2()
            except InfraError as e:
                self.log.error(f"[{label}] Test infrastructure not available: {e}")
                return TestResult(
                    passed=False,
                    exit_code=1,
                    output=f"Test infrastructure setup failed: {e}",
                    duration_seconds=0.0,
                    label=label,
                    tier=tier,
                    log_file=Path("/dev/null"),
                )

        log_file = Path("/dev/null")
        if log_dir:
            log_file = log_dir / f"{label.replace(' ', '-').lower()}.log"

        self.log.info(
            f"[{label}] Running: {cmd} (timeout: {self.config.timeout_seconds}s)"
        )
        start = time.monotonic()

        try:
            result = run_command(
                cmd,
                cwd=self.project_root,
                timeout=self.config.timeout_seconds,
                check=False,
                shell=True,
            )
            duration = time.monotonic() - start
            passed = result.returncode == 0
            output = result.stdout or ""

            if passed:
                self.log.success(f"[{label}] Tests PASSED")
            else:
                self.log.error(
                    f"[{label}] Tests FAILED (exit code: {result.returncode})"
                )

            return TestResult(
                passed=passed,
                exit_code=result.returncode,
                output=output,
                duration_seconds=duration,
                label=label,
                tier=tier,
                log_file=log_file,
            )
        except SubprocessError as e:
            duration = time.monotonic() - start
            if e.exit_code == 124:
                self.log.error(
                    f"[{label}] Tests TIMED OUT after {self.config.timeout_seconds}s"
                )
            else:
                self.log.error(f"[{label}] Tests FAILED (exit code: {e.exit_code})")
            return TestResult(
                passed=False,
                exit_code=e.exit_code,
                output=e.output,
                duration_seconds=duration,
                label=label,
                tier=tier,
                log_file=log_file,
            )

    def run_tier1_tests(self, label: str, log_dir: Path | None = None) -> TestResult:
        """Run all Tier 1 environments. All must pass."""
        if not self.config.tier1.environments:
            self.log.info(
                f"[{label}] No Tier 1 test environments configured — skipping"
            )
            return TestResult(
                passed=True,
                exit_code=0,
                output="",
                duration_seconds=0.0,
                label=label,
                tier=1,
                log_file=Path("/dev/null"),
            )

        try:
            self.infra.ensure_tier1()
        except InfraError as e:
            self.log.error(f"[{label}] Tier 1 infrastructure not available: {e}")
            return TestResult(
                passed=False,
                exit_code=1,
                output=f"Tier 1 infrastructure failed: {e}",
                duration_seconds=0.0,
                label=label,
                tier=1,
                log_file=Path("/dev/null"),
            )

        all_pass = True
        combined_output: list[str] = []
        start = time.monotonic()

        for env in self.config.tier1.environments:
            if not env.test_command:
                continue

            # Check condition
            if env.condition:
                try:
                    result = run_command(
                        env.condition,
                        cwd=self.project_root,
                        check=False,
                        shell=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        self.log.info(
                            f"[{label}][{env.name}] Condition not met — skipping"
                        )
                        continue
                except SubprocessError:
                    pass

            self.log.info(
                f"[{label}][{env.name}] Running: {env.test_command} (timeout: {env.timeout_seconds}s)"
            )
            try:
                result = run_command(
                    env.test_command,
                    cwd=self.project_root,
                    timeout=env.timeout_seconds,
                    check=False,
                    shell=True,
                )
                if result.returncode == 0:
                    self.log.success(f"[{label}][{env.name}] PASSED")
                else:
                    self.log.error(
                        f"[{label}][{env.name}] FAILED (exit: {result.returncode})"
                    )
                    all_pass = False
                combined_output.append(result.stdout or "")
            except SubprocessError as e:
                self.log.error(f"[{label}][{env.name}] FAILED: {e}")
                all_pass = False
                combined_output.append(e.output)

        # Teardown after tier1
        self.infra._t1_teardown()

        duration = time.monotonic() - start
        return TestResult(
            passed=all_pass,
            exit_code=0 if all_pass else 1,
            output="\n".join(combined_output),
            duration_seconds=duration,
            label=label,
            tier=1,
            log_file=Path("/dev/null"),
        )

    def store_results(self, result: TestResult, output_path: Path) -> None:
        """Write test results to docs/08-qa/."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(f"# Test Results: {result.label}\n")
            f.write(f"Date: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
            f.write(f"Command: {self.config.test_command}\n")
            f.write(f"Exit code: {result.exit_code}\n")
            f.write(f"Result: {'PASS' if result.passed else 'FAIL'}\n\n")
            f.write("## Output\n```\n")
            f.write(result.output)
            f.write("\n```\n")
