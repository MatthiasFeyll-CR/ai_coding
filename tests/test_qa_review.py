"""Tests for qa_review extraction and search functions."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from ralph_pipeline.phases.qa_review import (_ast_search_python_tests,
                                             _extract_milestone_test_ids,
                                             _find_implemented_test_ids,
                                             _load_test_manifest)

# ─── _extract_milestone_test_ids ──────────────────────────────────────────────


class TestExtractMilestoneTestIds:
    """Tests for Tier 1/2/3 extraction from PRD stories."""

    def _write_prd(self, path: Path, stories: list[dict]) -> Path:
        prd = path / "prd.json"
        prd.write_text(json.dumps({"userStories": stories}))
        return prd

    # -- Tier 1: structured testIds field --

    def test_tier1_structured_field(self, tmp_path: Path):
        """Structured testIds array is read directly."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "testIds": ["T-1.1", "API-2.01"]},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == ["API-2.01", "T-1.1"]

    def test_tier1_skips_notes_when_testids_present(self, tmp_path: Path):
        """When testIds is present, notes regex is NOT used (authoritative)."""
        prd = self._write_prd(tmp_path, [
            {
                "id": "US-001",
                "testIds": ["T-1.1"],
                "notes": "Testing: T-1.1, T-2.2, T-3.3",
            },
        ])
        result = _extract_milestone_test_ids(prd)
        # T-2.2 and T-3.3 from notes should NOT appear
        assert result == ["T-1.1"]

    def test_tier1_filters_invalid_ids(self, tmp_path: Path, caplog):
        """Invalid IDs in testIds are warned about and skipped."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "testIds": ["T-1.1", "not-a-test-id", "BOGUS"]},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == ["T-1.1"]
        assert "does not match" in caplog.text

    def test_tier1_empty_list(self, tmp_path: Path):
        """Empty testIds array produces no IDs (and skips notes)."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "testIds": [], "notes": "Testing: T-9.9"},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == []

    def test_tier1_all_id_prefixes(self, tmp_path: Path):
        """All known ID prefixes are accepted."""
        all_ids = [
            "T-1.1", "API-2.01", "DB-3.01", "UI-4.01",
            "LOOP-001", "STATE-002", "TIMEOUT-003", "LEAK-004",
            "INTEGRITY-005", "AI-SAFE-006", "SCN-007", "JOURNEY-008",
            "CONC-009", "ERR-010",
        ]
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "testIds": all_ids},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == sorted(all_ids)

    # -- Tier 2: regex on notes string (fallback) --

    def test_tier2_notes_regex(self, tmp_path: Path):
        """Regex extraction from notes when testIds is absent."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "notes": "Testing: T-1.1, T-1.2, API-3.01"},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == ["API-3.01", "T-1.1", "T-1.2"]

    def test_tier2_notes_markdown_table(self, tmp_path: Path):
        """IDs in markdown table format are extracted."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "notes": "| T-1.1 | User login | pass |\n| T-1.2 | Logout |"},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == ["T-1.1", "T-1.2"]

    def test_tier2_notes_non_string_warns(self, tmp_path: Path, caplog):
        """Non-string notes field produces a warning and is skipped."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-042", "notes": {"key": "value"}},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == []
        assert "expected str" in caplog.text
        assert "US-042" in caplog.text

    def test_tier2_notes_missing(self, tmp_path: Path):
        """Missing notes field defaults to empty string, no crash."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001"},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == []

    # -- Tier 3: regex on context.test_cases --

    def test_tier3_context_test_cases(self, tmp_path: Path):
        """IDs extracted from context.test_cases entries."""
        prd = self._write_prd(tmp_path, [
            {
                "id": "US-001",
                "notes": "",
                "context": {
                    "test_cases": [
                        "T-1.1.01 | Unit | Create user | {email} | 201",
                        "API-2.01 | Integration | List users | GET /users | 200",
                    ]
                },
            },
        ])
        result = _extract_milestone_test_ids(prd)
        assert "T-1.1.01" in result
        assert "API-2.01" in result

    def test_tier3_supplements_tier2(self, tmp_path: Path):
        """Tier 3 adds IDs not found in notes (union, not override)."""
        prd = self._write_prd(tmp_path, [
            {
                "id": "US-001",
                "notes": "Testing: T-1.1",
                "context": {"test_cases": ["DB-5.01 | Unit | ..."]},
            },
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == ["DB-5.01", "T-1.1"]

    # -- Edge cases --

    def test_file_not_found(self, tmp_path: Path):
        """Missing PRD file returns empty list."""
        result = _extract_milestone_test_ids(tmp_path / "missing.json")
        assert result == []

    def test_invalid_json(self, tmp_path: Path):
        """Malformed JSON returns empty list."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        result = _extract_milestone_test_ids(bad)
        assert result == []

    def test_deduplication(self, tmp_path: Path):
        """Same ID across multiple stories is deduplicated."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "notes": "Testing: T-1.1, T-1.2"},
            {"id": "US-002", "notes": "Testing: T-1.1, T-1.3"},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == ["T-1.1", "T-1.2", "T-1.3"]

    def test_mixed_tier1_and_tier2_across_stories(self, tmp_path: Path):
        """Different stories can use different tiers."""
        prd = self._write_prd(tmp_path, [
            {"id": "US-001", "testIds": ["T-1.1"]},
            {"id": "US-002", "notes": "Testing: T-2.2"},
        ])
        result = _extract_milestone_test_ids(prd)
        assert result == ["T-1.1", "T-2.2"]


# ─── _load_test_manifest ──────────────────────────────────────────────────────


class TestLoadTestManifest:
    def test_loads_valid_manifest(self, tmp_path: Path):
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        manifest = {
            "tests": {
                "T-1.1": {"file": "tests/test_a.py", "function": "test_login"},
                "API-2.01": {"file": "tests/test_b.py", "function": "test_create"},
            }
        }
        (ralph_dir / "test-manifest.json").write_text(json.dumps(manifest))
        result = _load_test_manifest(tmp_path)
        assert "T-1.1" in result
        assert result["T-1.1"]["function"] == "test_login"

    def test_missing_manifest(self, tmp_path: Path):
        result = _load_test_manifest(tmp_path)
        assert result == {}

    def test_invalid_json(self, tmp_path: Path):
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "test-manifest.json").write_text("{bad json")
        result = _load_test_manifest(tmp_path)
        assert result == {}

    def test_missing_tests_key(self, tmp_path: Path):
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "test-manifest.json").write_text(json.dumps({"other": "data"}))
        result = _load_test_manifest(tmp_path)
        assert result == {}


# ─── _ast_search_python_tests ─────────────────────────────────────────────────


class TestAstSearchPythonTests:
    def test_finds_id_in_function_name(self, tmp_path: Path):
        """AST search matches test ID in function name."""
        test_file = tmp_path / "test_auth.py"
        test_file.write_text(textwrap.dedent("""\
            def test_t_1_1_login_valid():
                assert True
        """))
        assert _ast_search_python_tests("T-1.1", tmp_path) is True

    def test_finds_id_in_docstring(self, tmp_path: Path):
        """AST search matches test ID in docstring."""
        test_file = tmp_path / "test_auth.py"
        test_file.write_text(textwrap.dedent("""\
            def test_login_valid():
                \"\"\"Covers T-1.1 — login with valid credentials.\"\"\"
                assert True
        """))
        assert _ast_search_python_tests("T-1.1", tmp_path) is True

    def test_finds_normalised_id_in_function_name(self, tmp_path: Path):
        """AST search matches normalised form (T-1.1 → t_1_1)."""
        test_file = tmp_path / "test_auth.py"
        test_file.write_text(textwrap.dedent("""\
            def test_t_1_1():
                pass
        """))
        assert _ast_search_python_tests("T-1.1", tmp_path) is True

    def test_no_match(self, tmp_path: Path):
        """Returns False when no test references the ID."""
        test_file = tmp_path / "test_auth.py"
        test_file.write_text(textwrap.dedent("""\
            def test_something_else():
                pass
        """))
        assert _ast_search_python_tests("T-99.99", tmp_path) is False

    def test_ignores_non_test_files(self, tmp_path: Path):
        """Only scans test_*.py and *_test.py files."""
        # ID exists in a non-test file — should not be found
        regular_file = tmp_path / "auth.py"
        regular_file.write_text(textwrap.dedent("""\
            def test_t_1_1():
                pass
        """))
        assert _ast_search_python_tests("T-1.1", tmp_path) is False

    def test_handles_syntax_error(self, tmp_path: Path):
        """Files with syntax errors are skipped, not crashed on."""
        test_file = tmp_path / "test_broken.py"
        test_file.write_text("def this is broken syntax {{{{")
        assert _ast_search_python_tests("T-1.1", tmp_path) is False

    def test_scans_subdirectories(self, tmp_path: Path):
        """AST search recurses into subdirectories."""
        sub = tmp_path / "tests" / "unit"
        sub.mkdir(parents=True)
        test_file = sub / "test_deep.py"
        test_file.write_text(textwrap.dedent("""\
            def test_t_1_1_deep():
                pass
        """))
        assert _ast_search_python_tests("T-1.1", tmp_path) is True

    def test_async_function(self, tmp_path: Path):
        """AST search matches async test functions."""
        test_file = tmp_path / "test_async.py"
        test_file.write_text(textwrap.dedent("""\
            async def test_t_1_1_async():
                pass
        """))
        assert _ast_search_python_tests("T-1.1", tmp_path) is True

    def test_star_test_pattern(self, tmp_path: Path):
        """AST search also scans *_test.py files."""
        test_file = tmp_path / "auth_test.py"
        test_file.write_text(textwrap.dedent("""\
            def test_t_1_1():
                pass
        """))
        assert _ast_search_python_tests("T-1.1", tmp_path) is True


# ─── _find_implemented_test_ids ───────────────────────────────────────────────


class TestFindImplementedTestIds:
    def test_tier1_manifest_lookup(self, tmp_path: Path):
        """Manifest hit short-circuits AST and grep."""
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        manifest = {
            "tests": {
                "T-1.1": {"file": "tests/test_a.py", "function": "test_login"},
            }
        }
        (ralph_dir / "test-manifest.json").write_text(json.dumps(manifest))
        result = _find_implemented_test_ids(["T-1.1"], tmp_path, tmp_path)
        assert result == ["T-1.1"]

    def test_tier2_ast_search(self, tmp_path: Path):
        """AST search finds ID when manifest is empty."""
        test_file = tmp_path / "test_auth.py"
        test_file.write_text(textwrap.dedent("""\
            def test_t_1_1_login():
                pass
        """))
        result = _find_implemented_test_ids(["T-1.1"], tmp_path, tmp_path)
        assert result == ["T-1.1"]

    def test_not_found_in_any_tier(self, tmp_path: Path):
        """ID not found in any tier is returned as missing."""
        result = _find_implemented_test_ids(["T-99.99"], tmp_path, tmp_path)
        assert result == []

    def test_multiple_ids_mixed_tiers(self, tmp_path: Path):
        """Different IDs can be found by different tiers."""
        # Set up manifest for T-1.1
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        manifest = {"tests": {"T-1.1": {"file": "a.py", "function": "test_a"}}}
        (ralph_dir / "test-manifest.json").write_text(json.dumps(manifest))

        # Set up AST match for T-2.2
        test_file = tmp_path / "test_b.py"
        test_file.write_text(textwrap.dedent("""\
            def test_t_2_2_feature():
                pass
        """))

        result = _find_implemented_test_ids(
            ["T-1.1", "T-2.2", "T-99.99"], tmp_path, tmp_path
        )
        assert "T-1.1" in result
        assert "T-2.2" in result
        assert "T-99.99" not in result
