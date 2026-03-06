"""Pydantic config models — replaces 50+ global variables from pipeline.sh load_config()."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator


class ProjectConfig(BaseModel):
    name: str
    description: str = ""


class PathsConfig(BaseModel):
    docs_dir: str = "docs"
    tasks_dir: str = "tasks"
    scripts_dir: str = ".ralph"
    skills_dir: str = "~/.claude/skills"
    qa_dir: str = "docs/08-qa"
    reconciliation_dir: str = "docs/05-reconciliation"
    milestones_dir: str = "docs/05-milestones"
    archive_dir: str = ".ralph/archive"


class MilestoneConfig(BaseModel):
    id: int
    slug: str
    name: str
    stories: int
    dependencies: list[int] = []


class ModelsConfig(BaseModel):
    """Controls which Claude model is used for each pipeline phase.
    Empty string = CLI default (typically Opus)."""

    ralph: str = ""
    prd_generation: str = ""
    qa_review: str = ""
    test_fix: str = ""
    gate_fix: str = ""
    reconciliation: str = ""


class RalphConfig(BaseModel):
    tool: str = "claude"
    max_iterations_multiplier: int = 3
    stuck_threshold: int = 3


class QAConfig(BaseModel):
    max_bugfix_cycles: int = 3


class GateCheck(BaseModel):
    name: str
    command: str
    condition: str = ""
    required: bool = True


class GateChecksConfig(BaseModel):
    max_fix_cycles: int = 3
    checks: list[GateCheck] = []


class ServiceConfig(BaseModel):
    """Structured health check definition for a test dependency service."""

    name: str
    type: str = "tcp"
    host: str = "localhost"
    port: int
    startup_timeout: int = 30
    ready_command: str = ""


class Tier1Environment(BaseModel):
    name: str
    service: str
    test_command: str
    build_command: str = ""
    rebuild_trigger_files: list[str] = []
    condition: str = ""
    timeout_seconds: int = 300


class Tier1Config(BaseModel):
    compose_file: str = ""
    teardown_command: str = ""
    setup_command: str = ""
    setup_timeout_seconds: int = 120
    build_timeout_seconds: int = 300
    image_hash_file: str = ".ralph/.test-image-hashes"
    environments: list[Tier1Environment] = []


class TestExecutionConfig(BaseModel):
    test_command: str = ""
    integration_test_command: Optional[str] = None
    timeout_seconds: int = 300
    max_fix_cycles: int = 5
    condition: str = ""
    build_command: Optional[str] = None
    build_timeout_seconds: int = 300
    setup_command: Optional[str] = None
    teardown_command: Optional[str] = None
    force_teardown_command: Optional[str] = None
    setup_timeout_seconds: int = 120
    tier1: Tier1Config = Tier1Config()
    services: list[ServiceConfig] = []


class EnvSetupConfig(BaseModel):
    """Legacy env_setup config — kept for backward compatibility.

    Deprecated: Use .ai.env file in the project root instead.
    """

    source_file: Optional[str] = None
    setup_function: Optional[str] = None


class AIEnvConfig(BaseModel):
    """AI credentials configuration — .ai.env file in the target project."""

    env_file: str = ".ai.env"
    required_keys: list[str] = ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"]


class RetryConfig(BaseModel):
    max_retries: int = 3
    backoff_seconds: int = 30


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration. Loaded from pipeline-config.json."""

    project: ProjectConfig
    paths: PathsConfig = PathsConfig()
    milestones: list[MilestoneConfig]
    models: ModelsConfig = ModelsConfig()
    ralph: RalphConfig = RalphConfig()
    qa: QAConfig = QAConfig()
    gate_checks: GateChecksConfig = GateChecksConfig()
    test_execution: TestExecutionConfig = TestExecutionConfig()
    env_setup: EnvSetupConfig = EnvSetupConfig()  # Legacy — ignored
    ai_env: AIEnvConfig = AIEnvConfig()
    retry: RetryConfig = RetryConfig()

    @field_validator("milestones")
    @classmethod
    def validate_dependencies(
        cls, milestones: list[MilestoneConfig]
    ) -> list[MilestoneConfig]:
        """Validate: no missing dependency IDs, no circular deps, order respected."""
        ids = {m.id for m in milestones}
        id_order = {m.id: i for i, m in enumerate(milestones)}
        for m in milestones:
            for dep in m.dependencies:
                if dep not in ids:
                    raise ValueError(f"M{m.id} depends on M{dep} which doesn't exist")
                if id_order[dep] >= id_order[m.id]:
                    raise ValueError(
                        f"M{m.id} depends on M{dep} which comes after it in execution order"
                    )
        return milestones

    @classmethod
    def load(cls, path: Path) -> PipelineConfig:
        """Load and validate config from JSON file."""
        data = json.loads(path.read_text())
        return cls(**data)
