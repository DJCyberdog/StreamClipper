"""M11a offscreen GUI smoke tests for history buttons and recovery."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox
from streamclipper.gui import MainWindow
from streamclipper.models import AnalysisResult, VideoInfo

def test_undo_redo_buttons_for_manual_highlights():
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        window.source="dummy.mp4"
        window._source_duration=21600
        window.timeline.set_duration(21600)
        window.analysis_finished(AnalysisResult(
            VideoInfo("dummy.mp4",21600,1920,1080,60,True),[]))
        assert not window.undo_button.isEnabled()
        assert not window.redo_button.isEnabled()
        window.add_manual_interval(120,140)
        assert len(window.analysis.candidates)==1
        assert window.undo_button.isEnabled()
        window.undo_edit()
        assert len(window.analysis.candidates)==0
        assert window.redo_button.isEnabled()
        window.redo_edit()
        assert len(window.analysis.candidates)==1
    finally:
        window._autosave_timer.stop()
        window.transcript_dirty=False
        window.close()
        app.processEvents()

def test_recovery_prompts_for_matching_video(tmp_path,monkeypatch):
    import streamclipper.gui as gui
    from streamclipper.autosave import save_autosave
    app=QApplication.instance() or QApplication([])
    video=tmp_path/"video.mkv"
    video.write_bytes(b"test source")
    info=VideoInfo(str(video),300,1920,1080,30,True)
    root=tmp_path/"backups"
    state=AnalysisResult(info,[])
    path=save_autosave(state,root=root)
    monkeypatch.setattr(gui,"autosave_path",lambda source: path)
    monkeypatch.setattr(gui,"load_autosave",
                        lambda source,**kwargs: state)
    monkeypatch.setattr(QMessageBox,"question",
                        lambda *args,**kwargs: QMessageBox.StandardButton.Yes)
    window=MainWindow()
    try:
        window.source=str(video)
        window.waveform_finished(str(video),(info,[0.1]*120))
        assert window.analysis is not None
        assert window.transcript_dirty
        assert "wiederhergestellt" in window.autosave_hint.text()
    finally:
        window._autosave_timer.stop()
        window.transcript_dirty=False
        window.close()
        app.processEvents()
