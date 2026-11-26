"""Scoped media hardware preference; never modify global system environment."""
from contextvars import ContextVar
import subprocess
from pathlib import Path

mode=ContextVar("media_hardware_mode",default="legacy")
phase_notice=ContextVar("media_phase_notice",default=None)
MODES=("legacy","auto","gpu","cpu")

def notify(text):
    fn=phase_notice.get()
    if fn:fn(text)
    print(text,flush=True)

def prefer_gpu(*,sparse=False):
    value=mode.get()
    return value=="gpu" or (value=="auto" and not sparse)

def torch_device(torch,override=None):
    if mode.get()=="cpu":return "cpu"
    return override or ("cuda" if torch.cuda.is_available() else "cpu")

def decode_options(width,height):
    if not (0<width<=4096 and (height==-2 or 0<height<=4096)):
        raise ValueError("Invalid CUDA resize")
    return ["-hwaccel","cuda","-hwaccel_output_format","cuda"], (
        f"scale_cuda={width}:{height}:format=nv12,hwdownload,format=nv12")

def test_decode(ffmpeg,source,*,runner=subprocess.run):
    """Real source frame and CUDA scaling, not just build capability listing."""
    prefix,filters=decode_options(96,54)
    try:
        result=runner([ffmpeg,"-hide_banner","-nostdin","-loglevel","error",
                    *prefix,"-i",str(source),"-map","0:v:0","-an","-sn",
                    "-frames:v","1","-vf",filters,"-f","null","-"],
                    capture_output=True,timeout=20,check=False)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def choose_decode(ffmpeg,video,*,sparse=False):
    if not prefer_gpu(sparse=sparse):return False
    available=test_decode(ffmpeg,video.path)
    if not available:notify("NVDEC/CUDA-Filter nicht nutzbar – CPU-Fallback")
    return available

def retry_decode(fn,enabled):
    """Retry only hardware-stage runtime errors, not cancellation or invalid input."""
    from .media import CancelledError
    if not enabled:return fn(False)
    try:return fn(True)
    except CancelledError:raise
    except RuntimeError:
        notify("GPU-Videodekodierung fehlgeschlagen – Neustart auf CPU")
    return fn(False)
