"""PRD JSON schema — validates and parses prd-mN.json files.

The PRD Writer produces these; the pipeline validates and uses them
to derive runtime parameters like iteration budgets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class StoryContext(BaseModel):
    """Embedded context references for a single user story."""

    data_model: list[str] = []
    api_endpoints: list[str] = []
    test_cases: list[str] = []
    components: list[str] = []
    existing_code: list[str] = []
    ai_specs: list[str] = []


class UserStory(BaseModel):
    """A single user story within the PRD."""

    id: str  # e.g. "US-001" or "BF-001"
    title: str
    description: str = ""
    acceptanceCriteria: list[str] = []
    priority: int = 1
    passes: bool = False
    testIds: list[str] = []
    notes: str = ""
    context: Optional[StoryContext] = None


class PRD(BaseModel):
    """Top-level PRD (Product Requirements Document) schema.

    Produced by the PRD Writer skill, consumed by Ralph and QA phases.
    """

    project: str = ""
    branchName: str = ""
    description: str = ""
    userStories: list[UserStory] = []

    @property
    def story_count(self) -> int:
        """Return the number of user stories in this PRD."""
        return len(self.userStories)

    @property
    def pending_story_count(self) -> int:
        """Return the number of stories that have not yet passed."""
        return sum(1 for s in self.userStories if not s.passes)

    @classmethod
    def load(cls, path: Path) -> PRD:
        """Load and validate a PRD from JSON file.

        Raises:
            PRDLoadError: If the file doesn't exist, is invalid JSON,
                          or fails schema validation.
        """
        if not path.exists():
            raise PRDLoadError(path, f"PRD file not found: {path}")
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise PRDLoadError(path, f"Invalid JSON in {path}: {e}") from e
        try:
            return cls(**data)
        except Exception as e:
            raise PRDLoadError(path, f"PRD schema validation failed: {e}") from e


class PRDLoadError(Exception):
    """Raised when a PRD file cannot be loaded or validated."""

    def __init__(self, path: Path, message: str):
        self.path = path
        super().__init__(message)
