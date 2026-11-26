"""Continuous linear speed in output time, shared inverse video/audio mapping.

Pitch changes naturally with playback speed. Pitch-preserving stepped ramps
remain a separate option. No optical-flow interpolation or pitch correction
is claimed for this path.
"""
import math
from pathlib import Path

def duration(length,initial,final):
    if not all(math.isfinite(v) for v in (length,initial,final)) or length<=0 or not .25<=initial<=4 or not .25<=final<=4:
        raise ValueError("Ungültige kontinuierliche Tempo-Kurve")
    return 2*length/(initial+final)

def source_time(t,length,initial,final):
    d=duration(length,initial,final)
    return initial*t+(final-initial)*t*t/(2*d)

def output_time(s,length,initial,final):
    d=duration(length,initial,final)
    return 2*s/(initial+math.sqrt(max(0.,initial*initial+2*(final-initial)*s/d)))

def setpts_expression(length,initial,final):
    d=duration(length,initial,final)
    # Stable inverse, including constant speed; AVExpr uses comma escaping
    # inside quoted setpts expression.
    s="((PTS-STARTPTS)*TB)"
    return f"2*{s}/({initial:.12g}+sqrt(max(0,{initial*initial:.12g}+{2*(final-initial)/d:.12g}*{s})))/TB"

def render_audio(video,beat,work,cancelled=None):
    """Decode and low-pass once; blockwise sample-rate warp using same time map."""
    import numpy as np
    from .media import tool_path,CancelledError
    from .montage import run_part
    work=Path(work)
    raw=work/"curve-input.f32";out=work/"curve-output.f32"
    for p in (raw,out):p.unlink(missing_ok=True)
    rate=48000
    length=beat.end-beat.start
    d=duration(length,beat.speed,beat.end_speed)
    cutoff=min(20000.,.45*rate/max(1.,beat.speed,beat.end_speed))
    run_part([tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error","-n",
        "-ss",f"{beat.start:.9f}","-t",f"{length:.9f}","-i",video.path,"-map","0:a:0",
        "-vn","-ac","2","-ar",str(rate),"-af",f"lowpass=f={cutoff:.4f}",
        "-f","f32le",str(raw)],work,cancelled)
    count=raw.stat().st_size//8
    if count<1:raise ValueError("Tempo-Kurve: keine Audiosamples")
    src=np.memmap(raw,dtype="<f4",mode="r",shape=(count,2))
    try:
        with out.open("wb") as f:
            for a in range(0,round(d*rate),65536):
                if cancelled and cancelled():raise CancelledError("Tempo-Kurve abgebrochen")
                t=np.arange(a,min(a+65536,round(d*rate)),dtype=np.float64)/rate
                pos=source_time(t,length,beat.speed,beat.end_speed)*rate
                idx=np.floor(pos).astype(np.int64)
                valid=(idx>=0)&(idx<count)
                lo=np.clip(idx,0,count-1);hi=np.minimum(lo+1,count-1)
                mix=(pos-idx)[:,None]
                data=(src[lo]*(1-mix)+src[hi]*mix).astype("<f4")
                data[~valid]=0.
                f.write(data.tobytes())
    finally:
        del src
        raw.unlink(missing_ok=True)
    return out
