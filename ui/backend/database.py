"""Database initialization."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Initialize database with app context."""
    with app.app_context():
        db.create_all()
