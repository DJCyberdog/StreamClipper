"""M11c Qt regression: mixed chronological history and native text undo."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
import streamclipper.gui as gui
from streamclipper.editor_project import add_track, save_project
from streamclipper.models import AnalysisResult, TranscriptSegment, VideoInfo


def make_window(tmp_path, monkeypatch):
    source_file = tmp_path / "recording.mkv"
    source_file.write_bytes(b"original")
    video = VideoInfo(str(source_file), 21600, 1920, 1080, 60, True)
    root = tmp_path / "editor"
    monkeypatch.setattr(gui, "save_project", lambda p: save_project(p, root=root))
    window = gui.MainWindow()
    window.source = str(source_file)
    window._source_duration = video.duration
    window.timeline.set_duration(video.duration)
    window._open_editor_project(video)
    window.analysis_finished(AnalysisResult(
        video, [], transcript=[TranscriptSegment(100, 101, "Hallo Welt")]))
    return window, source_file


def shutdown(window):
    window._autosave_timer.stop()
    window.transcript_dirty = False
    window.close()
    QApplication.instance().processEvents()


def test_mixed_history_gui_has_one_global_undo(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window, source = make_window(tmp_path, monkeypatch)
    try:
        assert not hasattr(window, "track_undo_button")
        assert window._apply_project_edit(add_track, "audio", "Kommentar")
        assert len(window.editor_project.tracks) == 6
        window.add_manual_interval(120, 140)
        assert len(window.analysis.candidates) == 1
        assert window.undo_button.isEnabled()
        window.tabs.setCurrentIndex(3)
        window.undo_edit()
        assert len(window.analysis.candidates) == 0
        assert len(window.editor_project.tracks) == 6
        window.undo_edit()
        assert len(window.editor_project.tracks) == 5
        assert window.redo_button.isEnabled()
        window.redo_edit()
        assert len(window.editor_project.tracks) == 6
        window.redo_edit()
        assert len(window.analysis.candidates) == 1
        assert source.read_bytes() == b"original"
    finally:
        shutdown(window)


def test_failed_track_undo_does_not_consume_history(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window, source = make_window(tmp_path, monkeypatch)
    try:
        assert window._apply_project_edit(add_track, "audio", "Kommentar")
        assert window._history.can_undo
        original_save = gui.save_project
        monkeypatch.setattr(gui, "save_project", lambda _p: (_ for _ in ()).throw(OSError("Disk full")))
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning",
                            lambda *args, **kw: warnings.append(args[2]))
        window.undo_edit()
        assert len(window.editor_project.tracks) == 6
        assert window._history.can_undo
        assert not window._history.can_redo
        assert any("Disk full" in msg for msg in warnings)
        monkeypatch.setattr(gui, "save_project", original_save)
        window.undo_edit()
        assert len(window.editor_project.tracks) == 5
        assert source.read_bytes() == b"original"
    finally:
        shutdown(window)


def test_shortcut_preserves_text_widget_native_undo(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window, _ = make_window(tmp_path, monkeypatch)
    try:
        window.show()
        app.processEvents()
        assert window._apply_project_edit(add_track, "audio", "Kommentar")
        editor = window.transcript_edit_text
        editor.setFocus()
        app.processEvents()
        original = editor.toPlainText()
        QTest.keyClicks(editor, "X")
        assert editor.toPlainText() != original
        # Text edits must be reverted *inside* the focused widget, not in the
        # studio history. Direct handler verifies both Qt shortcut branches.
        window._shortcut_undo()
        assert editor.toPlainText() == original
        assert len(window.editor_project.tracks) == 6
        assert window._history.can_undo
        window._shortcut_redo()
        assert editor.toPlainText() != original
        assert len(window.editor_project.tracks) == 6
        # Switching to a neutral focused widget activates workspace history.
        window.open_button.setFocus()
        app.processEvents()
        window._shortcut_undo()
        assert len(window.editor_project.tracks) == 5
    finally:
        shutdown(window)
