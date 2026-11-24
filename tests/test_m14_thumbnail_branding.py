"""M14 thumbnail/branding integration; actual reordered video frame, no proxy."""
import shutil
import subprocess
from dataclasses import replace
import pytest
from PIL import Image
from streamclipper.thumbnail import ThumbnailDesign,compose_thumbnail,save_thumbnail,capture_composed_frame
from streamclipper.branding_profile import BrandProfile,save_profile,load_profile,apply_profile
from streamclipper.caption_style import CaptionStyle
from streamclipper.editor_project import initial_project,toggle_track
from streamclipper.models import VideoInfo
from streamclipper.media import probe_video
from streamclipper.render_contract import RenderRequest
from streamclipper.scene_selection import initial_selection


def test_design_dimensions_title_and_nonoverwrite(tmp_path):
    frame=Image.new("RGB",(160,90),"red")
    design=ThumbnailDesign(title="EPIC WIN",background="#000000")
    image=compose_thumbnail(frame,design)
    assert image.size==(1280,720)
    assert image.getpixel((0,0))==(255,0,0)
    assert image.getpixel((100,500))!=(255,0,0)
    path=save_thumbnail(frame,design,tmp_path/"thumb.png")
    with Image.open(path) as saved:
        assert saved.tobytes()==image.tobytes()
    previous=path.read_bytes()
    with pytest.raises(FileExistsError):save_thumbnail(frame,design,path)
    assert path.read_bytes()==previous
    with pytest.raises(ValueError):compose_thumbnail(frame,replace(design,x=.9))
    fitted=compose_thumbnail(frame,ThumbnailDesign(width=1080,height=1920,fit="fit"))
    assert fitted.getpixel((0,0))==(24,32,54)
    assert fitted.getpixel((540,960))==(255,0,0)


def test_profile_roundtrip_and_style_only(tmp_path):
    style=CaptionStyle(mode="pop",accent_color="#123456")
    profile=BrandProfile("Channel",style)
    path=save_profile(profile,tmp_path/"brand.json")
    assert load_profile(path)==profile
    with pytest.raises(FileExistsError):save_profile(profile,path)
    video=VideoInfo(str(tmp_path/"source.mp4"),4,320,240,25,False)
    project=initial_project(video)
    updated=apply_profile(project,profile,0,4)
    assert updated.caption_style==style and updated.items==project.items
    with pytest.raises(ValueError):BrandProfile("bad",logo="https://example.com/logo.png").validate()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),reason="FFmpeg unavailable")
def test_logo_profile_existing_asset_and_idempotent(tmp_path):
    logo=tmp_path/"logo.png";Image.new("RGBA",(80,60),"blue").save(logo)
    p=BrandProfile("Brand",logo=str(logo.resolve()))
    video=VideoInfo(str(tmp_path/"source.mp4"),4,320,240,25,False)
    original=initial_project(video)
    updated=apply_profile(original,p,1,3,"graphics")
    assert len(updated.items)==len(original.items)+1
    item=updated.items[-1]
    assert item.media_path==str(logo.resolve()) and item.timeline_start==1 and item.source_end==2
    assert apply_profile(updated,p,1,3,"graphics")==updated
    with pytest.raises(ValueError):apply_profile(toggle_track(original,"graphics","locked"),p,1,3,"graphics")


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),reason="FFmpeg unavailable")
def test_actual_reordered_scene_thumbnail(tmp_path):
    path=tmp_path/"source.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",
        "-f","lavfi","-i","color=red:s=320x240:r=25:d=2",
        "-f","lavfi","-i","color=blue:s=320x240:r=25:d=2",
        "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0[v]","-map","[v]",
        "-c:v","libx264","-pix_fmt","yuv420p",str(path)],check=True,capture_output=True,timeout=90)
    video=probe_video(path)
    plan=initial_selection(0,4).split(0,2).move(1,-1).edit(0,mode="fixed").edit(1,mode="fixed")
    req=RenderRequest(video,0,4,"crop",width=320,height=240,scene_plan=plan)
    first=capture_composed_frame(req,.5,temp_root=tmp_path)
    second=capture_composed_frame(req,2.5,temp_root=tmp_path)
    assert first.size==second.size==(320,240)
    a,b=first.getpixel((160,120)),second.getpixel((160,120))
    assert a[2]>150 and a[0]<80 and b[0]>150 and b[2]<80
    assert not list(tmp_path.glob("thumbnail-*"))
