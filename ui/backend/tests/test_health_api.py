"""Integration tests for the Health API."""



class TestHealthCheck:
    """GET /api/health"""

    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "ralph-pipeline-ui"


class TestRequirementsCheck:
    """POST /api/requirements/check — exercises system checks."""

    def test_check_requirements_runs(self, client):
        """Requirements check should return a structured response even if some fail."""
        resp = client.post("/api/requirements/check")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] in ("passed", "failed")
        assert "checks" in data
        assert isinstance(data["checks"], list)
        assert len(data["checks"]) >= 5  # python, docker, etc.

        # Python should always pass in our test env
        python_check = next(c for c in data["checks"] if c["name"] == "python")
        assert python_check["status"] == "passed"

    def test_requirements_check_persists(self, client):
        """Checks should be saved to DB and retrievable."""
        client.post("/api/requirements/check")

        resp = client.get("/api/requirements/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 5


class TestRequirementsStatus:
    """GET /api/requirements/status"""

    def test_status_empty(self, client):
        resp = client.get("/api/requirements/status")
        assert resp.status_code == 200
        assert resp.get_json() == []
