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
    with pytest.raises(ValueError,match="zehn Minuten"):
        separate_stream(replace(selection,inventory=replace(selection.inventory,duration=601)),
                        tmp_path,backend=TestBackend())
    with pytest.raises(ValueError,match="gemischte Spur"):
        separate_stream(replace(selection,role="microphone"),tmp_path,backend=TestBackend())
    streams=tuple(replace(s,sample_rate=44100) for s in selection.inventory.streams)
    with pytest.raises(ValueError,match="48 kHz"):
        separate_stream(replace(selection,inventory=replace(selection.inventory,streams=streams)),
                        tmp_path,backend=TestBackend())
