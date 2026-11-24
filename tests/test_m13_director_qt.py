"""Offscreen GUI coverage for M13b/c scene-local controls."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication,QDialog
from streamclipper.models import VideoInfo
from streamclipper.scene_selection import initial_selection
from streamclipper.scene_selection_dialog import SceneSelectionDialog
from streamclipper.director_dialog import DirectorDialog


def test_director_edits_are_scene_local_and_persist_only_on_save(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    video=VideoInfo(str(tmp_path/"source.mp4"),6,320,240,25,True)
    plan=initial_selection(0,6).split(0,3)
    commits=[]
    dialog=SceneSelectionDialog(video,0,6,plan=plan,
                                commit=lambda p: commits.append(p) or True)
    def edit_director(self):
        assert self.x.value()==pytest.approx(.25)
        assert self.y.value()==pytest.approx(.75)
        self.at.setValue(1)
        self.zoom.setValue(1.4)
        self.add_key()
        self.kind.setCurrentText("alert")
        for field,value in zip(self.rect,(.7,.1,.2,.2)):
            field.setValue(value)
        self.dynamic.setChecked(True)
        self.zone_start.setValue(.5);self.zone_end.setValue(1.5)
        self.mask.setChecked(True)
        self.add_zone()
        self.removal.setChecked(True)
        self.safe.setCurrentText("top")
        self.finish()
        return self.result()
    monkeypatch.setattr(DirectorDialog,"exec",edit_director)
    try:
        dialog._subject_clicked((.25,.75))
        dialog._director()
        assert not commits
        first,second=dialog.plan.scenes
        assert first.director.manual[0].x==pytest.approx(.25)
        assert first.director.zones[0].kind=="alert"
        assert first.director.zones[0].start==.5
        assert first.director.removal_enabled
        assert first.director.caption_safe=="top"
        assert not second.director.manual and not second.director.zones
        dialog._save()
        assert dialog.result()==QDialog.DialogCode.Accepted
        assert len(commits)==1 and commits[0]==dialog.plan
    finally:
        dialog.close()
        app.processEvents()


def test_reload_frame_clears_stale_clicked_subject(tmp_path,monkeypatch):
    from streamclipper import scene_selection_dialog as module
    app=QApplication.instance() or QApplication([])
    video=VideoInfo(str(tmp_path/"source.mp4"),6,320,240,25,True)
    dialog=SceneSelectionDialog(video,0,6,plan=initial_selection(0,6))
    monkeypatch.setattr(module.FrameWorker,"start",lambda self:None)
    try:
        dialog.subject_point=(.25,.75)
        dialog.frame_at=1.
        dialog.cut.setValue(2.)
        dialog._load_frame()
        assert dialog.subject_point is None and dialog.frame_at is None
        assert dialog.frame_worker.at==2.
        dialog._frame_finished()
    finally:
        dialog.close()
        app.processEvents()
