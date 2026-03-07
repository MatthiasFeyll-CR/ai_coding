"""SQLAlchemy database models."""

from datetime import datetime

from database import db


class Project(db.Model):
    """Project model."""

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    root_path = db.Column(db.String(512), unique=True, nullable=False)
    config_path = db.Column(db.String(512), nullable=False)
    status = db.Column(
        db.String(50),
        default="initialized",
        nullable=False,
    )  # initialized, ready, running, error, success, paused, configuring
    last_run_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    snapshots = db.relationship(
        "StateSnapshot", backref="project", cascade="all, delete-orphan"
    )
    logs = db.relationship(
        "ExecutionLog", backref="project", cascade="all, delete-orphan"
    )
    tokens = db.relationship(
        "TokenUsage", backref="project", cascade="all, delete-orphan"
    )
    model_configs = db.relationship(
        "ModelConfig", backref="project", cascade="all, delete-orphan"
    )
    setups = db.relationship(
        "ProjectSetup", backref="project", cascade="all, delete-orphan"
    )
    backups = db.relationship(
        "InfrastructureBackup", backref="project", cascade="all, delete-orphan"
    )

    @property
    def has_config(self):
        """Check if pipeline-config.json exists on disk."""
        import os

        return os.path.exists(self.config_path)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "root_path": self.root_path,
            "project_path": self.root_path,
            "config_path": self.config_path,
            "status": self.status,
            "is_setup": self.has_config and self.status != "configuring",
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class StateSnapshot(db.Model):
    """State snapshot model for reinstantiation."""

    __tablename__ = "state_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    milestone_id = db.Column(db.Integer)
    phase = db.Column(db.String(100))
    state_json = db.Column(db.Text, nullable=False)
    snapshot_type = db.Column(db.String(50), default="auto")  # auto, manual, success
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "milestone_id": self.milestone_id,
            "phase": self.phase,
            "state_json": self.state_json,
            "snapshot_type": self.snapshot_type,
            "created_at": self.created_at.isoformat(),
        }


class ExecutionLog(db.Model):
    """Execution log model."""

    __tablename__ = "execution_logs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    milestone_id = db.Column(db.Integer)
    phase = db.Column(db.String(100))
    log_level = db.Column(db.String(20), default="info")  # debug, info, warning, error
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index("idx_logs_project_time", "project_id", "created_at"),)

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "milestone_id": self.milestone_id,
            "phase": self.phase,
            "log_level": self.log_level,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


class TokenUsage(db.Model):
    """Token usage tracking."""

    __tablename__ = "token_usage"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    milestone_id = db.Column(db.Integer)
    phase = db.Column(db.String(100))
    model = db.Column(db.String(100), nullable=False)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    cache_creation_tokens = db.Column(db.Integer, default=0)
    cache_read_tokens = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Float, default=0.0)
    session_id = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index("idx_tokens_project", "project_id", "milestone_id"),)

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "milestone_id": self.milestone_id,
            "phase": self.phase,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens or 0,
            "cache_read_tokens": self.cache_read_tokens or 0,
            "cost_usd": self.cost_usd,
            "session_id": self.session_id or "",
            "created_at": self.created_at.isoformat(),
        }


class ModelConfig(db.Model):
    """Model configuration per phase."""

    __tablename__ = "model_configs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    phase = db.Column(db.String(100), nullable=False)  # prd, ralph, qa, reconciliation
    model = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint("project_id", "phase", name="unique_project_phase"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "phase": self.phase,
            "model": self.model,
            "updated_at": self.updated_at.isoformat(),
        }


class RequirementCheck(db.Model):
    """System requirement checks."""

    __tablename__ = "requirement_checks"

    id = db.Column(db.Integer, primary_key=True)
    requirement_name = db.Column(
        db.String(100), nullable=False
    )  # python, docker, claude
    status = db.Column(db.String(20), nullable=False)  # passed, failed, skipped
    details = db.Column(db.Text)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "requirement_name": self.requirement_name,
            "status": self.status,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


class ProjectSetup(db.Model):
    """Project setup tracking."""

    __tablename__ = "project_setup"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    status = db.Column(
        db.String(50), nullable=False
    )  # checking, configuring, validating, fixing, intervention, complete, failed
    current_step = db.Column(db.String(255))
    progress = db.Column(db.Integer, default=0)  # 0-100
    configurator_output = db.Column(db.Text)
    validation_report = db.Column(db.Text)  # JSON
    auto_fix_attempts = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "current_step": self.current_step,
            "progress": self.progress,
            "configurator_output": self.configurator_output,
            "validation_report": self.validation_report,
            "auto_fix_attempts": self.auto_fix_attempts,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class InfrastructureBackup(db.Model):
    """Infrastructure backup tracking."""

    __tablename__ = "infrastructure_backups"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    backup_path = db.Column(db.String(512), nullable=False)
    files_backed_up = db.Column(db.Text)  # JSON array
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "backup_path": self.backup_path,
            "files_backed_up": self.files_backed_up,
            "created_at": self.created_at.isoformat(),
        }
