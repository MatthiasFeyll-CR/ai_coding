"""Test infrastructure lifecycle — Docker test containers for Tier 1 + Tier 2."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from ralph_pipeline.config import TestExecutionConfig, Tier1Environment
from ralph_pipeline.infra.health import HealthReport, ServiceHealthChecker
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.subprocess_utils import SubprocessError, run_command

logger = logging.getLogger(__name__)


class InfraError(Exception):
    """Raised when test infrastructure fails — always a HARD STOP."""

    def __init__(self, message: str, report: HealthReport | None = None):
        super().__init__(message)
        self.report = report


class TestInfraManager:
    """Manages Docker test infrastructure lifecycle for both tiers."""

    def __init__(
        self,
        config: TestExecutionConfig,
        project_root: Path,
        health_checker: ServiceHealthChecker,
        plogger: PipelineLogger,
    ):
        self.config = config
        self.project_root = project_root
        self.health = health_checker
        self.log = plogger
        self._tier2_ready = False
        self._tier1_ready = False

    # ─── Tier 2 (Full rebuild, post-merge) ────────────────────────────────

    def ensure_tier2(self) -> None:
        """Full rebuild: teardown → build (no-cache) → setup → health check."""
        self._teardown_force()
        self._build_images()
        self._setup_services()
        self._verify_health()
        self._tier2_ready = True

    def _teardown_force(self) -> None:
        """Force teardown of all containers."""
        if self.config.teardown_command:
            self._run_infra_cmd(
                self.config.teardown_command, timeout=30, label="teardown"
            )
        if self.config.force_teardown_command:
            self.log.info("[test-infra] Running force teardown...")
            self._run_infra_cmd(
                self.config.force_teardown_command, timeout=60, label="force-teardown"
            )

    def _build_images(self) -> None:
        """Build application images (no cache)."""
        if not self.config.build_command:
            return
        self.log.info("[test-infra] Building application images...")
        try:
            self._run_infra_cmd(
                self.config.build_command,
                timeout=self.config.build_timeout_seconds,
                label="build",
            )
            self.log.success("[test-infra] Build complete")
        except SubprocessError as e:
            self.log.error(f"[test-infra] Build FAILED: {e}")
            raise InfraError(f"Test infrastructure build failed: {e}") from e

    def _setup_services(self) -> None:
        """Start dependency services."""
        if not self.config.setup_command:
            return
        self.log.info("[test-infra] Starting fresh test infrastructure...")
        try:
            self._run_infra_cmd(
                self.config.setup_command,
                timeout=self.config.setup_timeout_seconds,
                label="setup",
            )
            self.log.success("[test-infra] Infrastructure ready")
        except SubprocessError as e:
            self.log.error(f"[test-infra] Setup FAILED: {e}")
            raise InfraError(f"Test infrastructure setup failed: {e}") from e

    def _verify_health(self) -> None:
        """Check all configured services. HARD STOP if any unhealthy."""
        if not self.config.services:
            return
        report = self.health.wait_all_ready(self.config.services)
        for r in report.services:
            if r.healthy:
                self.log.success(
                    f"{r.name} tcp:{self._port_for(r.name)} ready ({r.wait_seconds:.1f}s)"
                )
            else:
                self.log.error(f"{r.name}: {r.error}")
        if not report.all_healthy:
            raise InfraError("Test infrastructure health check failed", report)

    def _port_for(self, name: str) -> int:
        """Look up port for a service by name."""
        for s in self.config.services:
            if s.name == name:
                return s.port
        return 0

    # ─── Tier 1 (Dev containers, bind-mounted) ───────────────────────────

    def ensure_tier1(self) -> None:
        """Dev containers: teardown → build-if-needed (hash) → setup → health check."""
        if not self.config.tier1.compose_file:
            return
        self._t1_teardown()
        self._t1_build_if_needed()
        self._t1_setup()
        self._verify_health()
        self._tier1_ready = True

    def _t1_teardown(self) -> None:
        if not self.config.tier1.teardown_command:
            return
        self.log.info("[tier1-infra] Tearing down containers + volumes...")
        self._run_infra_cmd(
            self.config.tier1.teardown_command, timeout=60, label="tier1-teardown"
        )
        self._tier1_ready = False

    def _t1_build_if_needed(self) -> None:
        for env in self.config.tier1.environments:
            if not env.build_command:
                continue
            if self._t1_needs_rebuild(env):
                self.log.info(
                    f"[tier1-infra] Dependencies changed for '{env.name}' — rebuilding image..."
                )
                try:
                    self._run_infra_cmd(
                        env.build_command,
                        timeout=self.config.tier1.build_timeout_seconds,
                        label=f"tier1-build-{env.name}",
                    )
                    self.log.success(
                        f"[tier1-infra] Image '{env.name}' built successfully"
                    )
                    new_hash = self._t1_compute_dep_hash(env)
                    self._t1_store_hash(env, new_hash)
                except SubprocessError as e:
                    self.log.error(
                        f"[tier1-infra] Image build FAILED for '{env.name}': {e}"
                    )
                    raise InfraError(f"Tier 1 build failed for {env.name}") from e
            else:
                self.log.info(
                    f"[tier1-infra] Image '{env.name}' up-to-date (deps unchanged)"
                )

    def _t1_setup(self) -> None:
        if not self.config.tier1.setup_command:
            return
        self.log.info("[tier1-infra] Starting fresh test infrastructure...")
        try:
            self._run_infra_cmd(
                self.config.tier1.setup_command,
                timeout=self.config.tier1.setup_timeout_seconds,
                label="tier1-setup",
            )
            self.log.success("[tier1-infra] Infrastructure ready")
            self._tier1_ready = True
        except SubprocessError as e:
            self.log.error(f"[tier1-infra] Setup FAILED: {e}")
            raise InfraError(f"Tier 1 setup failed: {e}") from e

    def _t1_compute_dep_hash(self, env: Tier1Environment) -> str:
        """Hash dependency files for an environment."""
        if not env.rebuild_trigger_files:
            return "no-trigger-files"
        h = hashlib.md5()
        for f in env.rebuild_trigger_files:
            fpath = self.project_root / f
            if fpath.is_file():
                h.update(fpath.read_bytes())
            else:
                h.update(f"missing:{f}".encode())
        return h.hexdigest()

    def _t1_needs_rebuild(self, env: Tier1Environment) -> bool:
        """Compare current hash against stored hash."""
        current = self._t1_compute_dep_hash(env)
        hash_file = self.project_root / self.config.tier1.image_hash_file
        if not hash_file.exists():
            return True
        try:
            data = json.loads(hash_file.read_text())
            stored = data.get(env.name, "")
            return current != stored
        except (json.JSONDecodeError, KeyError):
            return True

    def _t1_store_hash(self, env: Tier1Environment, hash_val: str) -> None:
        """Persist hash to image hash file."""
        hash_file = self.project_root / self.config.tier1.image_hash_file
        hash_file.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if hash_file.exists():
            try:
                data = json.loads(hash_file.read_text())
            except json.JSONDecodeError:
                pass
        data[env.name] = hash_val
        hash_file.write_text(json.dumps(data, indent=2))

    # ─── Teardown ─────────────────────────────────────────────────────────

    def teardown_all(self) -> None:
        """Called on exit/cleanup."""
        if self._tier1_ready:
            self._t1_teardown()
        if self._tier2_ready:
            self._teardown_force()

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _run_infra_cmd(
        self, cmd: str, timeout: int = 300, label: str = "infra"
    ) -> None:
        """Run an infrastructure command (shell string)."""
        try:
            run_command(
                cmd,
                cwd=self.project_root,
                timeout=timeout,
                check=False,
                shell=True,
            )
        except SubprocessError:
            logger.warning("[%s] Command returned non-zero", label)
