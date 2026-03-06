"""WebSocket handler tests.

Tests the WebSocket event handlers (subscribe, unsubscribe, connect)
and emit helper functions as specified in the UI handoff doc.
"""

from unittest.mock import MagicMock

import pytest


class TestWebSocketHandlers:
    """Test WebSocket event handlers registered via register_handlers()."""

    @pytest.fixture()
    def socketio_test_client(self, app):
        """Create a Flask-SocketIO test client."""
        from app import socketio

        return socketio.test_client(app)

    def test_connect_emits_connected(self, socketio_test_client):
        """On connect, server should emit a 'connected' event."""
        received = socketio_test_client.get_received()
        # Filter for our 'connected' event
        connected_events = [r for r in received if r["name"] == "connected"]
        assert len(connected_events) == 1
        assert connected_events[0]["args"][0]["data"] == "Connected to server"

    def test_subscribe_joins_room(self, socketio_test_client):
        """Subscribing to a project should emit 'subscribed' confirmation."""
        socketio_test_client.emit("subscribe", {"project_id": 42})
        received = socketio_test_client.get_received()
        sub_events = [r for r in received if r["name"] == "subscribed"]
        assert len(sub_events) == 1
        assert sub_events[0]["args"][0]["project_id"] == 42
        assert sub_events[0]["args"][0]["room"] == "project_42"

    def test_unsubscribe_leaves_room(self, socketio_test_client):
        """Unsubscribing should emit 'unsubscribed' confirmation."""
        socketio_test_client.emit("subscribe", {"project_id": 7})
        socketio_test_client.get_received()  # clear
        socketio_test_client.emit("unsubscribe", {"project_id": 7})
        received = socketio_test_client.get_received()
        unsub_events = [r for r in received if r["name"] == "unsubscribed"]
        assert len(unsub_events) == 1
        assert unsub_events[0]["args"][0]["project_id"] == 7

    def test_disconnect_does_not_error(self, socketio_test_client):
        """Disconnect should be handled gracefully."""
        socketio_test_client.disconnect()
        assert not socketio_test_client.is_connected()


class TestEmitHelpers:
    """Test WebSocket emit helper functions."""

    def test_emit_log(self, app):
        """emit_log sends 'log' event to the correct room."""
        from api.websocket import emit_log

        mock_socketio = MagicMock()
        log_data = {
            "project_id": 1,
            "message": "test log",
            "timestamp": "2026-03-06T12:00:00",
        }

        emit_log(mock_socketio, 1, log_data)

        mock_socketio.emit.assert_called_once_with("log", log_data, room="project_1")

    def test_emit_state_change(self, app):
        """emit_state_change sends 'state_change' event to the correct room."""
        from api.websocket import emit_state_change

        mock_socketio = MagicMock()
        state_data = {"project_id": 2, "state": {"phase": "qa_review"}}

        emit_state_change(mock_socketio, 2, state_data)

        mock_socketio.emit.assert_called_once_with(
            "state_change", state_data, room="project_2"
        )

    def test_emit_token_update(self, app):
        """emit_token_update sends 'token_update' event to the correct room."""
        from api.websocket import emit_token_update

        mock_socketio = MagicMock()
        token_data = {"input_tokens": 500, "cost_usd": 0.01}

        emit_token_update(mock_socketio, 3, token_data)

        mock_socketio.emit.assert_called_once_with(
            "token_update", token_data, room="project_3"
        )

    def test_emit_status(self, app):
        """emit_status sends 'status' event to the correct room."""
        from api.websocket import emit_status

        mock_socketio = MagicMock()
        status_data = {"status": "running"}

        emit_status(mock_socketio, 4, status_data)

        mock_socketio.emit.assert_called_once_with(
            "status", status_data, room="project_4"
        )

    def test_emit_setup_progress(self, app):
        """emit_setup_progress sends 'setup_progress' event to setup room."""
        from api.websocket import emit_setup_progress

        mock_socketio = MagicMock()
        progress_data = {"progress": 50, "step": "validating"}

        emit_setup_progress(mock_socketio, 10, progress_data)

        mock_socketio.emit.assert_called_once_with(
            "setup_progress", progress_data, room="setup_10"
        )
