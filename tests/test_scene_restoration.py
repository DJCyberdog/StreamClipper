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
    video=VideoInfo("test.mp4",10,1920,1080,30,False)
    assert sr.frame_count(video,0,1)==30
    with pytest.raises(ValueError,match="33"):
        sr.frame_count(video,0,2)
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
