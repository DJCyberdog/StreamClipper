"""Experimental overlapping-window restoration of a scene's base video.

Explicitly CFR, at most 600 source-rate frames per scene. No audio or project track is
replaced; the resulting FFV1 is a private, temporary video-only input.
No inference is required when crop already excludes all mask zones.
"""
from __future__ import annotations

import math
import shutil
import tempfile
import os
from pathlib import Path
import subprocess
import time

from .media import CancelledError, tool_path, _stop_process
from .vace_inpainting import FRAME_COUNTS, restore_window, local_pipeline_factory


MAX_SCENE_FRAMES = 600
WINDOW = 33
OVERLAP = 8


def frame_count(video,start,end):
    if not math.isfinite(video.fps) or not 1<=video.fps<=120:
        raise ValueError("Ungültige Bildrate für experimentelles Inpainting")
    if not 0<=start<end<=video.duration+.001:
        raise ValueError("Ungültiges Inpainting-Zeitfenster")
    count=math.ceil((end-start)*video.fps-1e-7)
    if not 1<=count<=MAX_SCENE_FRAMES:
        raise ValueError(f"Experimentelles Inpainting: maximal {MAX_SCENE_FRAMES} Quellrate-Frames pro Szene")
    if not 64<=min(video.width,video.height) or max(video.width,video.height)>1920 or video.width*video.height>1920*1080:
        raise ValueError("Quellauflösung außerhalb der experimentellen Grenze")
    return count


def model_size(width,height):
    scale=min(1.,832/max(width,height),math.sqrt((832*480)/(width*height)))
    return max(64,int(width*scale)//16*16),max(64,int(height*scale)//16*16)


def frame_masks(video,start,count,zones,*,offset=0):
    from PIL import Image
    result=[]
    for index in range(count):
        at=start+(offset+index)/video.fps
        mask=Image.new("L",(video.width,video.height),0)
        for zone in zones:
            if not zone.enabled or not zone.mask:
                continue
            if zone.start is not None and not zone.start<=at<zone.end:
                continue
            x,y,w,h=zone.region
            mask.paste(255,(int(x*video.width),int(y*video.height),
                          min(video.width,math.ceil((x+w)*video.width)),
                          min(video.height,math.ceil((y+h)*video.height))))
        result.append(mask)
    return result


def run_bounded(cmd, *, cancelled=None, input_bytes=None, timeout=90):
    """Bounded output for the caller's prevalidated small frame count."""
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    deadline=time.monotonic()+timeout
    try:
        first=True
        while True:
            if cancelled and cancelled():
                raise CancelledError("Inpainting-Vorbereitung abgebrochen")
            if time.monotonic()>deadline:
                raise RuntimeError("Inpainting-FFmpeg-Zeitlimit überschritten")
            try:
                output,errors=proc.communicate(input=input_bytes if first else None,timeout=.2)
                break
            except subprocess.TimeoutExpired:
                first=False
        if proc.returncode:
            raise RuntimeError("Inpainting-FFmpeg: "+errors[-2000:].decode("utf-8","replace"))
        return output
    finally:
        _stop_process(proc)


def window_ranges(count):
    if not 1<=count<=MAX_SCENE_FRAMES:
        raise ValueError("Ungültige Anzahl Szenenframes")
    start=0
    while True:
        end=min(count,start+WINDOW)
        yield start,end
        if end==count:
            break
        start=end-OVERLAP


def _check(cancelled):
    if cancelled and cancelled():
        raise CancelledError("Inpainting abgebrochen")


def restore_scene_video(video,start,end,director,target,*,cancelled=None,
                        progress=None,restore=restore_window):
    """Decode once to bounded disk storage, restore overlapping windows.

    CFR normalization is explicit: output frame i maps to start+i/fps.\n    Blend only the generated region in the shared frames; the source RGB
    context remains byte-exact before encoding. A single local pipeline is
    reused. No claim of temporal model consistency across windows.
    """
    from PIL import Image
    count=frame_count(video,start,end)
    zones=tuple(z for z in director.zones if z.enabled and z.mask)
    if not any(z.start is None or any(z.start<=start+i/video.fps<z.end
               for i in range(count)) for z in zones):
        return None
    _check(cancelled)
    target=Path(target).resolve()
    if target.exists():
        raise FileExistsError(target)
    stride=video.width*video.height*3
    required=count*stride*3+64*1024*1024
    if shutil.disk_usage(target.parent).free<required:
        raise OSError("Nicht genug temporärer Speicher für Inpainting")
    fps=f"{video.fps:.9f}"
    size=model_size(video.width,video.height)
    ranges=tuple(window_ranges(count))
    factory=local_pipeline_factory() if restore is restore_window else None
    with tempfile.TemporaryDirectory(prefix=".restore-",dir=target.parent) as folder:
        raw=Path(folder)/"source.rgb"
        output=Path(folder)/"restored.rgb"
        staged=Path(folder)/"restored.mkv"
        run_bounded([tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error","-n",
            "-ss",f"{start:.3f}","-i",video.path,"-map","0:v:0","-an","-sn",
            "-vf",f"fps={fps}:start_time=0:round=near,format=rgb24","-frames:v",str(count),
            "-f","rawvideo",str(raw)],cancelled=cancelled,timeout=180)
        observed=raw.stat().st_size
        # At the actual EOF the FPS filter can round the last sample down.
        # Only allow one explicit held frame, never conceal a missing interval.
        if (observed==(count-1)*stride and count>1
                and abs(video.duration-end)<=1/video.fps):
            with raw.open("r+b") as stream:
                stream.seek(-stride,os.SEEK_END)
                last=stream.read(stride)
                stream.write(last)
        elif observed!=count*stride:
            raise ValueError("Inpainting: Quellfenster hat nicht die erwartete Frameanzahl")
        pending=[]
        written=0
        with raw.open("rb") as source,output.open("xb") as sink:
            for index,(left,right) in enumerate(ranges):
                _check(cancelled)
                source.seek(left*stride)
                frames=[]
                for _ in range(left,right):
                    data=source.read(stride)
                    if len(data)!=stride:
                        raise ValueError("Inpainting: Quelldatei unvollständig")
                    frames.append(Image.frombytes("RGB",(video.width,video.height),data))
                # Use absolute frame indices to avoid round-off at window edges.
                masks=frame_masks(video,start,right-left,zones,offset=left)
                if any(m.getbbox() for m in masks):
                    small=[f.resize(size,Image.Resampling.LANCZOS) for f in frames]
                    small_masks=[m.resize(size,Image.Resampling.BOX).point(lambda p:255 if p else 0) for m in masks]
                    padded=next(n for n in FRAME_COUNTS if n>=len(frames))
                    small.extend([small[-1]]*(padded-len(frames)))
                    small_masks.extend([small_masks[-1]]*(padded-len(frames)))
                    def report(step,steps):
                        if progress:
                            progress(index*steps+step,len(ranges)*steps)
                    kwargs=dict(cancelled=cancelled,progress=report)
                    if factory is not None:
                        kwargs["pipeline_factory"]=factory
                    generated=restore(small,small_masks,director.inpaint_model,**kwargs)
                    if len(generated)!=padded or any(p.size!=size for p in generated):
                        raise ValueError("Inpainting: falsche Modell-Frameanzahl oder Auflösung")
                    result=[Image.composite(p.resize(f.size,Image.Resampling.BICUBIC).convert("RGB"),f,m)
                            for f,m,p in zip(frames,masks,generated)]
                else:
                    result=frames.copy()
                # Both windows see exactly the same source samples and masks.
                for j,previous in enumerate(pending):
                    alpha=(j+1)/(len(pending)+1)
                    mixed=Image.blend(previous,result[j],alpha)
                    result[j]=Image.composite(mixed,frames[j],masks[j])
                keep=0 if index==len(ranges)-1 else OVERLAP
                emit=len(result)-keep
                for frame in result[:emit]:
                    _check(cancelled)
                    sink.write(frame.tobytes())
                    written+=1
                pending=result[emit:]
                if progress:
                    progress((index+1)*20,len(ranges)*20)
        if written!=count or output.stat().st_size!=count*stride:
            raise ValueError("Inpainting: falsche Ausgabeframeanzahl")
        _check(cancelled)
        run_bounded([tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error","-n",
            "-f","rawvideo","-pixel_format","rgb24","-video_size",f"{video.width}x{video.height}",
            "-framerate",fps,"-i",str(output),"-an","-c:v","ffv1","-pix_fmt","bgr0",str(staged)],
            cancelled=cancelled,timeout=180)
        _check(cancelled)
        # Hard-link is atomic and fails if target already exists.
        os.link(staged,target)
    return target
