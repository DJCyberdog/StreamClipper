"""Reference adapter contracts; injected model does not measure TSE quality."""
from types import SimpleNamespace
import sys
import numpy as np
import soundfile as sf
import pytest
from streamclipper.target_speaker import VoxLockBackend,load_reference,FILES
from streamclipper.media import CancelledError

@pytest.fixture
def reference(tmp_path):
    path=tmp_path/"reference.wav"
    x=.2*np.sin(2*np.pi*230*np.arange(5*48000)/48000)
    sf.write(path,x,48000,subtype="FLOAT")
    return path

def test_reference_validation(reference,tmp_path):
    with pytest.raises(ValueError,match="autorisierte"):load_reference(reference)
    assert load_reference(reference,consent=True).shape==(80000,)
    silent=tmp_path/"silent.wav"
    sf.write(silent,np.zeros(48000*3),48000)
    with pytest.raises(ValueError,match="stumm"):load_reference(silent,consent=True)
    short=tmp_path/"short.wav"
    sf.write(short,np.zeros(16000),16000)
    with pytest.raises(ValueError,match="3–30"):load_reference(short,consent=True)

def test_explicit_reference_and_sample_count(reference,tmp_path,monkeypatch):
    import importlib.metadata
    modeldir=tmp_path/"models";modeldir.mkdir()
    for name in FILES:(modeldir/name).write_bytes(b"x"*2048)
    calls=[]
    class Fake:
        def __init__(self,**kwargs):calls.append(kwargs)
        def isolate(self,audio,*,sample):
            assert sample.shape==(80000,)
            calls.append(len(audio))
            return audio*.5
    monkeypatch.setattr(importlib.metadata,"version",lambda name:"1.3.0")
    monkeypatch.setitem(sys.modules,"voxlock",SimpleNamespace(VoxLock=Fake))
    model=VoxLockBackend(modeldir,reference,consent=True)
    assert calls[0]=={"model_dir":str(modeldir.resolve()),"precision":"int8","threads":2}
    for n in (1,731,48000,384000):
        x=np.ones(n,dtype=np.float32)*.2
        result=model(x)
        assert result.shape==x.shape and np.isfinite(result).all()
    assert model.metadata["speaker_targeted"] is True
    assert model.metadata["publisher_hash_verified"] is False
    assert str(reference) not in str(model.metadata)
    assert not any(k in model.metadata for k in ("reference_path","reference_hash","embedding"))
    model.model.isolate=lambda audio,**kw:audio[:-1]
    with pytest.raises(ValueError,match="ungültige Samples"):model(np.ones(48000,dtype=np.float32))

def test_missing_model_and_cancel(reference,tmp_path):
    with pytest.raises(ValueError,match="unvollständig"):
        VoxLockBackend(tmp_path,reference,consent=True)
    for name in FILES:(tmp_path/name).write_bytes(b"x"*2048)
    with pytest.raises(CancelledError):
        VoxLockBackend(tmp_path,reference,consent=True,cancelled=lambda:True)
