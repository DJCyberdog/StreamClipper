"""M16g tests: explicit GPU policies, never infer support from FFmpeg listings."""
from types import SimpleNamespace
import pytest
from streamclipper import hardware_media as hw
from streamclipper.media import CancelledError
from streamclipper.live_resources import parse_nvidia,format_sample

@pytest.mark.parametrize("policy,sparse,expected",[("legacy",False,False),("cpu",False,False),("auto",False,True),("auto",True,False),("gpu",True,True)])
def test_hardware_policy(policy,sparse,expected):
    token=hw.mode.set(policy)
    try:assert hw.prefer_gpu(sparse=sparse)==expected
    finally:hw.mode.reset(token)

def test_actual_decode_probe():
    calls=[]
    def runner(cmd,**kwargs):
        calls.append((cmd,kwargs));return SimpleNamespace(returncode=0)
    assert hw.test_decode("ffmpeg","a b.mp4",runner=runner)
    command,options=calls[0]
    assert "-hwaccel_output_format" in command and "a b.mp4" in command
    assert any("scale_cuda=" in arg for arg in command)
    assert options["timeout"]==20
    assert not hw.test_decode("ffmpeg","x",runner=lambda *a,**k:SimpleNamespace(returncode=1))

def test_fallback_once_and_cancellation():
    calls=[]
    def run(gpu):
        calls.append(gpu)
        if gpu:raise RuntimeError("device failed")
        return "cpu"
    assert hw.retry_decode(run,True)=="cpu" and calls==[True,False]
    calls.clear()
    def cancel(gpu):
        calls.append(gpu);raise CancelledError("cancel")
    with pytest.raises(CancelledError):hw.retry_decode(cancel,True)
    assert calls==[True]

def test_cpu_forces_model_device():
    torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:True))
    token=hw.mode.set("cpu")
    try:assert hw.torch_device(torch)=="cpu" and hw.torch_device(torch,"cuda")=="cpu"
    finally:hw.mode.reset(token)
    assert hw.torch_device(torch)=="cuda"

def test_missing_nvidia_readings_remain_unknown():
    rows=parse_nvidia("RTX 5060 Ti, 7, 4096, 16384, [N/A], 23\n")
    assert rows[0]["decode"] is None and rows[0]["encode"]==23
    cpu,gpu=format_sample({"cpu":None,"ram_used":None,"ram_total":None,"gpus":rows})
    assert "CPU n/a" in cpu and "4.0/16.0 GiB" in gpu and "Decode n/a" in gpu

def test_proxy_falls_back_and_removes_partial(tmp_path,monkeypatch):
    import streamclipper.media as media
    import streamclipper.encoders as enc
    target=tmp_path/"partial.mp4"; calls=[]
    monkeypatch.setattr(media,"tool_path",lambda name:name)
    monkeypatch.setattr(enc,"probe_nvenc",lambda *a:True)
    def encode(video,target,*,progress=None,cancelled=None,gpu_encode=False):
        calls.append(gpu_encode)
        if gpu_encode:
            target.write_bytes(b"broken")
            raise RuntimeError("NVENC failed")
        assert not target.exists()
        target.write_bytes(b"cpu")
    monkeypatch.setattr(media,"_encode_preview_proxy",encode)
    token=hw.mode.set("auto")
    try:media.encode_preview_proxy(None,target)
    finally:hw.mode.reset(token)
    assert calls==[True,False] and target.read_bytes()==b"cpu"
