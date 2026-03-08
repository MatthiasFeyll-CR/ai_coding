"""Tests for milestone_schema — structured scope validation and prompt formatting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph_pipeline.milestone_schema import (
    MilestoneScope,
    MilestoneScopeValidationError,
    format_scope_for_prompt,
    validate_milestone_scope,
)


def _minimal_scope_data(**overrides) -> dict:
    """Return minimal valid milestone scope data."""
    base = {
        "id": 1,
        "slug": "foundation",
        "name": "Foundation",
        "execution_order": 1,
        "estimated_stories": 5,
        "dependencies": [],
        "mvp": True,
        "features": ["F-1.1"],
        "story_outline": [
            {"order": 1, "summary": "Create users table", "type": "schema"}
        ],
    }
    base.update(overrides)
    return base


class TestMilestoneScope:
    def test_minimal_valid_scope(self):
        scope = MilestoneScope(**_minimal_scope_data())
        assert scope.id == 1
        assert scope.slug == "foundation"
        assert scope.features == ["F-1.1"]

    def test_full_scope(self):
        data = _minimal_scope_data(
            narrative="Foundation milestone sets up core infrastructure.",
            data_model_refs=[
                {
                    "table": "users",
                    "operation": "CREATE",
                    "key_columns": ["id", "email"],
                    "source": "docs/02-architecture/data-model.md#users",
                }
            ],
            api_refs=[
                {
                    "endpoint": "/api/users",
                    "method": "POST",
                    "purpose": "Create user",
                    "auth": "public",
                    "source": "docs/02-architecture/api-design.md#create-user",
                }
            ],
            component_refs=[
                {
                    "name": "UserForm",
                    "type": "component",
                    "source": "docs/03-design/component-specs.md#UserForm",
                }
            ],
            test_ids=["T-1.1.01", "API-1.01"],
            context_weight={
                "unique_file_paths": 15,
                "doc_sections": 3,
                "estimated_stories": 5,
            },
        )
        scope = MilestoneScope(**data)
        assert len(scope.data_model_refs) == 1
        assert scope.data_model_refs[0].table == "users"
        assert len(scope.api_refs) == 1
        assert scope.test_ids == ["T-1.1.01", "API-1.01"]

    def test_empty_features_rejected(self):
        with pytest.raises(Exception, match="at least one feature"):
            MilestoneScope(**_minimal_scope_data(features=[]))

    def test_empty_story_outline_rejected(self):
        with pytest.raises(Exception, match="at least one story outline"):
            MilestoneScope(**_minimal_scope_data(story_outline=[]))


class TestValidateMilestoneScope:
    def test_valid_file(self, tmp_path: Path):
        scope_file = tmp_path / "milestone-1.json"
        scope_file.write_text(json.dumps(_minimal_scope_data()))
        scope = validate_milestone_scope(scope_file)
        assert scope.id == 1
        assert scope.slug == "foundation"

    def test_missing_file(self, tmp_path: Path):
        scope_file = tmp_path / "milestone-99.json"
        with pytest.raises(MilestoneScopeValidationError, match="not found"):
            validate_milestone_scope(scope_file)

    def test_invalid_json(self, tmp_path: Path):
        scope_file = tmp_path / "milestone-1.json"
        scope_file.write_text("{ bad json")
        with pytest.raises(MilestoneScopeValidationError, match="Invalid JSON"):
            validate_milestone_scope(scope_file)

    def test_missing_required_fields(self, tmp_path: Path):
        scope_file = tmp_path / "milestone-1.json"
        scope_file.write_text(json.dumps({"id": 1}))
        with pytest.raises(MilestoneScopeValidationError):
            validate_milestone_scope(scope_file)

    def test_context_weight_warnings_non_fatal(self, tmp_path: Path):
        data = _minimal_scope_data(
            context_weight={
                "unique_file_paths": 35,
                "doc_sections": 8,
                "estimated_stories": 12,
            }
        )
        scope_file = tmp_path / "milestone-1.json"
        scope_file.write_text(json.dumps(data))
        # Should not raise — warnings are non-fatal
        scope = validate_milestone_scope(scope_file)
        assert scope.context_weight.unique_file_paths == 35


class TestFormatScopeForPrompt:
    def test_minimal_format(self):
        scope = MilestoneScope(**_minimal_scope_data())
        result = format_scope_for_prompt(scope)
        assert "## Milestone M1: Foundation" in result
        assert "Slug: foundation" in result
        assert "F-1.1" in result
        assert "Create users table" in result

    def test_format_with_data_model_refs(self):
        data = _minimal_scope_data(
            data_model_refs=[
                {
                    "table": "users",
                    "operation": "CREATE",
                    "key_columns": ["id", "email"],
                    "source": "docs/02-architecture/data-model.md#users",
                }
            ]
        )
        scope = MilestoneScope(**data)
        result = format_scope_for_prompt(scope)
        assert "### Data Model References" in result
        assert "| users | CREATE |" in result

    def test_format_with_api_refs(self):
        data = _minimal_scope_data(
            api_refs=[
                {
                    "endpoint": "/api/users",
                    "method": "POST",
                    "purpose": "Create user",
                    "auth": "required",
                    "source": "docs/02-architecture/api-design.md",
                }
            ]
        )
        scope = MilestoneScope(**data)
        result = format_scope_for_prompt(scope)
        assert "### API Endpoint References" in result
        assert "| /api/users | POST |" in result

    def test_format_with_test_ids(self):
        data = _minimal_scope_data(test_ids=["T-1.1.01", "API-1.01", "T-1.2.03"])
        scope = MilestoneScope(**data)
        result = format_scope_for_prompt(scope)
        assert "### Test IDs:" in result
        assert "T-1.1.01" in result
        assert "API-1.01" in result

    def test_format_with_narrative(self):
        data = _minimal_scope_data(narrative="This milestone builds the core.")
        scope = MilestoneScope(**data)
        result = format_scope_for_prompt(scope)
        assert "### Narrative" in result
        assert "This milestone builds the core." in result

    def test_format_omits_empty_sections(self):
        scope = MilestoneScope(**_minimal_scope_data())
        result = format_scope_for_prompt(scope)
        assert "### Data Model References" not in result
        assert "### API Endpoint References" not in result
        assert "### AI Agent References" not in result
        assert "### Notes" not in result

    def test_format_with_all_sections(self):
        data = _minimal_scope_data(
            narrative="Full milestone.",
            data_model_refs=[{"table": "t", "operation": "CREATE", "source": "s"}],
            api_refs=[{"endpoint": "/e", "method": "GET", "source": "s"}],
            component_refs=[{"name": "C", "type": "page", "source": "s"}],
            ai_agent_refs=[{"agent": "A", "purpose": "p", "source": "s"}],
            shared_components=[
                {"component": "SC", "status": "new", "introduced_in": "M1"}
            ],
            test_ids=["T-1"],
            acceptance_criteria=["All tests pass"],
            notes=["Watch for circular deps"],
        )
        scope = MilestoneScope(**data)
        result = format_scope_for_prompt(scope)
        assert "### Data Model References" in result
        assert "### API Endpoint References" in result
        assert "### Page & Component References" in result
        assert "### AI Agent References" in result
        assert "### Shared Components Required" in result
        assert "### Test IDs:" in result
        assert "### Milestone Acceptance Criteria" in result
        assert "### Notes" in result
