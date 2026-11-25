"""M13e cross-path acceptance with reordering, masks, captions and A/V layers."""
from array import array
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from PIL import Image

from streamclipper.editor_project import initial_project, add_item, add_track
from streamclipper.export_qa import read_report
from streamclipper.media import probe_video
from streamclipper.models import TranscriptSegment
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.render_queue import RenderQueue
from streamclipper.rendered_preview import render_clip_preview
from streamclipper.scene_selection import initial_selection
from streamclipper.smart_director import Director, OverlayZone


pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                                reason="FFmpeg/FFprobe unavailable")


def run(*args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
                           *map(str,args)], check=True, capture_output=True, timeout=90).stdout


def frame(path, at):
    data = run("-ss",at,"-i",path,"-frames:v",1,"-pix_fmt","rgb24","-f","rawvideo","pipe:1")
    assert len(data)==320*240*3
    return data


def pixel(data,x,y):
    i=(y*320+x)*3
    return tuple(data[i:i+3])


def strength(path,at,frequency):
    raw=run("-ss",at,"-i",path,"-t",.25,"-vn","-ac",1,"-ar",8000,
            "-c:a","pcm_s16le","-f","s16le","pipe:1")
    values=array("h");values.frombytes(raw)
    if sys.byteorder!="little":values.byteswap()
    assert len(values)>=1500
    a=sum(v*math.sin(2*math.pi*frequency*i/8000) for i,v in enumerate(values))
    b=sum(v*math.cos(2*math.pi*frequency*i/8000) for i,v in enumerate(values))
    return 2*math.hypot(a,b)/len(values)


def test_reordered_multitrack_direct_queue_and_truncated_preview(tmp_path):
    source=tmp_path/"source.mp4"
    camera=tmp_path/"facecam.mp4"
    sound=tmp_path/"music.wav"
    logo=tmp_path/"logo.png"
    run("-f","lavfi","-i","color=red:s=320x240:r=25:d=6",
        "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=6",
        "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",source)
    run("-f","lavfi","-i","color=green:s=80x60:r=25:d=1",
        "-c:v","libx264","-pix_fmt","yuv420p",camera)
    run("-f","lavfi","-i","sine=frequency=880:sample_rate=48000:duration=1",
        "-c:a","pcm_s16le",sound)
    Image.new("RGB",(80,60),(0,0,255)).save(logo)
    video=probe_video(source)
    project=add_item(initial_project(video),"graphics",0,1,4.5,"Logo",
                     media_path=str(logo),x=.7,y=.55,width=.25,height=.25)
    project=add_track(project,"video","Facecam")
    project=add_item(project,project.tracks[-1].id,0,1,.5,"PiP",
                     media_path=str(camera),x=.05,y=.55,width=.25,height=.25)
    project=add_item(project,"music",0,1,4.5,"Music",media_path=str(sound))
    plan=initial_selection(0,6).split(0,2).split(1,4)
    plan=plan.edit(1,included=False).move(2,-1).move(1,-1)
    first=Director(zones=(OverlayZone("alert",(0,0,.5,1),4.2,4.8,mask=True),),
                   removal_enabled=True,caption_safe="top")
    plan=plan.edit(0,mode="fixed",director=first).edit(1,mode="fixed")
    request=RenderRequest(video,0,6,"crop",burn_subtitles=True,
        transcript=(TranscriptSegment(.2,1.8,"SECOND"),TranscriptSegment(4.2,5.8,"FIRST")),
        width=320,height=240,project=project,scene_plan=plan)
    direct=render_request(request,tmp_path/"direct.mp4")
    preview,owner=render_clip_preview(request,max_seconds=3.5,temp_root=tmp_path)
    try:
        queue=RenderQueue(root=tmp_path/"queue")
        try:
            job=queue.enqueue(request,tmp_path,label="M13 combined")
        finally:
            queue.close()
        queue=RenderQueue(root=tmp_path/"queue")
        try:
            done=queue.run_next()
            assert done.id==job.id and done.status=="COMPLETE",done.detail
            queued=Path(done.result)
        finally:
            queue.close()
        for path in (direct,queued,preview.path):
            assert read_report(path).status=="PASS"
            assert probe_video(path).has_audio
            assert max(pixel(frame(path,.4),40,110))<40
            assert pixel(frame(path,1.1),260,160)[2]>150
            assert pixel(frame(path,2.9),50,160)[1]>70
            assert pixel(frame(path,2.9),50,160)[0]<80
            assert pixel(frame(path,2.9),260,160)[0]>150
            assert strength(path,.9,880)>600
            assert strength(path,2.9,880)<300
            assert strength(path,2.9,440)>600
            # Source-time captions must follow scene order and own safe zone.
            a,b=frame(path,.9),frame(path,2.9)
            def whites(data,y0,y1):
                return sum(min(data[i:i+3])>175 for i in range(y0*320*3,y1*320*3,3))
            assert whites(a,0,100)>50 and whites(a,190,240)<20
            assert whites(b,190,240)>50 and whites(b,0,100)<20
        for at in (.4,1.1,2.9):
            a=frame(direct,at)
            for path in (queued,preview.path):
                other=frame(path,at)
                assert sum(abs(x-y) for x,y in zip(a,other))/len(a)<6
        assert abs(probe_video(direct).duration-4)<.2
        assert abs(probe_video(preview.path).duration-3.5)<.2
    finally:
        owner.cleanup()
    assert not list(tmp_path.glob(".scene-render-*"))
