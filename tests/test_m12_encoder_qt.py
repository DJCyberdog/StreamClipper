"""M12c Qt: real encoder choices flow unchanged through preview/export workers."""
import os

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog
import streamclipper.gui as gui
from streamclipper.models import AnalysisResult, Candidate, VideoInfo


def test_encoder_selector_preview_snapshot_never_replaces_original_player(
        tmp_path,monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path/"original OBS six hour.mkv"
    source.write_bytes(b"video-source-stays")
    window = gui.MainWindow()
    try:
        info=VideoInfo(str(source), 21600, 1920, 1080, 60, True)
        window.source=str(source)
        window._video_info=info
        window._source_duration=info.duration
        window.timeline.set_duration(info.duration)
        window.timeline.set_selection(120,130)
        window._busy(False)
        assert window.encoder_mode.count() == 6
        assert window.encoder_mode.currentData() == "auto_h264"
        window.encoder_mode.setCurrentIndex(
            window.encoder_mode.findData("auto_hevc"))
        player=window.player
        started=[]
        monkeypatch.setattr(gui.RenderPreviewThread,"start",
                            lambda self: started.append(self))
        window.start_render_preview()
        assert len(started)==1
        assert started[0].request.encoder=="auto_hevc"
        assert window.player is player
        assert not window.encoder_mode.isEnabled()
        window._encoder_notice("NVENC-Test fehlgeschlagen; CPU wird verwendet")
        assert "CPU" in window.encoder_status.text()
        window.cancel_job()
        assert started[0]._cancelled.is_set()
        assert source.read_bytes()==b"video-source-stays"
    finally:
        window.worker=None
        window._autosave_timer.stop()
        window.close()
        app.processEvents()


def test_export_combo_passes_exact_selection_into_worker(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    source=tmp_path/"source.mkv"
    source.write_bytes(b"unchanged")
    info=VideoInfo(str(source),300,1920,1080,30,True)
    window=gui.MainWindow()
    try:
        window.source=str(source)
        window.analysis=AnalysisResult(
            info,[Candidate(10,15,80,"Loud",12)])
        window.table.setRowCount(1)
        window.table.selectRow(0)
        window.encoder_mode.setCurrentIndex(
            window.encoder_mode.findData("nvenc_h264"))
        monkeypatch.setattr(QFileDialog,"getExistingDirectory",
                            lambda *args: str(tmp_path))
        started=[]
        monkeypatch.setattr(gui.ExportThread,"start",
                            lambda self: started.append(self))
        window.start_export(False)
        assert len(started)==1
        assert started[0].encoder=="nvenc_h264"
        assert started[0].analysis is window.analysis
        assert started[0].items==window.analysis.candidates
        assert not window.encoder_mode.isEnabled()
        assert source.read_bytes()==b"unchanged"
    finally:
        window.worker=None
        window._autosave_timer.stop()
        window.close()
        app.processEvents()


def test_export_thread_forwards_profile_and_notice_without_live_gpu(
        tmp_path,monkeypatch):
    source=tmp_path/"video.mkv"
    source.write_bytes(b"unchanged")
    info=VideoInfo(str(source),20,320,180,25,True)
    analysis=AnalysisResult(info,[Candidate(1,3,50,"test",2)])
    thread=gui.ExportThread(analysis,analysis.candidates,str(tmp_path),
                            "crop",encoder="auto_hevc")
    observed,received=[],[]
    def fake_render(request,target,**kwargs):
        observed.append(request)
        kwargs["encoder_notice"]("NVENC-Test fehlgeschlagen; CPU HEVC")
        kwargs["progress"](100)
        return tmp_path/"no-actual-encode-in-qt-test.mp4"
    monkeypatch.setattr(gui,"render_request",fake_render)
    thread.encoder_notice.connect(received.append)
    thread.run()
    assert len(observed)==1
    assert observed[0].encoder=="auto_hevc"
    assert "CPU HEVC" in received[0]
    assert source.read_bytes()==b"unchanged"
