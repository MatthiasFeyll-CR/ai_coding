"""Phase 0: Infrastructure Bootstrap — scaffolding + test infra generation.

Runs ONCE before the milestone loop. Reads declarative test_infrastructure
and scaffolding config, invokes Claude to generate files, verifies lifecycle,
and writes back concrete test_execution commands.
"""

from __future__ import annotations

import json
from pathlib import Path

from ralph_pipeline.ai.claude import ClaudeError, ClaudeRunner
from ralph_pipeline.ai.prompts import (
    phase0_lifecycle_verify_prompt,
    phase0_scaffolding_prompt,
    phase0_test_infra_prompt,
)
from ralph_pipeline.config import PipelineConfig
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import is_dry_run


class Phase0Error(Exception):
    """Raised when Phase 0 bootstrap fails fatally."""

    pass


def run_phase0_bootstrap(
    config: PipelineConfig,
    claude: ClaudeRunner,
    plogger: PipelineLogger,
    project_root: Path,
    config_path: Path,
) -> None:
    """Run Phase 0 Infrastructure Bootstrap.

    Steps:
    1. Scaffolding — create project directory structure + boilerplate
    2. Test infra generation — generate docker-compose.test.yml + Dockerfiles
    3. Lifecycle verification — build → setup → health → smoke → teardown
    4. Write-back — update pipeline-config.json with concrete test_execution
    """
    plogger.section("Phase 0: Infrastructure Bootstrap")

    log_dir = project_root / ".ralph" / "logs" / "phase0"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Scaffolding
    if config.scaffolding and config.scaffolding.enabled:
        _run_scaffolding(config, claude, plogger, project_root, log_dir)
    else:
        plogger.info("Scaffolding: skipped (not configured or disabled)")

    # Step 2: Test infrastructure generation
    if config.test_infrastructure and (
        config.test_infrastructure.services or config.test_infrastructure.runtimes
    ):
        _run_test_infra_generation(config, claude, plogger, project_root, log_dir)
    else:
        plogger.info("Test infrastructure: skipped (not configured)")
        return  # No infra to verify or write back

    # Step 3: Lifecycle verification
    _run_lifecycle_verification(config, claude, plogger, project_root, log_dir)

    # Step 4: Write-back — update config with concrete test_execution
    _write_back_config(config, plogger, project_root, config_path)

    plogger.success("Phase 0: Infrastructure Bootstrap complete")


def _run_scaffolding(
    config: PipelineConfig,
    claude: ClaudeRunner,
    plogger: PipelineLogger,
    project_root: Path,
    log_dir: Path,
) -> None:
    """Step 1: Invoke Claude to create project skeleton."""
    plogger.info("Phase 0 Step 1: Scaffolding — creating project structure")

    if is_dry_run():
        plogger.info("[DRY RUN] Would generate project scaffolding")
        return

    assert config.scaffolding is not None

    prompt = phase0_scaffolding_prompt(
        project_structure_doc=config.scaffolding.project_structure_doc,
        tech_stack_doc=config.scaffolding.tech_stack_doc,
        project_root=str(project_root),
        framework_boilerplate=config.scaffolding.framework_boilerplate,
    )

    log_file = log_dir / "scaffolding.log"

    try:
        claude.run(
            prompt,
            model=config.models.phase0,
            phase="phase0_scaffolding",
            milestone=0,
            log_file=log_file,
        )
    except ClaudeError as e:
        raise Phase0Error("Phase 0 scaffolding failed") from e

    plogger.success("Scaffolding complete")


def _run_test_infra_generation(
    config: PipelineConfig,
    claude: ClaudeRunner,
    plogger: PipelineLogger,
    project_root: Path,
    log_dir: Path,
) -> None:
    """Step 2: Invoke Claude to generate docker-compose + Dockerfiles."""
    plogger.info("Phase 0 Step 2: Generating test infrastructure files")

    if is_dry_run():
        plogger.info("[DRY RUN] Would generate test infrastructure")
        return

    assert config.test_infrastructure is not None

    # Serialize the test_infrastructure spec for the prompt
    test_infra_json = config.test_infrastructure.model_dump_json(indent=2)

    prompt = phase0_test_infra_prompt(
        test_infrastructure_json=test_infra_json,
        project_root=str(project_root),
        compose_file=config.test_infrastructure.compose_file,
    )

    log_file = log_dir / "test-infra-generation.log"

    try:
        claude.run(
            prompt,
            model=config.models.phase0,
            phase="phase0_test_infra",
            milestone=0,
            log_file=log_file,
        )
    except ClaudeError as e:
        raise Phase0Error("Phase 0 test infrastructure generation failed") from e

    # Verify compose file was created
    compose_path = project_root / config.test_infrastructure.compose_file
    if not compose_path.exists():
        raise Phase0Error(
            f"Phase 0 did not produce compose file: {compose_path}"
        )

    plogger.success("Test infrastructure files generated")


def _run_lifecycle_verification(
    config: PipelineConfig,
    claude: ClaudeRunner,
    plogger: PipelineLogger,
    project_root: Path,
    log_dir: Path,
) -> None:
    """Step 3: Invoke Claude to verify build→setup→health→smoke→teardown."""
    plogger.info("Phase 0 Step 3: Lifecycle verification")

    if is_dry_run():
        plogger.info("[DRY RUN] Would verify test infrastructure lifecycle")
        return

    assert config.test_infrastructure is not None

    test_infra_json = config.test_infrastructure.model_dump_json(indent=2)

    prompt = phase0_lifecycle_verify_prompt(
        project_root=str(project_root),
        compose_file=config.test_infrastructure.compose_file,
        test_infrastructure_json=test_infra_json,
    )

    log_file = log_dir / "lifecycle-verification.log"

    try:
        claude.run(
            prompt,
            model=config.models.phase0,
            phase="phase0_lifecycle",
            milestone=0,
            log_file=log_file,
        )
    except ClaudeError as e:
        raise Phase0Error("Phase 0 lifecycle verification failed") from e

    # Check verification report
    report_path = project_root / ".ralph" / "phase0-verification.json"
    if not report_path.exists():
        raise Phase0Error(
            "Phase 0 lifecycle verification did not produce report at "
            f"{report_path}"
        )

    report = json.loads(report_path.read_text())
    if not report.get("verified", False):
        failed_steps = {
            k: v for k, v in report.get("steps", {}).items() if v != "pass"
        }
        raise Phase0Error(
            f"Phase 0 lifecycle verification failed: {failed_steps}"
        )

    plogger.success("Lifecycle verification passed")


def _write_back_config(
    config: PipelineConfig,
    plogger: PipelineLogger,
    project_root: Path,
    config_path: Path,
) -> None:
    """Step 4: Read verification report, update pipeline-config.json.

    - Generates concrete test_execution commands from verification results
    - Removes consumed test_infrastructure and scaffolding sections
    """
    plogger.info("Phase 0 Step 4: Writing back concrete test_execution config")

    if is_dry_run():
        plogger.info("[DRY RUN] Would update pipeline-config.json")
        return

    assert config.test_infrastructure is not None

    report_path = project_root / ".ralph" / "phase0-verification.json"
    report = json.loads(report_path.read_text())

    compose_file = config.test_infrastructure.compose_file
    timeouts = config.test_infrastructure.timeouts

    # Read current config JSON to update it
    config_data = json.loads(config_path.read_text())

    # Build concrete test_execution from verification report
    test_commands = report.get("test_commands", {})

    # Build the first runtime's test command as the primary test command
    runtimes = config.test_infrastructure.runtimes
    if runtimes and test_commands:
        primary_runtime = runtimes[0].name
        primary_cmd = test_commands.get(primary_runtime, "")
        if primary_cmd:
            config_data.setdefault("test_execution", {})
            config_data["test_execution"]["test_command"] = primary_cmd

        # Set integration_test_command from remaining runtimes
        if len(runtimes) > 1:
            secondary_cmds = [
                test_commands.get(rt.name, rt.test_cmd)
                for rt in runtimes[1:]
                if test_commands.get(rt.name, rt.test_cmd)
            ]
            if secondary_cmds:
                config_data["test_execution"]["integration_test_command"] = (
                    " && ".join(secondary_cmds) if len(secondary_cmds) > 1
                    else secondary_cmds[0]
                )

    # Set setup/teardown commands
    config_data.setdefault("test_execution", {})
    config_data["test_execution"]["setup_command"] = (
        f"docker compose -f {compose_file} up -d --build"
    )
    config_data["test_execution"]["teardown_command"] = (
        f"docker compose -f {compose_file} down"
    )
    config_data["test_execution"]["force_teardown_command"] = (
        f"docker compose -f {compose_file} down -v --remove-orphans"
    )
    # Set build_command for explicit image building (separate from setup)
    config_data["test_execution"]["build_command"] = (
        f"docker compose -f {compose_file} build"
    )
    # Set condition — guard check that Docker is available before running tests
    config_data["test_execution"]["condition"] = "command -v docker"
    config_data["test_execution"]["setup_timeout_seconds"] = timeouts.setup_seconds
    config_data["test_execution"]["timeout_seconds"] = timeouts.test_seconds
    config_data["test_execution"]["build_timeout_seconds"] = timeouts.build_seconds

    # Build tier1 config if multiple runtimes
    if len(runtimes) > 1:
        environments = []
        for rt in runtimes:
            cmd = test_commands.get(rt.name, rt.test_cmd)
            environments.append(
                {
                    "name": rt.name,
                    "service": rt.name,
                    "test_command": cmd,
                    "timeout_seconds": timeouts.test_seconds,
                }
            )
        config_data["test_execution"].setdefault("tier1", {})
        config_data["test_execution"]["tier1"]["compose_file"] = compose_file
        config_data["test_execution"]["tier1"]["environments"] = environments

    # Build services health checks from infrastructure services
    # Note: readiness probes (pg_isready, redis-cli ping, etc.) are for Docker
    # Compose healthchecks INSIDE containers. The pipeline's built-in TCP port
    # check handles host-side readiness, so we do NOT copy readiness as
    # ready_command (those tools may not be installed on the host).
    services = []
    for svc in config.test_infrastructure.services:
        services.append(
            {
                "name": svc.name,
                "type": "tcp",
                "host": "localhost",
                "port": svc.port,
                "startup_timeout": timeouts.setup_seconds,
            }
        )
    if services:
        config_data["test_execution"]["services"] = services

    # Remove consumed Phase 0 sections — they're now concrete
    config_data.pop("test_infrastructure", None)
    config_data.pop("scaffolding", None)

    # Write back
    config_path.write_text(json.dumps(config_data, indent=2) + "\n")
    plogger.success(
        "pipeline-config.json updated: test_infrastructure → test_execution"
    )
