"""M12b2 Qt: explicit local graphics/facecam import and visual Inspector undo."""
import os

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog
import streamclipper.gui as gui
from streamclipper.editor_project import add_track, initial_project, save_project
from streamclipper.models import VideoInfo
from streamclipper.render_contract import RenderRequest
from streamclipper.render_graph import build_render_graph


@pytest.fixture
def editor(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(gui, "load_workspace", lambda: None)
    monkeypatch.setattr(gui, "save_workspace", lambda _: None)
    monkeypatch.setattr(gui, "save_project",
                        lambda project: save_project(
                            project,root=tmp_path/"projects"))
    base = tmp_path/"OBS.mkv"
    base.write_bytes(b"video-source-must-not-change")
    video = VideoInfo(str(base), 300, 640, 360, 30, True)
    window = gui.MainWindow()
    window.source=str(base)
    window._video_info=video
    window._source_duration=300
    window.timeline.set_duration(300)
    window.editor_project=initial_project(video)
    window._refresh_track_tables()
    window._busy(False)
    window.show()
    app.processEvents()
    yield window, video, base
    window._autosave_timer.stop()
    window.close()
    app.processEvents()


def test_insert_logo_then_edit_geometry_with_atomic_undo(editor,tmp_path,monkeypatch):
    window,video,base = editor
    logo=tmp_path/"Doghouse-logo.png"
    logo.write_bytes(b"image-source-must-not-change")
    monkeypatch.setattr(QFileDialog,"getOpenFileName",
                        lambda *a,**kw:(str(logo),"Graphic"))
    monkeypatch.setattr(gui,"probe_still_image",lambda path:(320,200))
    window.tracks_table.selectRow(4)  # original graphics lane
    assert window.track_visual_import.isEnabled()
    assert not window.track_audio_import.isEnabled()
    window.timeline.set_selection(20,24)
    window._add_visual_file_to_track()
    assert len(window.editor_project.items)==2
    item=window.editor_project.items[-1]
    assert item.track_id=="graphics"
    assert item.media_path==str(logo)
    assert item.timeline_start==20
    assert item.source_end==4
    assert window.include_track_audio.isEnabled()
    window.include_track_audio.setChecked(True)
    window.workspace_picker.setCurrentText("Schnitt")
    window.track_clips_table.selectRow(1)
    QApplication.processEvents()
    assert window.inspector_visual_area.isVisible()
    assert window.inspector_opacity.value()==1
    window.inspector_x.setValue(.2)
    window.inspector_y.setValue(.4)
    window.inspector_width.setValue(.3)
    window.inspector_height.setValue(.2)
    window.inspector_opacity.setValue(.5)
    window._apply_inspector_clip()
    updated=window.editor_project.items[-1]
    assert (updated.x,updated.y,updated.width,updated.height,updated.opacity)==(
        .2,.4,.3,.2,.5)
    assert len(build_render_graph(window.editor_project,video,20,24).visual_layers)==1
    window.undo_edit()
    assert window.editor_project.items[-1]==item
    window.redo_edit()
    assert window.editor_project.items[-1]==updated
    assert window.include_track_audio.isChecked()
    assert base.read_bytes()==b"video-source-must-not-change"
    assert logo.read_bytes()==b"image-source-must-not-change"


def test_insert_facecam_file_to_new_video_track(editor,tmp_path,monkeypatch):
    window,video,base=editor
    facecam=tmp_path/"facecam.mp4"
    facecam.write_bytes(b"never-overwrite")
    monkeypatch.setattr(QFileDialog,"getOpenFileName",
                        lambda *a,**kw:(str(facecam),"Video"))
    monkeypatch.setattr(gui,"probe_video",
                        lambda path: VideoInfo(str(facecam),3,320,240,25,True))
    window._apply_project_edit(add_track,"video","Facecam")
    window.tracks_table.selectRow(5)
    assert window.track_visual_import.isEnabled()
    window.timeline.set_selection(30,35)
    window._add_visual_file_to_track()
    item=window.editor_project.items[-1]
    assert item.track_id=="video_1"
    assert item.media_path==str(facecam)
    assert item.source_end==3
    assert item.timeline_start==30
    assert window.include_track_audio.isEnabled()
    window.include_track_audio.setChecked(True)
    request=RenderRequest(video,30,33,"crop",False,0,(),360,640,
                          window.editor_project)
    assert len(build_render_graph(request.project,video,30,33).visual_layers)==1
    assert facecam.read_bytes()==b"never-overwrite"
    window.tracks_table.selectRow(0)
    assert not window.track_visual_import.isEnabled()


def test_locked_visual_inspector_and_invalid_bounds_do_not_mutate(editor,tmp_path,monkeypatch):
    from streamclipper.editor_project import add_item,toggle_track
    from PySide6.QtWidgets import QMessageBox
    window,video,base=editor
    logo=tmp_path/"logo.png"
    logo.write_bytes(b"still")
    project=add_item(window.editor_project,"graphics",0,4,12,
                     media_path=str(logo))
    window.editor_project=project
    window._refresh_track_tables()
    window.workspace_picker.setCurrentText("Schnitt")
    window.tracks_table.selectRow(4)
    window.track_clips_table.selectRow(1)
    warnings=[]
    monkeypatch.setattr(QMessageBox,"warning",
                        lambda *a: warnings.append(str(a[2])))
    window.inspector_x.setValue(.9)
    window.inspector_width.setValue(.3)
    window._apply_inspector_clip()
    assert window.editor_project==project
    assert any("ungültig" in w.lower() or "Clip" in w for w in warnings)
    window._apply_project_edit(toggle_track,"graphics","locked")
    locked=window.editor_project
    assert not window.inspector_apply_button.isEnabled()
    window._apply_inspector_clip()
    assert window.editor_project==locked
    assert base.read_bytes()==b"video-source-must-not-change"
