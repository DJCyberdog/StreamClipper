"""M12b real FFmpeg audio mix, source/timeline placement, preview parity."""
from array import array
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from streamclipper.editor_project import add_item, initial_project
from streamclipper.media import CancelledError, probe_video
from streamclipper.models import VideoInfo
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.rendered_preview import render_clip_preview
from streamclipper.render_graph import build_render_graph
from streamclipper.media import build_export_command


def ffmpeg(*args):
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str,args)],
        check=True, capture_output=True, timeout=50)


def pcm(path: Path) -> array:
    output = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-vn", "-ac", "1", "-ar", "8000",
        "-c:a", "pcm_s16le", "-f", "s16le", "-"],
        check=True, capture_output=True, timeout=45).stdout
    samples = array("h")
    samples.frombytes(output)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def signal_strength(samples: array, frequency: int, second: float, span: float=.4) -> float:
    sr = 8000
    start = int(second*sr)
    length = int(span*sr)
    region = samples[start:start+length]
    assert len(region) == length
    # Signed-sine projection, normalized for easy threshold testing
    sine = sum(x*math.sin(2*math.pi*frequency*i/sr)
               for i,x in enumerate(region))
    cosine = sum(x*math.cos(2*math.pi*frequency*i/sr)
                 for i,x in enumerate(region))
    return math.hypot(sine,cosine) * 2 / length


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg/FFprobe unavailable")
def test_real_overlay_audio_and_export_preview_pcm_identical(tmp_path):
    video_path = tmp_path / "game source.mp4"
    layer_path = tmp_path / "music 880 Hz.wav"
    ffmpeg("-f","lavfi","-i","testsrc2=s=320x180:r=10:d=4",
           "-f","lavfi","-i","sine=frequency=440:sample_rate=8000:duration=4",
           "-c:v","mpeg4","-q:v","5","-c:a","aac","-shortest",video_path)
    ffmpeg("-f","lavfi","-i","sine=frequency=880:sample_rate=8000:duration=1",
           "-c:a","pcm_s16le",layer_path)
    video = probe_video(video_path)
    project = add_item(initial_project(video), "music", 0, 1, 1,
                       "Music", media_path=str(layer_path), gain_db=-3)
    request = RenderRequest(
        video, 0, 3, "crop", False, 0, (), 180, 320, project)
    graph = build_render_graph(project, video, 0, 3)
    assert len(graph.audio_layers) == 1
    command = build_export_command(
        video, 0, 3, tmp_path/"not-executed.mp4", mode="crop",
        width=180, height=320, audio_layers=graph.audio_layers)
    assert command.count("-i") == 2
    assert str(layer_path) in command
    assert str(layer_path) not in command[command.index("-filter_complex")+1]
    export_file = render_request(request, tmp_path / "export.mp4")
    result, owner = render_clip_preview(request, temp_root=tmp_path)
    try:
        assert probe_video(export_file).has_audio
        assert probe_video(result.path).has_audio
        a, b = pcm(export_file), pcm(result.path)
        assert a == b
        assert signal_strength(a,880,.2) < 500
        assert signal_strength(a,880,1.25) > 1000
        assert signal_strength(a,880,2.3) < 500
        assert signal_strength(a,440,.2) > 1000
        assert video_path.stat().st_size > 0 and layer_path.stat().st_size > 0
    finally:
        owner.cleanup()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg/FFprobe unavailable")
def test_missing_external_audio_fails_before_export_with_no_partial(tmp_path):
    vid = tmp_path / "source.mp4"
    ffmpeg("-f","lavfi","-i","color=c=red:s=320x180:r=10:d=2",
           "-f","lavfi","-i","sine=frequency=440:duration=2",
           "-c:v","mpeg4","-c:a","aac","-shortest",vid)
    info = probe_video(vid)
    absent = tmp_path / "not-here.wav"
    p = add_item(initial_project(info), "music",0,1,.2,
                 media_path=str(absent))
    req = RenderRequest(info,0,1.5,"crop",False,0,(),180,320,p)
    with pytest.raises((FileNotFoundError, OSError)):
        render_request(req,tmp_path/"should-not-appear.mp4")
    assert not list(tmp_path.glob("*.partial.mp4"))
    assert not (tmp_path/"should-not-appear.mp4").exists()
    with pytest.raises(CancelledError):
        render_request(req,tmp_path/"cancelled.mp4",cancelled=lambda:True)
    assert not (tmp_path/"cancelled.mp4").exists()
