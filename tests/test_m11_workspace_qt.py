"""M11b: responsive workspace and metadata track editing (Qt offscreen)."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from streamclipper.gui import MainWindow
import streamclipper.gui as gui
from streamclipper.editor_project import add_track, load_project, toggle_track
from streamclipper.models import VideoInfo


def test_workspace_tabs_and_collapsible_word_editor():
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        labels=[window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert labels==["Highlights","Untertitel","KI & Modelle","Spuren","Export"]
        assert window.word_editor_panel.isHidden()
        window.word_editor_toggle.setChecked(True)
        assert not window.word_editor_panel.isHidden()
        window.word_editor_toggle.setChecked(False)
        assert window.word_editor_panel.isHidden()
        assert window.video_widget is not None and window.timeline is not None
        assert window.speech_select.count()>=6
        assert window.mode.count()==4
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()


def test_multitrack_tab_atomic_edits_and_project_history(tmp_path,monkeypatch):
    from streamclipper.editor_project import save_project
    app=QApplication.instance() or QApplication([])
    src=tmp_path/"gaming vod.mkv"
    src.write_bytes(b"not decoded in metadata test")
    source=VideoInfo(str(src),21600,1920,1080,60,True)
    folder=tmp_path/"metadata"
    monkeypatch.setattr(gui,"save_project",lambda p: save_project(p,root=folder))
    window=MainWindow()
    try:
        window.source=str(src)
        window._source_duration=21600
        window.timeline.set_duration(21600)
        window._open_editor_project(source)
        assert window.tracks_table.rowCount()==5
        assert window.track_clips_table.rowCount()==1
        assert window._apply_project_edit(add_track,"audio","Voiceover")
        assert window.tracks_table.rowCount()==6
        assert load_project(source,root=folder).tracks[-1].name=="Voiceover"
        window._undo_project()
        assert window.tracks_table.rowCount()==5
        window._redo_project()
        assert window.tracks_table.rowCount()==6
        window.tracks_table.selectRow(0)
        window.timeline.set_selection(120,141)
        window._add_selected_track_clip()
        assert window.track_clips_table.rowCount()==2
        assert load_project(source,root=folder).items[-1].source_start==120
        window.tracks_table.selectRow(2)
        window._toggle_selected_track("locked")
        assert window.editor_project.tracks[2].locked
        assert src.read_bytes()==b"not decoded in metadata test"
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()
