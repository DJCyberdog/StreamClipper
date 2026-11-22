"""SC-P0-01: real FFmpeg tests use synthetic fixtures, not private VODs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import threading

import pytest

from streamclipper.media import (CancelledError, _progress_seconds,
                                 export_clip, probe_video)


@pytest.fixture
def fixture_video(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and FFprobe required")
    source = tmp_path / "Aufnahme mit Ümlaut ö.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc2=s=160x90:r=15:d=4",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:v", "mpeg4", "-q:v", "6", "-c:a", "aac", "-shortest", str(source)],
        check=True, capture_output=True, timeout=40,
    )
    return source, probe_video(source)


def test_parse_progress_microseconds_and_time():
    assert _progress_seconds("out_time_us", "1200000") == 1.2
    assert _progress_seconds("out_time_ms", "1200000") == 1.2
    assert _progress_seconds("out_time", "00:01:01.500000") == 61.5
    assert _progress_seconds("out_time", "N/A") is None
    assert _progress_seconds("progress", "end") is None


def test_export_unicode_progress_and_atomic_publish(fixture_video, tmp_path):
    source, info = fixture_video
    before = source.read_bytes()
    progress = []
    dest = tmp_path / "Mein Clip 💚.mp4"
    final = export_clip(info, 0.2, 1.6, dest, mode="crop", width=180,
                        height=320, progress=progress.append)
    assert final == dest
    assert progress and progress[-1] == 100
    assert all(0 <= p <= 100 for p in progress)
    assert progress == sorted(progress)
    assert source.read_bytes() == before
    assert probe_video(final).height == 320
    assert not list(tmp_path.rglob("*.partial.mp4"))


def test_existing_destination_and_input_preserved(fixture_video, tmp_path):
    source, info = fixture_video
    target = tmp_path / "locked.mp4"
    target.write_bytes(b"already present, must never be overwritten")
    before = target.read_bytes()
    result = export_clip(info, 0.3, 1.5, target, width=180, height=320)
    assert result == tmp_path / "locked_2.mp4"
    assert target.read_bytes() == before
    assert result.stat().st_size > 0
    assert not list(tmp_path.rglob("*.partial.mp4"))
    original = source.read_bytes()
    renamed = export_clip(info, 0.3, 1.3, source, width=180, height=320)
    assert renamed != source
    assert source.read_bytes() == original


def test_cancel_mid_encode_and_cleanup(fixture_video, tmp_path):
    _, info = fixture_video
    requested = tmp_path / "cancelled.mp4"
    abort = threading.Event()
    callbacks = []

    def on_progress(value):
        callbacks.append(value)
        abort.set()

    with pytest.raises(CancelledError, match="abgebrochen"):
        export_clip(info, 0.2, 3.6, requested, width=180, height=320,
                    cancelled=abort.is_set, progress=on_progress)
    assert callbacks, "ffmpeg did not report progress before exit"
    assert not requested.exists()
    assert not list(tmp_path.rglob("*.partial.mp4"))


def test_cancel_before_ffmpeg_launch(fixture_video, tmp_path):
    _, info = fixture_video
    destination = tmp_path / "cancel_immediately.mp4"
    with pytest.raises(CancelledError):
        export_clip(info, 0.0, 2.0, destination, cancelled=lambda: True)
    assert not destination.exists()


def test_ffmpeg_error_does_not_publish_or_touch_source(fixture_video, tmp_path):
    _, info = fixture_video
    invalid = tmp_path / "invalid.mp4"
    invalid.write_bytes(b"not actually a video")
    from dataclasses import replace
    damaged_info = replace(info, path=str(invalid))
    output = tmp_path / "result.mp4"
    with pytest.raises(RuntimeError, match="FFmpeg-Export fehlgeschlagen"):
        export_clip(damaged_info, 0.1, 1.1, output, width=180, height=320)
    assert invalid.read_bytes() == b"not actually a video"
    assert not output.exists()
    assert not list(tmp_path.rglob("*.partial.mp4"))


def test_two_simultaneous_exports_cannot_clobber(fixture_video, tmp_path):
    _, info = fixture_video
    target = tmp_path / "parallel.mp4"

    def run_export(_):
        return export_clip(info, 0.2, 1.4, target, width=180, height=320)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(run_export, range(2)))
    assert set(outputs) == {target, tmp_path / "parallel_2.mp4"}
    for path in outputs:
        assert path.is_file() and probe_video(path).height == 320
    assert not list(tmp_path.rglob("*.partial.mp4"))
