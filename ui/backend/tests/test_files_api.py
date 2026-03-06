"""Integration tests for the Files API."""

import os



class TestFileTree:
    """GET /api/files/<id>/tree"""

    def test_get_tree(self, client, linked_project):
        resp = client.get(f"/api/files/{linked_project['id']}/tree")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["type"] == "directory"
        assert "children" in data

        # The docs folder should be present
        child_names = [c["name"] for c in data["children"]]
        assert "docs" in child_names

    def test_get_tree_nonexistent_project(self, client):
        resp = client.get("/api/files/99999/tree")
        assert resp.status_code == 404


class TestReadFile:
    """GET /api/files/<id>/read"""

    def test_read_file(self, client, linked_project):
        resp = client.get(
            f"/api/files/{linked_project['id']}/read",
            query_string={"path": "README.md"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["path"] == "README.md"
        assert "# Test Project" in data["content"]
        assert data["size"] > 0

    def test_read_file_missing(self, client, linked_project):
        resp = client.get(
            f"/api/files/{linked_project['id']}/read",
            query_string={"path": "nonexistent.txt"},
        )
        assert resp.status_code == 404

    def test_read_file_no_path_param(self, client, linked_project):
        resp = client.get(f"/api/files/{linked_project['id']}/read")
        assert resp.status_code == 400

    def test_read_file_path_traversal_blocked(self, client, linked_project):
        """Security: cannot read files outside project root."""
        resp = client.get(
            f"/api/files/{linked_project['id']}/read",
            query_string={"path": "../../../etc/passwd"},
        )
        assert resp.status_code == 403

    def test_read_large_file_rejected(self, client, linked_project):
        """Files > 1MB should be rejected."""
        project_path = linked_project["root_path"]
        big_file = os.path.join(project_path, "big.txt")
        with open(big_file, "w") as f:
            f.write("x" * 1_100_000)

        resp = client.get(
            f"/api/files/{linked_project['id']}/read",
            query_string={"path": "big.txt"},
        )
        assert resp.status_code == 413

    def test_read_directory_rejected(self, client, linked_project):
        resp = client.get(
            f"/api/files/{linked_project['id']}/read",
            query_string={"path": "docs"},
        )
        assert resp.status_code == 400
