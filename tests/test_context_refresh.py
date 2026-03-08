"""Tests for context_refresh.py — bugfix-cycle context refresh."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from ralph_pipeline.config import GateChecksConfig
from ralph_pipeline.config import MilestoneConfig as MilestoneConfigModel
from ralph_pipeline.config import (PipelineConfig, ProjectConfig,
                                   TestExecutionConfig)
from ralph_pipeline.context_refresh import (_build_bugfix_context,
                                            _build_codebase_snapshot,
                                            _extract_file_paths_from_prd,
                                            _remove_section,
                                            _summarise_qa_report,
                                            refresh_context_for_bugfix)
from ralph_pipeline.phases.ralph_execution import (BUGFIX_NOTICE_END,
                                                   BUGFIX_NOTICE_START,
                                                   RUNTIME_FOOTER_END,
                                                   RUNTIME_FOOTER_START,
                                                   _inject_bugfix_notice,
                                                   _remove_bugfix_notice)


def _make_config(**overrides) -> PipelineConfig:
    """Create a minimal PipelineConfig for testing."""
    defaults = {
        "project": ProjectConfig(name="TestProject"),
        "milestones": [
            MilestoneConfigModel(id=1, slug="alpha", name="Alpha", stories=3)
        ],
        "test_execution": TestExecutionConfig(),
        "gate_checks": GateChecksConfig(),
    }
    defaults.update(overrides)
    return PipelineConfig(**defaults)


# ── _extract_file_paths_from_prd ─────────────────────────────────────────


class TestExtractFilePathsFromPrd:
    def test_extracts_paths_from_notes(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text(
            json.dumps(
                {
                    "userStories": [
                        {
                            "id": "US-001",
                            "notes": "Architecture: ...\nFiles: src/models.py, src/api.py\nGotchas: none",
                        },
                        {
                            "id": "US-002",
                            "notes": "Files: src/utils.py",
                        },
                    ]
                }
            )
        )
        result = _extract_file_paths_from_prd(prd)
        assert result == ["src/api.py", "src/models.py", "src/utils.py"]

    def test_handles_backtick_wrapped_paths(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text(
            json.dumps(
                {
                    "userStories": [
                        {
                            "id": "US-001",
                            "notes": "Files: `src/app.py`, `src/config.py`",
                        }
                    ]
                }
            )
        )
        result = _extract_file_paths_from_prd(prd)
        assert result == ["src/app.py", "src/config.py"]

    def test_deduplicates_paths(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text(
            json.dumps(
                {
                    "userStories": [
                        {"id": "US-001", "notes": "Files: src/shared.py"},
                        {"id": "US-002", "notes": "Files: src/shared.py, src/other.py"},
                    ]
                }
            )
        )
        result = _extract_file_paths_from_prd(prd)
        assert result == ["src/other.py", "src/shared.py"]

    def test_missing_prd_returns_empty(self, tmp_path: Path):
        result = _extract_file_paths_from_prd(tmp_path / "nonexistent.json")
        assert result == []

    def test_no_files_field_returns_empty(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text(
            json.dumps(
                {
                    "userStories": [
                        {"id": "US-001", "notes": "Architecture: some ref"}
                    ]
                }
            )
        )
        result = _extract_file_paths_from_prd(prd)
        assert result == []

    def test_non_string_notes_skipped(self, tmp_path: Path):
        prd = tmp_path / "prd.json"
        prd.write_text(
            json.dumps(
                {
                    "userStories": [
                        {"id": "US-001", "notes": {"key": "value"}},
                        {"id": "US-002", "notes": "Files: src/good.py"},
                    ]
                }
            )
        )
        result = _extract_file_paths_from_prd(prd)
        assert result == ["src/good.py"]


# ── _build_codebase_snapshot ─────────────────────────────────────────────


class TestBuildCodebaseSnapshot:
    def test_existing_file_included(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("print('hello')\n")

        snapshot = _build_codebase_snapshot(tmp_path, ["src/app.py"])
        assert "## Codebase Snapshot" in snapshot
        assert "### File Tree" in snapshot
        assert "src/app.py" in snapshot
        assert "print('hello')" in snapshot
        assert "(exists)" in snapshot

    def test_missing_file_noted(self, tmp_path: Path):
        snapshot = _build_codebase_snapshot(tmp_path, ["src/new_file.py"])
        assert "(to be created)" in snapshot
        assert "File does not exist yet" in snapshot

    def test_large_file_truncated(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "big.py").write_text("\n".join(f"line {i}" for i in range(300)))

        snapshot = _build_codebase_snapshot(tmp_path, ["src/big.py"])
        assert "first 200" in snapshot
        assert "100 lines omitted" in snapshot

    def test_empty_file_list(self, tmp_path: Path):
        snapshot = _build_codebase_snapshot(tmp_path, [])
        assert "## Codebase Snapshot" in snapshot
        assert "### File Tree" in snapshot


# ── _summarise_qa_report ─────────────────────────────────────────────────


class TestSummariseQaReport:
    def test_missing_report(self, tmp_path: Path):
        result = _summarise_qa_report(tmp_path / "nonexistent.md")
        assert "No QA report available" in result

    def test_short_report_included_fully(self, tmp_path: Path):
        report = tmp_path / "qa.md"
        report.write_text(
            "# QA Report\n\nResult: FAIL\n\n- US-001: Missing validation\n"
        )
        result = _summarise_qa_report(report)
        assert "FAIL" in result
        assert "US-001" in result

    def test_long_report_truncated(self, tmp_path: Path):
        report = tmp_path / "qa.md"
        lines = [f"Line {i}: some detail" for i in range(50)]
        lines.append("Verdict: FAIL")
        report.write_text("\n".join(lines))
        result = _summarise_qa_report(report, max_lines=10)
        assert "more lines" in result
        assert "FAIL" in result


# ── _remove_section ──────────────────────────────────────────────────────


class TestRemoveSection:
    def test_removes_target_section(self):
        text = (
            "## Architecture Reference\n\nSome arch content.\n\n"
            "## Codebase Snapshot\n\nSnapshot content.\nMore snapshot.\n\n"
            "## Quality Checks\n\nCheck commands.\n"
        )
        result = _remove_section(text, "## Codebase Snapshot")
        assert "Architecture Reference" in result
        assert "Codebase Snapshot" not in result
        assert "Snapshot content" not in result
        assert "Quality Checks" in result

    def test_removes_last_section(self):
        text = (
            "## Architecture Reference\n\nContent.\n\n"
            "## Codebase Snapshot\n\nLast section.\n"
        )
        result = _remove_section(text, "## Codebase Snapshot")
        assert "Architecture Reference" in result
        assert "Codebase Snapshot" not in result

    def test_noop_when_section_missing(self):
        text = "## Architecture Reference\n\nContent.\n"
        result = _remove_section(text, "## Nonexistent")
        assert result == text


# ── _build_bugfix_context ────────────────────────────────────────────────


class TestBuildBugfixContext:
    def test_includes_qa_summary(self, tmp_path: Path):
        qa = tmp_path / "qa.md"
        qa.write_text("# QA\nResult: FAIL\n- US-001 broken\n")

        git = MagicMock()
        git.diff_stat.return_value = " src/app.py | 50 +++\n 1 file changed"

        result = _build_bugfix_context(1, 1, qa, git, "ralph/m1-alpha")
        assert "## Bugfix Context" in result
        assert "QA Failure Summary" in result
        assert "US-001" in result
        assert "src/app.py" in result
        assert "Instructions" in result

    def test_handles_git_error(self, tmp_path: Path):
        qa = tmp_path / "qa.md"
        qa.write_text("Result: FAIL\n")

        git = MagicMock()
        git.diff_stat.side_effect = Exception("git error")

        result = _build_bugfix_context(1, 1, qa, git, "ralph/m1-alpha")
        assert "unable to compute diff" in result

    def test_handles_missing_qa_report(self, tmp_path: Path):
        git = MagicMock()
        git.diff_stat.return_value = ""

        result = _build_bugfix_context(1, 2, tmp_path / "nope.md", git, "ralph/m1-alpha")
        assert "No QA report available" in result


# ── refresh_context_for_bugfix (integration) ─────────────────────────────


class TestRefreshContextForBugfix:
    def _make_project(self, tmp_path: Path) -> tuple[Path, PipelineConfig]:
        """Set up a minimal project structure for testing."""
        scripts_dir = tmp_path / ".ralph"
        scripts_dir.mkdir()
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        qa_dir = tmp_path / "docs" / "08-qa"
        qa_dir.mkdir(parents=True)

        # Write initial context.md with a stale snapshot
        (scripts_dir / "context.md").write_text(
            "# Context Bundle: M1 — Alpha\n\n"
            "## Architecture Reference\n\nKeep this.\n\n"
            "## Codebase Snapshot\n\n### File Tree\n```\nold tree\n```\n\n"
            "### src/app.py (exists)\n```\nold content\n```\n"
        )

        # Write PRD with file references
        (tasks_dir / "prd-m1.json").write_text(
            json.dumps(
                {
                    "userStories": [
                        {"id": "US-001", "notes": "Files: src/app.py, src/new.py"}
                    ]
                }
            )
        )

        # Write QA report
        (qa_dir / "qa-m1-alpha.md").write_text(
            "# QA Report M1\n\nResult: FAIL\n\n- US-001: Missing validation\n"
        )

        # Write actual source file (simulating Phase 2 changes)
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("# Updated by Ralph\nclass App:\n    pass\n")

        config = _make_config()
        return tmp_path, config

    def test_refreshes_snapshot_and_adds_bugfix_context(self, tmp_path: Path):
        project_root, config = self._make_project(tmp_path)
        git = MagicMock()
        git.diff_stat.return_value = " src/app.py | 3 +++\n 1 file changed"
        plogger = MagicMock()

        refresh_context_for_bugfix(
            project_root=project_root,
            config=config,
            milestone_id=1,
            cycle=1,
            git=git,
            plogger=plogger,
        )

        content = (project_root / ".ralph" / "context.md").read_text()

        # Architecture preserved
        assert "## Architecture Reference" in content
        assert "Keep this." in content

        # Old snapshot replaced
        assert "old content" not in content
        assert "old tree" not in content

        # New snapshot present
        assert "## Codebase Snapshot" in content
        assert "Updated by Ralph" in content

        # Missing file noted
        assert "(to be created)" in content

        # Bugfix context present
        assert "## Bugfix Context" in content
        assert "QA Failure Summary" in content
        assert "US-001" in content
        assert "src/app.py | 3" in content

    def test_idempotent_across_cycles(self, tmp_path: Path):
        """Running refresh multiple times doesn't duplicate sections."""
        project_root, config = self._make_project(tmp_path)
        git = MagicMock()
        git.diff_stat.return_value = "1 file changed"
        plogger = MagicMock()

        refresh_context_for_bugfix(
            project_root, config, 1, 1, git, plogger
        )
        refresh_context_for_bugfix(
            project_root, config, 1, 2, git, plogger
        )

        content = (project_root / ".ralph" / "context.md").read_text()
        assert content.count("## Codebase Snapshot") == 1
        assert content.count("## Bugfix Context") == 1
        # Second cycle number present
        assert "cycle 2" in content

    def test_noop_when_context_md_missing(self, tmp_path: Path):
        scripts = tmp_path / ".ralph"
        scripts.mkdir()
        tasks = tmp_path / "tasks"
        tasks.mkdir()

        config = _make_config()
        plogger = MagicMock()
        git = MagicMock()

        refresh_context_for_bugfix(tmp_path, config, 1, 1, git, plogger)
        plogger.warning.assert_called()

    def test_custom_qa_report_path(self, tmp_path: Path):
        project_root, config = self._make_project(tmp_path)
        custom_qa = tmp_path / "custom-qa.md"
        custom_qa.write_text("Result: FAIL\nCustom report content\n")

        git = MagicMock()
        git.diff_stat.return_value = ""
        plogger = MagicMock()

        refresh_context_for_bugfix(
            project_root, config, 1, 1, git, plogger,
            qa_report_path=custom_qa,
        )

        content = (project_root / ".ralph" / "context.md").read_text()
        assert "Custom report content" in content


# ── Bugfix notice injection/removal ─────────────────────────────────────


class TestBugfixNotice:
    def test_injects_notice_into_claude_md(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("# CLAUDE.md\n\nInstructions.")
        plogger = MagicMock()

        _inject_bugfix_notice(scripts, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        assert "BUGFIX MODE" in content
        assert "Trust the actual codebase" in content
        assert BUGFIX_NOTICE_START.strip() in content
        assert BUGFIX_NOTICE_END.strip() in content
        # Original content preserved
        assert "# CLAUDE.md" in content
        assert "Instructions." in content

    def test_idempotent_reinjection(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("# CLAUDE.md\n\nContent.")
        plogger = MagicMock()

        _inject_bugfix_notice(scripts, plogger)
        first = (scripts / "CLAUDE.md").read_text()

        _inject_bugfix_notice(scripts, plogger)
        second = (scripts / "CLAUDE.md").read_text()

        assert first == second
        assert second.count(BUGFIX_NOTICE_START.strip()) == 1

    def test_inserts_before_runtime_footer(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\nContent."
            + RUNTIME_FOOTER_START
            + "## Quality Commands\n"
            + RUNTIME_FOOTER_END
        )
        plogger = MagicMock()

        _inject_bugfix_notice(scripts, plogger)

        content = (scripts / "CLAUDE.md").read_text()
        bugfix_pos = content.index(BUGFIX_NOTICE_START.strip())
        footer_pos = content.index(RUNTIME_FOOTER_START.strip())
        assert bugfix_pos < footer_pos

    def test_remove_bugfix_notice(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "CLAUDE.md").write_text("# CLAUDE.md\n\nContent.")
        plogger = MagicMock()

        _inject_bugfix_notice(scripts, plogger)
        assert "BUGFIX MODE" in (scripts / "CLAUDE.md").read_text()

        _remove_bugfix_notice(scripts, plogger)
        content = (scripts / "CLAUDE.md").read_text()
        assert "BUGFIX MODE" not in content
        assert BUGFIX_NOTICE_START.strip() not in content
        # Original content still present
        assert "# CLAUDE.md" in content

    def test_remove_noop_when_no_notice(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        original = "# CLAUDE.md\n\nContent."
        (scripts / "CLAUDE.md").write_text(original)
        plogger = MagicMock()

        _remove_bugfix_notice(scripts, plogger)
        assert (scripts / "CLAUDE.md").read_text() == original

    def test_noop_when_no_claude_md(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        plogger = MagicMock()

        _inject_bugfix_notice(scripts, plogger)
        assert not (scripts / "CLAUDE.md").exists()


# ── Progress.txt structured format ───────────────────────────────────────


class TestProgressTxtFormat:
    """Verify that _setup_workspace creates a structured progress.txt."""

    def test_structured_sections(self, tmp_path: Path):
        """Validate the format by importing and calling _setup_workspace."""
        from unittest.mock import patch

        from ralph_pipeline.phases.ralph_execution import _setup_workspace

        config = _make_config()
        milestone = config.milestones[0]
        git = MagicMock()
        git.branch_exists.return_value = False
        plogger = MagicMock()

        with patch(
            "ralph_pipeline.phases.ralph_execution.os.path.relpath",
            return_value="../tasks/prd-m1.json",
        ):
            scripts_dir, _, _ = _setup_workspace(
                milestone, config, git, plogger, tmp_path
            )

        progress = (scripts_dir / "progress.txt").read_text()
        assert "## Implementation Log" in progress
        assert "## Codebase Patterns" in progress
        assert "## Deviations & Decisions" in progress
        assert "M1" in progress
