"""M13a end-to-end scene selection regression tests."""
from dataclasses import asdict
import json
import shutil
import subprocess

import pytest

from streamclipper.editor_project import (
    initial_project, set_scene_plan, scene_plan_for, save_project, load_project)
from streamclipper.edit_history import WorkspaceHistory
from streamclipper.models import VideoInfo
from streamclipper.project_checkpoints import create_checkpoint, load_checkpoint
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.render_queue import _snapshot, _rehydrate
from streamclipper.scene_selection import initial_selection
from streamclipper.media import probe_video
from streamclipper.export_qa import read_report


def test_project_undo_checkpoint_and_queue_roundtrip(tmp_path):
    video = VideoInfo(str(tmp_path / "source.mp4"), 12, 640, 360, 30, True)
    before = initial_project(video)
    plan = initial_selection(0, 12).split(0, 4).move(0, 1).edit(1, included=False)
    after = set_scene_plan(before, plan)
    save_project(after, root=tmp_path)
    assert load_project(video, root=tmp_path) == after
    checkpoint = create_checkpoint(after, "Szenen", root=tmp_path)
    assert load_checkpoint(video, checkpoint.id, root=tmp_path)[0] == after
    history = WorkspaceHistory()
    history.record_project(before, after)
    assert history.undo(None, after)[1] == before
    assert history.redo(None, before)[1] == after
    assert scene_plan_for(after, 0, 12) == plan
    request = RenderRequest(video, 0, 12, "crop", project=after, scene_plan=plan)
    assert _rehydrate(json.loads(json.dumps(_snapshot(request)))) == request
    excerpt = request.preview_excerpt(3)
    assert excerpt.duration == 3
    assert excerpt.scene_plan.output_scenes[0].start == 4
    assert excerpt.scene_plan.output_scenes[0].end == 7


def test_all_excluded_fails_closed(tmp_path):
    video = VideoInfo(str(tmp_path / "source.mp4"), 12, 640, 360, 30, False)
    plan = initial_selection(0, 12).edit(0, included=False)
    with pytest.raises(ValueError, match="Keine eingeschlossene"):
        RenderRequest(video, 0, 12, "crop", scene_plan=plan).validate()


def _ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe fehlen")
    return shutil.which("ffmpeg")


def _run(*args):
    return subprocess.run([_ffmpeg(), "-hide_banner", "-nostdin", "-loglevel", "error", *map(str,args)],
                          check=True, capture_output=True, timeout=90).stdout


def _rgb(path, at):
    data = _run("-ss", at, "-i", path, "-frames:v", 1, "-vf", "scale=1:1",
                "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1")
    return tuple(data[:3])


def test_real_mp4_reorder_exclusion_and_audio(tmp_path):
    src = tmp_path / "source.mp4"
    _run("-f", "lavfi", "-i", "color=red:s=160x120:r=25:d=1.5",
         "-f", "lavfi", "-i", "color=green:s=160x120:r=25:d=1.5",
         "-f", "lavfi", "-i", "color=blue:s=160x120:r=25:d=1.5",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4.5",
         "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
         "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", src)
    video = probe_video(src)
    plan = initial_selection(0, 4.5).split(0, 1.5).split(1, 3)
    plan = plan.edit(1, included=False).move(2, -1).move(1, -1)
    plan = plan.edit(0, mode="fixed").edit(2, mode="fixed")
    # Blue then red, green excluded. Avoid boundary sampling.
    out = render_request(RenderRequest(video, 0, 4.5, "crop", width=160, height=120,
                                       scene_plan=plan), tmp_path / "out.mp4")
    first = _rgb(out, .5)
    second = _rgb(out, 2.0)
    assert first[2] > 150 and first[0] < 80
    assert second[0] > 150 and second[2] < 80
    assert probe_video(out).has_audio
    assert abs(probe_video(out).duration - 3) < .2
    assert read_report(out)


def test_real_manual_region(tmp_path):
    src = tmp_path / "split.mp4"
    _run("-f", "lavfi", "-i", "color=red:s=80x120:r=25:d=2",
         "-f", "lavfi", "-i", "color=blue:s=80x120:r=25:d=2",
         "-filter_complex", "[0:v][1:v]hstack[v]", "-map", "[v]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", src)
    video = probe_video(src)
    plan = initial_selection(0, 2).edit(0, mode="manual", region=(.5,0,.5,1))
    out = render_request(RenderRequest(video, 0, 2, "crop", width=80, height=120,
                                       scene_plan=plan), tmp_path / "out.mp4")
    rgb = _rgb(out, .5)
    assert rgb[2] > 150 and rgb[0] < 80
