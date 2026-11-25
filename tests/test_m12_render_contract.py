"""M12a render-contract regression: preview and export follow the same FFmpeg path."""
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess

import pytest

from streamclipper.media import CancelledError, probe_video
from streamclipper.models import TranscriptSegment, VideoInfo
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.rendered_preview import render_clip_preview
import streamclipper.render_contract as contract
import streamclipper.rendered_preview as preview


def video():
    return VideoInfo("/not/opened/source.mp4", 21600.0, 1920, 1080, 60, True)


def test_request_validation_and_short_excerpt():
    request = RenderRequest(video(), 300.5, 345.0, "smart16",
                            burn_subtitles=True,
                            transcript=(TranscriptSegment(300, 340, "Test"),))
    cut = request.preview_excerpt()
    assert cut.start == 300.5 and cut.end == 320.5
    assert request.end == 345.0
    assert cut.video == request.video
    assert cut.mode == request.mode and cut.transcript == request.transcript
    for corrupt in [
        replace(request, start=-1),
        replace(request, end=21601),
        replace(request, mode="unknown"),
        replace(request, subtitle_offset=float("nan")),
        replace(request, subtitle_offset=6),
        replace(request, burn_subtitles=True, transcript=()),
        replace(request, width=201),
    ]:
        with pytest.raises(ValueError):
            corrupt.validate()
    with pytest.raises(ValueError):
        request.preview_excerpt(61)


def test_export_and_preview_share_exact_render_request(tmp_path, monkeypatch):
    calls = []
    def fake_export(video, start, end, destination, **kwargs):
        calls.append((video, start, end, kwargs))
        path = Path(destination)
        path.write_bytes(b"rendered")
        return path
    monkeypatch.setattr(contract, "export_clip", fake_export)
    req = RenderRequest(video(), 10, 17, "crop", True, .3,
                        (TranscriptSegment(11, 13, "Wow"),), 180, 320)
    export_path = render_request(req, tmp_path / "regular.mp4")
    result, holder = render_clip_preview(req, temp_root=tmp_path)
    try:
        assert export_path.read_bytes() == b"rendered"
        assert result.path.read_bytes() == b"rendered"
        assert calls[0] == calls[1]
        assert result.request == req
    finally:
        path = result.path
        holder.cleanup()
        assert not path.exists()


def test_cancel_and_failure_leave_no_preview_media(tmp_path, monkeypatch):
    req = RenderRequest(video(), 100, 104, "crop", False, 0, (), 180, 320)
    with pytest.raises(CancelledError):
        render_clip_preview(req, temp_root=tmp_path, cancelled=lambda: True)
    assert not list(tmp_path.glob("m12-render-preview-*"))
    def error(*args, **kwargs):
        Path(args[1]).write_bytes(b"partial")
        raise RuntimeError("encoder failed")
    monkeypatch.setattr(preview, "render_request", error)
    with pytest.raises(RuntimeError):
        render_clip_preview(req, temp_root=tmp_path)
    assert not list(tmp_path.glob("m12-render-preview-*"))


def _video_framemd5(path):
    proc = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-map", "0:v:0", "-f", "framemd5", "-"],
        check=True, capture_output=True, text=True, timeout=50)
    return "\n".join(line for line in proc.stdout.splitlines()
                     if line and not line.startswith("#"))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="Real FFmpeg/FFprobe unavailable")
def test_real_preview_vs_export_decoded_frames_with_burned_captions(tmp_path):
    source = tmp_path / "recorded stream.mkv"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=430:duration=4",
        "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", "-shortest", str(source)],
        check=True, capture_output=True, timeout=45)
    info = probe_video(source)
    req = RenderRequest(
        info, .5, 2.7, "crop", True, 0,
        (TranscriptSegment(.6, 2.2, "Test Untertitel"),), 180, 320)
    output = render_request(req, tmp_path / "export.mp4")
    rendered, owner = render_clip_preview(req, temp_root=tmp_path)
    try:
        assert rendered.request == req
        assert rendered.path.is_file()
        info1 = probe_video(output)
        info2 = probe_video(rendered.path)
        assert (info1.width, info1.height) == (180, 320)
        assert (info2.width, info2.height) == (180, 320)
        assert abs(info1.duration - info2.duration) < .02
        assert _video_framemd5(output) == _video_framemd5(rendered.path)
    finally:
        owner.cleanup()
