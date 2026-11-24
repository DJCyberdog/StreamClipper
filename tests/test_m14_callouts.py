"""M14 callouts: persistent editable metadata and real compositing."""
from dataclasses import replace
import json
import shutil
import subprocess
import pytest
from streamclipper.callouts import Callout,rasterize
from streamclipper.editor_project import (initial_project,add_item,update_callout,save_project,
    load_project,toggle_track)
from streamclipper.models import VideoInfo
from streamclipper.render_graph import build_render_graph
from streamclipper.render_contract import RenderRequest,render_request
from streamclipper.render_queue import _snapshot,_rehydrate
from streamclipper.project_checkpoints import create_checkpoint,load_checkpoint
from streamclipper.edit_history import WorkspaceHistory
from streamclipper.media import probe_video


@pytest.mark.parametrize("kind",["text","bubble","arrow","rectangle","ellipse"])
def test_raster_transparency(kind):
    image=rasterize(Callout(kind,text="Test",filled=False),240,120)
    assert image.mode=="RGBA" and image.size==(240,120)
    assert image.getpixel((0,0))[3]==0
    assert image.getchannel("A").getbbox() is not None


def test_editable_persistence_and_locked_track(tmp_path):
    video=VideoInfo(str(tmp_path/"source.mp4"),10,320,240,25,False)
    p=add_item(initial_project(video),"graphics",0,2,3,"Arrow",
               x=.1,y=.1,width=.4,height=.3,callout=Callout("arrow"))
    old=p.items[-1]
    edited=update_callout(p,old.id,Callout("bubble","Look!"),timeline_start=4,
                         source_end=2,x=.2,y=.2,width=.5,height=.4,opacity=.7)
    assert p.items[-1]==old
    save_project(edited,root=tmp_path)
    assert load_project(video,root=tmp_path)==edited
    cp=create_checkpoint(edited,"Callout",root=tmp_path)
    assert load_checkpoint(video,cp.id,root=tmp_path)[0]==edited
    req=RenderRequest(video,3,7,"crop",project=edited)
    assert _rehydrate(json.loads(json.dumps(_snapshot(req))))==req
    h=WorkspaceHistory();assert h.record_project(p,edited)
    assert h.undo(None,edited)==(None,p)
    assert h.redo(None,p)==(None,edited)
    layers=build_render_graph(edited,video,5,7).visual_layers
    assert len(layers)==1 and layers[0].source_start==1 and layers[0].source_end==2
    assert layers[0].callout==edited.items[-1].callout
    assert not build_render_graph(toggle_track(edited,"graphics","muted"),video,3,7).visual_layers
    with pytest.raises(ValueError,match="gesperrt"):
        update_callout(toggle_track(p,"graphics","locked"),old.id,old.callout,
            timeline_start=3,source_end=2,x=.1,y=.1,width=.4,height=.3,opacity=1)


def test_invalid_callouts():
    with pytest.raises(ValueError):Callout("bubble","").validate()
    with pytest.raises(ValueError):Callout("arrow",accent="red").validate()
    with pytest.raises(ValueError):rasterize(Callout(text="hello"),5000,5000)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),reason="FFmpeg unavailable")
def test_actual_timed_callout_preview_export(tmp_path):
    source=tmp_path/"source.mp4"
    def run(*args):
        return subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",*map(str,args)],
            check=True,capture_output=True,timeout=90).stdout
    run("-f","lavfi","-i","color=black:s=320x240:r=25:d=4","-c:v","libx264","-pix_fmt","yuv420p",source)
    video=probe_video(source)
    p=add_item(initial_project(video),"graphics",0,1,1,"Marker",
        x=.1,y=.1,width=.5,height=.5,callout=Callout("rectangle",background="#00FF00"))
    req=RenderRequest(video,0,4,"crop",width=320,height=240,project=p)
    full=render_request(req,tmp_path/"full.mp4")
    short=render_request(req.preview_excerpt(2.5),tmp_path/"short.mp4")
    def frame(path,at):
        return run("-ss",at,"-i",path,"-frames:v",1,"-pix_fmt","rgb24","-f","rawvideo","pipe:1")
    for at in (.4,1.4,2.3):
        a,b=frame(full,at),frame(short,at)
        assert len(a)==len(b)==320*240*3
        idx=(80*320+100)*3
        assert (a[idx+1]>150)==(at==1.4)
        assert sum(abs(x-y) for x,y in zip(a,b))/len(a)<3
    assert not list(tmp_path.glob(".*-*/callout-*.png"))
