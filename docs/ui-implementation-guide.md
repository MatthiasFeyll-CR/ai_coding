# Ralph Pipeline UI - AI Agent Implementation Guide

## Document Overview

This document provides comprehensive implementation instructions for building the Ralph Pipeline Web UI. It is designed for AI agents to implement the system autonomously with all necessary technical details, specifications, and code examples.

**Project Goal:** Transform the CLI-based Ralph Pipeline into a web application with real-time monitoring, infrastructure validation, and project management capabilities.

**Target User:** Single developer running locally on the same machine as the target project.

**Deployment Model:** Self-hosted Docker Compose setup (local-only).

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Development Environment Setup](#2-development-environment-setup)
3. [Backend Implementation](#3-backend-implementation)
4. [Frontend Implementation](#4-frontend-implementation)
5. [Database Implementation](#5-database-implementation)
6. [Infrastructure Integration](#6-infrastructure-integration)
7. [Testing Implementation](#7-testing-implementation)
8. [Deployment](#8-deployment)
9. [Common Patterns](#9-common-patterns)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Project Structure

Create the following directory structure:

```
ralph-pipeline/  (existing repository)
├── ui/  (NEW - create this)
│   ├── backend/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── requirements.txt
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── projects.py
│   │   │   ├── pipeline.py
│   │   │   ├── files.py
│   │   │   ├── websocket.py
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── file_watcher.py
│   │   │   ├── pipeline_runner.py
│   │   │   ├── requirement_checker.py
│   │   │   └── configurator_invoker.py
│   │   ├── migrations/
│   │   │   └── versions/
│   │   └── static/  (React build output)
│   │
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── components/
│   │   │   │   ├── layout/
│   │   │   │   │   ├── Sidebar.tsx
│   │   │   │   │   ├── TopBar.tsx
│   │   │   │   │   └── Layout.tsx
│   │   │   │   ├── pipeline/
│   │   │   │   │   ├── FSMVisualization.tsx
│   │   │   │   │   ├── ControlPanel.tsx
│   │   │   │   │   ├── TokenDashboard.tsx
│   │   │   │   │   ├── LiveLogs.tsx
│   │   │   │   │   └── MilestoneList.tsx
│   │   │   │   ├── editor/
│   │   │   │   │   ├── MonacoEditor.tsx
│   │   │   │   │   └── FileTree.tsx
│   │   │   │   ├── infrastructure/
│   │   │   │   │   ├── InfrastructureTab.tsx
│   │   │   │   │   ├── SetupFlow.tsx
│   │   │   │   │   └── ValidationReport.tsx
│   │   │   │   ├── modals/
│   │   │   │   │   ├── LinkProjectModal.tsx
│   │   │   │   │   ├── ModelSelectorModal.tsx
│   │   │   │   │   ├── ReinstantiateModal.tsx
│   │   │   │   │   └── ErrorModal.tsx
│   │   │   │   └── shared/
│   │   │   │       ├── Button.tsx
│   │   │   │       ├── Badge.tsx
│   │   │   │       ├── Card.tsx
│   │   │   │       └── EmptyState.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useWebSocket.ts
│   │   │   │   ├── useProject.ts
│   │   │   │   ├── usePipeline.ts
│   │   │   │   └── useFileSystem.ts
│   │   │   ├── store/
│   │   │   │   └── appStore.ts
│   │   │   ├── api/
│   │   │   │   └── client.ts
│   │   │   ├── types/
│   │   │   │   └── index.ts
│   │   │   ├── pages/
│   │   │   │   ├── RequirementsPage.tsx
│   │   │   │   ├── DashboardPage.tsx
│   │   │   │   └── EditorPage.tsx
│   │   │   ├── styles/
│   │   │   │   └── globals.css
│   │   │   ├── App.tsx
│   │   │   └── main.tsx
│   │   ├── public/
│   │   ├── index.html
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.js
│   │   └── postcss.config.js
│   │
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── .env.example
│   └── README.md
│
├── src/  (existing ralph-pipeline code)
├── tests/  (existing tests)
└── docs/  (existing documentation)
```

---

## 2. Development Environment Setup

### 2.1 Prerequisites

Ensure the following are installed on the development machine:
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Claude CLI (for testing)

### 2.2 Backend Setup

**File: `ui/backend/requirements.txt`**

```txt
Flask==3.0.0
Flask-SocketIO==5.3.6
Flask-CORS==4.0.0
python-socketio==5.10.0
eventlet==0.33.3

SQLAlchemy==2.0.23
alembic==1.12.1

watchdog==3.0.0
psutil==5.9.6

python-dotenv==1.0.0
```

**Installation:**

```bash
cd ui/backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2.3 Frontend Setup

**File: `ui/frontend/package.json`**

```json
{
  "name": "ralph-pipeline-ui",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint src --ext ts,tsx"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.1",
    "@monaco-editor/react": "^4.6.0",
    "monaco-editor": "^0.45.0",
    "socket.io-client": "^4.6.1",
    "@tanstack/react-query": "^5.12.2",
    "axios": "^1.6.2",
    "zustand": "^4.4.7",
    "framer-motion": "^10.16.16",
    "reactflow": "^11.10.4",
    "recharts": "^2.10.3",
    "lucide-react": "^0.300.0",
    "date-fns": "^2.30.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.45",
    "@types/react-dom": "^18.2.18",
    "@types/node": "^20.10.5",
    "typescript": "^5.3.3",
    "vite": "^5.0.8",
    "@vitejs/plugin-react": "^4.2.1",
    "vitest": "^1.0.4",
    "@testing-library/react": "^14.1.2",
    "@testing-library/jest-dom": "^6.1.5",
    "@testing-library/user-event": "^14.5.1",
    "eslint": "^8.56.0",
    "@typescript-eslint/eslint-plugin": "^6.15.0",
    "@typescript-eslint/parser": "^6.15.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "prettier": "^3.1.1",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.4.0"
  }
}
```

**Installation:**

```bash
cd ui/frontend
npm install
```

### 2.4 Environment Configuration

**File: `ui/.env.example`**

```env
# Backend
FLASK_APP=backend/app.py
FLASK_ENV=development
DATABASE_URL=sqlite:///data/pipeline.db
SECRET_KEY=your-secret-key-change-in-production
CORS_ORIGINS=http://localhost:3000

# Frontend (for production build)
VITE_API_URL=http://localhost:5000
VITE_WS_URL=ws://localhost:5000

# Project paths
HOST_PROJECTS_ROOT=/path/to/your/projects

# Ralph Pipeline CLI path (if not in PATH)
RALPH_CLI_PATH=ralph-pipeline
```

Copy to `.env` and customize:

```bash
cp .env.example .env
```

---

## 3. Backend Implementation

### 3.1 Application Setup

**File: `ui/backend/app.py`**

```python
"""Flask application entry point."""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv

from database import db, init_db
from api import projects, pipeline, files, websocket, health

load_dotenv()

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///data/pipeline.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# CORS
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins=cors_origins,
    async_mode='eventlet',
    logger=True,
    engineio_logger=True
)

# Database
db.init_app(app)

# Register API blueprints
app.register_blueprint(projects.bp, url_prefix='/api/projects')
app.register_blueprint(pipeline.bp, url_prefix='/api/pipeline')
app.register_blueprint(files.bp, url_prefix='/api/files')
app.register_blueprint(health.bp, url_prefix='/api')

# Register WebSocket handlers
websocket.register_handlers(socketio)

# Serve React static files (production)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

@app.cli.command()
def init_database():
    """Initialize the database."""
    init_db(app)
    print("Database initialized successfully!")

if __name__ == '__main__':
    # Ensure database directory exists
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Initialize database
    with app.app_context():
        db.create_all()
    
    # Run with SocketIO
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

### 3.2 Database Models

**File: `ui/backend/models.py`**

```python
"""SQLAlchemy database models."""

from datetime import datetime
from database import db

class Project(db.Model):
    """Project model."""
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    root_path = db.Column(db.String(512), unique=True, nullable=False)
    config_path = db.Column(db.String(512), nullable=False)
    status = db.Column(
        db.String(50),
        default='initialized',
        nullable=False
    )  # initialized, ready, running, error, success, paused
    last_run_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    snapshots = db.relationship('StateSnapshot', backref='project', cascade='all, delete-orphan')
    logs = db.relationship('ExecutionLog', backref='project', cascade='all, delete-orphan')
    tokens = db.relationship('TokenUsage', backref='project', cascade='all, delete-orphan')
    model_configs = db.relationship('ModelConfig', backref='project', cascade='all, delete-orphan')
    setups = db.relationship('ProjectSetup', backref='project', cascade='all, delete-orphan')
    backups = db.relationship('InfrastructureBackup', backref='project', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'root_path': self.root_path,
            'config_path': self.config_path,
            'status': self.status,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class StateSnapshot(db.Model):
    """State snapshot model for reinstantiation."""
    __tablename__ = 'state_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    milestone_id = db.Column(db.Integer)
    phase = db.Column(db.String(100))
    state_json = db.Column(db.Text, nullable=False)
    snapshot_type = db.Column(db.String(50), default='auto')  # auto, manual, success
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'milestone_id': self.milestone_id,
            'phase': self.phase,
            'state_json': self.state_json,
            'snapshot_type': self.snapshot_type,
            'created_at': self.created_at.isoformat()
        }

class ExecutionLog(db.Model):
    """Execution log model."""
    __tablename__ = 'execution_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    milestone_id = db.Column(db.Integer)
    phase = db.Column(db.String(100))
    log_level = db.Column(db.String(20), default='info')  # debug, info, warning, error
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_logs_project_time', 'project_id', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'milestone_id': self.milestone_id,
            'phase': self.phase,
            'log_level': self.log_level,
            'message': self.message,
            'created_at': self.created_at.isoformat()
        }

class TokenUsage(db.Model):
    """Token usage tracking."""
    __tablename__ = 'token_usage'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    milestone_id = db.Column(db.Integer)
    phase = db.Column(db.String(100))
    model = db.Column(db.String(100), nullable=False)
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_tokens_project', 'project_id', 'milestone_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'milestone_id': self.milestone_id,
            'phase': self.phase,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'cost_usd': self.cost_usd,
            'created_at': self.created_at.isoformat()
        }

class ModelConfig(db.Model):
    """Model configuration per phase."""
    __tablename__ = 'model_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    phase = db.Column(db.String(100), nullable=False)  # prd, ralph, qa, reconciliation
    model = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('project_id', 'phase', name='unique_project_phase'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'phase': self.phase,
            'model': self.model,
            'updated_at': self.updated_at.isoformat()
        }

class RequirementCheck(db.Model):
    """System requirement checks."""
    __tablename__ = 'requirement_checks'
    
    id = db.Column(db.Integer, primary_key=True)
    requirement_name = db.Column(db.String(100), nullable=False)  # python, docker, claude
    status = db.Column(db.String(20), nullable=False)  # passed, failed, skipped
    details = db.Column(db.Text)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'requirement_name': self.requirement_name,
            'status': self.status,
            'details': self.details,
            'checked_at': self.checked_at.isoformat()
        }

class ProjectSetup(db.Model):
    """Project setup tracking."""
    __tablename__ = 'project_setup'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)  # checking, configuring, validating, fixing, intervention, complete, failed
    current_step = db.Column(db.String(255))
    progress = db.Column(db.Integer, default=0)  # 0-100
    configurator_output = db.Column(db.Text)
    validation_report = db.Column(db.Text)  # JSON
    auto_fix_attempts = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'status': self.status,
            'current_step': self.current_step,
            'progress': self.progress,
            'configurator_output': self.configurator_output,
            'validation_report': self.validation_report,
            'auto_fix_attempts': self.auto_fix_attempts,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class InfrastructureBackup(db.Model):
    """Infrastructure backup tracking."""
    __tablename__ = 'infrastructure_backups'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    backup_path = db.Column(db.String(512), nullable=False)
    files_backed_up = db.Column(db.Text)  # JSON array
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'backup_path': self.backup_path,
            'files_backed_up': self.files_backed_up,
            'created_at': self.created_at.isoformat()
        }
```

**File: `ui/backend/database.py`**

```python
"""Database initialization."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    """Initialize database with app context."""
    with app.app_context():
        db.create_all()
```

### 3.3 API Endpoints - Projects

**File: `ui/backend/api/projects.py`**

```python
"""Projects API endpoints."""

import os
import json
from pathlib import Path
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from database import db
from models import Project, StateSnapshot, ModelConfig
from services.pipeline_runner import PipelineRunner
from services.configurator_invoker import ConfiguratorInvoker

bp = Blueprint('projects', __name__)

@bp.route('', methods=['GET'])
def list_projects():
    """List all projects sorted by last activity."""
    projects = Project.query.order_by(Project.last_run_at.desc().nullsfirst()).all()
    return jsonify([p.to_dict() for p in projects])

@bp.route('', methods=['POST'])
def create_project():
    """Create a new project after pre-check."""
    data = request.json
    project_path = data.get('project_path')
    
    if not project_path:
        return jsonify({'error': 'project_path is required'}), 400
    
    # Validate path exists
    if not os.path.exists(project_path):
        return jsonify({'error': 'Project path does not exist'}), 400
    
    # Extract project name from path
    project_name = data.get('name') or Path(project_path).name
    
    # Find config file
    config_path = os.path.join(project_path, 'pipeline-config.json')
    if not os.path.exists(config_path):
        return jsonify({'error': 'pipeline-config.json not found'}), 400
    
    try:
        project = Project(
            name=project_name,
            root_path=project_path,
            config_path=config_path,
            status='initialized'
        )
        db.session.add(project)
        db.session.commit()
        
        return jsonify(project.to_dict()), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Project already exists'}), 409

@bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details."""
    project = Project.query.get_or_404(project_id)
    return jsonify(project.to_dict())

@bp.route('/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project."""
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/pre-check', methods=['POST'])
def pre_check_project():
    """Pre-check project for required documentation."""
    data = request.json
    project_path = Path(data.get('project_path'))
    
    if not project_path.exists():
        return jsonify({'error': 'Path does not exist'}), 400
    
    # Check required docs folders
    required_docs = [
        'docs/01-requirements',
        'docs/02-architecture',
        'docs/03-design',  # or docs/03-ai, docs/03-integration
        'docs/04-test-architecture',
        'docs/05-milestones'
    ]
    
    docs_check = {}
    all_valid = True
    
    for doc_path in required_docs:
        full_path = project_path / doc_path
        exists = full_path.exists()
        has_handover = (full_path / 'handover.json').exists() if exists else False
        
        docs_check[doc_path] = {
            'exists': exists,
            'has_handover': has_handover
        }
        
        if not exists:
            all_valid = False
    
    # Check for existing infrastructure files
    infra_files = [
        'docker-compose.yml',
        'docker-compose.test.yml',
        'pipeline-config.json'
    ]
    
    existing_infra = []
    for file in infra_files:
        file_path = project_path / file
        if file_path.exists():
            existing_infra.append({
                'file': file,
                'size': file_path.stat().st_size,
                'modified': file_path.stat().st_mtime
            })
    
    return jsonify({
        'valid': all_valid,
        'docs_structure': docs_check,
        'existing_infrastructure': existing_infra,
        'project_name': project_path.name
    })

@bp.route('/setup', methods=['POST'])
def setup_project():
    """Start automated project setup."""
    data = request.json
    project_path = data.get('project_path')
    
    # Create project record
    project_name = Path(project_path).name
    config_path = os.path.join(project_path, 'pipeline-config.json')
    
    project = Project(
        name=project_name,
        root_path=project_path,
        config_path=config_path,
        status='configuring'
    )
    db.session.add(project)
    db.session.commit()
    
    # Invoke configurator in background (async task recommended, using simple threading for now)
    from threading import Thread
    configurator = ConfiguratorInvoker(project)
    thread = Thread(target=configurator.run_setup)
    thread.start()
    
    return jsonify({
        'project_id': project.id,
        'status': 'setup_started'
    }), 202

@bp.route('/<int:project_id>/config', methods=['GET'])
def get_config(project_id):
    """Get pipeline configuration."""
    project = Project.query.get_or_404(project_id)
    
    try:
        with open(project.config_path, 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except FileNotFoundError:
        return jsonify({'error': 'Config file not found'}), 404

@bp.route('/<int:project_id>/state', methods=['GET'])
def get_state(project_id):
    """Get current pipeline state."""
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / '.ralph' / 'state.json'
    
    if not state_path.exists():
        return jsonify({'message': 'No state file found'}), 404
    
    try:
        with open(state_path, 'r') as f:
            state = json.load(f)
        return jsonify(state)
    except FileNotFoundError:
        return jsonify({'error': 'State file not found'}), 404

@bp.route('/<int:project_id>/snapshots', methods=['GET'])
def list_snapshots(project_id):
    """List state snapshots."""
    snapshots = StateSnapshot.query.filter_by(project_id=project_id).order_by(StateSnapshot.created_at.desc()).limit(10).all()
    return jsonify([s.to_dict() for s in snapshots])

@bp.route('/<int:project_id>/snapshots', methods=['POST'])
def create_snapshot(project_id):
    """Create manual snapshot."""
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / '.ralph' / 'state.json'
    
    if not state_path.exists():
        return jsonify({'error': 'No state file to snapshot'}), 404
    
    with open(state_path, 'r') as f:
        state_json = f.read()
    
    snapshot = StateSnapshot(
        project_id=project_id,
        state_json=state_json,
        snapshot_type='manual'
    )
    db.session.add(snapshot)
    db.session.commit()
    
    return jsonify(snapshot.to_dict()), 201

@bp.route('/<int:project_id>/restore/<int:snapshot_id>', methods=['PUT'])
def restore_snapshot(project_id, snapshot_id):
    """Restore state from snapshot."""
    project = Project.query.get_or_404(project_id)
    snapshot = StateSnapshot.query.filter_by(id=snapshot_id, project_id=project_id).first_or_404()
    
    # Write state back to file
    state_path = Path(project.root_path) / '.ralph' / 'state.json'
    state_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(state_path, 'w') as f:
        f.write(snapshot.state_json)
    
    return jsonify({'success': True})

@bp.route('/<int:project_id>/models', methods=['GET'])
def get_models(project_id):
    """Get model configuration."""
    configs = ModelConfig.query.filter_by(project_id=project_id).all()
    return jsonify({c.phase: c.model for c in configs})

@bp.route('/<int:project_id>/models', methods=['PUT'])
def update_models(project_id):
    """Update model configuration."""
    project = Project.query.get_or_404(project_id)
    data = request.json
    
    for phase, model in data.items():
        config = ModelConfig.query.filter_by(project_id=project_id, phase=phase).first()
        if config:
            config.model = model
        else:
            config = ModelConfig(project_id=project_id, phase=phase, model=model)
            db.session.add(config)
    
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/models/available', methods=['GET'])
def list_available_models():
    """List available models."""
    models = [
        'claude-opus-4.6',
        'claude-sonnet-4.5',
    ]
    return jsonify(models)
```

### 3.4 API Endpoints - Pipeline Control

**File: `ui/backend/api/pipeline.py`**

```python
"""Pipeline control API endpoints."""

import os
from pathlib import Path
from flask import Blueprint, request, jsonify

from database import db
from models import Project
from services.pipeline_runner import PipelineRunner

bp = Blueprint('pipeline', __name__)

# Store active pipeline runners (in-memory, could use Redis for production)
active_pipelines = {}

@bp.route('/<int:project_id>/start', methods=['POST'])
def start_pipeline(project_id):
    """Start pipeline execution."""
    project = Project.query.get_or_404(project_id)
    
    # Check for lock file
    lock_path = Path(project.root_path) / '.ralph' / 'pipeline.lock'
    if lock_path.exists():
        return jsonify({'error': 'Pipeline is already running or locked'}), 409
    
    # Get optional milestone parameter
    milestone_id = request.json.get('milestone_id') if request.json else None
    
    # Create and start runner
    runner = PipelineRunner(project, milestone_id=milestone_id)
    runner.start()
    
    active_pipelines[project_id] = runner
    
    # Update project status
    project.status = 'running'
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Pipeline started'})

@bp.route('/<int:project_id>/stop', methods=['POST'])
def stop_pipeline(project_id):
    """Stop pipeline execution."""
    project = Project.query.get_or_404(project_id)
    
    runner = active_pipelines.get(project_id)
    if runner:
        runner.stop()
        del active_pipelines[project_id]
    
    # Remove lock file
    lock_path = Path(project.root_path) / '.ralph' / 'pipeline.lock'
    if lock_path.exists():
        lock_path.unlink()
    
    project.status = 'paused'
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/<int:project_id>/resume', methods=['POST'])
def resume_pipeline(project_id):
    """Resume pipeline from current state."""
    project = Project.query.get_or_404(project_id)
    
    runner = PipelineRunner(project, resume=True)
    runner.start()
    
    active_pipelines[project_id] = runner
    
    project.status = 'running'
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/<int:project_id>/logs', methods=['GET'])
def get_logs(project_id):
    """Get execution logs."""
    from models import ExecutionLog
    
    milestone_id = request.args.get('milestone_id', type=int)
    phase = request.args.get('phase')
    limit = request.args.get('limit', 1000, type=int)
    
    query = ExecutionLog.query.filter_by(project_id=project_id)
    
    if milestone_id:
        query = query.filter_by(milestone_id=milestone_id)
    if phase:
        query = query.filter_by(phase=phase)
    
    logs = query.order_by(ExecutionLog.created_at.desc()).limit(limit).all()
    return jsonify([log.to_dict() for log in logs])

@bp.route('/<int:project_id>/tokens', methods=['GET'])
def get_tokens(project_id):
    """Get token usage."""
    from models import TokenUsage
    
    tokens = TokenUsage.query.filter_by(project_id=project_id).all()
    
    # Aggregate by milestone
    by_milestone = {}
    total = {
        'input_tokens': 0,
        'output_tokens': 0,
        'cost_usd': 0.0
    }
    
    for token in tokens:
        total['input_tokens'] += token.input_tokens
        total['output_tokens'] += token.output_tokens
        total['cost_usd'] += token.cost_usd
        
        if token.milestone_id:
            if token.milestone_id not in by_milestone:
                by_milestone[token.milestone_id] = {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cost_usd': 0.0
                }
            by_milestone[token.milestone_id]['input_tokens'] += token.input_tokens
            by_milestone[token.milestone_id]['output_tokens'] += token.output_tokens
            by_milestone[token.milestone_id]['cost_usd'] += token.cost_usd
    
    return jsonify({
        'total': total,
        'by_milestone': by_milestone,
        'history': [t.to_dict() for t in tokens]
    })

@bp.route('/<int:project_id>/milestones', methods=['GET'])
def get_milestones(project_id):
    """Get milestone status from state."""
    project = Project.query.get_or_404(project_id)
    state_path = Path(project.root_path) / '.ralph' / 'state.json'
    
    if not state_path.exists():
        return jsonify([])
    
    import json
    with open(state_path, 'r') as f:
        state = json.load(f)
    
    milestones = []
    for m_id, m_state in state.get('milestones', {}).items():
        milestones.append({
            'id': int(m_id),
            **m_state
        })
    
    return jsonify(milestones)
```

### 3.5 WebSocket Implementation

**File: `ui/backend/api/websocket.py`**

```python
"""WebSocket handlers for real-time updates."""

from flask_socketio import emit, join_room, leave_room

def register_handlers(socketio):
    """Register WebSocket event handlers."""
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        """Subscribe to project updates."""
        project_id = data.get('project_id')
        room = f'project_{project_id}'
        join_room(room)
        emit('subscribed', {'project_id': project_id, 'room': room})
    
    @socketio.on('unsubscribe')
    def handle_unsubscribe(data):
        """Unsubscribe from project updates."""
        project_id = data.get('project_id')
        room = f'project_{project_id}'
        leave_room(room)
        emit('unsubscribed', {'project_id': project_id})
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        emit('connected', {'data': 'Connected to server'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        print('Client disconnected')

def emit_log(socketio, project_id, log_data):
    """Emit log event to subscribed clients."""
    socketio.emit('log', log_data, room=f'project_{project_id}')

def emit_state_change(socketio, project_id, state_data):
    """Emit state change event."""
    socketio.emit('state_change', state_data, room=f'project_{project_id}')

def emit_token_update(socketio, project_id, token_data):
    """Emit token usage update."""
    socketio.emit('token_update', token_data, room=f'project_{project_id}')

def emit_status(socketio, project_id, status_data):
    """Emit pipeline status update."""
    socketio.emit('status', status_data, room=f'project_{project_id}')

def emit_setup_progress(socketio, setup_id, progress_data):
    """Emit setup progress."""
    socketio.emit('setup_progress', progress_data, room=f'setup_{setup_id}')
```

### 3.6 Pipeline Runner Service

**File: `ui/backend/services/pipeline_runner.py`**

```python
"""Pipeline execution service."""

import os
import subprocess
import threading
import json
from pathlib import Path
from datetime import datetime

from database import db
from models import ExecutionLog

class PipelineRunner:
    """Manages pipeline execution as a subprocess."""
    
    def __init__(self, project, milestone_id=None, resume=False):
        self.project = project
        self.milestone_id = milestone_id
        self.resume = resume
        self.process = None
        self.thread = None
        self.running = False
    
    def start(self):
        """Start pipeline in background thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run_pipeline)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop the pipeline."""
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
    
    def _run_pipeline(self):
        """Run pipeline subprocess and stream output."""
        # Create lock file
        lock_path = Path(self.project.root_path) / '.ralph' / 'pipeline.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        lock_data = {
            'pid': os.getpid(),
            'started_at': datetime.utcnow().isoformat(),
            'project_id': self.project.id,
            'source': 'ui'
        }
        
        with open(lock_path, 'w') as f:
            json.dump(lock_data, f)
        
        try:
            # Build command
            cmd = [
                'ralph-pipeline',
                'run',
                '--config', self.project.config_path
            ]
            
            if self.resume:
                cmd.append('--resume')
            elif self.milestone_id:
                cmd.extend(['--milestone', str(self.milestone_id)])
            
            # Run subprocess
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self.project.root_path
            )
            
            # Stream output
            for line in self.process.stdout:
                if not self.running:
                    break
                
                # Log to database
                log = ExecutionLog(
                    project_id=self.project.id,
                    message=line.strip(),
                    log_level='info'
                )
                db.session.add(log)
                db.session.commit()
                
                # Emit via WebSocket (import here to avoid circular deps)
                from app import socketio
                from api.websocket import emit_log
                
                emit_log(socketio, self.project.id, {
                    'project_id': self.project.id,
                    'message': line.strip(),
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Wait for completion
            self.process.wait()
            
            # Update project status
            if self.process.returncode == 0:
                self.project.status = 'success'
            else:
                self.project.status = 'error'
            
            self.project.last_run_at = datetime.utcnow()
            db.session.commit()
            
        finally:
            # Remove lock file
            if lock_path.exists():
                lock_path.unlink()
            
            self.running = False
```

### 3.7 File Watcher Service

**File: `ui/backend/services/file_watcher.py`**

```python
"""File system watcher for .ralph/ changes."""

import json
import time
from pathlib import Path
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class RalphFileHandler(FileSystemEventHandler):
    """Handler for .ralph/ file changes."""
    
    def __init__(self, project_id, socketio):
        self.project_id = project_id
        self.socketio = socketio
        self.last_state_emit = 0
        self.debounce_interval = 0.1  # 100ms
    
    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Debounce rapid changes
        now = time.time()
        if now - self.last_state_emit < self.debounce_interval:
            return
        
        # Handle state.json changes
        if file_path.name == 'state.json':
            self._emit_state_change(file_path)
            self.last_state_emit = now
        
        # Handle progress.txt changes
        elif file_path.name == 'progress.txt':
            self._emit_progress_update(file_path)
        
        # Handle pipeline.jsonl log changes
        elif file_path.name == 'pipeline.jsonl':
            self._emit_new_logs(file_path)
    
    def _emit_state_change(self, state_path):
        """Emit state change event."""
        try:
            with open(state_path, 'r') as f:
                state = json.load(f)
            
            from api.websocket import emit_state_change
            emit_state_change(self.socketio, self.project_id, {
                'project_id': self.project_id,
                'state': state
            })
        except Exception as e:
            print(f"Error emitting state change: {e}")
    
    def _emit_progress_update(self, progress_path):
        """Emit progress update."""
        try:
            with open(progress_path, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    
                    from api.websocket import emit_log
                    emit_log(self.socketio, self.project_id, {
                        'project_id': self.project_id,
                        'message': last_line,
                        'timestamp': time.time()
                    })
        except Exception as e:
            print(f"Error emitting progress: {e}")
    
    def _emit_new_logs(self, log_path):
        """Emit new log entries."""
        # Parse JSONL and emit new entries
        # Implementation depends on log format
        pass

class FileWatcher:
    """Watches .ralph/ directory for changes."""
    
    def __init__(self, project, socketio):
        self.project = project
        self.socketio = socketio
        self.observer = None
    
    def start(self):
        """Start watching."""
        ralph_path = Path(self.project.root_path) / '.ralph'
        ralph_path.mkdir(parents=True, exist_ok=True)
        
        handler = RalphFileHandler(self.project.id, self.socketio)
        self.observer = Observer()
        self.observer.schedule(handler, str(ralph_path), recursive=True)
        self.observer.start()
    
    def stop(self):
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
```

---

## 4. Frontend Implementation

### 4.1 Project Configuration

**File: `ui/frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:5000',
        ws: true,
      },
    },
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
});
```

**File: `ui/frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**File: `ui/frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Background colors
        'bg-primary': '#0a0e1a',
        'bg-secondary': '#111827',
        'bg-tertiary': '#1f2937',
        'bg-hover': '#374151',
        
        // Accent colors
        'accent-cyan': '#06b6d4',
        'accent-purple': '#a855f7',
        'accent-blue': '#3b82f6',
        
        // Status colors
        'status-success': '#10b981',
        'status-warning': '#f59e0b',
        'status-error': '#ef4444',
        'status-idle': '#6b7280',
        
        // Text colors
        'text-primary': '#f9fafb',
        'text-secondary': '#9ca3af',
        'text-muted': '#6b7280',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

### 4.2 Types Definition

**File: `ui/frontend/src/types/index.ts`**

```typescript
export interface Project {
  id: number;
  name: string;
  root_path: string;
  config_path: string;
  status: 'initialized' | 'ready' | 'running' | 'error' | 'success' | 'paused';
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PipelineState {
  base_branch: string;
  current_milestone: number;
  milestones: Record<string, MilestoneState>;
  test_milestone_map: Record<string, number>;
  timestamp: string;
}

export interface MilestoneState {
  id: number;
  phase: string;
  bugfix_cycle: number;
  test_fix_cycle: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface ExecutionLog {
  id: number;
  project_id: number;
  milestone_id: number | null;
  phase: string | null;
  log_level: 'debug' | 'info' | 'warning' | 'error';
  message: string;
  created_at: string;
}

export interface TokenUsage {
  total: {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  };
  by_milestone: Record<number, {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  }>;
  history: Array<{
    id: number;
    project_id: number;
    milestone_id: number | null;
    phase: string | null;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    created_at: string;
  }>;
}

export interface StateSnapshot {
  id: number;
  project_id: number;
  milestone_id: number | null;
  phase: string | null;
  state_json: string;
  snapshot_type: 'auto' | 'manual' | 'success';
  created_at: string;
}

export interface ValidationReport {
  status: 'passed' | 'failed';
  duration_seconds: number;
  steps: Array<{
    name: string;
    command?: string;
    status: 'passed' | 'failed' | 'warning';
    duration?: number;
    output?: string;
    error?: string;
    expected?: string;
    actual?: string;
    fix_suggestion?: string;
  }>;
  summary: {
    total: number;
    passed: number;
    failed: number;
    warnings: number;
  };
}

export interface PreCheckResult {
  valid: boolean;
  docs_structure: Record<string, {
    exists: boolean;
    has_handover: boolean;
  }>;
  existing_infrastructure: Array<{
    file: string;
    size: number;
    modified: number;
  }>;
  project_name: string;
}

export interface WebSocketEvents {
  log: {
    project_id: number;
    milestone_id?: number;
    phase?: string;
    timestamp: string;
    message: string;
    level: 'info' | 'warning' | 'error';
  };
  state_change: {
    project_id: number;
    milestone_id?: number;
    old_phase?: string;
    new_phase?: string;
    state: PipelineState;
  };
  token_update: {
    project_id: number;
    milestone_id: number;
    phase: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  };
  status: {
    project_id: number;
    status: string;
    message: string;
  };
  setup_progress: {
    setup_id: string;
    step: string;
    status: string;
    message: string;
  };
}
```

### 4.3 API Client

**File: `ui/frontend/src/api/client.ts`**

```typescript
import axios from 'axios';
import type { Project, PipelineState, ExecutionLog, TokenUsage, StateSnapshot, PreCheckResult } from '@/types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Projects
export const projectsApi = {
  list: () => api.get<Project[]>('/projects'),
  get: (id: number) => api.get<Project>(`/projects/${id}`),
  create: (data: { project_path: string; name?: string }) => 
    api.post<Project>('/projects', data),
  delete: (id: number) => api.delete(`/projects/${id}`),
  preCheck: (projectPath: string) => 
    api.post<PreCheckResult>('/projects/pre-check', { project_path: projectPath }),
  setup: (projectPath: string) => 
    api.post('/projects/setup', { project_path: projectPath }),
  getConfig: (id: number) => api.get(`/projects/${id}/config`),
  getState: (id: number) => api.get<PipelineState>(`/projects/${id}/state`),
  listSnapshots: (id: number) => api.get<StateSnapshot[]>(`/projects/${id}/snapshots`),
  createSnapshot: (id: number) => api.post(`/projects/${id}/snapshots`),
  restoreSnapshot: (id: number, snapshotId: number) => 
    api.put(`/projects/${id}/restore/${snapshotId}`),
  getModels: (id: number) => api.get<Record<string, string>>(`/projects/${id}/models`),
  updateModels: (id: number, models: Record<string, string>) => 
    api.put(`/projects/${id}/models`, models),
};

// Pipeline control
export const pipelineApi = {
  start: (projectId: number, milestoneId?: number) => 
    api.post(`/pipeline/${projectId}/start`, { milestone_id: milestoneId }),
  stop: (projectId: number) => api.post(`/pipeline/${projectId}/stop`),
  resume: (projectId: number) => api.post(`/pipeline/${projectId}/resume`),
  getLogs: (projectId: number, params?: { milestone_id?: number; phase?: string; limit?: number }) => 
    api.get<ExecutionLog[]>(`/pipeline/${projectId}/logs`, { params }),
  getTokens: (projectId: number) => api.get<TokenUsage>(`/pipeline/${projectId}/tokens`),
  getMilestones: (projectId: number) => api.get(`/pipeline/${projectId}/milestones`),
};

// Models
export const modelsApi = {
  listAvailable: () => api.get<string[]>('/projects/models/available'),
};

// Health
export const healthApi = {
  check: () => api.get('/health'),
  checkRequirements: () => api.post('/requirements/check'),
  getRequirementsStatus: () => api.get('/requirements/status'),
};

export default api;
```

### 4.4 WebSocket Hook

**File: `ui/frontend/src/hooks/useWebSocket.ts`**

```typescript
import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import type { WebSocketEvents } from '@/types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:5000';

export function useWebSocket(projectId?: number) {
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);
  const [lastEvent, setLastEvent] = useState<any>(null);

  useEffect(() => {
    // Initialize socket
    const socket = io(WS_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
    });

    socketRef.current = socket;

    // Connection handlers
    socket.on('connect', () => {
      console.log('WebSocket connected');
      setConnected(true);
      
      // Subscribe to project if provided
      if (projectId) {
        socket.emit('subscribe', { project_id: projectId });
      }
    });

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    });

    socket.on('connected', (data) => {
      console.log('Server acknowledged connection:', data);
    });

    // Cleanup
    return () => {
      if (projectId) {
        socket.emit('unsubscribe', { project_id: projectId });
      }
      socket.close();
    };
  }, [projectId]);

  const subscribe = (eventName: keyof WebSocketEvents, callback: (data: any) => void) => {
    if (!socketRef.current) return;

    socketRef.current.on(eventName, callback);

    // Return unsubscribe function
    return () => {
      socketRef.current?.off(eventName, callback);
    };
  };

  const emit = (eventName: string, data: any) => {
    if (!socketRef.current) return;
    socketRef.current.emit(eventName, data);
  };

  return {
    connected,
    subscribe,
    emit,
    socket: socketRef.current,
  };
}
```

### 4.5 Zustand Store

**File: `ui/frontend/src/store/appStore.ts`**

```typescript
import { create } from 'zustand';
import type { Project } from '@/types';

interface AppState {
  // UI State
  sidebarCollapsed: boolean;
  activeProject: Project | null;
  theme: 'dark' | 'light';
  activeTab: 'state' | 'git' | 'costs' | 'tests' | 'infrastructure';
  
  // Modal State
  modals: {
    linkProject: boolean;
    modelSelector: boolean;
    reinstantiate: boolean;
    errorDetail: {
      open: boolean;
      error: any;
    };
  };
  
  // Actions
  toggleSidebar: () => void;
  setActiveProject: (project: Project | null) => void;
  setTheme: (theme: 'dark' | 'light') => void;
  setActiveTab: (tab: AppState['activeTab']) => void;
  openModal: (name: keyof AppState['modals']) => void;
  closeModal: (name: keyof AppState['modals']) => void;
  setError: (error: any) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  sidebarCollapsed: false,
  activeProject: null,
  theme: 'dark',
  activeTab: 'state',
  modals: {
    linkProject: false,
    modelSelector: false,
    reinstantiate: false,
    errorDetail: {
      open: false,
      error: null,
    },
  },
  
  // Actions
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  
  setActiveProject: (project) => set({ activeProject: project }),
  
  setTheme: (theme) => {
    set({ theme });
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  },
  
  setActiveTab: (tab) => set({ activeTab: tab }),
  
  openModal: (name) =>
    set((state) => ({
      modals: {
        ...state.modals,
        [name]: typeof state.modals[name] === 'object' 
          ? { ...state.modals[name], open: true }
          : true,
      },
    })),
  
  closeModal: (name) =>
    set((state) => ({
      modals: {
        ...state.modals,
        [name]: typeof state.modals[name] === 'object'
          ? { ...state.modals[name], open: false }
          : false,
      },
    })),
  
  setError: (error) =>
    set((state) => ({
      modals: {
        ...state.modals,
        errorDetail: { open: true, error },
      },
    })),
}));

// Initialize theme from localStorage
const savedTheme = localStorage.getItem('theme') as 'dark' | 'light' | null;
if (savedTheme) {
  useAppStore.getState().setTheme(savedTheme);
} else {
  useAppStore.getState().setTheme('dark');
}
```

---

**Due to length limitations, I'll continue the frontend implementation in a follow-up response. Shall I continue with:**

1. **React Components** (Layout, Dashboard, FSM Visualization, etc.)
2. **Testing Implementation**
3. **Docker & Deployment Configuration**

Please confirm and I'll complete the documentation.
