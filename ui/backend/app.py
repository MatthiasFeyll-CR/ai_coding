"""Flask application entry point."""

import os

from api import files, health, pipeline, projects, websocket
from database import db, init_db
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "pipeline.db")

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", f"sqlite:///{DB_PATH}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins=cors_origins,
    async_mode="eventlet",
    logger=True,
    engineio_logger=True,
)

# Database
db.init_app(app)

# Register API blueprints
app.register_blueprint(projects.bp, url_prefix="/api/projects")
app.register_blueprint(pipeline.bp, url_prefix="/api/pipeline")
app.register_blueprint(files.bp, url_prefix="/api/files")
app.register_blueprint(health.bp, url_prefix="/api")

# Register WebSocket handlers
websocket.register_handlers(socketio)


# Serve React static files (production)
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, "index.html")


@app.cli.command()
def init_database():
    """Initialize the database."""
    init_db(app)
    print("Database initialized successfully!")


if __name__ == "__main__":
    # Ensure database directory exists
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    db_path = db_uri.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # Initialize database
    with app.app_context():
        db.create_all()

    # Run with SocketIO
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
