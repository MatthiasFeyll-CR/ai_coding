"""Flask application entry point."""

import logging
import os
import sys
import traceback

from api import files, health, pipeline, projects, websocket
from database import db, init_db
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
# Silence noisy loggers
for _name in ("watchdog", "engineio", "socketio", "urllib3"):
    logging.getLogger(_name).setLevel(logging.WARNING)
log = logging.getLogger("ralph-ui")

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "pipeline.db")

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", f"sqlite:///{DB_PATH}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Ensure our error handlers run even in debug mode
app.config["PROPAGATE_EXCEPTIONS"] = False
app.config["TRAP_HTTP_EXCEPTIONS"] = False

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins=cors_origins,
    async_mode="eventlet",
    logger=False,
    engineio_logger=False,
)

# Database
db.init_app(app)

# Ensure tables exist (covers both direct run and dev.sh / gunicorn)
with app.app_context():
    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    db_path = db_uri.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    db.create_all()

# Register API blueprints
app.register_blueprint(projects.bp, url_prefix="/api/projects")
app.register_blueprint(pipeline.bp, url_prefix="/api/pipeline")
app.register_blueprint(files.bp, url_prefix="/api/files")
app.register_blueprint(health.bp, url_prefix="/api")

# Register WebSocket handlers
websocket.register_handlers(socketio)


@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON (not HTML) for every unhandled error."""
    tb = traceback.format_exc()
    log.error(
        "Unhandled %s on %s %s\n%s", type(e).__name__, request.method, request.path, tb
    )
    return jsonify({"error": str(e), "traceback": tb}), getattr(e, "code", 500)


@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        log.warning("404 %s %s", request.method, request.path)
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(app.static_folder, "index.html")


@app.errorhandler(500)
def handle_500(e):
    tb = traceback.format_exc()
    log.error("500 on %s %s\n%s", request.method, request.path, tb)
    return jsonify({"error": str(e), "traceback": tb}), 500


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
    # Do NOT pass debug=True to socketio.run() — it wraps the app with
    # Werkzeug's DebuggedApplication which intercepts every 500 and renders
    # an HTML traceback, preventing our @app.errorhandler from returning JSON.
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=True,
        log_output=True,
    )
