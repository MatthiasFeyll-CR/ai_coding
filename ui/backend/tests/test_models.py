"""Unit tests for SQLAlchemy models."""

import os

import pytest


class TestProjectModel:
    """Project model unit tests."""

    def test_create_project(self, app, db_session):
        from models import Project

        p = Project(
            name="test-project",
            root_path="/tmp/test-project",
            config_path="/tmp/test-project/pipeline-config.json",
            status="initialized",
        )
        db_session.add(p)
        db_session.commit()

        assert p.id is not None
        assert p.name == "test-project"
        assert p.status == "initialized"

    def test_to_dict_has_required_keys(self, app, db_session):
        from models import Project

        p = Project(
            name="test",
            root_path="/tmp/nonexistent",
            config_path="/tmp/nonexistent/pipeline-config.json",
            status="initialized",
        )
        db_session.add(p)
        db_session.commit()

        d = p.to_dict()
        required = {
            "id",
            "name",
            "root_path",
            "project_path",
            "config_path",
            "status",
            "is_setup",
            "last_run_at",
            "created_at",
            "updated_at",
        }
        assert required.issubset(d.keys())

    def test_is_setup_false_without_config_file(self, app, db_session):
        from models import Project

        p = Project(
            name="test",
            root_path="/tmp/definitely-does-not-exist-12345",
            config_path="/tmp/definitely-does-not-exist-12345/pipeline-config.json",
            status="initialized",
        )
        db_session.add(p)
        db_session.commit()

        assert p.to_dict()["is_setup"] is False

    def test_is_setup_true_with_config_file(self, app, db_session, sample_project_with_config):
        from models import Project

        p = Project(
            name="test",
            root_path=sample_project_with_config,
            config_path=os.path.join(sample_project_with_config, "pipeline-config.json"),
            status="initialized",
        )
        db_session.add(p)
        db_session.commit()

        assert p.to_dict()["is_setup"] is True

    def test_is_setup_false_while_configuring(self, app, db_session, sample_project_with_config):
        from models import Project

        p = Project(
            name="test",
            root_path=sample_project_with_config,
            config_path=os.path.join(sample_project_with_config, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(p)
        db_session.commit()

        assert p.to_dict()["is_setup"] is False

    def test_unique_root_path(self, app, db_session):
        from models import Project
        from sqlalchemy.exc import IntegrityError

        p1 = Project(
            name="a",
            root_path="/tmp/unique",
            config_path="/tmp/unique/config.json",
        )
        p2 = Project(
            name="b",
            root_path="/tmp/unique",
            config_path="/tmp/unique/config.json",
        )
        db_session.add(p1)
        db_session.commit()
        db_session.add(p2)

        with pytest.raises(IntegrityError):
            db_session.commit()


class TestStateSnapshotModel:
    def test_create_snapshot(self, app, db_session):
        from models import Project, StateSnapshot

        p = Project(
            name="test",
            root_path="/tmp/snap",
            config_path="/tmp/snap/c.json",
        )
        db_session.add(p)
        db_session.commit()

        snap = StateSnapshot(
            project_id=p.id,
            state_json='{"phase": "test"}',
            snapshot_type="manual",
        )
        db_session.add(snap)
        db_session.commit()

        assert snap.id is not None
        d = snap.to_dict()
        assert d["snapshot_type"] == "manual"
        assert d["state_json"] == '{"phase": "test"}'


class TestTokenUsageModel:
    def test_create_token_usage(self, app, db_session):
        from models import Project, TokenUsage

        p = Project(
            name="test",
            root_path="/tmp/tok",
            config_path="/tmp/tok/c.json",
        )
        db_session.add(p)
        db_session.commit()

        t = TokenUsage(
            project_id=p.id,
            milestone_id=1,
            phase="prd",
            model="claude-opus-4",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.05,
        )
        db_session.add(t)
        db_session.commit()

        d = t.to_dict()
        assert d["input_tokens"] == 1000
        assert d["cost_usd"] == 0.05


class TestModelConfigModel:
    def test_unique_project_phase(self, app, db_session):
        from models import ModelConfig, Project
        from sqlalchemy.exc import IntegrityError

        p = Project(
            name="test",
            root_path="/tmp/mc",
            config_path="/tmp/mc/c.json",
        )
        db_session.add(p)
        db_session.commit()

        c1 = ModelConfig(project_id=p.id, phase="prd", model="claude-opus-4")
        c2 = ModelConfig(project_id=p.id, phase="prd", model="claude-3-5-sonnet")
        db_session.add(c1)
        db_session.commit()
        db_session.add(c2)

        with pytest.raises(IntegrityError):
            db_session.commit()


class TestExecutionLogModel:
    def test_create_log(self, app, db_session):
        from models import ExecutionLog, Project

        p = Project(
            name="test",
            root_path="/tmp/log",
            config_path="/tmp/log/c.json",
        )
        db_session.add(p)
        db_session.commit()

        log = ExecutionLog(
            project_id=p.id,
            milestone_id=1,
            phase="ralph_execution",
            log_level="info",
            message="Test log message",
        )
        db_session.add(log)
        db_session.commit()

        d = log.to_dict()
        assert d["message"] == "Test log message"
        assert d["log_level"] == "info"


class TestCascadeDelete:
    def test_deleting_project_deletes_related(self, app, db_session):
        from models import ExecutionLog, Project, StateSnapshot, TokenUsage

        p = Project(
            name="test",
            root_path="/tmp/cascade",
            config_path="/tmp/cascade/c.json",
        )
        db_session.add(p)
        db_session.commit()

        db_session.add(
            StateSnapshot(project_id=p.id, state_json="{}", snapshot_type="auto")
        )
        db_session.add(
            ExecutionLog(project_id=p.id, message="log", log_level="info")
        )
        db_session.add(
            TokenUsage(
                project_id=p.id,
                model="claude-opus-4",
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
            )
        )
        db_session.commit()

        db_session.delete(p)
        db_session.commit()

        assert StateSnapshot.query.count() == 0
        assert ExecutionLog.query.count() == 0
        assert TokenUsage.query.count() == 0
