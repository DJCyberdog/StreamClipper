"""M11c Qt smoke: project menu and checkpoint UI without media decoding."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog
import streamclipper.gui as gui
import streamclipper.project_checkpoints as cp
from streamclipper.editor_project import initial_project, add_track
from streamclipper.models import VideoInfo


def test_project_menu_and_save_restore(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source_path = tmp_path / "recording.mkv"
    source_path.write_bytes(b"untouched")
    video = VideoInfo(str(source_path), 300, 1920, 1080, 30, True)
    root = tmp_path / "checkpoints"
    editor_root = tmp_path / "editor"
    monkeypatch.setattr(gui, "create_checkpoint",
                        lambda project, name, analysis: cp.create_checkpoint(
                            project, name, analysis, root=root))
    monkeypatch.setattr(gui, "list_checkpoints",
                        lambda source: cp.list_checkpoints(source, root=root))
    monkeypatch.setattr(gui, "load_checkpoint",
                        lambda source, id: cp.load_checkpoint(source, id, root=root))
    monkeypatch.setattr(gui, "save_project",
                        lambda project: __import__(
                            "streamclipper.editor_project", fromlist=["save_project"]
                        ).save_project(project, root=editor_root))
    monkeypatch.setattr(QInputDialog, "getText",
                        lambda *args, **kwargs: ("Vor dem Feinschnitt", True))
    monkeypatch.setattr(QInputDialog, "getItem",
                        lambda *args, **kwargs: (args[3][0], True))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    window = gui.MainWindow()
    try:
        assert not window.checkpoint_save_action.isEnabled()
        assert not window.checkpoint_restore_action.isEnabled()
        assert any(action.text() == "Datei && Projekt" for action in window.menuBar().actions())
        assert window.tabs.count() == 5
        window.source = str(source_path)
        window._source_duration = video.duration
        window.timeline.set_duration(video.duration)
        window._open_editor_project(video)
        assert window.checkpoint_save_action.isEnabled()
        window._save_project_checkpoint()
        assert len(cp.list_checkpoints(video, root=root)) == 1
        window._apply_project_edit(add_track, "audio", "Kommentar")
        assert len(window.editor_project.tracks) == 6
        window._restore_project_checkpoint()
        assert len(window.editor_project.tracks) == 5
        assert not window._history.can_undo
        assert source_path.read_bytes() == b"untouched"
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()
