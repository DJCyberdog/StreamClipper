"""M12-UX Part 2: one aligned waveform/track view and atomic inspector editing."""
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox
from streamclipper.editor_project import (
    add_item, initial_project, load_project, save_project, toggle_track)
from streamclipper.models import VideoInfo
import streamclipper.gui as gui


@pytest.fixture
def editor(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    # Test isolation: no permanent portable UI or video files touched.
    monkeypatch.setattr(gui, "save_workspace", lambda _: None)
    monkeypatch.setattr(gui, "load_workspace", lambda: None)
    monkeypatch.setattr(gui, "delete_workspace", lambda: None)
    folder = tmp_path / "projects"
    monkeypatch.setattr(gui, "save_project", lambda p: save_project(p, root=folder))
    source = tmp_path / "OBS six hour recording.mkv"
    source.write_bytes(b"unchanged-media")
    video = VideoInfo(str(source), 21600, 1920, 1080, 60, True)
    window = gui.MainWindow()
    window.resize(1366, 768)
    window.source = str(source)
    window._video_info = video
    window._source_duration = video.duration
    window.timeline.set_duration(video.duration)
    window.editor_project = initial_project(video)
    window._refresh_track_tables()
    window._busy(False)
    window.show()
    app.processEvents()
    yield app, window, video, source, folder
    window._autosave_timer.stop()
    window.close()
    app.processEvents()


def test_waveform_and_tracks_one_shared_visible_time_axis(editor):
    app, window, info, source, folder = editor
    assert window.timeline.parentWidget() is window.unified_timeline
    assert window.track_canvas.parentWidget() is window.unified_timeline
    assert window.track_canvas._LEFT == window.timeline.left_gutter == 128
    assert window.timeline_scroll is not None
    window.timeline.set_zoom(360, center=200)
    window._sync_timeline_scroll()
    app.processEvents()
    assert window.track_canvas.view_start == pytest.approx(window.timeline.visible()[0])
    assert window.track_canvas.view_end == pytest.approx(window.timeline.visible()[1])
    for second in (190, 200, 210, 230):
        assert abs(window.track_canvas._x(second) - window.timeline._x(second)) <= 2
    window.timeline_scroll_changed(100)
    assert window.track_canvas.view_start == window.timeline.visible()[0]
    window.timeline_range_changed(200, 215)
    assert window.track_canvas._selection == (200, 215)
    window.timeline_seek(210)
    assert window.track_canvas._playhead == 210
    assert source.read_bytes() == b"unchanged-media"


def test_magnetic_snap_to_existing_clips_with_8px_threshold(editor):
    app, window, info, source, folder = editor
    project = add_item(window.editor_project, "music", 0, 5, 20, "Bass")
    project = add_item(project, "music", 6, 12, 28, "Beat")
    window.editor_project = project
    window._refresh_track_tables()
    window.track_canvas.resize(1000, 300)
    window.track_canvas.set_visible_range(0, 100)
    moving = project.items[-2]
    # At 1000 px, eight pixels are ~0.93 seconds; 27.6 -> 28.0
    # (another clip's start). The moved clip cannot snap to itself.
    assert window.track_canvas._snap_time(27.6, moving.id, 5) == 28
    window.timeline_snap.setChecked(False)
    assert window.track_canvas._snap_time(27.6, moving.id, 5) == 27.6
    window.timeline_snap.setChecked(True)
    assert window.track_canvas._snap_enabled
    assert source.read_bytes() == b"unchanged-media"


def test_inspector_applies_all_audio_clip_values_atomically_and_undo(editor):
    app, window, info, source, folder = editor
    audio_path = source.parent / "mic take.wav"
    audio_path.write_bytes(b"untouched-audio")
    project = add_item(
        window.editor_project, "mic", 100, 110, 20, "Mic",
        media_path=str(audio_path), gain_db=-3)
    window.editor_project = project
    window._refresh_track_tables()
    window.workspace_picker.setCurrentText("Audio")
    window.tracks_table.selectRow(1)
    window.track_clips_table.selectRow(1)
    app.processEvents()
    assert window.inspector_edit_area.isVisible()
    assert window._inspector_item_id == project.items[-1].id
    assert window.inspector_apply_button.isEnabled()
    window.inspector_source_start.setValue(101.5)
    window.inspector_source_end.setValue(109)
    window.inspector_timeline_start.setValue(30)
    window.inspector_gain.setValue(-8)
    window.inspector_apply_button.click()
    edited = window.editor_project.items[-1]
    assert (edited.source_start, edited.source_end, edited.timeline_start, edited.gain_db) == (
        101.5, 109, 30, -8)
    assert load_project(info, root=folder).items[-1] == edited
    assert window.track_canvas.project == window.editor_project
    assert window._history.can_undo
    window.undo_edit()
    reverted = window.editor_project.items[-1]
    assert (reverted.source_start, reverted.source_end,
            reverted.timeline_start, reverted.gain_db) == (100, 110, 20, -3)
    window.redo_edit()
    assert window.editor_project.items[-1] == edited
    assert source.read_bytes() == b"unchanged-media"
    assert audio_path.read_bytes() == b"untouched-audio"


def test_locked_track_and_original_source_cannot_be_edited_from_inspector(editor):
    app, window, info, source, folder = editor
    project = add_item(window.editor_project, "music", 1, 5, 10, "Music")
    window.editor_project = project
    window._refresh_track_tables()
    window.workspace_picker.setCurrentText("Schnitt")
    window.tracks_table.selectRow(2)
    window.track_clips_table.selectRow(1)
    window._apply_project_edit(toggle_track, "music", "locked")
    app.processEvents()
    assert not window.inspector_apply_button.isEnabled()
    state = window.editor_project
    window._apply_inspector_clip()
    assert window.editor_project == state
    window.track_clips_table.selectRow(0)
    assert window._inspector_item_id == "source"
    assert not window.inspector_apply_button.isEnabled()
    window._drag_project_clip("source", 10.0)
    assert window.editor_project == state
    assert source.read_bytes() == b"unchanged-media"


def test_inspector_save_failure_is_not_undoable(editor, monkeypatch):
    app, window, info, source, folder = editor
    window.editor_project = add_item(
        window.editor_project, "music", 1, 5, 10, "Intro")
    window._refresh_track_tables()
    window.workspace_picker.setCurrentText("Schnitt")
    window.tracks_table.selectRow(2)
    window.track_clips_table.selectRow(1)
    before = window.editor_project
    warnings = []
    monkeypatch.setattr(gui, "save_project",
                        lambda _: (_ for _ in ()).throw(OSError("Voll")))
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a: warnings.append(str(a[2])))
    window.inspector_timeline_start.setValue(30)
    window._apply_inspector_clip()
    assert window.editor_project == before
    assert not window._history.can_undo
    assert any("Voll" in w for w in warnings)
    assert source.read_bytes() == b"unchanged-media"
