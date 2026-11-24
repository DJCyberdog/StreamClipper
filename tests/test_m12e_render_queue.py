"""M12e offline queue: crash recovery, at-most-once publication, lock and cancellation."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

import streamclipper.render_queue as rq
from streamclipper.export_qa import QualityReport, write_report
from streamclipper.models import VideoInfo
from streamclipper.render_contract import RenderRequest


def request(tmp_path):
    return RenderRequest(VideoInfo(str(tmp_path/"source.mkv"),
                         300,320,180,25,True),
                         10,12,"crop",False,0,(),320,180)


def fake_success(calls, *, fail=False, cancel=False):
    def render(req, path, **kw):
        calls.append(path)
        if cancel:
            kw["cancelled"]()  # existing cancel flag
            raise rq.CancelledError("Stop")
        if fail:
            raise RuntimeError("Simulierte FFmpeg-Unterbrechung")
        path=Path(path)
        path.write_bytes(b"VALID_RENDER_OUTPUT_FOR_TESTS")
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        report=QualityReport(
            1,"PASS","h264","h264",320,180,2,2,0,
            False,None,None,None,None,None,0,(),digest,
            path.stat().st_size,"2026-11-24T08:00:00+00:00")
        write_report(report,path)
        kw["progress"](100)
        return path
    return render


def test_queue_snapshot_and_explicit_start_and_recovery(tmp_path,monkeypatch):
    root=tmp_path/"queue"
    calls=[]
    monkeypatch.setattr(rq,"render_request",fake_success(calls))
    queue=rq.RenderQueue(root=root)
    try:
        job=queue.enqueue(request(tmp_path),tmp_path,label="Clip 1")
        assert job.status=="QUEUED"
        assert not Path(job.destination).exists()
        assert rq._rehydrate(queue.jobs()[0].request)==request(tmp_path)
        assert queue.jobs()[0].request_sha256==rq._fingerprint(job.request)
        rendered=queue.run_next()
        assert rendered.status=="COMPLETE"
        assert rendered.result==job.destination
        assert Path(job.destination).exists()
        assert Path(job.destination+".qa.json").exists()
        assert Path(job.destination+".scjob.json").exists()
        assert len(calls)==1
        assert queue.run_next() is None
    finally:
        queue.close()
    recovered=rq.RenderQueue(root=root)
    try:
        assert recovered.jobs()[0].status=="COMPLETE"
        assert recovered.run_next() is None
        assert len(calls)==1
    finally:
        recovered.close()


def test_running_at_restart_becomes_manual_interrupted_not_auto_run(tmp_path):
    root=tmp_path/"queue"
    queue=rq.RenderQueue(root=root)
    job=queue.enqueue(request(tmp_path),tmp_path)
    queue.close()
    path=root/"render-queue-v1.json"
    doc=json.loads(path.read_text("utf-8"))
    doc["jobs"][0]["status"]="RUNNING"
    path.write_text(json.dumps(doc))
    resumed=rq.RenderQueue(root=root)
    try:
        assert resumed.jobs()[0].status=="INTERRUPTED"
        assert resumed.run_next() is None
        resumed.resume(job.id)
        assert resumed.jobs()[0].status=="QUEUED"
    finally:
        resumed.close()


def test_existing_unreceipted_file_is_blocked_and_never_reencoded(
        tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(rq,"render_request",fake_success(calls))
    queue=rq.RenderQueue(root=tmp_path/"queue")
    job=queue.enqueue(request(tmp_path),tmp_path)
    Path(job.destination).write_bytes(b"possibly-somebody-elses-video")
    try:
        result=queue.run_next()
        assert result.status=="BLOCKED"
        assert not calls
        assert Path(job.destination).read_bytes()==b"possibly-somebody-elses-video"
        with pytest.raises(ValueError):
            queue.resume(job.id)
        queue.discard(job.id)
        assert Path(job.destination).read_bytes()==b"possibly-somebody-elses-video"
    finally:
        queue.close()


def test_crash_after_publish_before_receipt_blocks_duplicate(tmp_path,monkeypatch):
    original_write=rq._write_json
    calls=[]
    monkeypatch.setattr(rq,"render_request",fake_success(calls))
    def fail_receipt(path,data):
        if str(path).endswith(".scjob.json"):
            raise OSError("receipt disk full")
        original_write(path,data)
    queue=rq.RenderQueue(root=tmp_path/"queue")
    job=queue.enqueue(request(tmp_path),tmp_path)
    monkeypatch.setattr(rq,"_write_json",fail_receipt)
    finished=queue.run_next()
    assert finished.status=="BLOCKED"
    assert len(calls)==1
    assert Path(job.destination).exists()
    queue.close()
    monkeypatch.setattr(rq,"_write_json",original_write)
    again=rq.RenderQueue(root=tmp_path/"queue")
    try:
        assert again.jobs()[0].status=="BLOCKED"
        assert again.run_next() is None
        assert len(calls)==1
    finally:
        again.close()


def test_failure_then_explicit_resume_preserves_job_target(tmp_path,monkeypatch):
    calls=[]
    queue=rq.RenderQueue(root=tmp_path/"queue")
    job=queue.enqueue(request(tmp_path),tmp_path)
    monkeypatch.setattr(rq,"render_request",fake_success(calls,fail=True))
    try:
        failed=queue.run_next()
        assert failed.status=="FAILED"
        assert queue.run_next() is None
        resumed=queue.resume(job.id)
        assert resumed.status=="QUEUED"
        assert resumed.destination==job.destination
        monkeypatch.setattr(rq,"render_request",fake_success(calls))
        done=queue.run_next()
        assert done.status=="COMPLETE"
        assert len(calls)==2
    finally:
        queue.close()


def test_queue_cancellation_keeps_original_and_requires_manual_resume(
        tmp_path,monkeypatch):
    calls=[]
    queue=rq.RenderQueue(root=tmp_path/"queue")
    job=queue.enqueue(request(tmp_path),tmp_path)
    monkeypatch.setattr(rq,"render_request",fake_success(calls,cancel=True))
    try:
        assert queue.run_next().status=="CANCELLED"
        assert not Path(job.destination).exists()
        assert queue.run_next() is None
        assert queue.resume(job.id).status=="QUEUED"
        queue.cancel(job.id)
        assert queue.jobs()[0].status=="CANCELLED"
        assert not Path(job.destination).exists()
    finally:
        queue.close()


def test_lock_prevents_two_processes_same_queue(tmp_path):
    root=tmp_path/"queue"
    first=rq.RenderQueue(root=root)
    try:
        with pytest.raises(RuntimeError,match="anderen Instanz"):
            rq.RenderQueue(root=root)
    finally:
        first.close()
    again=rq.RenderQueue(root=root)
    again.close()


def test_invalid_queue_json_fails_closed_no_overwrite(tmp_path):
    root=tmp_path/"queue"
    root.mkdir()
    path=root/"render-queue-v1.json"
    path.write_text('{"schema_version":777,"jobs":[]}')
    before=path.read_bytes()
    with pytest.raises(ValueError,match="Version"):
        rq.RenderQueue(root=root)
    assert path.read_bytes()==before


def test_completed_file_tamper_blocks_on_restart(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(rq,"render_request",fake_success(calls))
    root=tmp_path/"queue"
    store=rq.RenderQueue(root=root)
    item=store.enqueue(request(tmp_path),tmp_path)
    assert store.run_next().status=="COMPLETE"
    store.close()
    with Path(item.destination).open("ab") as f:
        f.write(b"tampered")
    restarted=rq.RenderQueue(root=root)
    try:
        assert restarted.jobs()[0].status=="BLOCKED"
        assert restarted.run_next() is None
        assert len(calls)==1
    finally:
        restarted.close()
