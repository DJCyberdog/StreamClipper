"""M12d/e GUI: queue actions never render until asked, persistent jobs, progress."""
import os
from pathlib import Path

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog
import streamclipper.gui as gui
from streamclipper.models import VideoInfo, AnalysisResult, Candidate
from streamclipper.render_queue import RenderQueue
import streamclipper.render_queue as rq
from streamclipper.export_qa import QualityReport, write_report
import hashlib


@pytest.fixture
def window(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(gui,"load_workspace",lambda:None)
    monkeypatch.setattr(gui,"save_workspace",lambda _:None)
    monkeypatch.setattr(gui,"RenderQueue",lambda: RenderQueue(
        root=tmp_path/"queue"))
    source=tmp_path/"full-OBS.mkv"
    source.write_bytes(b"original-untouched")
    info=VideoInfo(str(source),21600,1920,1080,60,True)
    main=gui.MainWindow()
    main.source=str(source)
    main._video_info=info
    main._source_duration=info.duration
    main.timeline.set_duration(info.duration)
    main.analysis=AnalysisResult(
        info,[Candidate(80,90,90,"Rage",85),
              Candidate(120,129,88,"Clutch",123)])
    main.refresh_highlight_table()
    main.table.selectRow(0)
    main._busy(False)
    main.show()
    app.processEvents()
    yield app,main,source
    main.worker=None
    main.queue_worker=None
    main._autosave_timer.stop()
    main.close()
    app.processEvents()


def test_queue_is_opt_in_and_persists_per_clip_encoder_snapshot(window,tmp_path,monkeypatch):
    app,win,source=window
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",
                        lambda *a: str(tmp_path))
    win.encoder_mode.setCurrentIndex(
        win.encoder_mode.findData("auto_hevc"))
    win.mode.setCurrentIndex(2)
    assert win.render_queue is None
    win._queue_enqueue(True)
    assert win.render_queue is not None
    jobs=win.render_queue.jobs()
    assert len(jobs)==2
    assert all(j.status=="QUEUED" for j in jobs)
    assert [j.request["encoder"] for j in jobs]==[
        "auto_hevc","auto_hevc"]
    assert [j.request["start"] for j in jobs]==[80,120]
    assert win.queue_table.rowCount()==2
    assert not any(Path(j.destination).exists() for j in jobs)
    win.encoder_mode.setCurrentIndex(
        win.encoder_mode.findData("cpu_h264"))
    assert all(j.request["encoder"]=="auto_hevc" for j in jobs)
    assert source.read_bytes()==b"original-untouched"


def test_user_start_queue_and_recover_from_fail_then_retry(window,tmp_path,monkeypatch):
    app,win,source=window
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",
                        lambda *a: str(tmp_path))
    win._queue_enqueue(False)
    job=win.render_queue.jobs()[0]
    calls=[]
    def fail(req,path,**kw):
        calls.append(path)
        raise RuntimeError("Test-Abbruch")
    monkeypatch.setattr(rq,"render_request",fail)
    # Run QThread synchronously in an offscreen test; the real GUI uses start().
    win._queue_start()
    worker=win.queue_worker
    worker.cancel() if False else None
    worker.wait(10000)
    app.processEvents()
    assert win.render_queue.jobs()[0].status=="FAILED"
    assert len(calls)==1
    win.queue_table.selectRow(0)
    win._queue_resume()
    assert win.render_queue.jobs()[0].status=="QUEUED"
    assert source.read_bytes()==b"original-untouched"


def test_queue_cancel_and_discard_only_metadata(window,tmp_path,monkeypatch):
    app,win,source=window
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",
                        lambda *a: str(tmp_path))
    win._queue_enqueue(False)
    assert len(win.render_queue.jobs())==1
    win.queue_table.selectRow(0)
    win._queue_cancel()
    assert win.render_queue.jobs()[0].status=="CANCELLED"
    win.queue_table.selectRow(0)
    win._queue_discard()
    assert not win.render_queue.jobs()
    assert source.read_bytes()==b"original-untouched"
