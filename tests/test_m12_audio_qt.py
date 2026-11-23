"""Qt M12b: local audio import, gain and opt-in render snapshot (offline)."""
from pathlib import Path
import os

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog
from streamclipper.gui import MainWindow, RenderPreviewThread
import streamclipper.gui as gui
from streamclipper.editor_project import initial_project, save_project
from streamclipper.models import VideoInfo


def test_audio_file_adds_to_selected_track_and_goes_to_preview_request(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    video = tmp_path/"original.mp4"
    audio = tmp_path/"voice.wav"
    video.write_bytes(b"original")
    audio.write_bytes(b"unchanged audio")
    info = VideoInfo(str(video), 100, 320, 180, 30, True)
    monkeypatch.setattr(gui,"save_project",lambda project: save_project(
        project,root=tmp_path/"saved"))
    monkeypatch.setattr(gui,"probe_audio_duration",lambda _: 8.0)
    monkeypatch.setattr(QFileDialog,"getOpenFileName",
                        lambda *args, **kwargs: (str(audio),"Audio"))
    monkeypatch.setattr(QInputDialog,"getDouble",
                        lambda *args, **kwargs: (-9., True))
    monkeypatch.setattr(RenderPreviewThread,"start",
                        lambda self: None)
    window = MainWindow()
    try:
        window.source = str(video)
        window._video_info = info
        window._source_duration = 100
        window.timeline.set_duration(100)
        window._open_editor_project(info)
        assert not window.include_track_audio.isEnabled()
        window.tracks_table.selectRow(1)  # microphone
        assert window.track_audio_import.isEnabled()
        window.timeline.set_selection(20, 35)
        window._add_audio_file_to_track()
        assert window.include_track_audio.isEnabled()
        assert window.track_clips_table.rowCount() == 2
        item = window.editor_project.items[-1]
        assert item.track_id == "mic"
        assert item.media_path == str(audio)
        assert item.timeline_start == 20
        assert item.gain_db == -9
        window.include_track_audio.setChecked(True)
        assert window.render_preview_button.isEnabled()
        window.start_render_preview()
        assert isinstance(window.worker, RenderPreviewThread)
        assert window.worker.request.project == window.editor_project
        assert window.worker.request.start == 20
        assert audio.read_bytes() == b"unchanged audio"
        assert video.read_bytes() == b"original"
        window.worker = None
        window._busy(False)
        window.track_clips_table.selectRow(1)
        window._edit_selected_clip_gain()
        assert window.editor_project.items[-1].gain_db == -9
        window._undo_project()
        assert window.editor_project.items[-1].gain_db == -9
    finally:
        window.worker = None
        window._autosave_timer.stop()
        window.close()
        app.processEvents()


def test_no_audio_track_selection_disables_import_and_no_implicit_mix(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        src=tmp_path/"game.mp4"
        src.write_bytes(b"unchanged")
        info=VideoInfo(str(src), 100, 320, 180, 30, True)
        window.source=str(src)
        window._video_info=info
        window._source_duration=100
        window._open_editor_project(info)
        window.tracks_table.selectRow(0)
        assert not window.track_audio_import.isEnabled()
        assert not window.include_track_audio.isChecked()
        assert not window.include_track_audio.isEnabled()
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()
