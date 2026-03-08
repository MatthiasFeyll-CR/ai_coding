"""Milestone scope JSON schema — structured bridge between planning and execution.

Replaces free-form milestone-N.md with machine-parseable milestone-N.json.
The Strategy Planner produces these; the pipeline validates and injects them
into the PRD Writer prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, field_validator


class DataModelRef(BaseModel):
    """Reference to a data model table from architecture docs."""

    table: str
    operation: str  # CREATE, READ, UPDATE, DELETE
    key_columns: list[str] = []
    source: str  # e.g. "docs/02-architecture/data-model.md#users"


class ApiRef(BaseModel):
    """Reference to an API endpoint from architecture docs."""

    endpoint: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    purpose: str = ""
    auth: str = ""  # e.g. "required", "public", "admin"
    source: str = ""


class ComponentRef(BaseModel):
    """Reference to a UI page or component from design docs."""

    name: str
    type: str  # "page", "component", "layout", "shared"
    source: str = ""


class AIAgentRef(BaseModel):
    """Reference to an AI agent from AI docs."""

    agent: str
    purpose: str = ""
    source: str = ""


class SharedComponentRef(BaseModel):
    """Reference to a shared/cross-cutting component."""

    component: str
    status: str = ""  # "new", "exists", "extends"
    introduced_in: str = ""  # e.g. "M1"


class StoryOutlineItem(BaseModel):
    """One item in the suggested story outline."""

    order: int
    summary: str
    type: str  # "schema", "api", "component", "page", "integration", "ai", "test"


class ContextWeight(BaseModel):
    """Context weight metrics for the milestone."""

    unique_file_paths: int = 0
    doc_sections: int = 0
    estimated_stories: int = 0


class MilestoneScope(BaseModel):
    """Complete structured milestone scope — replaces milestone-N.md.

    Produced by Strategy Planner, consumed by pipeline + PRD Writer.
    """

    id: int
    slug: str
    name: str
    execution_order: int
    estimated_stories: int
    dependencies: list[int] = []
    mvp: bool = True
    narrative: str = ""  # Free-form prose for human context

    features: list[str]  # Feature IDs, e.g. ["F-2.1", "F-2.2"]

    data_model_refs: list[DataModelRef] = []
    api_refs: list[ApiRef] = []
    component_refs: list[ComponentRef] = []
    ai_agent_refs: list[AIAgentRef] = []
    shared_components: list[SharedComponentRef] = []

    story_outline: list[StoryOutlineItem] = []
    test_ids: list[str] = []  # e.g. ["T-2.1.01", "API-2.01"]

    acceptance_criteria: list[str] = []
    notes: list[str] = []  # Implementation warnings, risks

    context_weight: ContextWeight = ContextWeight()

    @field_validator("features")
    @classmethod
    def features_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Milestone must reference at least one feature")
        return v

    @field_validator("story_outline")
    @classmethod
    def story_outline_not_empty(
        cls, v: list[StoryOutlineItem]
    ) -> list[StoryOutlineItem]:
        if not v:
            raise ValueError("Milestone must have at least one story outline item")
        return v

    @classmethod
    def load(cls, path: Path) -> MilestoneScope:
        """Load and validate a milestone scope from JSON file."""
        data = json.loads(path.read_text())
        return cls(**data)


class MilestoneScopeValidationError(Exception):
    """Raised when milestone scope JSON fails validation."""

    def __init__(self, milestone_id: int, errors: list[str]):
        self.milestone_id = milestone_id
        self.errors = errors
        msg = f"Milestone M{milestone_id} scope validation failed:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        super().__init__(msg)


def validate_milestone_scope(
    scope_path: Path,
) -> MilestoneScope:
    """Validate a milestone scope JSON file.

    Returns the parsed MilestoneScope on success.
    Raises MilestoneScopeValidationError on failure.
    """
    errors: list[str] = []

    if not scope_path.exists():
        raise MilestoneScopeValidationError(
            milestone_id=0,
            errors=[f"Milestone scope file not found: {scope_path}"],
        )

    try:
        raw = json.loads(scope_path.read_text())
    except json.JSONDecodeError as e:
        raise MilestoneScopeValidationError(
            milestone_id=0,
            errors=[f"Invalid JSON in {scope_path}: {e}"],
        )

    # Extract ID for error reporting before full validation
    milestone_id = raw.get("id", 0)

    try:
        scope = MilestoneScope(**raw)
    except Exception as e:
        raise MilestoneScopeValidationError(
            milestone_id=milestone_id,
            errors=[str(e)],
        )

    # Additional semantic checks
    if scope.context_weight.unique_file_paths > 30:
        errors.append(
            f"Context weight warning: {scope.context_weight.unique_file_paths} "
            f"file paths (threshold: 30)"
        )

    if scope.context_weight.doc_sections > 5:
        errors.append(
            f"Context weight warning: {scope.context_weight.doc_sections} "
            f"doc sections (threshold: 5)"
        )

    if scope.context_weight.estimated_stories > 10:
        errors.append(
            f"Context weight warning: {scope.context_weight.estimated_stories} "
            f"stories (threshold: 10)"
        )

    # Context weight warnings are non-fatal — log them but don't fail
    # Only Pydantic validation errors above are fatal

    return scope


def format_scope_for_prompt(scope: MilestoneScope) -> str:
    """Format a MilestoneScope as structured text for injection into the PRD Writer prompt.

    This replaces the AI's need to parse prose from milestone scope files.
    The PRD Writer receives pre-parsed, structured references directly.
    """
    lines: list[str] = []
    lines.append(f"## Milestone M{scope.id}: {scope.name}")
    lines.append(f"- Slug: {scope.slug}")
    lines.append(f"- Execution order: {scope.execution_order}")
    lines.append(f"- Estimated stories: {scope.estimated_stories}")
    lines.append(f"- Dependencies: {scope.dependencies or 'None'}")
    lines.append(f"- MVP: {'Yes' if scope.mvp else 'No'}")
    lines.append("")

    if scope.narrative:
        lines.append("### Narrative")
        lines.append(scope.narrative)
        lines.append("")

    lines.append(f"### Features: {', '.join(scope.features)}")
    lines.append("")

    if scope.data_model_refs:
        lines.append("### Data Model References")
        lines.append("| Table | Operation | Key Columns | Source |")
        lines.append("|-------|-----------|-------------|--------|")
        for ref in scope.data_model_refs:
            cols = ", ".join(ref.key_columns) if ref.key_columns else "—"
            lines.append(f"| {ref.table} | {ref.operation} | {cols} | {ref.source} |")
        lines.append("")

    if scope.api_refs:
        lines.append("### API Endpoint References")
        lines.append("| Endpoint | Method | Purpose | Auth | Source |")
        lines.append("|----------|--------|---------|------|--------|")
        for ref in scope.api_refs:
            lines.append(
                f"| {ref.endpoint} | {ref.method} | {ref.purpose} | {ref.auth} | {ref.source} |"
            )
        lines.append("")

    if scope.component_refs:
        lines.append("### Page & Component References")
        lines.append("| Name | Type | Source |")
        lines.append("|------|------|--------|")
        for ref in scope.component_refs:
            lines.append(f"| {ref.name} | {ref.type} | {ref.source} |")
        lines.append("")

    if scope.ai_agent_refs:
        lines.append("### AI Agent References")
        lines.append("| Agent | Purpose | Source |")
        lines.append("|-------|---------|--------|")
        for ref in scope.ai_agent_refs:
            lines.append(f"| {ref.agent} | {ref.purpose} | {ref.source} |")
        lines.append("")

    if scope.shared_components:
        lines.append("### Shared Components Required")
        lines.append("| Component | Status | Introduced In |")
        lines.append("|-----------|--------|---------------|")
        for sc in scope.shared_components:
            lines.append(f"| {sc.component} | {sc.status} | {sc.introduced_in} |")
        lines.append("")

    if scope.story_outline:
        lines.append("### Story Outline (Suggested Order)")
        for item in scope.story_outline:
            lines.append(f"{item.order}. [{item.type}] {item.summary}")
        lines.append("")

    if scope.test_ids:
        lines.append(f"### Test IDs: {', '.join(scope.test_ids)}")
        lines.append("")

    if scope.acceptance_criteria:
        lines.append("### Milestone Acceptance Criteria")
        for ac in scope.acceptance_criteria:
            lines.append(f"- [ ] {ac}")
        lines.append("")

    if scope.notes:
        lines.append("### Notes")
        for note in scope.notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)
