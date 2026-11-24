"""M12b2 integration: real frame-level PiP/logo composition and preview parity."""
import binascii
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zlib

import pytest

from streamclipper.editor_project import add_item, add_track, initial_project
from streamclipper.media import CancelledError, build_export_command, probe_video
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.rendered_preview import render_clip_preview
from streamclipper.render_graph import build_render_graph


FFMPEG_AVAILABLE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ffmpeg(*args):
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         *map(str, args)],
        check=True, capture_output=True, timeout=60)


def write_png(path: Path, color=(0, 0, 255), width=100, height=60):
    """One genuine PNG without any Pillow dependency in Windows/Linux CI."""
    def chunk(code, value):
        return (struct.pack(">I", len(value)) + code + value
                + struct.pack(">I", binascii.crc32(code+value)&0xffffffff))
    pixels = b"".join(b"\\x00" + bytes((*color, 255)) * width
                      for _ in range(height))
    path.write_bytes(
        b"\\x89PNG\\r\\n\\x1a\\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB",
                width,height,8,6,0,0,0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b""))


def pixel_at(path: Path, t: float, x: int, y: int,
             width: int=320, height: int=180):
    raw = subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(t), "-i", str(path), "-frames:v", "1",
        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
        capture_output=True, check=True, timeout=45).stdout
    assert len(raw) == width*height*3
    start = (y*width+x)*3
    return tuple(raw[start:start+3])


def decode_audio(path: Path) -> bytes:
    return subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-vn", "-ac", "1", "-ar", "8000",
        "-f", "s16le", "-acodec", "pcm_s16le", "-"],
        capture_output=True, check=True, timeout=45).stdout


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/FFprobe unavailable")
def test_actual_pip_logo_audio_same_pixel_audio_in_preview_and_mp4(tmp_path):
    base = tmp_path / "OBS original.mp4"
    camera = tmp_path / "second camera.mp4"
    logo = tmp_path / "logo blue.png"
    sound = tmp_path / "mic.wav"
    ffmpeg("-f","lavfi","-i","color=c=red:s=320x180:r=30:d=4",
           "-f","lavfi","-i","sine=frequency=440:duration=4",
           "-c:v","mpeg4","-q:v","3","-c:a","aac","-shortest",base)
    ffmpeg("-f","lavfi","-i","color=c=green:s=160x90:r=30:d=3",
           "-c:v","mpeg4","-q:v","3",camera)
    ffmpeg("-f","lavfi","-i","sine=frequency=880:duration=1",
           "-c:a","pcm_s16le",sound)
    write_png(logo)
    info = probe_video(base)
    project = initial_project(info)
    project = add_item(project, "graphics", 0, 1, 2, "Logo",
                       media_path=str(logo),
                       x=.5, y=.1, width=.25, height=.25, opacity=.8)
    project = add_track(project, "video", "Facecam")
    project = add_item(project, project.tracks[-1].id,
                       .4, 1.4, 1, "PiP", media_path=str(camera),
                       x=.1, y=.1, width=.25, height=.25)
    project = add_item(project, "mic", 0, 1, 1, "Sound",
                       media_path=str(sound), gain_db=-6)
    graph = build_render_graph(project, info, 0, 4)
    assert [x.kind for x in graph.visual_layers] == ["overlay", "video"]
    assert len(graph.audio_layers) == 1
    args = build_export_command(
        info,0,4,tmp_path/"not-written.mp4",
        mode="crop",width=320,height=180,
        audio_layers=graph.audio_layers,visual_layers=graph.visual_layers)
    assert args.count("-i") == 4  # source, logo, PiP, mic
    filtergraph = args[args.index("-filter_complex")+1]
    assert str(base) not in filtergraph
    assert str(camera) not in filtergraph
    assert str(logo) not in filtergraph
    request = RenderRequest(info, 0, 4, "crop", False, 0, (),
                            320,180,project)
    output = render_request(request,tmp_path/"final.mp4")
    preview, owner = render_clip_preview(request,temp_root=tmp_path)
    try:
        assert probe_video(output).has_audio
        assert probe_video(preview.path).has_audio
        # Confirm that pixels are *actually composited* only within windows.
        for t in (.3,1.5,2.5,3.5):
            for pos in ((60,40),(200,40),(300,140)):
                assert pixel_at(output,t,*pos) == pixel_at(preview.path,t,*pos)
        before = pixel_at(output,.3,60,40)
        during = pixel_at(output,1.5,60,40)
        after = pixel_at(output,2.5,60,40)
        assert before[0] > 180 and before[1] < 80
        assert during[1] > 70 and during[0] < 80
        assert after[0] > 180 and after[1] < 80
        logo_before = pixel_at(output,1.5,200,40)
        logo_during = pixel_at(output,2.5,200,40)
        logo_after = pixel_at(output,3.5,200,40)
        assert logo_before[0] > 180 and logo_before[2] < 80
        assert logo_during[2] > 140 and logo_during[0] < 120
        assert logo_after[0] > 180 and logo_after[2] < 80
        assert decode_audio(output) == decode_audio(preview.path)
        assert all(x.stat().st_size > 0 for x in (base,camera,sound,logo))
    finally:
        owner.cleanup()


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/FFprobe unavailable")
def test_clipped_visual_excerpt_and_missing_assets_no_output(tmp_path):
    base = tmp_path / "base.mp4"
    camera = tmp_path / "facecam.mp4"
    logo = tmp_path / "logo.png"
    ffmpeg("-f","lavfi","-i","color=c=red:s=320x180:r=25:d=4",
           "-c:v","mpeg4",base)
    ffmpeg("-f","lavfi","-i","color=c=green:s=160x90:r=25:d=3",
           "-c:v","mpeg4",camera)
    write_png(logo)
    video = probe_video(base)
    project = add_track(initial_project(video), "video", "Facecam")
    project = add_item(project, project.tracks[-1].id, 0, 3, .5,
                       media_path=str(camera),x=.1,y=.1,width=.3,height=.3)
    req = RenderRequest(video,1,2,"crop",False,0,(),320,180,project)
    graph = build_render_graph(project, video,1,2)
    assert len(graph.visual_layers) == 1
    layer = graph.visual_layers[0]
    assert (layer.source_start,layer.source_end,layer.timeline_offset) == (.5,1.5,0)
    export = render_request(req,tmp_path/"valid.mp4")
    green = pixel_at(export,.4,60,40)
    assert green[1] > 70 and green[0] < 80
    camera.unlink()
    with pytest.raises(FileNotFoundError):
        render_request(req,tmp_path/"missing.mp4")
    assert not (tmp_path/"missing.mp4").exists()
    assert not list(tmp_path.glob("*.partial.mp4"))
    with pytest.raises(CancelledError):
        render_request(req,tmp_path/"cancel.mp4",cancelled=lambda:True)
    assert not (tmp_path/"cancel.mp4").exists()
    bad_image = add_item(initial_project(video), "graphics", 0, 1, 1,
                         media_path=str(tmp_path/"absent.png"))
    with pytest.raises(FileNotFoundError):
        render_request(RenderRequest(
            video,0,2,"crop",False,0,(),320,180,bad_image),
            tmp_path/"missing-logo.mp4")
    assert not (tmp_path/"missing-logo.mp4").exists()
