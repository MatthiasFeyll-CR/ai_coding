"""FileWatcher and RalphFileHandler service tests.

Tests file system event handling, debouncing, and WebSocket emission
as specified in the UI handoff doc.
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from watchdog.events import DirModifiedEvent, FileModifiedEvent


class TestRalphFileHandlerDebounce:
    """Test debounce logic on file events."""

    def test_debounce_blocks_rapid_events(self):
        """Events within debounce interval should be ignored."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=1, socketio=mock_socketio)

        state_path = "/tmp/test_ralph/.ralph/state.json"

        # First event should go through
        event = FileModifiedEvent(state_path)
        handler.last_state_emit = time.time()  # pretend we just emitted

        with patch.object(handler, "_emit_state_change") as mock_emit:
            handler.on_modified(event)
            # Should be blocked by debounce
            mock_emit.assert_not_called()

    def test_debounce_allows_after_interval(self):
        """Events after debounce interval should be processed."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=1, socketio=mock_socketio)

        state_path = "/tmp/test_ralph/.ralph/state.json"
        event = FileModifiedEvent(state_path)

        # Set last emit time far in the past
        handler.last_state_emit = 0

        with patch.object(handler, "_emit_state_change") as mock_emit:
            handler.on_modified(event)
            mock_emit.assert_called_once_with(Path(state_path))

    def test_ignores_directory_events(self):
        """Directory modification events should be skipped."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=1, socketio=mock_socketio)

        event = DirModifiedEvent("/tmp/test_ralph/.ralph/")

        with patch.object(handler, "_emit_state_change") as mock_emit:
            handler.on_modified(event)
            mock_emit.assert_not_called()


class TestRalphFileHandlerRouting:
    """Test event routing to correct emit method."""

    def test_state_json_routes_to_state_change(self):
        """state.json modifications should call _emit_state_change."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=1, socketio=mock_socketio)
        handler.last_state_emit = 0

        event = FileModifiedEvent("/project/.ralph/state.json")
        with patch.object(handler, "_emit_state_change") as mock_emit:
            handler.on_modified(event)
            mock_emit.assert_called_once()

    def test_progress_txt_routes_to_progress(self):
        """progress.txt modifications should call _emit_progress_update."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=1, socketio=mock_socketio)
        handler.last_state_emit = 0

        event = FileModifiedEvent("/project/.ralph/progress.txt")
        with patch.object(handler, "_emit_progress_update") as mock_emit:
            handler.on_modified(event)
            mock_emit.assert_called_once()

    def test_pipeline_jsonl_routes_to_logs(self):
        """pipeline.jsonl modifications should call _emit_new_logs."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=1, socketio=mock_socketio)
        handler.last_state_emit = 0

        event = FileModifiedEvent("/project/.ralph/pipeline.jsonl")
        with patch.object(handler, "_emit_new_logs") as mock_emit:
            handler.on_modified(event)
            mock_emit.assert_called_once()


class TestRalphFileHandlerEmit:
    """Test actual emit calls."""

    def test_emit_state_change_reads_json_and_emits(self, tmp_path):
        """_emit_state_change should read state.json and emit via WebSocket."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=5, socketio=mock_socketio)

        state_file = tmp_path / "state.json"
        state_data = {"current_phase": "qa_review", "current_milestone": 2}
        state_file.write_text(json.dumps(state_data))

        with patch("api.websocket.emit_state_change") as mock_emit:
            handler._emit_state_change(state_file)
            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][0] == mock_socketio
            assert call_args[0][1] == 5
            assert call_args[0][2]["state"] == state_data

    def test_emit_state_change_handles_invalid_json(self, tmp_path):
        """_emit_state_change should not crash on invalid JSON."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=1, socketio=mock_socketio)

        state_file = tmp_path / "state.json"
        state_file.write_text("not valid json {{{")

        # Should not raise
        handler._emit_state_change(state_file)

    def test_emit_progress_reads_last_line(self, tmp_path):
        """_emit_progress_update should emit the last line of progress.txt."""
        from services.file_watcher import RalphFileHandler

        mock_socketio = MagicMock()
        handler = RalphFileHandler(project_id=5, socketio=mock_socketio)

        progress_file = tmp_path / "progress.txt"
        progress_file.write_text("Step 1\nStep 2\nStep 3 final\n")

        with patch("api.websocket.emit_log") as mock_emit:
            handler._emit_progress_update(progress_file)
            mock_emit.assert_called_once()
            call_args = mock_emit.call_args
            assert call_args[0][2]["message"] == "Step 3 final"


class TestFileWatcher:
    """Test FileWatcher lifecycle (start/stop)."""

    def test_start_creates_observer(self, app, sample_project_dir):
        """start() should create and start watchdog observer."""
        from models import Project
        from services.file_watcher import FileWatcher

        with app.app_context():
            from database import db

            project = Project(
                name="fw-test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            mock_socketio = MagicMock()
            watcher = FileWatcher(project, mock_socketio)

            with patch("services.file_watcher.Observer") as MockObserver:
                mock_obs = MagicMock()
                MockObserver.return_value = mock_obs

                watcher.start()

                mock_obs.schedule.assert_called_once()
                mock_obs.start.assert_called_once()

    def test_stop_stops_observer(self, app, sample_project_dir):
        """stop() should stop and join the observer."""
        from models import Project
        from services.file_watcher import FileWatcher

        with app.app_context():
            from database import db

            project = Project(
                name="fw-test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            mock_socketio = MagicMock()
            watcher = FileWatcher(project, mock_socketio)
            watcher.observer = MagicMock()

            watcher.stop()

            watcher.observer.stop.assert_called_once()
            watcher.observer.join.assert_called_once()

    def test_stop_without_start_is_safe(self, app, sample_project_dir):
        """stop() should not raise if observer is None."""
        from models import Project
        from services.file_watcher import FileWatcher

        with app.app_context():
            from database import db

            project = Project(
                name="fw-test",
                root_path=sample_project_dir,
                config_path=os.path.join(sample_project_dir, "pipeline-config.json"),
                status="ready",
            )
            db.session.add(project)
            db.session.commit()

            mock_socketio = MagicMock()
            watcher = FileWatcher(project, mock_socketio)

            # Should not raise
            watcher.stop()
