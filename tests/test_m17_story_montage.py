from dataclasses import replace
from pathlib import Path
import subprocess
import pytest
from streamclipper.models import Candidate,AnalysisResult,VideoInfo,TranscriptSegment,TranscriptWord
from streamclipper.semantic import EventEvidence
from streamclipper.story_clipping import (StoryOptions,story_bounds,refine_result,length_variants,
    speech_spans,chapters,hook_candidates)
from streamclipper.montage import Beat,Montage,speed_ramp,atempo,render_montage
from streamclipper.m17_benchmark import compare_boundaries

def candidate(t=30):
    return Candidate(t-8,t+17,70,"cue",t)

def test_dynamic_story_includes_late_reaction_and_corrected_word_boundaries():
    c=candidate()
    cues=[TranscriptSegment(23,29,"setup",(TranscriptWord(23,24,"setup","manual"),)),
          TranscriptSegment(40,58,"reaction",(TranscriptWord(40,43,"reaction","manual"),))]
    e=[EventEvidence(30,"visual",.8,"hint"),EventEvidence(40,"reaction",.8,"reaction")]
    out=story_bounds(c,120,cues,e,StoryOptions(10,60))
    assert out.start<=24 and out.end>=43 and out.end<58
    assert out.score==c.score and out.peak_at==c.peak_at
    assert speech_spans(cues,120)==[(23,24),(40,43)]

def test_manual_immutable_and_fixed_budget():
    c=candidate();manual=replace(c,origin="manual")
    result=AnalysisResult(VideoInfo("unused",120,1920,1080,30,True),[c,manual])
    new=refine_result(result,options=StoryOptions(10,20))
    assert new.candidates[-1] is manual and result.candidates[0] is c
    assert 10<=new.candidates[0].end-new.candidates[0].start<=20.001
    for name,v in length_variants(c,120):
        assert v.end-v.start==pytest.approx(float(name[:-1]),abs=.001)
        assert v.start<=c.peak_at<=v.end

def test_short_video_edge_and_chapters():
    c=Candidate(0,3,5,"cue",.1)
    out=story_bounds(c,3,options=StoryOptions())
    assert (out.start,out.end)==(0,3)
    assert chapters(1300,[])==[(0.,600.,"Aufnahmeabschnitt"),(600.,1200.,"Aufnahmeabschnitt"),(1200.,1300.,"Aufnahmeabschnitt")]
    assert hook_candidates(c)[0]==(0,"Originaler Einstieg")

def test_boundary_benchmark_not_ranking():
    c=candidate()
    story=replace(c,start=20,end=60)
    report=compare_boundaries([c],[story],[{"start":21,"end":55,"label":"other"}],120)
    assert report["fixed"]["fully_contained"]==0
    assert report["story"]["fully_contained"]==1
    assert report["quality_acceptance"]=="NOT_EVALUATED"

def test_montage_contract():
    assert atempo(4)=="atempo=2.00000000,atempo=2.00000000"
    assert atempo(.25)=="atempo=0.50000000,atempo=0.50000000"
    parts=speed_ramp(0,6)
    assert [(b.start,b.end,b.speed) for b in parts]==[(0,2,.5),(2,4,1),(4,6,2)]
    assert sum(b.duration for b in parts)==7
    with pytest.raises(ValueError):Montage((Beat(0,2,speed=0),)).validate(10)
    with pytest.raises(ValueError):Montage((Beat(0,2,text="no freeze"),)).validate(10)

def test_real_montage_order_speed_freeze_and_audio(tmp_path,monkeypatch):
    import streamclipper.montage as m
    from streamclipper.media import tool_path,probe_video
    source=tmp_path/"source.mp4"
    subprocess.run([tool_path("ffmpeg"),"-v","error","-y","-f","lavfi","-i",
        "testsrc2=s=96x54:r=30:d=4","-f","lavfi","-i","sine=frequency=440:duration=4",
        "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(source)],check=True)
    original=source.read_bytes()
    monkeypatch.setattr(m,"dimensions",lambda aspect:(96,54))
    plan=Montage((Beat(2,3,speed=.5),Beat(0,1,speed=2,freeze=.5,zoom=1.2,look="mono")),"16:9","cpu_h264")
    output=render_montage(probe_video(source),plan,tmp_path/"out.mp4")
    result=probe_video(output)
    assert result.duration==pytest.approx(3,abs=.4) and result.has_audio
    assert source.read_bytes()==original
    second=render_montage(probe_video(source),plan,tmp_path/"out.mp4")
    assert second!=output and output.exists()
