"""M13b-e regression gates; synthetic source, no model or network required."""
from dataclasses import asdict, replace
import json
import shutil
import subprocess

import pytest

from streamclipper.models import VideoInfo
from streamclipper.scene_camera import CameraKeyframe as K
from streamclipper.scene_selection import initial_selection, selection_from_dict
from streamclipper.smart_director import Director, OverlayZone, safe_crop, overlap, crop_for_scene
from streamclipper.director_analysis import W,H,follow_patch,edge_candidates
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.render_queue import _snapshot, _rehydrate
from streamclipper.media import probe_video
from streamclipper.captioning import render_ass


def test_camera_priority_and_queue_roundtrip():
    video=VideoInfo("source.mp4",10,1920,1080,30,False)
    manual=(K(0,.2,.5,1),K(10,.8,.5,1.4))
    d=Director(manual=manual,tracked=(K(2,.9,.9),),
               zones=(OverlayZone("alert",(.1,.1,.2,.2),3,4,mask=True),),
               removal_enabled=True,caption_safe="top")
    plan=initial_selection(0,10).edit(0,director=d)
    assert plan.scenes[0].director.keys==manual
    assert selection_from_dict(json.loads(json.dumps(asdict(plan))))==plan
    request=RenderRequest(video,0,10,"crop",scene_plan=plan)
    assert _rehydrate(json.loads(json.dumps(_snapshot(request))))==request
    excerpt=request.preview_excerpt(4)
    assert excerpt.scene_plan.scenes[0].director==d
    assert excerpt.scene_plan.scenes[0].framing_end==10


def test_crop_geometry_and_protected_subject():
    zones=((0,0,1,.1),(.8,.1,.2,.9))
    crop=safe_crop(zones,1920,1080,1080,1920,protected=(.4,.4,.1,.1))
    assert crop and all(overlap(crop,z)<1e-9 for z in zones)
    assert (crop[2]*1920)/(crop[3]*1080)==pytest.approx(1080/1920)
    assert safe_crop(((0,0,1,1),),1920,1080,1080,1920) is None


def test_dynamic_zone_same_crop_in_excerpt():
    video=VideoInfo("source.mp4",10,1920,1080,30,False)
    d=Director(zones=(OverlayZone("alert",(.7,0,.3,1),8,9),),avoid_overlays=True)
    plan=initial_selection(0,10).edit(0,director=d)
    request=RenderRequest(video,0,10,"crop",scene_plan=plan)
    short=request.preview_excerpt(2)
    assert crop_for_scene(plan.scenes[0],video,1080,1920)==crop_for_scene(short.scene_plan.scenes[0],video,1080,1920)


def test_manual_conflict_does_not_override():
    video=VideoInfo("source.mp4",10,1920,1080,30,False)
    d=Director(zones=(OverlayZone("hud",(0,0,.2,1)),),avoid_overlays=True)
    scene=initial_selection(0,10).edit(0,mode="manual",region=(0,0,.4,1),director=d).scenes[0]
    with pytest.raises(ValueError,match="Konflikt"):
        crop_for_scene(scene,video,1080,1920)


def test_sparse_tracking_stops_on_ambiguous_frame():
    def frame(x,y):
        data=bytearray(W*H)
        for dy in range(-3,4):
            for dx in range(-3,4):
                data[(y+dy)*W+x+dx]=60+((dx*53+dy*71)%180)
        return bytes(data)
    frames=[(0.,frame(20,20)),(.5,frame(24,21)),(1.,bytes(W*H))]
    keys=follow_patch(frames,20/(W-1),20/(H-1))
    assert len(keys)==2
    assert keys[-1].x>keys[0].x


def test_edge_proposals_and_caption_safe_position():
    frame=bytes(255*((i%W)%2) for i in range(W*H))
    assert edge_candidates([(0,frame),(1,frame),(2,frame)])
    assert ",1,3,1,8," in render_ass([],0,1,safe_position="top")


def run(*args):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe fehlen")
    return subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",*map(str,args)],
        check=True,capture_output=True,timeout=90).stdout


def rgb(path,at):
    return tuple(run("-ss",at,"-i",path,"-frames:v",1,"-vf","scale=1:1",
                     "-pix_fmt","rgb24","-f","rawvideo","pipe:1")[:3])


def test_real_keyframes_and_preview_parity(tmp_path):
    source=tmp_path/"source.mp4"
    run("-f","lavfi","-i","color=red:s=80x120:r=25:d=3",
        "-f","lavfi","-i","color=blue:s=80x120:r=25:d=3",
        "-filter_complex","[0:v][1:v]hstack[v]","-map","[v]",
        "-c:v","libx264","-pix_fmt","yuv420p",source)
    video=probe_video(source)
    d=Director(manual=(K(0,.25,.5,1),K(2,.75,.5,1.4)))
    plan=initial_selection(0,3).edit(0,director=d)
    request=RenderRequest(video,0,3,"crop",width=80,height=120,scene_plan=plan)
    full=render_request(request,tmp_path/"full.mp4")
    preview=render_request(request.preview_excerpt(2.5),tmp_path/"preview.mp4")
    first=rgb(full,.1);last=rgb(full,2.2)
    assert first[0]>150 and first[2]<80
    assert last[2]>150 and last[0]<80
    for at in (.1,.8,1.6,2.2):
        assert max(abs(a-b) for a,b in zip(rgb(full,at),rgb(preview,at)))<=15


def test_real_opt_in_timed_mask(tmp_path):
    source=tmp_path/"source.mp4"
    run("-f","lavfi","-i","color=red:s=160x120:r=25:d=3",
        "-c:v","libx264","-pix_fmt","yuv420p",source)
    video=probe_video(source)
    zone=OverlayZone("alert",(0,0,1,1),.5,1.5,mask=True)
    d=Director(zones=(zone,),removal_enabled=True)
    plan=initial_selection(0,3).edit(0,mode="fixed",director=d)
    request=RenderRequest(video,0,3,"crop",width=160,height=120,scene_plan=plan)
    out=render_request(request,tmp_path/"masked.mp4")
    assert max(rgb(out,1))<30
    assert rgb(out,2)[0]>150
    off=replace(plan,scenes=(replace(plan.scenes[0],director=replace(d,removal_enabled=False)),))
    unmasked=render_request(replace(request,scene_plan=off),tmp_path/"unmasked.mp4")
    assert rgb(unmasked,1)[0]>150


def test_real_timed_mask_preview_and_export_agree(tmp_path):
    source=tmp_path/"source.mp4"
    run("-f","lavfi","-i","color=red:s=160x120:r=25:d=4",
        "-c:v","libx264","-pix_fmt","yuv420p",source)
    video=probe_video(source)
    d=Director(zones=(OverlayZone("alert",(0,0,1,1),.5,1.5,mask=True),),
               removal_enabled=True)
    plan=initial_selection(0,4).edit(0,mode="fixed",director=d)
    request=RenderRequest(video,0,4,"crop",width=160,height=120,scene_plan=plan)
    full=render_request(request,tmp_path/"full.mp4")
    preview=render_request(request.preview_excerpt(2.5),tmp_path/"preview.mp4")
    for at in (.2,.8,2.0):
        assert max(abs(a-b) for a,b in zip(rgb(full,at),rgb(preview,at)))<=15
    assert max(rgb(preview,.8))<30
    assert rgb(preview,2)[0]>150
