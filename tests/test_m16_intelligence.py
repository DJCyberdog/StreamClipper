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
