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


def test_plan_roundtrip_and_changed_media(tmp_path):
    from streamclipper.montage_request import MontageRequest,save_plan,load_plan
    src=tmp_path/"original.mp4";src.write_bytes(b"source")
    video=VideoInfo(str(src),10,1920,1080,30,True)
    req=MontageRequest.create(video,Montage((Beat(0,3),Beat(5,7,speed=2)),encoder="cpu_h264"))
    path=tmp_path/"montage.json";save_plan(path,req)
    assert load_plan(path)==req
    src.write_bytes(b"changed source")
    with pytest.raises(ValueError,match="geändert"):load_plan(path)
    assert path.exists()

def test_sound_library_content_addressed(tmp_path,monkeypatch):
    from streamclipper import sound_library as lib
    monkeypatch.setattr(lib,"probe_audio_duration",lambda p:1.25)
    src=tmp_path/"effect.wav";src.write_bytes(b"test waveform")
    root=tmp_path/"sounds"
    item=lib.import_sound(src,"Own effect","Self recorded",root=root)
    assert lib.entries(root)==[item]
    assert lib.import_sound(src,"Second name","Own",root=root)==item
    assert Path(item["path"]).read_bytes()==src.read_bytes()
    with pytest.raises(ValueError,match="Rechtehinweis"):lib.import_sound(src,"No rights","",root=root)

def test_montage_queue_snapshot_recovery(tmp_path,monkeypatch):
    from streamclipper import montage as m
    from streamclipper import montage_request as mr
    from streamclipper.render_queue import RenderQueue
    from streamclipper.render_contract import RenderRequest
    from streamclipper.media import tool_path,probe_video
    from streamclipper.export_qa import read_report
    source=tmp_path/"source.mp4"
    subprocess.run([tool_path("ffmpeg"),"-v","error","-y","-f","lavfi","-i",
        "testsrc2=s=96x54:r=30:d=4","-f","lavfi","-i","sine=frequency=440:duration=4",
        "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(source)],check=True)
    video=probe_video(source)
    monkeypatch.setattr(m,"dimensions",lambda aspect:(96,54))
    monkeypatch.setattr(mr,"dimensions",lambda aspect:(96,54))
    plan=Montage((Beat(2,3),Beat(0,1)), "16:9","cpu_h264")
    comps=tuple(RenderRequest(video,b.start,b.end,"crop",width=96,height=54,
                              encoder="cpu_h264") for b in plan.beats)
    req=mr.MontageRequest.create(video,plan,comps)
    saved=tmp_path/"project.json";mr.save_plan(saved,req)
    assert mr.load_plan(saved)==req
    root=tmp_path/"queue";output=tmp_path/"output";output.mkdir()
    queue=RenderQueue(root=root)
    try:
        job=queue.enqueue(req,output,label="M17 Montage")
        assert job.request["kind"]=="montage-v1"
    finally:queue.close()
    queue=RenderQueue(root=root)
    try:
        done=queue.run_next()
        assert done.status=="COMPLETE",done.detail
        assert read_report(done.result).status=="PASS"
        assert queue.run_next() is None
    finally:queue.close()
    queue=RenderQueue(root=root)
    try:assert queue.jobs()[0].status=="COMPLETE"
    finally:queue.close()

def test_queue_modified_source_fails_closed(tmp_path):
    from streamclipper.montage_request import MontageRequest
    from streamclipper.render_queue import RenderQueue
    src=tmp_path/"source.mp4";src.write_bytes(b"source")
    video=VideoInfo(str(src),10,1920,1080,30,True)
    req=MontageRequest.create(video,Montage((Beat(0,3),),encoder="cpu_h264"))
    queue=RenderQueue(root=tmp_path/"queue")
    try:
        job=queue.enqueue(req,tmp_path,label="Montage")
        src.write_bytes(b"modified original")
        result=queue.run_next()
        assert result.status=="FAILED" and "geändert" in result.detail
        assert not Path(job.destination).exists()
    finally:queue.close()


def test_sampled_ramp_monotone_and_bounded():
    from streamclipper.montage import sampled_ramp
    beats=sampled_ramp(1,9,.5,2,16,"smooth")
    assert len(beats)==16 and beats[0].start==1 and beats[-1].end==9
    assert beats[0].speed==.5 and beats[-1].speed==2
    assert [b.speed for b in beats]==sorted(b.speed for b in beats)
    assert all(a.end==b.start for a,b in zip(beats,beats[1:]))
    with pytest.raises(ValueError):sampled_ramp(0,1,steps=32)


def test_real_montage_sound_lut_and_freeze_caption(tmp_path,monkeypatch):
    from streamclipper import montage as m
    from streamclipper.media import tool_path,probe_video
    from streamclipper.export_qa import read_report
    source=tmp_path/"silent.mp4";sound=tmp_path/"own.wav";lut=tmp_path/"identity.cube"
    ffmpeg=tool_path("ffmpeg")
    subprocess.run([ffmpeg,"-v","error","-y","-f","lavfi","-i","testsrc2=s=160x90:r=30:d=2",
                    "-c:v","libx264","-pix_fmt","yuv420p",str(source)],check=True)
    subprocess.run([ffmpeg,"-v","error","-y","-f","lavfi","-i","sine=frequency=880:duration=0.5",
                    str(sound)],check=True)
    lut.write_text("LUT_3D_SIZE 2\n"+"\n".join(f"{r} {g} {b}" for b in (0,1) for g in (0,1) for r in (0,1))+"\n",encoding="ascii")
    monkeypatch.setattr(m,"dimensions",lambda aspect:(160,90))
    plan=Montage((Beat(0,1,freeze=.5,zoom=1.1,text="TEST",lut=str(lut),sound=str(sound)),),"16:9","cpu_h264")
    path=render_montage(probe_video(source),plan,tmp_path/"effects.mp4")
    qa=read_report(path)
    assert qa.status=="PASS" and qa.audio_present and qa.duration==pytest.approx(1.5,abs=.4)


@pytest.mark.parametrize("initial,final",[(.25,4),(4,.25),(1,1),(.5,2)])
def test_continuous_time_map_inverse(initial,final):
    from streamclipper.speed_curve import duration,source_time,output_time
    length=8;d=duration(length,initial,final)
    assert source_time(0,length,initial,final)==0
    assert source_time(d,length,initial,final)==pytest.approx(length)
    for i in range(21):
        t=d*i/20
        assert output_time(source_time(t,length,initial,final),length,initial,final)==pytest.approx(t)
    assert Beat(0,8,speed=initial,end_speed=final).duration==pytest.approx(d)

@pytest.mark.parametrize("initial,final",[(.5,2),(2,.5)])
def test_real_continuous_curve_audio_video(tmp_path,monkeypatch,initial,final):
    from streamclipper import montage as m
    from streamclipper.media import tool_path,probe_video
    from streamclipper.export_qa import read_report
    ffmpeg=tool_path("ffmpeg");source=tmp_path/"curve.mp4"
    subprocess.run([ffmpeg,"-v","error","-y","-f","lavfi","-i","testsrc2=s=96x54:r=30:d=4",
                    "-f","lavfi","-i","sine=frequency=440:duration=4",
                    "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(source)],check=True)
    monkeypatch.setattr(m,"dimensions",lambda aspect:(96,54))
    beat=Beat(.5,3.5,speed=initial,end_speed=final)
    output=render_montage(probe_video(source),Montage((beat,),"16:9","cpu_h264"),tmp_path/"out.mp4")
    qa=read_report(output)
    assert qa.status=="PASS" and qa.audio_present
    assert qa.duration==pytest.approx(beat.duration,abs=.25)
    assert abs(qa.audio_end_delta or 0)<.25

def test_curve_audio_mapping_marker(tmp_path):
    import numpy as np
    from streamclipper.speed_curve import render_audio,output_time
    from streamclipper.media import tool_path,probe_video
    ffmpeg=tool_path("ffmpeg");source=tmp_path/"marker.mp4"
    # A short tone in the middle of a 3-second clip maps to the same time
    # as the video expression, not merely to a matching total duration.
    subprocess.run([ffmpeg,"-v","error","-y","-f","lavfi","-i","testsrc2=s=96x54:r=30:d=3",
                    "-f","lavfi","-i","aevalsrc=if(between(t\\,1.4\\,1.6)\\,0.5*sin(2*PI*440*t)\\,0):s=48000:d=3",
                    "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(source)],check=True)
    beat=Beat(0,3,speed=.5,end_speed=2)
    wav=render_audio(probe_video(source),beat,tmp_path)
    data=np.fromfile(wav,dtype="<f4").reshape(-1,2)
    indices=np.flatnonzero(np.abs(data[:,0])>.08)
    assert len(indices)>100
    assert float(np.median(indices))/48000==pytest.approx(output_time(1.5,3,.5,2),abs=.06)
