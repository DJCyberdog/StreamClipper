import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from streamclipper.models import AnalysisResult,VideoInfo,Candidate
from streamclipper.m17_montage_dialog import MontageDialog
from streamclipper.m17_preview import MontageTimeline
from streamclipper.montage import Beat

def test_montage_timeline_selection_reorder_and_immutability():
    app=QApplication.instance() or QApplication([])
    original=[Candidate(0,5,50,"first",2),Candidate(10,20,40,"second",14)]
    analysis=AnalysisResult(VideoInfo("dummy.mp4",30,1920,1080,30,True),original)
    dialog=MontageDialog(analysis)
    try:
        dialog.source.setCurrentIndex(0);dialog.add()
        dialog.source.setCurrentIndex(1);dialog.add()
        dialog.move(-1)
        assert [b.start for b in dialog.beats]==[10,0]
        assert analysis.candidates==original
        dialog.timeline.resize(316,78)
        assert dialog.timeline.index_at(20)==0
        assert dialog.timeline.index_at(280)==1
        dialog.timeline.selected.emit(1)
        assert dialog.list.currentRow()==1
        dialog.remove()
        assert len(dialog.beats)==1 and len(analysis.candidates)==2
    finally:dialog.close();app.processEvents()

def test_preview_worker_uses_snapshot_and_cancels(tmp_path):
    from streamclipper.m17_preview import PreviewWorker
    class Fake:
        def render(self,path,*,cancelled,progress):
            assert cancelled()
            raise RuntimeError("cancelled")
    worker=PreviewWorker(Fake(),tmp_path/"preview.mp4")
    worker.stop.set()
    result=[];worker.outcome.connect(result.append)
    worker.run()
    assert result==[(None,"cancelled")]
    assert not (tmp_path/"preview.mp4").exists()
