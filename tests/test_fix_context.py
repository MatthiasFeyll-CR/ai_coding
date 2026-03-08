"""Tests for fix_context — domain context loading for fix prompts."""

from __future__ import annotations

from pathlib import Path

from ralph_pipeline.fix_context import load_domain_context, load_type_config


class TestLoadDomainContext:
    def test_returns_empty_when_no_context_file(self, tmp_path: Path):
        result = load_domain_context(tmp_path)
        assert result == ""

    def test_returns_empty_when_context_file_is_empty(self, tmp_path: Path):
        (tmp_path / ".ralph").mkdir()
        (tmp_path / ".ralph" / "context.md").write_text("")
        result = load_domain_context(tmp_path)
        assert result == ""

    def test_extracts_architecture_section(self, tmp_path: Path):
        (tmp_path / ".ralph").mkdir()
        context = (
            "# Context Bundle\n\n"
            "## Architecture Reference\n"
            "- API uses REST\n"
            "- Data model: User has id, name, email\n\n"
            "## Some Other Section\n"
            "- Unrelated content\n"
        )
        (tmp_path / ".ralph" / "context.md").write_text(context)
        result = load_domain_context(tmp_path)
        assert "Architecture Reference" in result
        assert "API uses REST" in result
        assert "Data model" in result

    def test_extracts_multiple_relevant_sections(self, tmp_path: Path):
        (tmp_path / ".ralph").mkdir()
        context = (
            "# Context Bundle\n\n"
            "## Architecture Reference\n"
            "- REST API\n\n"
            "## Design Reference\n"
            "- Blue theme\n\n"
            "## Test Specifications\n"
            "- T-1.1: Login flow\n\n"
            "## Codebase Patterns\n"
            "- Pattern A\n\n"
            "## Quality Checks\n"
            "- npm run lint\n\n"
            "## Browser Testing\n"
            "- Playwright config\n"
        )
        (tmp_path / ".ralph" / "context.md").write_text(context)
        result = load_domain_context(tmp_path)
        assert "Architecture Reference" in result
        assert "Design Reference" in result
        assert "Test Specifications" in result
        assert "Codebase Patterns" in result
        assert "Quality Checks" in result
        # Browser Testing is NOT in the fix-relevant list
        assert "Browser Testing" not in result

    def test_respects_max_lines(self, tmp_path: Path):
        (tmp_path / ".ralph").mkdir()
        # Create a context with a long section
        lines = ["## Architecture Reference"] + [f"- Line {i}" for i in range(100)]
        lines += ["## Design Reference"] + [f"- Design {i}" for i in range(100)]
        (tmp_path / ".ralph" / "context.md").write_text("\n".join(lines))

        result = load_domain_context(tmp_path, max_lines=50)
        result_lines = result.splitlines()
        # Should be capped near 50 lines (+ truncation marker)
        assert len(result_lines) <= 55

    def test_truncation_marker_added(self, tmp_path: Path):
        (tmp_path / ".ralph").mkdir()
        lines = ["## Architecture Reference"] + [f"- Line {i}" for i in range(200)]
        (tmp_path / ".ralph" / "context.md").write_text("\n".join(lines))

        result = load_domain_context(tmp_path, max_lines=50)
        assert "truncated" in result

    def test_skips_irrelevant_sections(self, tmp_path: Path):
        (tmp_path / ".ralph").mkdir()
        context = (
            "## Codebase Snapshot\n"
            "- File tree goes here\n\n"
            "## Browser Testing\n"
            "- Playwright setup\n"
        )
        (tmp_path / ".ralph" / "context.md").write_text(context)
        result = load_domain_context(tmp_path)
        assert result == ""


class TestLoadTypeConfig:
    def test_returns_empty_when_no_config_files(self, tmp_path: Path):
        result = load_type_config(tmp_path)
        assert result == ""

    def test_loads_tsconfig(self, tmp_path: Path):
        tsconfig = '{"compilerOptions": {"strict": true}}'
        (tmp_path / "tsconfig.json").write_text(tsconfig)
        result = load_type_config(tmp_path)
        assert "tsconfig.json" in result
        assert '"strict": true' in result

    def test_loads_pyproject_toml(self, tmp_path: Path):
        pyproject = "[tool.mypy]\nstrict = true\n"
        (tmp_path / "pyproject.toml").write_text(pyproject)
        result = load_type_config(tmp_path)
        assert "pyproject.toml" in result
        assert "strict = true" in result

    def test_loads_multiple_configs(self, tmp_path: Path):
        (tmp_path / "tsconfig.json").write_text('{"strict": true}')
        (tmp_path / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n")
        result = load_type_config(tmp_path)
        assert "tsconfig.json" in result
        assert "pyproject.toml" in result

    def test_skips_large_config_files(self, tmp_path: Path):
        large_content = "\n".join([f"line {i}" for i in range(300)])
        (tmp_path / "tsconfig.json").write_text(large_content)
        result = load_type_config(tmp_path)
        assert "too large" in result
        assert "300 lines" in result
