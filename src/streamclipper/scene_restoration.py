"""Experimental single-window restoration of a scene's base video.

Explicitly CFR, at most 33 source-rate frames. No audio or project track is
replaced; the resulting FFV1 is a private, temporary video-only input.
No inference is required when crop already excludes all mask zones.
"""
from __future__ import annotations

import math
from pathlib import Path
import subprocess
import time

from .media import CancelledError, tool_path, _stop_process
from .vace_inpainting import FRAME_COUNTS, restore_window


def frame_count(video,start,end):
    if not math.isfinite(video.fps) or not 1<=video.fps<=120:
        raise ValueError("Ungültige Bildrate für experimentelles Inpainting")
    if not 0<=start<end<=video.duration+.001:
        raise ValueError("Ungültiges Inpainting-Zeitfenster")
    count=math.ceil((end-start)*video.fps-1e-7)
    if not 1<=count<=max(FRAME_COUNTS):
        raise ValueError("Experimentelles Inpainting: maximal 33 Quellrate-Frames pro Szene")
    if not 64<=min(video.width,video.height) or max(video.width,video.height)>3840 or video.width*video.height>3840*2160:
        raise ValueError("Quellauflösung außerhalb der experimentellen Grenze")
    return count


def model_size(width,height):
    scale=min(1.,832/max(width,height),math.sqrt((832*480)/(width*height)))
    return max(64,int(width*scale)//16*16),max(64,int(height*scale)//16*16)


def frame_masks(video,start,count,zones):
    from PIL import Image
    result=[]
    for index in range(count):
        at=start+index/video.fps
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


def restore_scene_video(video,start,end,director,target,*,cancelled=None,
                        progress=None,restore=restore_window):
    """Prepare one full scene, including frames beyond a short preview.

    Source-rate sampling is CFR even for VFR input; VFR acceptance is open.
    Downsample only for inference. Recompose original RGB at native size.
    """
    from PIL import Image, ImageChops
    count=frame_count(video,start,end)
    masks=frame_masks(video,start,count,director.zones)
    if not any(m.getbbox() for m in masks):
        return None
    if cancelled and cancelled():
        raise CancelledError("Inpainting abgebrochen")
    fps=f"{video.fps:.9f}"
    source=run_bounded([tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error",
        "-ss",f"{start:.3f}","-i",video.path,"-map","0:v:0","-an","-sn",
        "-vf",f"fps={fps},format=rgb24","-frames:v",str(count),
        "-f","rawvideo","pipe:1"],cancelled=cancelled)
    stride=video.width*video.height*3
    if len(source)!=count*stride:
        raise ValueError("Inpainting: Quellfenster hat nicht die erwartete Frameanzahl")
    frames=[Image.frombytes("RGB",(video.width,video.height),source[i*stride:(i+1)*stride])
            for i in range(count)]
    del source
    size=model_size(video.width,video.height)
    # A conservative max-pooled mask avoids leaking small overlay pixels
    # through the downscaled conditioning. Composite at exact original mask.
    small=[f.resize(size,Image.Resampling.LANCZOS) for f in frames]
    small_masks=[m.resize(size,Image.Resampling.BOX).point(lambda p:255 if p else 0) for m in masks]
    padded=next(n for n in FRAME_COUNTS if n>=count)
    small.extend([small[-1]]*(padded-count))
    small_masks.extend([small_masks[-1]]*(padded-count))
    generated=restore(small,small_masks,director.inpaint_model,cancelled=cancelled,progress=progress)
    if len(generated)!=padded:
        raise ValueError("Inpainting: falsche Frameanzahl")
    result=[]
    for frame,mask,prediction in zip(frames,masks,generated):
        if cancelled and cancelled():
            raise CancelledError("Inpainting abgebrochen")
        if prediction.size!=size:
            raise ValueError("Inpainting: falsche Modellauflösung")
        result.append(Image.composite(prediction.resize(frame.size,Image.Resampling.BICUBIC).convert("RGB"),
                                      frame,mask).tobytes())
    target=Path(target).resolve()
    try:
        run_bounded([tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error","-n",
            "-f","rawvideo","-pixel_format","rgb24","-video_size",f"{video.width}x{video.height}",
            "-framerate",fps,"-i","pipe:0","-an","-c:v","ffv1","-pix_fmt","bgr0",str(target)],
            cancelled=cancelled,input_bytes=b"".join(result))
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target
