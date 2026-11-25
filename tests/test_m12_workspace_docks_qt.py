"""M12-UX Qt offscreen: a real dockable editor shell, no destructive rebuild."""
import os

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import streamclipper.gui as gui
from streamclipper.workspace_layout import (
    save_workspace as save_to_disk,
    load_workspace as load_from_disk,
    delete_workspace as delete_from_disk)


@pytest.fixture
def layout_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gui, "save_workspace", lambda layout: save_to_disk(layout, root=tmp_path))
    monkeypatch.setattr(
        gui, "load_workspace", lambda: load_from_disk(root=tmp_path))
    monkeypatch.setattr(
        gui, "delete_workspace", lambda: delete_from_disk(root=tmp_path))
    return tmp_path


def _window(app):
    window = gui.MainWindow()
    window.resize(1366, 768)
    window.show()
    app.processEvents()
    return window


def test_docked_workspace_keeps_real_editor_controls(layout_storage):
    app = QApplication.instance() or QApplication([])
    window = _window(app)
    try:
        assert window.project_dock.objectName() == "streamclipper.projectDock"
        assert window.timeline_dock.objectName() == "streamclipper.timelineDock"
        assert window.inspector_dock.objectName() == "streamclipper.inspectorDock"
        assert window.dockWidgetArea(window.project_dock) == Qt.DockWidgetArea.LeftDockWidgetArea
        assert window.dockWidgetArea(window.timeline_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
        assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
            "Highlights", "Untertitel", "KI & Modelle", "Spuren", "Export"]
        assert window.project_dock.isVisible()
        assert window.timeline_dock.isVisible()
        assert window.video_widget.isVisible()
        assert window.timeline.isVisible()
        assert window.player is not None
        assert window.track_canvas is not None
        assert window.word_editor_toggle is not None
        assert window.open_button.isEnabled()
        assert window.workspace_picker.currentText() == "Highlights"
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()


def test_workspace_switch_and_restore_do_not_touch_playhead_or_project(
        layout_storage):
    app = QApplication.instance() or QApplication([])
    window = _window(app)
    try:
        player = window.player
        timeline = window.timeline
        source_before = window.source
        project_before = window.editor_project
        player_pos = window.player.position()
        window.workspace_picker.setCurrentText("Audio")
        app.processEvents()
        assert window.tabs.currentIndex() == 3  # existing multitrack controls
        assert window.inspector_dock.isVisible()
        assert window.timeline_dock.isVisible()
        window.workspace_picker.setCurrentText("Export")
        app.processEvents()
        assert window.tabs.currentIndex() == 4
        assert not window.inspector_dock.isVisible()
        assert window.player is player
        assert window.timeline is timeline
        assert window.source == source_before
        assert window.editor_project is project_before
        assert window.player.position() == player_pos
        window.workspace_picker.setCurrentText("Schnitt")
        window.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, window.project_dock)
        app.processEvents()
        assert window.dockWidgetArea(window.project_dock) == Qt.DockWidgetArea.RightDockWidgetArea
        window._save_workspace_layout()
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()
    reopened = _window(app)
    try:
        assert reopened.workspace_picker.currentText() == "Schnitt"
        assert reopened.dockWidgetArea(reopened.project_dock) == Qt.DockWidgetArea.RightDockWidgetArea
        assert reopened.timeline_dock.isVisible()
        reopened._reset_workspace_layout()
        app.processEvents()
        assert reopened.workspace_picker.currentText() == "Highlights"
        assert reopened.dockWidgetArea(reopened.project_dock) == Qt.DockWidgetArea.LeftDockWidgetArea
        assert load_from_disk(root=layout_storage) is None
    finally:
        reopened._autosave_timer.stop()
        reopened.close()
        app.processEvents()


def test_workspace_inspector_tracks_clip_details_without_editing_project(
        layout_storage, tmp_path, monkeypatch):
    from streamclipper.models import VideoInfo
    from streamclipper.editor_project import initial_project
    app = QApplication.instance() or QApplication([])
    window = _window(app)
    try:
        source = tmp_path / "source.mkv"
        source.write_bytes(b"source-not-touched")
        info = VideoInfo(str(source), 300, 1920, 1080, 30, True)
        window.source = str(source)
        window._video_info = info
        window._source_duration = 300
        window.timeline.set_duration(300)
        window.editor_project = initial_project(info)
        window._refresh_track_tables()
        window._busy(False)
        window.workspace_picker.setCurrentText("Audio")
        window.tracks_table.selectRow(0)
        window.track_clips_table.selectRow(0)
        app.processEvents()
        assert window.inspector_dock.isVisible()
        assert "Originalaufnahme" in window.inspector_heading.text()
        assert "Timeline:" in window.inspector_details.text()
        assert "0.0 dB" in window.inspector_details.text()
        assert window.inspector_edit_button.isEnabled()
        assert source.read_bytes() == b"source-not-touched"
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()
