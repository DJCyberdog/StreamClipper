"""Separation pipeline contract with synthetic audio and an injected backend.
No claim of real neural-model quality is made by these tests.
"""
import json
import shutil
import subprocess
from dataclasses import replace
import numpy as np
import soundfile as sf
import pytest
from streamclipper.audio_sources import inventory, SpeechSource
from streamclipper.audio_separation import separate_stream, InworldBackend, sha256_file, RATE
from streamclipper.media import CancelledError


class TestBackend:
    __test__=False
    metadata={"backend":"synthetic-test","speaker_targeted":False}
    def __init__(self):
        self.calls=[]
    def __call__(self,mono):
        self.calls.append(len(mono))
        return mono*.25


@pytest.fixture
def mix(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe required")
    n=RATE*15+731
    x=np.arange(n,dtype=np.float64)/RATE
    left=.3*np.sin(2*np.pi*440*x)
    right=.2*np.sin(2*np.pi*710*x)
    samples=np.column_stack((left,right)).astype(np.float32)
    path=tmp_path/"mix.wav"
    sf.write(path,samples,RATE,subtype="FLOAT")
    snapshot=inventory(path)
    return path,samples,SpeechSource(snapshot,snapshot.streams[0].index,"mix")


def test_stereo_overlap_residual_and_provenance(mix,tmp_path):
    path,original,selection=mix
    sha=sha256_file(path);backend=TestBackend();progress=[]
    out=separate_stream(selection,tmp_path/"stems",backend=backend,progress=progress.append)
    v,rate=sf.read(out/"voice_estimate.wav",dtype="float32",always_2d=True)
    residual,rr=sf.read(out/"residual.wav",dtype="float32",always_2d=True)
    assert rate==rr==RATE
    assert v.shape==residual.shape==original.shape
    assert len(backend.calls)==3
    assert max(backend.calls)<=8*RATE
    np.testing.assert_allclose(v[:,0],original.mean(axis=1)*.25,atol=1e-6)
    np.testing.assert_allclose(v[:,0],v[:,1],atol=1e-7)
    np.testing.assert_allclose(v+residual,original,atol=1e-6)
    assert progress[-1]==100 and progress==sorted(progress)
    m=json.loads((out/"provenance.json").read_text())
    assert m["kind"]=="reconstructed_foreground_voice_and_residual"
    assert m["backend"]["speaker_targeted"] is False
    assert m["samples"]==len(original)
    assert m["outputs"]["residual.wav"]["sha256"]==sha256_file(out/"residual.wav")
    assert sha256_file(path)==sha
    assert not list(out.glob("input-*"))


def test_cancel_and_bad_model_do_not_publish(mix,tmp_path):
    _,_,selection=mix
    root=tmp_path/"stems"
    backend=TestBackend()
    with pytest.raises(CancelledError):
        separate_stream(selection,root,backend=backend,cancelled=lambda:bool(backend.calls))
    assert not list(root.iterdir())
    class Wrong(TestBackend):
        def __call__(self,mono):return mono[:-1]
    with pytest.raises(ValueError,match="Sample-Anzahl"):
        separate_stream(selection,root,backend=Wrong())
    assert not list(root.iterdir())


def test_model_hash_checked_before_import(tmp_path):
    bad=tmp_path/"denoiser.safetensors";bad.write_bytes(b"fake")
    with pytest.raises(ValueError,match="Modellprüfsumme"):
        InworldBackend(bad)
    with pytest.raises(FileNotFoundError):
        InworldBackend(tmp_path/"missing.safetensors")


def test_declared_limits(mix,tmp_path):
    _,_,selection=mix
    with pytest.raises(ValueError,match="sechs Stunden"):
        separate_stream(replace(selection,inventory=replace(selection.inventory,duration=21601)),
                        tmp_path,backend=TestBackend())
    with pytest.raises(ValueError,match="gemischte Spur"):
        separate_stream(replace(selection,role="microphone"),tmp_path,backend=TestBackend())
    streams=tuple(replace(s,sample_rate=44100) for s in selection.inventory.streams)
    with pytest.raises(ValueError,match="48 kHz"):
        separate_stream(replace(selection,inventory=replace(selection.inventory,streams=streams)),
                        tmp_path,backend=TestBackend())


def test_large_wave_container_choice(tmp_path):
    from streamclipper.audio_separation import output_format
    assert output_format(RATE*600,2)=="WAV"
    assert output_format(RATE*21600,2)=="RF64"
    # Real small RF64 roundtrip tests library/FFprobe compatibility without
    # allocating gigabytes on CI. Whole six-hour run still a native gate.
    path=tmp_path/"rf64.wav"
    sf.write(path,np.zeros((RATE,2),dtype=np.float32),RATE,subtype="FLOAT",format="RF64")
    assert sf.info(path).format=="RF64"
    if shutil.which("ffprobe"):
        snap=inventory(path)
        assert snap.duration==1 and snap.streams[0].channels==2


def test_reconstructed_selection_and_mock_asr_vad(mix,tmp_path,monkeypatch):
    from streamclipper.reconstructed_speech import select_reconstructed,transcribe_reconstructed
    from streamclipper.speech_activity import detect_speech
    from streamclipper.models import VideoInfo,TranscriptSegment,TranscriptWord
    import streamclipper.reconstructed_speech as rs
    path,_,selection=mix
    bundle=separate_stream(selection,tmp_path/"stems",backend=TestBackend())
    chosen=select_reconstructed(selection.inventory,bundle/"voice_estimate.wav")
    assert chosen.role=="foreground_voice_estimate"
    assert "reconstructed=" in chosen.method_suffix
    with pytest.raises(ValueError):select_reconstructed(selection.inventory,bundle/"residual.wav")
    video=VideoInfo(str(path),selection.inventory.duration,320,240,25,True)
    seen=[]
    def mock_asr(v,model,**kw):
        seen.append(v.path)
        return [TranscriptSegment(1,2,"test",(TranscriptWord(1,2,"test"),))] if v.duration>=2 else []
    real_windows=rs.audio_windows
    monkeypatch.setattr(rs,"audio_windows",lambda path,**kw:real_windows(path,**{**kw,"block_seconds":5,"context_seconds":1}))
    cues=transcribe_reconstructed(video,"mock",chosen,transcriber=mock_asr,temp_root=tmp_path)
    assert [c.start for c in cues]==[1,5,10]
    assert all(c.words[0].start==c.start for c in cues)
    assert all(not __import__("pathlib").Path(p).exists() for p in seen)
    def vad(file):
        return [(0.,sf.info(file).duration)]
    spans=detect_speech(chosen,detector=vad,temp_root=tmp_path)
    assert len(spans)==1 and spans[0][0]==0 and abs(spans[0][1]-video.duration)<.002
    # Same geometry but altered content must be rejected before ASR.
    with sf.SoundFile(chosen.path,"r+") as audio:
        audio.seek(0);audio.write(np.ones((1,2),dtype=np.float32)*.5)
    with pytest.raises(ValueError,match="Prüfsumme"):
        transcribe_reconstructed(video,"mock",chosen,transcriber=mock_asr)


def test_foreground_restart_cache(mix,tmp_path):
    _,_,selection=mix
    root=tmp_path/"stems"
    backend=TestBackend()
    # First call persists its result then cancellation removes partial bundle.
    with pytest.raises(CancelledError):
        separate_stream(selection,root,backend=backend,use_cache=True,cancelled=lambda:bool(backend.calls))
    cache=root/".streamclipper-separation-cache"
    assert len(list(cache.glob("*.pcm")))==1
    assert not list(root.glob(".separation-*"))
    second=TestBackend()
    bundle=separate_stream(selection,root,backend=second,use_cache=True)
    m=json.loads((bundle/"provenance.json").read_text())
    assert m["cache"]=={"enabled":True,"reused_windows":1,"computed_windows":2}
    assert len(second.calls)==2
    third=TestBackend()
    other=separate_stream(selection,root,backend=third,use_cache=True)
    assert not third.calls
    assert sha256_file(bundle/"voice_estimate.wav")==sha256_file(other/"voice_estimate.wav")
    bad=next(cache.glob("*.pcm"))
    with bad.open("r+b") as stream:
        stream.seek(35);stream.write(b"\xff"*4)
    with pytest.raises(ValueError,match="Cache beschädigt"):
        separate_stream(selection,root,backend=TestBackend(),use_cache=True)
    targeted=TestBackend();targeted.metadata={"speaker_targeted":True}
    with pytest.raises(ValueError,match="Stimmreferenz"):
        separate_stream(selection,root,backend=targeted,use_cache=True)
