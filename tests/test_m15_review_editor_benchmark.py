"""M15c–f: source-bound review, processed audio and benchmark contracts."""
from dataclasses import replace
from pathlib import Path
import json
import shutil
import numpy as np
import soundfile as sf
import pytest
from streamclipper.models import VideoInfo,AnalysisResult,TranscriptSegment,TranscriptWord
from streamclipper.transcript_editor import apply_segment_changes,load_analysis_report
from streamclipper.speech_timing import propose_timings,apply_proposals
from streamclipper.asr_quality import ASROptions,flags,archive_raw,retry_cue,accept_retry
from streamclipper.audio_editor import MixOptions,import_pair,create_processed_mix,pause_suggestions
from streamclipper.audio_sources import inventory,SpeechSource
from streamclipper.audio_separation import separate_stream,sha256_file
from streamclipper.reconstructed_speech import select_reconstructed
from streamclipper.editor_project import initial_project,save_project,load_project
from streamclipper.edit_history import WorkspaceHistory
from streamclipper.project_checkpoints import create_checkpoint,load_checkpoint
from streamclipper.render_graph import build_render_graph
from streamclipper.speech_benchmark import text_errors,cue_errors,signal_metrics,evaluate_manifest

class Estimate:
    metadata={"backend":"test-only","speaker_targeted":False}
    def __call__(self,mono):return mono*.4

@pytest.fixture
def source(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):pytest.skip("FFmpeg required")
    path=tmp_path/"source.wav";t=np.arange(48000*4)/48000
    sf.write(path,(.2*np.sin(2*np.pi*440*t)+.08*np.sin(2*np.pi*710*t)).astype(np.float32),48000,subtype="FLOAT")
    snapshot=inventory(path);selection=SpeechSource(snapshot,snapshot.streams[0].index,"mix")
    bundle=separate_stream(selection,tmp_path/"stems",backend=Estimate())
    return VideoInfo(str(path),4,320,240,25,True),bundle

def test_edge_word_review_and_manual_protection_roundtrip(tmp_path):
    path=tmp_path/"original.mp4";path.write_bytes(b"source")
    video=VideoInfo(str(path),10,320,240,25,True)
    raw=TranscriptSegment(0,5,"Das klappt",(TranscriptWord(0,1,"Das"),TranscriptWord(1,5,"klappt")),"asr",-1.2,.1,1.)
    result=AnalysisResult(video,[],transcript=[raw])
    assert not propose_timings(result.transcript,[(0,2)],duration=10)
    p=propose_timings(result.transcript,[(0,2)],duration=10,trim_outer_words=True)[0]
    assert p.after.end==pytest.approx(2.12)
    assert p.after.words[-1].end==pytest.approx(2.12)
    assert p.after.words[-1].origin=="estimated"
    corrected=apply_proposals(result,[p]);assert corrected.transcript[0].review_origin=="vad"
    history=WorkspaceHistory();assert history.record_analysis(result,corrected)
    assert history.undo(corrected,None)[0]==result
    assert history.redo(result,None)[0]==corrected
    manual=apply_segment_changes(result,0,"0","4","Das klappt")
    assert manual.transcript[0].review_origin=="manual"
    assert not propose_timings(manual.transcript,[(0,2)],duration=10,trim_outer_words=True)
    with pytest.raises(ValueError):apply_proposals(manual,[p])
    target=tmp_path/"edited.json";manual.save_json(target)
    assert load_analysis_report(target,path)==manual
    project=initial_project(video);cp=create_checkpoint(project,"review",manual,root=tmp_path/"cp")
    assert load_checkpoint(video,cp.id,root=tmp_path/"cp")[1]==manual
    raw_path=archive_raw(result,tmp_path/"raw")
    assert archive_raw(result,tmp_path/"raw")==raw_path
    assert json.loads(raw_path.read_text())["transcript"][0]["end"]==5
    assert raw_path!=archive_raw(corrected,tmp_path/"raw")

def test_asr_flags_retry_source_and_manual_adoption(source,tmp_path):
    video,bundle=source
    selection=select_reconstructed(inventory(video.path),bundle/"voice_estimate.wav")
    cue=TranscriptSegment(1,3,"ja ja ja",review_origin="asr",avg_logprob=-1.2)
    result=AnalysisResult(video,[],method="m"+selection.method_suffix,transcript=[cue])
    assert "Textwiederholung" in flags(cue)
    assert "niedriger Logprob" in flags(cue)
    calls=[]
    def fake(v,model,**kw):
        calls.append((v.path,kw["quality_options"].whisper_kwargs()))
        assert v.duration==4
        return [TranscriptSegment(1,2,"Genau")]
    text=retry_cue(result,0,selection,"local",transcriber=fake,options=ASROptions("de","GTA"))
    assert text=="Genau"
    assert calls[0][1]=={"beam_size":5,"language":"de","hotwords":"GTA"}
    assert not Path(calls[0][0]).exists()
    updated=accept_retry(result,0,cue,text)
    assert updated.transcript[0].review_origin=="manual" and updated.transcript[0].text=="Genau"
    assert not flags(updated.transcript[0])
    with pytest.raises(ValueError):accept_retry(updated,0,cue,"falsch")

def test_pair_mix_and_graph(source,tmp_path):
    video,bundle=source;project=initial_project(video)
    path=bundle/"voice_estimate.wav";digest=sha256_file(path)
    pair=import_pair(project,path,MixOptions(-3,-8))
    assert not pair.base_audio_enabled and project.base_audio_enabled
    graph=build_render_graph(pair,video,1,3)
    assert not graph.base_audio_enabled and [layer.gain_db for layer in graph.audio_layers]==[-3,-8]
    assert all(layer.source_start==1 and layer.source_end==3 for layer in graph.audio_layers)
    save_project(pair,root=tmp_path/"p");assert load_project(video,root=tmp_path/"p")==pair
    with pytest.raises(ValueError):import_pair(pair,path)
    # Real FFmpeg mix with sidechain/cleanup, kept as one immutable local asset.
    baked=create_processed_mix(project,path,tmp_path/"mix",MixOptions(0,-6,True,True,True))
    output=Path(baked.items[-1].media_path)
    assert output.is_file() and abs(sf.info(output).duration-4)<.002
    assert len(build_render_graph(baked,video,0,4).audio_layers)==1
    assert sha256_file(path)==digest
    manifest=json.loads((output.parent/"mix.json").read_text())
    assert manifest["options"]["ducking"] and manifest["output_sha256"]==sha256_file(output)
    assert isinstance(manifest["measured_wav_loudness"]["true_peak_dbtp"],float)
    assert pause_suggestions([(0,1),(2.5,3)],4)==((1,2.5),)

def test_benchmark_synthetic_metrics_and_split_guard(tmp_path):
    t=np.arange(48000)/48000
    ref=.2*np.sin(2*np.pi*440*t);noise=.2*np.sin(2*np.pi*710*t)
    for name,x in (("ref",ref),("mix",ref+noise),("estimate",ref+.1*noise),("noise",noise)):
        sf.write(tmp_path/(name+".wav"),x,48000,subtype="FLOAT")
    base=signal_metrics(tmp_path/"ref.wav",tmp_path/"mix.wav",tmp_path/"noise.wav")
    variant=signal_metrics(tmp_path/"ref.wav",tmp_path/"estimate.wav",tmp_path/"noise.wav")
    assert abs(base["si_sdr_db"])<.01 and variant["si_sdr_db"]==pytest.approx(20,abs=.01)
    assert variant["interference_projection_ratio"]<base["interference_projection_ratio"]
    assert text_errors("eins zwei","eins drei")["wer"]==.5
    assert text_errors("","phantom")["unexpected_words"]==1
    ref_cues=[{"start":0,"end":.5,"text":"eins zwei"}]
    hyp=[{"start":0,"end":.9,"text":"eins zwei"}]
    assert cue_errors(ref_cues,hyp)["mean_trailing_seconds"]==pytest.approx(.4)
    case={"id":"synthetic","split":"holdout","speaker_group":"not-a-person",
          "language":"de","conditions":["synthetic tones"],"reference_voice":"ref.wav",
          "mix":"mix.wav","estimate":"estimate.wav","interferer":"noise.wav","reference_cues":ref_cues}
    manifest=tmp_path/"cases.json";doc={"schema_version":1,"evidence_kind":"synthetic","cases":[case]}
    manifest.write_text(json.dumps(doc))
    report=evaluate_manifest(manifest)
    assert report["quality_acceptance"]=="NOT_EVALUATED"
    assert report["cases"][0]["si_sdr_improvement_db"]==pytest.approx(20,abs=.01)
    doc["cases"].append({**case,"id":"other","split":"development"})
    manifest.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="beiden Splits"):evaluate_manifest(manifest)


def test_handoff_distinguishes_uncertain_estimates(tmp_path):
    from streamclipper.speech_handoff import handoff
    video=VideoInfo(str(tmp_path/"source.mp4"),10,320,240,25,True)
    cue=TranscriptSegment(1,2,"Hallo",review_origin="vad")
    result=AnalysisResult(video,[],method="m|asr:reconstructed=target_voice_estimate,stream=1,sha256="+"a"*64,transcript=[cue])
    doc=handoff(result);event=doc["events"][0]
    assert event["source_kind"]=="target_voice_estimate"
    assert event["timing_origin"]=="vad" and event["estimated_word_times"]
    assert event["speaker_identity_verified"] is False
    assert handoff(replace(result,transcript=[replace(cue,end=2.5)]))["transcript_sha256"]!=doc["transcript_sha256"]

def test_whisper_model_reuse_and_options(tmp_path,monkeypatch):
    import sys
    from types import ModuleType,SimpleNamespace
    from streamclipper.semantic import transcribe_video
    constructors=[];calls=[]
    class Fake:
        def __init__(self,*a,**kw):constructors.append(kw)
        def transcribe(self,path,**kw):
            calls.append(kw)
            return iter([SimpleNamespace(start=0.,end=1.,text="Hallo",words=[],avg_logprob=-1.2)]),None
    module=ModuleType("faster_whisper");module.WhisperModel=Fake
    monkeypatch.setitem(sys.modules,"faster_whisper",module)
    monkeypatch.setenv("STREAMCLIPPER_WHISPER_DEVICE","cpu")
    video=VideoInfo(str(tmp_path/"x.wav"),2,1,1,1,True)
    cache={}
    for i in range(2):
        result=transcribe_video(video,str(tmp_path),model_cache=cache,quality_options=ASROptions("de","GTA"))
        assert result[0].review_origin=="asr" and result[0].avg_logprob==-1.2
    assert len(constructors)==1 and len(calls)==2
    assert calls[0]["beam_size"]==5 and calls[1]["hotwords"]=="GTA"
