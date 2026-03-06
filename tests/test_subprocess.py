"""Tests for subprocess utilities."""

from __future__ import annotations

from pathlib import Path

import pytest
from ralph_pipeline.subprocess_utils import (
    SubprocessError,
    is_dry_run,
    run_command,
    set_dry_run,
)


class TestDryRun:
    def setup_method(self):
        set_dry_run(False)

    def teardown_method(self):
        set_dry_run(False)

    def test_dry_run_flag(self):
        assert is_dry_run() is False
        set_dry_run(True)
        assert is_dry_run() is True
        set_dry_run(False)
        assert is_dry_run() is False

    def test_dry_run_skips_execution(self, tmp_path: Path):
        set_dry_run(True)
        result = run_command("echo hello", cwd=tmp_path, shell=True)
        assert result.returncode == 0
        assert result.stdout == "[dry-run]"


class TestRunCommand:
    def test_simple_command(self, tmp_path: Path):
        result = run_command("echo hello", cwd=tmp_path, shell=True, check=False)
        assert "hello" in result.stdout

    def test_failing_command_no_check(self, tmp_path: Path):
        result = run_command("exit 1", cwd=tmp_path, shell=True, check=False)
        assert result.returncode == 1

    def test_failing_command_with_check(self, tmp_path: Path):
        with pytest.raises(SubprocessError):
            run_command("exit 1", cwd=tmp_path, shell=True, check=True)

    def test_list_command(self, tmp_path: Path):
        result = run_command(["echo", "hello"], cwd=tmp_path, check=False)
        assert "hello" in result.stdout
