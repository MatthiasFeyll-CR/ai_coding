"""Tests for CLI argument parsing."""

from __future__ import annotations

from ralph_pipeline.cli import _build_parser


class TestCLIParser:
    def test_run_required_config(self):
        parser = _build_parser()
        args = parser.parse_args(["run", "--config", "test.json"])
        assert args.command == "run"
        assert args.config == "test.json"
        assert args.resume is False
        assert args.dry_run is False

    def test_run_all_flags(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                "test.json",
                "--resume",
                "--milestone",
                "3",
                "--dry-run",
            ]
        )
        assert args.resume is True
        assert args.milestone == 3
        assert args.dry_run is True

    def test_install_skills(self):
        parser = _build_parser()
        args = parser.parse_args(["install-skills"])
        assert args.command == "install-skills"

    def test_validate_infra(self):
        parser = _build_parser()
        args = parser.parse_args(["validate-infra", "--config", "test.json"])
        assert args.command == "validate-infra"
        assert args.config == "test.json"

    def test_no_command(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.command is None
