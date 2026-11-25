"""M14 regression coverage for caption editing and export-identical branding."""
from dataclasses import asdict, replace
import json
import shutil
import subprocess

import pytest

from streamclipper.caption_style import CaptionStyle, PRESETS
from streamclipper.captioning import render_ass
from streamclipper.editor_project import initial_project, set_caption_style, save_project, load_project
from streamclipper.models import AnalysisResult, TranscriptSegment, TranscriptWord, VideoInfo
from streamclipper.project_checkpoints import create_checkpoint, load_checkpoint
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.render_queue import _snapshot, _rehydrate
from streamclipper.transcript_editor import apply_segment_changes
from streamclipper.media import probe_video


def sample():
    return TranscriptSegment(0,2,"Hello world",(
        TranscriptWord(.2,.8,"Hello"),TranscriptWord(1,1.7,"world")))


def test_word_text_correction_preserves_timing_and_noop():
    v=VideoInfo("source.mp4",10,320,240,25,False)
    r=AnalysisResult(v,[],transcript=[sample()])
    assert apply_segment_changes(r,0,"0","2","Hello world") is r
    s=apply_segment_changes(r,0,"0","2","Hello earth").transcript[0]
    assert s.words[0]==sample().words[0]
    assert s.words[1]==TranscriptWord(1,1.7,"earth","manual")
    assert not apply_segment_changes(r,0,"0","2","Hello big world").transcript[0].words


def test_style_serialization_and_backward_defaults(tmp_path):
    video=VideoInfo(str(tmp_path/"source.mp4"),10,320,240,25,False)
    style=PRESETS["Neon Pop"]
    project=set_caption_style(initial_project(video),style)
    save_project(project,root=tmp_path)
    assert load_project(video,root=tmp_path)==project
    cp=create_checkpoint(project,"Branding",root=tmp_path)
    assert load_checkpoint(video,cp.id,root=tmp_path)[0]==project
    request=RenderRequest(video,0,2,"crop",caption_style=style,project=project)
    doc=json.loads(json.dumps(_snapshot(request)))
    assert _rehydrate(doc)==request
    doc.pop("caption_style")
    doc["project"].pop("caption_style")
    assert _rehydrate(doc).caption_style==CaptionStyle()
    assert _rehydrate(doc).project.caption_style==CaptionStyle()


@pytest.mark.parametrize("changes",[{"font":"Arial,evil"},{"text_color":"{bad}"},
    {"scale":float("nan")},{"group_words":0},{"position":"unknown"}])
def test_invalid_style(changes):
    with pytest.raises(ValueError):
        replace(CaptionStyle(),**changes).validate()


def test_ass_word_animation_and_escape():
    style=PRESETS["Neon Pop"]
    ass=render_ass([sample()],0,2,caption_style=style)
    assert r"\fscx115" in ass and r"\t(0,120," in ass
    assert r"\1c&H00C2E350&" in ass
    assert "0:00:00.20,0:00:00.80" in ass
    assert "0:00:01.00,0:00:01.70" in ass
    unsafe=TranscriptSegment(0,1,"{evil}",(TranscriptWord(0,1,r"{\pos(0,0)}"),))
    result=render_ass([unsafe],0,1,caption_style=style)
    assert r"{\pos(0,0)}" not in result
    legacy=render_ass([TranscriptSegment(0,1,"No timings")],0,1,caption_style=style)
    assert r"\fscx115" not in legacy


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="FFmpeg/FFprobe unavailable")
def test_real_word_accent_preview_and_export(tmp_path):
    source=tmp_path/"source.mp4"
    def run(*args):
        return subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",*map(str,args)],
            capture_output=True,check=True,timeout=90).stdout
    run("-f","lavfi","-i","color=black:s=640x360:r=25:d=3",
        "-c:v","libx264","-pix_fmt","yuv420p",source)
    video=probe_video(source)
    style=CaptionStyle(mode="highlight",accent_color="#FF0000",position="top",group_words=2)
    request=RenderRequest(video,0,3,"crop",True,0,(sample(),),
                          640,360,caption_style=style)
    full=render_request(request,tmp_path/"full.mp4")
    preview=render_request(request.preview_excerpt(2),tmp_path/"short.mp4")
    def frame(path,t):
        return run("-ss",t,"-i",path,"-frames:v",1,"-pix_fmt","rgb24","-f","rawvideo","pipe:1")
    for t in (.4,1.3):
        a,b=frame(full,t),frame(preview,t)
        assert len(a)==len(b)==640*360*3
        assert sum(a[i]>150 and a[i+1]<90 and a[i+2]<90 for i in range(0,len(a),3))>30
        assert sum(abs(x-y) for x,y in zip(a,b))/len(a)<3
