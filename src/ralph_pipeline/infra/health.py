"""Service health checker — TCP socket checks + optional ready commands."""

from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass

from ralph_pipeline.config import ServiceConfig


@dataclass
class ServiceHealthResult:
    name: str
    healthy: bool
    wait_seconds: float
    error: str = ""


@dataclass
class HealthReport:
    services: list[ServiceHealthResult]
    all_healthy: bool


class ServiceHealthChecker:
    """Built-in health check system. Uses TCP socket connects with
    exponential backoff retry. Deterministic and framework-controlled."""

    def check_tcp(self, host: str, port: int, timeout: float = 1.0) -> bool:
        """TCP connect check. Returns True if port is accepting connections."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False

    def wait_for_service(self, service: ServiceConfig) -> ServiceHealthResult:
        """Wait for a single service to become ready.
        1. Poll TCP port with exponential backoff until open or timeout.
        2. If ready_command is set, run it after TCP is open.
        """
        start = time.monotonic()
        deadline = start + service.startup_timeout
        backoff = 0.5

        # Phase 1: Wait for TCP port
        tcp_open = False
        while time.monotonic() < deadline:
            if self.check_tcp(service.host, service.port):
                tcp_open = True
                break
            time.sleep(min(backoff, 5.0))
            backoff *= 2

        if not tcp_open:
            return ServiceHealthResult(
                name=service.name,
                healthy=False,
                wait_seconds=time.monotonic() - start,
                error=f"TCP port {service.port} not open after {service.startup_timeout}s",
            )

        # Phase 2: Run ready_command if defined
        if service.ready_command:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return ServiceHealthResult(
                    name=service.name,
                    healthy=False,
                    wait_seconds=time.monotonic() - start,
                    error="No time remaining for ready_command after TCP wait",
                )
            try:
                subprocess.run(
                    service.ready_command,
                    shell=True,
                    timeout=remaining,
                    check=True,
                    capture_output=True,
                )
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                return ServiceHealthResult(
                    name=service.name,
                    healthy=False,
                    wait_seconds=time.monotonic() - start,
                    error=f"ready_command failed: {e}",
                )

        return ServiceHealthResult(
            name=service.name,
            healthy=True,
            wait_seconds=time.monotonic() - start,
        )

    def wait_all_ready(self, services: list[ServiceConfig]) -> HealthReport:
        """Check all services. Returns structured report with per-service status."""
        results = [self.wait_for_service(s) for s in services]
        return HealthReport(
            services=results,
            all_healthy=all(r.healthy for r in results),
        )
