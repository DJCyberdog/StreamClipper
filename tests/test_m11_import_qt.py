"""M11c-3 Qt offscreen: explicit import, no silent mutation or duplicate clips."""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
import streamclipper.gui as gui
from streamclipper.editor_project import save_project, load_project, toggle_track
from streamclipper.models import AnalysisResult, Candidate, VideoInfo


def window_for(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    media = tmp_path / "gaming.mkv"
    media.write_bytes(b"unchanged media")
    video = VideoInfo(str(media), 21600, 1920, 1080, 60, True)
    folder = tmp_path / "editor"
    monkeypatch.setattr(gui, "save_project", lambda p: save_project(p, root=folder))
    window = gui.MainWindow()
    window.source = str(media)
    window._source_duration = video.duration
    window.timeline.set_duration(video.duration)
    window._open_editor_project(video)
    window.analysis_finished(AnalysisResult(video, [
        Candidate(80, 99, 45, "Audiohinweis", 91),
        Candidate(144.5, 170, 0, "Manuell", 150, "manual")]))
    return app, window, video, media, folder


def clean(window, app):
    window._autosave_timer.stop()
    window.transcript_dirty = False
    window.close()
    app.processEvents()


def test_explicit_import_and_repeat_are_one_undoable_edit(tmp_path, monkeypatch):
    app, window, video, media, folder = window_for(tmp_path, monkeypatch)
    monkeypatch.setattr(QInputDialog, "getItem",
                        lambda *args, **kwargs: (args[3][0], True))
    try:
        assert window.track_import_button.isEnabled()
        assert len(window.editor_project.items) == 1
        window._import_analysis_highlights()
        assert len(window.editor_project.items) == 3
        assert window.editor_project.tracks[-1].id == "highlights_import"
        assert load_project(video, root=folder) == window.editor_project
        assert "2 neue" in window.track_status.text()
        window._import_analysis_highlights()
        assert len(window.editor_project.items) == 3
        assert "0 neue" in window.track_status.text()
        assert window._history.can_undo
        window.undo_edit()
        assert len(window.editor_project.items) == 1
        assert len(window.editor_project.tracks) == 5
        window.redo_edit()
        assert len(window.editor_project.items) == 3
        assert media.read_bytes() == b"unchanged media"
    finally:
        clean(window, app)


def test_import_to_locked_video_track_fails_without_writing(tmp_path, monkeypatch):
    app, window, video, media, folder = window_for(tmp_path, monkeypatch)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args, **kwargs: warnings.append(str(args[2])))
    # Choose the already existing gameplay track, now locked.
    monkeypatch.setattr(QInputDialog, "getItem",
                        lambda *args, **kwargs: (args[3][1], True))
    try:
        window._apply_project_edit(toggle_track, "gameplay", "locked")
        before = window.editor_project
        window._import_analysis_highlights()
        assert window.editor_project == before
        assert len(before.items) == 1
        assert any("gesperrt" in w for w in warnings)
        assert media.read_bytes() == b"unchanged media"
    finally:
        clean(window, app)


def test_import_write_failure_does_not_advance_history(tmp_path, monkeypatch):
    app, window, video, media, folder = window_for(tmp_path, monkeypatch)
    monkeypatch.setattr(QInputDialog, "getItem",
                        lambda *args, **kwargs: (args[3][0], True))
    messages = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args, **kwargs: messages.append(str(args[2])))
    try:
        monkeypatch.setattr(gui, "save_project",
                            lambda _: (_ for _ in ()).throw(OSError("Speicher voll")))
        before = window.editor_project
        window._import_analysis_highlights()
        assert window.editor_project == before
        assert not window._history.can_undo
        assert len(before.tracks) == 5
        assert any("Speicher voll" in x for x in messages)
        assert media.read_bytes() == b"unchanged media"
    finally:
        clean(window, app)
