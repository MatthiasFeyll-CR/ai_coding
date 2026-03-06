"""Additional model tests.

Tests the ProjectSetup and InfrastructureBackup models
that were not covered in the existing test_models.py.
Also covers RequirementCheck to_dict.
"""

import json
import os


class TestProjectSetupModel:
    """Test ProjectSetup database model."""

    def test_create_setup(self, app, db_session, sample_project_dir):
        """Can create a ProjectSetup record."""
        from models import Project, ProjectSetup

        project = Project(
            name="setup-test",
            root_path=sample_project_dir,
            config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(project)
        db_session.commit()

        setup = ProjectSetup(
            project_id=project.id,
            status="checking",
            current_step="pre-check",
            progress=10,
        )
        db_session.add(setup)
        db_session.commit()

        assert setup.id is not None
        assert setup.project_id == project.id
        assert setup.status == "checking"
        assert setup.progress == 10

    def test_to_dict_has_required_keys(self, app, db_session, sample_project_dir):
        """to_dict() should include all required keys."""
        from models import Project, ProjectSetup

        project = Project(
            name="setup-test",
            root_path=sample_project_dir,
            config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(project)
        db_session.commit()

        setup = ProjectSetup(
            project_id=project.id,
            status="validating",
            current_step="test_environment_validation",
            progress=60,
            auto_fix_attempts=1,
            configurator_output="output text",
            validation_report='{"status": "passed"}',
        )
        db_session.add(setup)
        db_session.commit()

        d = setup.to_dict()
        assert "id" in d
        assert "project_id" in d
        assert "status" in d
        assert "current_step" in d
        assert "progress" in d
        assert "configurator_output" in d
        assert "validation_report" in d
        assert "auto_fix_attempts" in d
        assert "started_at" in d
        assert "completed_at" in d
        assert d["status"] == "validating"
        assert d["auto_fix_attempts"] == 1

    def test_setup_status_transitions(self, app, db_session, sample_project_dir):
        """Setup status can transition through all valid states."""
        from models import Project, ProjectSetup

        project = Project(
            name="setup-test",
            root_path=sample_project_dir,
            config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(project)
        db_session.commit()

        valid_statuses = [
            "checking",
            "configuring",
            "validating",
            "fixing",
            "intervention",
            "complete",
            "failed",
        ]

        for status in valid_statuses:
            setup = ProjectSetup(
                project_id=project.id,
                status=status,
                current_step=f"step-{status}",
                progress=50,
            )
            db_session.add(setup)
            db_session.commit()
            assert setup.status == status

    def test_cascade_delete_with_project(self, app, db_session, sample_project_dir):
        """Deleting project should cascade delete setup records."""
        from models import Project, ProjectSetup

        project = Project(
            name="setup-cascade",
            root_path=sample_project_dir,
            config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(project)
        db_session.commit()

        setup = ProjectSetup(
            project_id=project.id,
            status="complete",
            current_step="done",
            progress=100,
        )
        db_session.add(setup)
        db_session.commit()

        pid = project.id
        db_session.delete(project)
        db_session.commit()

        assert ProjectSetup.query.filter_by(project_id=pid).count() == 0


class TestInfrastructureBackupModel:
    """Test InfrastructureBackup database model."""

    def test_create_backup(self, app, db_session, sample_project_dir):
        """Can create an InfrastructureBackup record."""
        from models import InfrastructureBackup, Project

        project = Project(
            name="backup-test",
            root_path=sample_project_dir,
            config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(project)
        db_session.commit()

        backup = InfrastructureBackup(
            project_id=project.id,
            backup_path="/tmp/backup/20260306_120000",
            files_backed_up=json.dumps(["docker-compose.yml", "pipeline-config.json"]),
        )
        db_session.add(backup)
        db_session.commit()

        assert backup.id is not None
        assert backup.project_id == project.id

    def test_to_dict_has_required_keys(self, app, db_session, sample_project_dir):
        """to_dict() should include all required keys."""
        from models import InfrastructureBackup, Project

        project = Project(
            name="backup-test",
            root_path=sample_project_dir,
            config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(project)
        db_session.commit()

        backup = InfrastructureBackup(
            project_id=project.id,
            backup_path="/tmp/backup/path",
            files_backed_up=json.dumps(["file1.yml"]),
        )
        db_session.add(backup)
        db_session.commit()

        d = backup.to_dict()
        assert "id" in d
        assert "project_id" in d
        assert "backup_path" in d
        assert "files_backed_up" in d
        assert "created_at" in d
        assert d["backup_path"] == "/tmp/backup/path"

    def test_cascade_delete_with_project(self, app, db_session, sample_project_dir):
        """Deleting project should cascade delete backup records."""
        from models import InfrastructureBackup, Project

        project = Project(
            name="backup-cascade",
            root_path=sample_project_dir,
            config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
            status="configuring",
        )
        db_session.add(project)
        db_session.commit()

        backup = InfrastructureBackup(
            project_id=project.id,
            backup_path="/tmp/backup/path",
            files_backed_up=json.dumps([]),
        )
        db_session.add(backup)
        db_session.commit()

        pid = project.id
        db_session.delete(project)
        db_session.commit()

        assert InfrastructureBackup.query.filter_by(project_id=pid).count() == 0


class TestRequirementCheckToDict:
    """Test RequirementCheck model to_dict serialization."""

    def test_to_dict_complete(self, app, db_session):
        """to_dict() should serialize all fields correctly."""
        from models import RequirementCheck

        check = RequirementCheck(
            requirement_name="docker",
            status="passed",
            details="Docker version 24.0.7",
        )
        db_session.add(check)
        db_session.commit()

        d = check.to_dict()
        assert d["requirement_name"] == "docker"
        assert d["status"] == "passed"
        assert d["details"] == "Docker version 24.0.7"
        assert "checked_at" in d
        assert "id" in d
