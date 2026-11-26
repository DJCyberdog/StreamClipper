from dataclasses import asdict
from pathlib import Path
import json
import pytest
from streamclipper.semantic import EventEvidence
from streamclipper.models import Candidate,VideoInfo,TranscriptSegment
from streamclipper.gaming_intelligence import (adaptive_samples,rank,feedback_preferences,chat_hints,
    search_transcript,speech_reaction_hints,store_evidence,load_evidence)
from streamclipper.m16_benchmark import freeze,evaluate,compare
from streamclipper.m16_review import record_feedback,personal_preferences,read_chat
from streamclipper import m16_pipeline as pipeline

def ev(at,kind,strength=.8,description="test"):
    return EventEvidence(at,kind,strength,description)

def test_budget_control_late_and_quiet():
    events=[ev(1,"motion"),ev(21590,"speech")]
    times=adaptive_samples(events,21600,180)
    assert 1<=len(times)<=180 and times==sorted(set(times))
    assert min(times)<20 and max(times)>21580
    assert any(1000<t<20000 for t in times)

def test_dependent_modalities_and_context():
    assert rank([ev(12,"audio"),ev(12,"speech_context"),ev(12,"chat")],120)==[]
    single=rank([ev(30,"visual")],120)
    multi=rank([ev(30,"visual"),ev(30,"object"),ev(30,"visual")],120)
    assert single[0].score==multi[0].score
    fused=rank([ev(30,"visual"),ev(30,"speech")],120)
    assert fused[0].score>single[0].score
    assert "Heuristik" in fused[0].reason
    assert len(rank([ev(30,"visual"),ev(31,"speech"),ev(32,"motion")],120))==1

def test_reaction_requires_designated_source():
    levels=[-40.]*8+[-20.]
    assert not speech_reaction_hints(levels,10)
    assert speech_reaction_hints(levels,10,designated_microphone=True)[0].kind=="reaction"

def test_feedback_and_chat(tmp_path):
    c=Candidate(0,25,50,"",10)
    p=tmp_path/"feedback.json"
    record_feedback(p,"test",c,"speech",1)
    assert personal_preferences(p)["speech"]>0
    assert not feedback_preferences([{"split":"holdout","kind":"speech","vote":1}])
    record_feedback(p,"test",c,"speech",-1)
    assert personal_preferences(p)["speech"]<0
    assert c.score==50
    chat=tmp_path/"chat.jsonl"
    chat.write_text('{"at": 1, "name": "private"}\n',encoding="utf-8")
    assert read_chat(chat,100)==[{"at":1.}]
    assert not rank(chat_hints([{"at":1}]*100+[{"at":20},{"at":40}],100),100)
    assert search_transcript([TranscriptSegment(0,1,"Hallo Welt"),TranscriptSegment(2,3,"Test")],"welt")[0].start==0

def test_evidence_integrity(tmp_path):
    p=tmp_path/"cache.json";events=[ev(1,"motion")]
    store_evidence(p,"source",events,100)
    assert load_evidence(p,"source",100)==events
    with pytest.raises(ValueError):load_evidence(p,"other",100)

def test_partial_ground_truth_not_false_positive():
    vod={"duration":100,"moments":[{"id":"a","start":10,"end":20,"label":"crash","uncertain":False},
         {"id":"b","start":40,"end":50,"label":"none","uncertain":False}]}
    c=lambda a:dict(start=a-1,end=a+1,peak_at=a)
    report=evaluate(vod,[c(15),c(16),c(45),c(80)])
    assert report["hits"]==1 and report["duplicates"]==1
    assert report["unknown_predictions"]==1 and report["known_false_positives"]==1
    assert report["recall"]==1

def test_corpus_freeze_and_leakage(tmp_path):
    (tmp_path/"a.mp4").write_bytes(b"a")
    (tmp_path/"b.mp4").write_bytes(b"b")
    v=lambda name,split:dict(id=name,creator_group="same",split=split,duration=100,
        path=name+".mp4",game="game",language="de",moments=[])
    p=tmp_path/"manifest.json"
    data=dict(schema_version=1,authorized=True,vods=[v("a","development"),v("b","holdout")])
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="leakage"):freeze(p)
    data["vods"][1]["creator_group"]="other";p.write_text(json.dumps(data))
    assert "100 annotated moments" in freeze(p)["gaps"]

def test_pipeline_cache_reuses_completed_stages(tmp_path,monkeypatch):
    video=tmp_path/"video.mp4";video.write_bytes(b"video")
    info=VideoInfo(str(video),120,1920,1080,30,True)
    monkeypatch.setattr(pipeline,"probe_video",lambda p:info)
    monkeypatch.setattr(pipeline,"audio_levels",lambda *a,**kw:[-30.]*120)
    monkeypatch.setattr(pipeline,"scan_temporal_activity",lambda *a,**kw:[ev(60,"motion")])
    cache=tmp_path/"cache"
    a=pipeline.analyze_m16(str(video),cache_root=cache)
    def forbidden(*a,**kw):raise AssertionError("repeated stage")
    monkeypatch.setattr(pipeline,"audio_levels",forbidden)
    monkeypatch.setattr(pipeline,"scan_temporal_activity",forbidden)
    b=pipeline.analyze_m16(str(video),cache_root=cache)
    assert a==b and len(a.candidates)==1
    video.write_bytes(b"changed")
    with pytest.raises(AssertionError):pipeline.analyze_m16(str(video),cache_root=cache)

def test_visual_cpu_retry(monkeypatch):
    seen=[]
    def f(device):
        seen.append(device)
        if device is None:raise RuntimeError("CUDA out of memory")
        return "ok"
    with pytest.warns(RuntimeWarning):assert pipeline.visual_retry(f)=="ok"
    assert seen==[None,"cpu"]
    with pytest.raises(RuntimeError,match="corrupt"):
        pipeline.visual_retry(lambda d:(_ for _ in ()).throw(RuntimeError("corrupt")))

def test_real_ffmpeg_motion_smoke(tmp_path):
    import subprocess
    from streamclipper.media import tool_path
    source=tmp_path/"sample.mp4"
    subprocess.run([tool_path("ffmpeg"),"-v","error","-y","-f","lavfi","-i",
        "color=c=black:s=96x54:r=10:d=2","-f","lavfi","-i","color=c=white:s=96x54:r=10:d=2",
        "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0","-c:v","libx264","-pix_fmt","yuv420p",str(source)],check=True)
    result=pipeline.analyze_m16(str(source),cache_root=tmp_path/"cache")
    assert result.video.duration>=3.9
    assert result.candidates and "Heuristik" in result.candidates[0].reason
    assert result.method.startswith("m16-experimental")
    assert pipeline.analyze_m16(str(source),cache_root=tmp_path/"cache")==result

def test_relative_motion_rejects_common_translation():
    from streamclipper.object_tracking import Detection,relative_motion_evidence
    def box(x):return (x,.1,x+.1,.2)
    constant=[Detection(t,"car",.9,box(x+.02*t)) for t in (0,1,2) for x in (.1,.35,.6)]
    assert not relative_motion_evidence(constant)
    changed=[Detection(t,"car",.9,box(x+.02*t+(.07 if t==2 and x==.6 else 0)))
             for t in (0,1,2) for x in (.1,.35,.6)]
    assert relative_motion_evidence(changed)


def test_batch_tail_order_and_cancel():
    from io import BytesIO
    from PIL import Image
    from streamclipper.vision_batch import frame_batches,vision_batch_size
    from streamclipper.media import CancelledError
    buf=BytesIO();Image.new("RGB",(4,3)).save(buf,format="JPEG")
    rows=[(float(i),buf.getvalue()) for i in range(5)]
    batches=list(frame_batches(rows,2))
    assert [len(b) for b in batches]==[2,2,1]
    assert [t for b in batches for t,_ in b]==list(range(5))
    assert vision_batch_size("cpu",None)==1 and vision_batch_size("cuda",None)==4
    with pytest.raises(CancelledError):list(frame_batches(rows,2,lambda:True))

def test_acoustic_pitch_and_labels():
    import numpy as np
    from streamclipper.m16_reactions import pitch_hz,reaction_labels
    rate=16000;t=np.arange(640)/rate
    tone=.2*np.sin(2*np.pi*200*t)
    assert pitch_hz(tone,rate)==pytest.approx(200,rel=.03)
    assert pitch_hz(np.zeros(640),rate) is None
    assert reaction_labels({0:"Laughter",1:"Screaming",2:"Speech"})=={0:"Lachen",1:"Schreien"}

def test_visual_search_budget_and_deduplication():
    from streamclipper.m16_visual_search import search_positions,diverse_hits
    stamps=search_positions(21600,240,[20,21599])
    assert len(stamps)<=240 and min(stamps)<=20 and max(stamps)>21590
    assert diverse_hits([(1,5),(.9,6),(.8,20)],2)==[(1,5),(.8,20)]

def test_chat_export_discards_identity_and_checks_id(tmp_path):
    from streamclipper.m16_chat_import import parse_chat_export
    p=tmp_path/"chat.json"
    p.write_text(json.dumps({"video":{"id":"123"},"comments":[
        {"content_offset_seconds":12.5,"commenter":{"name":"private"},"message":"private"},
        {"content_offset_seconds":1000}]}),encoding="utf-8")
    assert parse_chat_export(p,100,vod_id="123")==[{"at":12.5}]
    assert read_chat(p,100)==[{"at":12.5}]
    with pytest.raises(ValueError,match="requested VOD"):parse_chat_export(p,100,vod_id="124")

def test_development_tuning_rejects_holdout_evidence():
    from streamclipper.m16_tuning import tune_weights
    def vod(id,split):
        return {"id":id,"split":split,"duration":100,"moments":[
            {"id":"m","start":10,"end":20,"label":"crash","uncertain":False}]}
    lock={"corpus_sha256":"frozen","vods":[vod("dev","development"),vod("hold","holdout")]}
    evidence={"dev":[ev(15,"visual")]}
    result=tune_weights(lock,evidence)
    assert result["development_ids"]==["dev"] and len(result["trials"])==13
    assert result==tune_weights(lock,evidence)
    with pytest.raises(ValueError,match="development VOD IDs"):
        tune_weights(lock,{**evidence,"hold":[ev(15,"visual")]})

def test_full_review_and_cluster_interval():
    from streamclipper.m16_benchmark import paired_intervals
    vod={"duration":100,"fully_reviewed":True,"moments":[
         {"id":"m","start":10,"end":20,"label":"crash","uncertain":False}]}
    report=evaluate(vod,[dict(start=10,end=20,peak_at=15),dict(start=59,end=61,peak_at=60)])
    assert report["precision_at_8"]==.125
    assert report["false_alarms_per_hour"]==pytest.approx(36)
    better={**report,"precision_at_8":.25}
    rows=[{"creator_group":str(i),"baseline":report,"variant":better} for i in range(2)]
    ci=paired_intervals(rows,repetitions=100)
    assert ci["metrics"]["precision_at_8"]["bootstrap_95"]==[.125,.125]
