"""WebSocket handlers for real-time updates."""

import logging

from flask_socketio import emit, join_room, leave_room

log = logging.getLogger("ralph-ui.websocket")


def register_handlers(socketio):
    """Register WebSocket event handlers."""

    @socketio.on("subscribe")
    def handle_subscribe(data):
        """Subscribe to project updates."""
        project_id = data.get("project_id")
        room = f"project_{project_id}"
        join_room(room)
        emit("subscribed", {"project_id": project_id, "room": room})

    @socketio.on("unsubscribe")
    def handle_unsubscribe(data):
        """Unsubscribe from project updates."""
        project_id = data.get("project_id")
        room = f"project_{project_id}"
        leave_room(room)
        emit("unsubscribed", {"project_id": project_id})

    @socketio.on("cancel_configurator")
    def handle_cancel_configurator(data):
        """Cancel a running configurator process."""
        from services.configurator_invoker import cancel_configurator

        project_id = data.get("project_id")
        if project_id is None:
            emit("error", {"message": "project_id is required"})
            return

        cancelled = cancel_configurator(project_id)
        log.info(
            "Cancel request for project %d: %s",
            project_id,
            "cancelled" if cancelled else "nothing running",
        )
        emit(
            "cancel_ack",
            {"project_id": project_id, "cancelled": cancelled},
        )

    @socketio.on("connect")
    def handle_connect():
        """Handle client connection."""
        emit("connected", {"data": "Connected to server"})

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle client disconnection."""
        pass


def emit_log(socketio, project_id, log_data):
    """Emit log event to subscribed clients."""
    socketio.emit("log", log_data, room=f"project_{project_id}")


def emit_state_change(socketio, project_id, state_data):
    """Emit state change event."""
    socketio.emit("state_change", state_data, room=f"project_{project_id}")


def emit_token_update(socketio, project_id, token_data):
    """Emit token usage update."""
    socketio.emit("token_update", token_data, room=f"project_{project_id}")


def emit_status(socketio, project_id, status_data):
    """Emit pipeline status update."""
    socketio.emit("status", status_data, room=f"project_{project_id}")


def emit_setup_progress(socketio, setup_id, progress_data):
    """Emit setup progress."""
    socketio.emit("setup_progress", progress_data, room=f"setup_{setup_id}")
