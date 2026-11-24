"""M14 translation persistence and explicit rendering language."""
from dataclasses import replace
import json
import shutil
import subprocess

import pytest

from streamclipper.models import AnalysisResult, VideoInfo, TranscriptSegment, TranscriptWord
from streamclipper.subtitle_translation import set_translations, select_language, export_transcript, translate_local
from streamclipper.transcript_editor import load_analysis_report, apply_segment_changes
from streamclipper.autosave import save_autosave, load_autosave
from streamclipper.edit_history import WorkspaceHistory
from streamclipper.editor_project import initial_project
from streamclipper.project_checkpoints import create_checkpoint, load_checkpoint
from streamclipper.render_contract import RenderRequest, render_request
from streamclipper.render_queue import _snapshot, _rehydrate
from streamclipper.captioning import render_ass
from streamclipper.media import probe_video


def source(tmp_path):
    path=tmp_path/"original.mp4";path.write_bytes(b"unchanged")
    video=VideoInfo(str(path),10,320,240,25,False)
    return AnalysisResult(video,[],transcript=[
        TranscriptSegment(1,2,"Hello",(TranscriptWord(1,2,"Hello"),)),
        TranscriptSegment(5,6,"Goodbye")])


def test_selected_interval_and_stale_translation(tmp_path):
    r=source(tmp_path)
    t=set_translations(r,"de",[(0,"Hallo","model")])
    assert t.transcript==r.transcript
    assert export_transcript(t,[(0,3)])==(TranscriptSegment(1,2,"Hallo"),)
    with pytest.raises(ValueError,match="fehlt"):
        export_transcript(t)
    assert export_transcript(select_language(t,""))==tuple(r.transcript)
    changed=apply_segment_changes(t,0,"1","2","Welcome")
    with pytest.raises(ValueError,match="fehlt"):
        export_transcript(changed,[(0,3)])
    assert export_transcript(t,[(3,4)])==()


def test_persistence_and_history(tmp_path):
    r=source(tmp_path);t=set_translations(r,"de",[(0,"Hallo","manual"),(1,"Tschüss","manual")])
    path=tmp_path/"report.json";t.save_json(path)
    assert load_analysis_report(path,r.video.path)==t
    save_autosave(t,root=tmp_path/"autosaves")
    assert load_autosave(r.video.path,root=tmp_path/"autosaves")==t
    project=initial_project(r.video)
    cp=create_checkpoint(project,"translation",t,root=tmp_path)
    assert load_checkpoint(r.video,cp.id,root=tmp_path)==(project,t)
    h=WorkspaceHistory()
    assert h.record_analysis(r,t)
    assert h.undo(t,project)==(r,project)
    assert h.redo(r,project)==(t,project)
    original=select_language(t,"")
    assert h.record_analysis(t,original)
    assert h.undo(original,project)==(t,project)
    assert h.redo(t,project)==(original,project)


def test_queue_freezes_resolved_language(tmp_path):
    r=source(tmp_path)
    t=set_translations(r,"de",[(0,"Hallo","manual")])
    req=RenderRequest(r.video,0,3,"crop",True,0,export_transcript(t,[(0,3)]))
    restored=_rehydrate(json.loads(json.dumps(_snapshot(req))))
    assert restored==req
    assert "Hallo" in render_ass(restored.transcript,0,3)
    assert "Hello" not in render_ass(restored.transcript,0,3)
    assert not restored.transcript[0].words


def test_no_download_or_missing_model_fallback(tmp_path):
    with pytest.raises(FileNotFoundError):
        translate_local(["hello"],tmp_path)
    (tmp_path/"model.safetensors").write_bytes(b"mock")
    (tmp_path/"config.json").write_text('{"model_type":"other"}')
    with pytest.raises(ValueError,match="Marian"):
        translate_local(["hello"],tmp_path)


def test_manual_translation_does_not_invent_alignment(tmp_path):
    r=source(tmp_path)
    t=set_translations(r,"de",[(0,"Guten Tag","manual")])
    assert export_transcript(t,[(0,3)])[0].words==()
    with pytest.raises(ValueError):
        set_translations(r,"de",[(200,"invalid","manual")])


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),reason="FFmpeg unavailable")
def test_translated_mp4_and_preview(tmp_path):
    path=tmp_path/"real.mp4"
    def run(*args):
        return subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",*map(str,args)],
            capture_output=True,check=True,timeout=90).stdout
    run("-f","lavfi","-i","color=black:s=320x240:r=25:d=3","-c:v","libx264","-pix_fmt","yuv420p",path)
    video=probe_video(path)
    r=AnalysisResult(video,[],transcript=[TranscriptSegment(.2,2.4,"A")])
    t=set_translations(r,"de",[(0,"GUTEN TAG","manual")])
    req=RenderRequest(video,0,3,"crop",True,0,export_transcript(t),320,240)
    full=render_request(req,tmp_path/"translated.mp4")
    short=render_request(req.preview_excerpt(2),tmp_path/"preview.mp4")
    original=render_request(replace(req,transcript=tuple(r.transcript)),tmp_path/"original-caption.mp4")
    def frame(p):
        return run("-ss",1,"-i",p,"-frames:v",1,"-pix_fmt","gray","-f","rawvideo","pipe:1")
    a,b,c=frame(full),frame(short),frame(original)
    assert len(a)==len(b)==len(c)==320*240
    assert sum(v>175 for v in a)>sum(v>175 for v in c)
    assert sum(abs(x-y) for x,y in zip(a,b))/len(a)<3
