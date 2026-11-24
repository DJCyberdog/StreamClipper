"""M12c real FFmpeg failover: no damaged final videos, retries or silent codec shifts."""
from pathlib import Path
import shutil
import subprocess

import pytest

import streamclipper.media as media
from streamclipper.encoders import EncoderPlan
from streamclipper.models import VideoInfo
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.rendered_preview import render_clip_preview


AVAILABLE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def make_source(tmp_path):
    path = tmp_path / "source-original.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(path)],
        check=True, capture_output=True, timeout=45)
    return media.probe_video(path), path.read_bytes()


def fake_nvenc_fails_at_runtime(monkeypatch):
    """Simulate GPU disappearing *after* a successful two-frame probe."""
    original = media.build_export_command
    calls = []
    def fail_video_encode(*args, **kwargs):
        command = original(*args, **kwargs)
        profile = kwargs.get("encoder", "cpu_h264")
        calls.append(profile)
        if profile == "nvenc_h264":
            index = command.index("-c:v")
            command[index+1] = "streamclipper_invalid_test_encoder"
        return command
    monkeypatch.setattr(media, "build_export_command", fail_video_encode)
    return calls


@pytest.mark.skipif(not AVAILABLE, reason="FFmpeg/FFprobe unavailable")
def test_auto_nvenc_failure_retries_once_from_zero_and_publishes_only_cpu(
        tmp_path, monkeypatch):
    info, original = make_source(tmp_path)
    monkeypatch.setattr(media, "resolve_encoder",
                        lambda *a: EncoderPlan("auto_h264","nvenc_h264","cpu_h264"))
    calls = fake_nvenc_fails_at_runtime(monkeypatch)
    notices, progress = [], []
    request = RenderRequest(info, 0, 1.4, "crop", False, 0, (), 320, 180,
                            None, "auto_h264")
    target = tmp_path / "finished.mp4"
    target.write_bytes(b"user-old-result")
    path = render_request(request,target,progress=progress.append,
                          encoder_notice=notices.append)
    assert path != target
    assert target.read_bytes() == b"user-old-result"
    assert calls.count("nvenc_h264") == 1
    assert calls.count("cpu_h264") >= 1  # includes validation passes
    assert "CPU-Encoding wird neu gestartet" in " ".join(notices)
    assert progress[-1] == 100
    assert media.probe_video(path).width == 320
    assert media.probe_video(path).has_audio
    assert not list(tmp_path.rglob("*.partial.mp4"))
    assert Path(info.path).read_bytes() == original


@pytest.mark.skipif(not AVAILABLE, reason="FFmpeg/FFprobe unavailable")
def test_explicit_nvenc_failure_never_silently_uses_cpu(tmp_path,monkeypatch):
    info, original = make_source(tmp_path)
    monkeypatch.setattr(media, "resolve_encoder",
                        lambda *a: EncoderPlan("nvenc_h264","nvenc_h264"))
    calls = fake_nvenc_fails_at_runtime(monkeypatch)
    request = RenderRequest(info,0,1,"crop",False,0,(),320,180,None,"nvenc_h264")
    with pytest.raises(RuntimeError, match="nvenc_h264"):
        render_request(request, tmp_path / "not-finished.mp4")
    assert calls.count("nvenc_h264") == 1
    assert not (tmp_path/"not-finished.mp4").exists()
    assert not list(tmp_path.rglob("*.partial.mp4"))
    assert Path(info.path).read_bytes() == original


@pytest.mark.skipif(not AVAILABLE, reason="FFmpeg/FFprobe unavailable")
def test_cancel_when_gpu_fails_prevents_cpu_retry(tmp_path,monkeypatch):
    info, original = make_source(tmp_path)
    monkeypatch.setattr(media, "resolve_encoder",
                        lambda *a: EncoderPlan("auto_h264","nvenc_h264","cpu_h264"))
    calls = fake_nvenc_fails_at_runtime(monkeypatch)
    state = {"cancel": False}
    def notice(message):
        if "neu gestartet" in message:
            state["cancel"] = True
    request = RenderRequest(info,0,1,"crop",False,0,(),320,180,None,"auto_h264")
    with pytest.raises(media.CancelledError):
        render_request(request, tmp_path / "cancelled.mp4",
                       cancelled=lambda: state["cancel"],
                       encoder_notice=notice)
    assert calls.count("nvenc_h264") == 1
    assert calls.count("cpu_h264") >= 1  # validation only
    assert not (tmp_path/"cancelled.mp4").exists()
    assert not list(tmp_path.rglob("*.partial.mp4"))
    assert Path(info.path).read_bytes() == original


@pytest.mark.skipif(not AVAILABLE, reason="FFmpeg/FFprobe unavailable")
def test_auto_without_gpu_selects_cpu_and_keeps_preview_export_in_sync(
        tmp_path,monkeypatch):
    info, original = make_source(tmp_path)
    monkeypatch.setattr(media, "resolve_encoder",
                        lambda *a: EncoderPlan("auto_h264","cpu_h264",None,True))
    notices=[]
    request=RenderRequest(info,.2,1.5,"crop",False,0,(),320,180,None,"auto_h264")
    exported=render_request(request,tmp_path/"export.mp4",
                            encoder_notice=notices.append)
    preview,holder=render_clip_preview(
        request,temp_root=tmp_path,encoder_notice=notices.append)
    try:
        assert "NVENC-Test fehlgeschlagen" in " ".join(notices)
        assert media.probe_video(exported).width == 320
        assert media.probe_video(preview.path).width == 320
        def framemd5(path):
            res=subprocess.run([
                "ffmpeg","-hide_banner","-loglevel","error",
                "-i",str(path),"-map","0:v:0","-f","framemd5","-"],
                check=True,capture_output=True,text=True,timeout=35)
            return "\n".join(x for x in res.stdout.splitlines()
                             if x and not x.startswith("#"))
        assert framemd5(exported)==framemd5(preview.path)
    finally:
        holder.cleanup()
    assert Path(info.path).read_bytes()==original


@pytest.mark.skipif(not AVAILABLE, reason="FFmpeg/FFprobe unavailable")
def test_real_cpu_hevc_mp4_uses_hevc_codec_and_hvc1_tag(tmp_path):
    """HEVC is not only a command string: verify a decodable output container."""
    availability = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-h",
         "encoder=libx265"], capture_output=True, timeout=20)
    if availability.returncode:
        pytest.skip("This FFmpeg build lacks libx265")
    info, original = make_source(tmp_path)
    request = RenderRequest(
        info, 0, .8, "crop", False, 0, (), 320, 180, None, "cpu_hevc")
    output = render_request(request, tmp_path/"hevc.mp4")
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,codec_tag_string",
        "-of", "json", str(output)], check=True, capture_output=True,
        text=True, timeout=30)
    import json
    stream = json.loads(result.stdout)["streams"][0]
    assert stream["codec_name"] == "hevc"
    assert stream["codec_tag_string"] == "hvc1"
    assert media.probe_video(output).width == 320
    assert Path(info.path).read_bytes() == original
