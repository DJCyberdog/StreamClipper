"""Real short VFR FFmpeg smoke; separate from synthetic 6h metadata tests."""
from __future__ import annotations
import json
import shutil
import subprocess

import pytest

from streamclipper.media import probe_video
from streamclipper.proxy import ensure_proxy, original_to_proxy_ms, proxy_to_original_ms


def _frame_times(path):
    output = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "frame=best_effort_timestamp_time",
        "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30)
    frames = json.loads(output.stdout)["frames"]
    return [float(frame["best_effort_timestamp_time"])
            for frame in frames if "best_effort_timestamp_time" in frame]


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg is optional on the desktop build runner")
def test_preview_preserves_real_vfr_frame_spacing(tmp_path):
    source = tmp_path / "variable-rate.mkv"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=duration=3:size=320x180:rate=25",
        "-vf", r"select=not(eq(mod(n\,6)\,2))",
        "-fps_mode", "vfr", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-an", str(source)],
        check=True, capture_output=True, timeout=30)
    info = probe_video(source)
    state = ensure_proxy(info, root=tmp_path / "proxies")
    assert state.media_path.is_file()
    assert source.is_file()
    assert state.timing.original_duration == info.duration
    a = _frame_times(source)
    b = _frame_times(state.media_path)
    assert len(a) > 20
    assert len(b) == len(a)
    # A VFR pause must not be collapsed by treating frames as 1/30s.
    for x, y in zip(a, b):
        assert abs((x - a[0]) - (y - b[0])) < .08
    assert any(a[i + 1] - a[i] > .06 for i in range(len(a) - 1))
    for ms in (120, 1333, 2570):
        offset = original_to_proxy_ms(ms, state.timing)
        returned = proxy_to_original_ms(offset, state.timing)
        assert abs(ms - returned) <= 150
