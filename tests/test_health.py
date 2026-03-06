"""Tests for service health checker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ralph_pipeline.config import ServiceConfig
from ralph_pipeline.infra.health import ServiceHealthChecker, ServiceHealthResult


class TestServiceHealthChecker:
    def test_check_tcp_success(self):
        checker = ServiceHealthChecker()
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()
            assert checker.check_tcp("localhost", 5432) is True

    def test_check_tcp_failure(self):
        checker = ServiceHealthChecker()
        with patch("socket.create_connection", side_effect=ConnectionRefusedError):
            assert checker.check_tcp("localhost", 5432) is False

    def test_check_tcp_timeout(self):
        checker = ServiceHealthChecker()
        with patch("socket.create_connection", side_effect=TimeoutError):
            assert checker.check_tcp("localhost", 5432) is False

    def test_wait_for_service_immediate(self):
        checker = ServiceHealthChecker()
        svc = ServiceConfig(name="test-db", port=5432, startup_timeout=5)

        with patch.object(checker, "check_tcp", return_value=True):
            result = checker.wait_for_service(svc)
            assert result.healthy is True
            assert result.name == "test-db"
            assert result.wait_seconds >= 0

    def test_wait_for_service_timeout(self):
        checker = ServiceHealthChecker()
        svc = ServiceConfig(name="test-db", port=5432, startup_timeout=1)

        with patch.object(checker, "check_tcp", return_value=False):
            result = checker.wait_for_service(svc)
            assert result.healthy is False
            assert result.error != ""

    def test_wait_all_ready_all_healthy(self):
        checker = ServiceHealthChecker()
        services = [
            ServiceConfig(name="postgres", port=5432, startup_timeout=5),
            ServiceConfig(name="redis", port=6379, startup_timeout=5),
        ]
        healthy_result = ServiceHealthResult(
            name="test", healthy=True, wait_seconds=0.1
        )

        with patch.object(checker, "wait_for_service", return_value=healthy_result):
            report = checker.wait_all_ready(services)
            assert report.all_healthy is True
            assert len(report.services) == 2
