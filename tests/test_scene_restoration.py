"""M13d/e experimental render contract. Mock restoration is not GPU evidence."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from PIL import Image

from streamclipper.models import VideoInfo
from streamclipper.media import probe_video
from streamclipper.scene_selection import initial_selection
from streamclipper.smart_director import Director,OverlayZone
from streamclipper.render_contract import RenderRequest,render_request
from streamclipper import scene_restoration as sr
from streamclipper.render_queue import _snapshot,_rehydrate


def test_window_limit_and_model_opt_in(tmp_path):
    video=VideoInfo("test.mp4",30,1920,1080,30,False)
    assert sr.frame_count(video,0,1)==30
    assert sr.frame_count(video,0,20)==600
    with pytest.raises(ValueError,match="600"):
        sr.frame_count(video,0,21)
    with pytest.raises(ValueError,match="Opt-in"):
        Director(inpaint_model=str(tmp_path)).validate()


def test_timed_masks():
    video=VideoInfo("test.mp4",1,160,128,10,False)
    zones=(OverlayZone("alert",(0,0,.5,.5),.2,.5,mask=True),)
    masks=sr.frame_masks(video,0,9,zones)
    assert [bool(m.getbbox()) for m in masks]==[False,False,True,True,True,False,False,False,False]
    assert masks[2].getpixel((79,63))==255
    assert masks[2].getpixel((80,64))==0


def run(*args):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg fehlt")
    return subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",*map(str,args)],
                          check=True,capture_output=True,timeout=90).stdout


def rgb(path,at,x,y):
    result=run("-ss",at,"-i",path,"-frames:v",1,"-pix_fmt","rgb24","-f","rawvideo","pipe:1")
    offset=(y*160+x)*3
    return tuple(result[offset:offset+3])


def test_mock_model_real_mp4_audio_and_preview(tmp_path,monkeypatch):
    source=tmp_path/"source.mp4"
    run("-f","lavfi","-i","color=red:s=160x128:r=10:d=2",
        "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2",
        "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",source)
    video=probe_video(source)
    model=tmp_path/"model";model.mkdir()
    (model/"model_index.json").write_text(json.dumps({"_class_name":"WanVACEPipeline"}))
    director=Director(zones=(OverlayZone("hud",(0,0,.5,1),mask=True),),
                      removal_enabled=True,inpaint_model=str(model))
    plan=initial_selection(0,2).edit(0,mode="fixed",director=director)
    request=RenderRequest(video,0,2,"crop",width=160,height=128,scene_plan=plan)
    assert _rehydrate(json.loads(json.dumps(_snapshot(request))))==request
    actual=sr.restore_scene_video
    calls=[]
    def fake(frames,masks,model_directory,**kwargs):
        calls.append((len(frames),model_directory))
        return [Image.new("RGB",f.size,(0,0,255)) for f in frames]
    def wrapped(*args,**kwargs):
        return actual(*args,**kwargs,restore=fake)
    monkeypatch.setattr(sr,"restore_scene_video",wrapped)
    full=render_request(request,tmp_path/"full.mp4")
    short=render_request(request.preview_excerpt(1),tmp_path/"short.mp4")
    assert calls==[(33,str(model)),(33,str(model))]
    assert probe_video(full).has_audio and probe_video(short).has_audio
    for path in (full,short):
        left=rgb(path,.5,20,64);right=rgb(path,.5,140,64)
        assert left[2]>150 and left[0]<80
        assert right[0]>150 and right[2]<80
    assert source.exists()
    assert not list(tmp_path.glob(".*/restored.mkv"))


def test_crop_excludes_zone_without_model(tmp_path):
    video=VideoInfo("test.mp4",10,1920,1080,30,False)
    director=Director(zones=(OverlayZone("chat",(.8,0,.2,1),mask=True),),
                      avoid_overlays=True,removal_enabled=True,
                      inpaint_model=str(tmp_path/"missing"))
    plan=initial_selection(0,10).edit(0,director=director)
    request=RenderRequest(video,0,10,"crop",scene_plan=plan)
    assert request.validate() is request


@pytest.mark.parametrize("count", [1,9,17,33,34,58,59,100,600])
def test_window_coverage(count):
    ranges=list(sr.window_ranges(count))
    assert ranges[0][0]==0 and ranges[-1][1]==count
    assert all(1<=b-a<=33 for a,b in ranges)
    assert all(b-c==8 for (a,b),(c,d) in zip(ranges,ranges[1:]))


def test_multiwindow_seam_and_original_pixels(tmp_path):
    source=tmp_path/"source.mp4"
    run("-f","lavfi","-i","color=red:s=160x128:r=10:d=7",
        "-c:v","libx264","-pix_fmt","yuv420p",source)
    video=probe_video(source)
    director=Director(zones=(OverlayZone("hud",(0,0,.5,1),mask=True),),
                      removal_enabled=True,inpaint_model=str(tmp_path/"model"))
    calls=[]
    def fake(frames,masks,path,**kwargs):
        calls.append(len(frames))
        color=(0,0,255) if len(calls)%2 else (0,255,0)
        return [Image.new("RGB",f.size,color) for f in frames]
    target=tmp_path/"restored.mkv"
    sr.restore_scene_video(video,0,7,director,target,restore=fake)
    assert calls==[33,33,33]
    before=run("-i",source,"-vf","fps=10,format=rgb24","-f","rawvideo","pipe:1")
    after=run("-i",target,"-pix_fmt","rgb24","-f","rawvideo","pipe:1")
    stride=160*128*3
    assert len(after)==len(before)==70*stride
    for i in range(70):
        for y in range(128):
            a=i*stride+y*160*3+80*3
            b=a+80*3
            assert after[a:b]==before[a:b]
    def pixel(i):
        return tuple(after[i*stride:i*stride+3])
    assert pixel(24)==(0,0,255)
    assert 0<pixel(25)[1]<pixel(32)[1]<255
    assert pixel(33)==(0,255,0)
    assert not list(tmp_path.glob(".restore-*"))
    original=target.read_bytes()
    with pytest.raises(FileExistsError):
        sr.restore_scene_video(video,0,7,director,target,restore=fake)
    assert target.read_bytes()==original


def test_multiwindow_cancel_removes_temp_files(tmp_path):
    source=tmp_path/"source.mp4"
    run("-f","lavfi","-i","color=red:s=160x128:r=10:d=4",
        "-c:v","libx264","-pix_fmt","yuv420p",source)
    video=probe_video(source)
    director=Director(zones=(OverlayZone("hud",(0,0,.5,1),mask=True),),
                      removal_enabled=True,inpaint_model=str(tmp_path/"model"))
    stopped=False
    def fake(frames,masks,path,**kwargs):
        nonlocal stopped
        stopped=True
        return frames
    from streamclipper.media import CancelledError
    target=tmp_path/"restored.mkv"
    with pytest.raises(CancelledError):
        sr.restore_scene_video(video,0,4,director,target,restore=fake,cancelled=lambda:stopped)
    assert not target.exists()
    assert not list(tmp_path.glob(".restore-*"))
