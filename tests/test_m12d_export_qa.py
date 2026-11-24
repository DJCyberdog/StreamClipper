"""M12d: real MP4 QA, decoded frames, sampled EBU R128, fail-closed publication."""
import dataclasses
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from streamclipper.export_qa import inspect_export, read_report, write_report
from streamclipper.media import export_clip, probe_video
from streamclipper.render_contract import RenderRequest, render_request

AVAILABLE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ffmpeg(*args):
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         *map(str, args)], check=True, capture_output=True, timeout=70)


def make_video(tmp_path, *, with_audio=True):
    source = tmp_path/"OBS Aufnahme ö.mp4"
    args = ["-f", "lavfi", "-i", "color=c=red:s=320x180:r=25:d=2"]
    if with_audio:
        args += ["-f", "lavfi", "-i",
                 "sine=frequency=500:sample_rate=48000:duration=2"]
    args += ["-c:v", "mpeg4", "-q:v", "3"]
    if with_audio:
        args += ["-c:a", "aac", "-shortest"]
    ffmpeg(*args, source)
    return probe_video(source), source.read_bytes()


@pytest.mark.skipif(not AVAILABLE, reason="ffmpeg/ffprobe unavailable")
def test_strict_actual_codec_and_video_dimensions_quality_report(tmp_path):
    info, original = make_video(tmp_path)
    rendered = render_request(
        RenderRequest(info,0,1.5,"crop",False,0,(),320,180),
        tmp_path/"rendered.mp4")
    report = read_report(rendered)
    assert report.schema_version == 1 and report.status == "PASS"
    assert report.actual_codec == "h264"
    assert (report.width,report.height) == (320,180)
    assert abs(report.duration-1.5) < .2
    assert report.audio_present and report.audio_codec == "aac"
    assert report.sampled_seconds > 0
    assert report.file_sha256 and len(report.file_sha256) == 64
    assert report.file_bytes == rendered.stat().st_size
    assert report.sample_peak_dbfs is None or report.sample_peak_dbfs <= 1.0
    assert Path(info.path).read_bytes() == original
    assert (tmp_path/"rendered.mp4.qa.json").is_file()
    record = json.loads((tmp_path/"rendered.mp4.qa.json").read_text("utf-8"))
    assert record["sampled_seconds"] <= 16  # Never a full 6-hour scan


@pytest.mark.skipif(not AVAILABLE, reason="ffmpeg/ffprobe unavailable")
def test_codec_and_duration_mismatch_are_hard_errors(tmp_path):
    info, _ = make_video(tmp_path)
    rendered=render_request(
        RenderRequest(info,0,1.3,"crop",False,0,(),320,180),
        tmp_path/"finished.mp4")
    with pytest.raises(ValueError,match="codec"):
        inspect_export(rendered,expected_codec="hevc",width=320,height=180,
                       duration=1.3,audio_expected=True)
    with pytest.raises(ValueError,match="auflösung"):
        inspect_export(rendered,expected_codec="h264",width=180,height=320,
                       duration=1.3,audio_expected=True)
    with pytest.raises(ValueError,match="Dauer"):
        inspect_export(rendered,expected_codec="h264",width=320,height=180,
                       duration=10,audio_expected=True)


@pytest.mark.skipif(not AVAILABLE, reason="ffmpeg/ffprobe unavailable")
def test_failed_qa_never_publishes_mp4_even_with_valid_ffmpeg_encode(
        tmp_path, monkeypatch):
    import streamclipper.export_qa as qa
    info, original=make_video(tmp_path,with_audio=False)
    def reject(*args,**kw):
        raise ValueError("QA: künstlich fehlgeschlagene Frame-Prüfung")
    monkeypatch.setattr(qa,"inspect_export",reject)
    with pytest.raises(ValueError,match="QA:"):
        export_clip(info,0,1.2,tmp_path/"bad.mp4",mode="crop",
                    width=320,height=180)
    assert not (tmp_path/"bad.mp4").exists()
    assert not (tmp_path/"bad.mp4.qa.json").exists()
    assert not list(tmp_path.rglob("*.partial.mp4"))
    assert Path(info.path).read_bytes()==original


@pytest.mark.skipif(not AVAILABLE, reason="ffmpeg/ffprobe unavailable")
def test_qa_sidecar_does_not_modify_mp4_and_rejects_corrupt_report(tmp_path):
    info,_=make_video(tmp_path)
    out=render_request(
        RenderRequest(info,0,1,"crop",False,0,(),320,180),
        tmp_path/"output.mp4")
    before=out.read_bytes()
    qa=read_report(out)
    assert write_report(qa,out).is_file()
    assert out.read_bytes()==before
    report=tmp_path/"output.mp4.qa.json"
    report.write_text('{"schema_version":9,"status":"PASS"}')
    with pytest.raises(ValueError,match="QA-Bericht"):
        read_report(out)


def test_qa_rejects_empty_zero_frame_decode_even_when_ffmpeg_exits_zero(
        tmp_path,monkeypatch):
    import streamclipper.export_qa as qa
    def empty(*args,**kwargs):
        return subprocess.CompletedProcess(args,0,stdout=b"# framemd5 file\\n",
                                           stderr=b"")
    monkeypatch.setattr(qa.subprocess,"run",empty)
    monkeypatch.setattr(qa,"tool_path",lambda name: name)
    with pytest.raises(ValueError,match="Videoframe"):
        qa._decode_frame(tmp_path/"any.mp4",.3)
