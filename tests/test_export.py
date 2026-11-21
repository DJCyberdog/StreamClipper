from pathlib import Path
import shutil
import subprocess

import pytest

from streamclipper.media import build_export_command, export_clip, probe_video, safe_destination
from streamclipper.models import VideoInfo


def fake_video():
    return VideoInfo("/tmp/source.mp4", 100, 1920, 1080, 60, True)


def test_export_command_is_safe_and_vertical():
    cmd = build_export_command(fake_video(), 2, 27, "output.mp4", "blur")
    assert "-filter_complex" in cmd
    assert "1080:1920" in " ".join(cmd)
    assert "-n" in cmd
    assert "-map" in cmd
    assert cmd[-1] == "output.mp4"


def test_invalid_parameters():
    with pytest.raises(ValueError):
        build_export_command(fake_video(), -1, 3, "test.mp4")
    with pytest.raises(ValueError):
        build_export_command(fake_video(), 0, 3, "test.mp4", width=601)


def test_export_file_not_overwritten(tmp_path):
    original = tmp_path / "clip.mp4"
    original.write_bytes(b"original")
    assert safe_destination(tmp_path, "clip.mp4").name == "clip_2.mp4"
    assert original.read_bytes() == b"original"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg missing")
def test_integration_media_pipeline(tmp_path):
    source = tmp_path / "sample.mp4"
    # Test fixture is generated locally; no external media or rights concerns.
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=10:d=5",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=5",
        "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", "-shortest", str(source)
    ], check=True, capture_output=True, timeout=40)
    info = probe_video(source)
    assert info.has_audio and info.width == 320
    from streamclipper.analyze import analyze
    result = analyze(str(source), clip_seconds=10, max_clips=1)
    assert result.candidates and result.candidates[0].end <= info.duration
    for mode in ("crop", "blur"):
        output = tmp_path / f"output_{mode}.mp4"
        export_clip(info, 1.0, 2.5, output, mode=mode, width=180, height=320)
        exported_info = probe_video(output)
        assert exported_info.width == 180 and exported_info.height == 320
        assert 1.2 < exported_info.duration < 2.0
