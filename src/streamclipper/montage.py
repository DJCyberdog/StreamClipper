"""M17 independent montage plan and bounded effects render.
Explicit source-only composition; existing editor project remains unchanged.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import math
import os
import shutil
import subprocess
import tempfile
from .media import (tool_path,probe_video,probe_audio_duration,CancelledError,
                    _stop_process,_publish_without_overwrite,concatenate_scene_parts)
from .gaming_intelligence import atomic_json
from .encoders import resolve_encoder,encoder_options

LOOKS={"neutral":"","warm":"eq=saturation=1.08:brightness=0.02,colorbalance=rs=.04:bs=-.03",
       "contrast":"eq=contrast=1.12:saturation=1.10","mono":"hue=s=0"}

@dataclass(frozen=True)
class Beat:
    start:float
    end:float
    speed:float=1.
    freeze:float=0.
    zoom:float=1.
    text:str=""
    look:str="neutral"
    lut:str=""
    sound:str=""
    sound_gain:float=-12.
    def validate(self,duration):
        if not all(math.isfinite(v) for v in (self.start,self.end,self.speed,self.freeze,self.zoom,self.sound_gain)):
            raise ValueError("Ungültige Effektparameter")
        if not 0<=self.start<self.end<=duration or self.end-self.start<.2:
            raise ValueError("Ungültiges Zeitfenster")
        if not .25<=self.speed<=4 or not 0<=self.freeze<=5 or not 1<=self.zoom<=2 or not -60<=self.sound_gain<=0:
            raise ValueError("Ungültige Effektparameter")
        if self.look not in LOOKS or len(self.text)>120 or (self.text and not self.freeze):
            raise ValueError("Standbildtext benötigt Standbild")
        if self.lut and (Path(self.lut).suffix.lower()!=".cube" or not Path(self.lut).is_file() or Path(self.lut).stat().st_size>16*1024*1024):
            raise ValueError("Lokale .cube-LUT fehlt oder ist zu groß")
        if self.sound and not Path(self.sound).is_file():raise ValueError("Lokaler Sound fehlt")
        return self
    @property
    def duration(self):return (self.end-self.start)/self.speed+self.freeze

@dataclass(frozen=True)
class Montage:
    beats:tuple[Beat,...]
    aspect:str="9:16"
    encoder:str="auto_h264"
    def validate(self,duration):
        if not 1<=len(self.beats)<=64 or self.aspect not in ("9:16","16:9","1:1"):
            raise ValueError("Ungültiger Montageplan")
        if self.encoder not in ("auto_h264","cpu_h264","nvenc_h264"):
            raise ValueError("Montage unterstützt H.264")
        for b in self.beats:b.validate(duration)
        if not .2<=sum(b.duration for b in self.beats)<=900:raise ValueError("Montage maximal 15 Minuten")
        return self

def speed_ramp(start,end,speeds=(.5,1.,2.)):
    """Piecewise constant, editable speed ramp; audio pitch preserved."""
    if not 2<=len(speeds)<=8 or not math.isfinite(start) or not math.isfinite(end) or end-start<.2*len(speeds):
        raise ValueError("Zu kurzer Rampenabschnitt")
    return tuple(Beat(start+(end-start)*i/len(speeds),start+(end-start)*(i+1)/len(speeds),speed)
                 for i,speed in enumerate(speeds))

def atempo(speed):
    if not math.isfinite(speed) or not .25<=speed<=4:raise ValueError("Ungültige Geschwindigkeit")
    factors=[]
    while speed>2:factors.append(2.);speed/=2
    while speed<.5:factors.append(.5);speed*=2
    factors.append(speed)
    return ",".join(f"atempo={s:.8f}" for s in factors)

def dimensions(aspect):
    return {"9:16":(1080,1920),"16:9":(1920,1080),"1:1":(1080,1080)}[aspect]

def build_part(video,beat,aspect,encoder,work,destination):
    """Generated filter graph only; user paths are separate argv entries."""
    w,h=dimensions(aspect)
    d=beat.duration;active=d-beat.freeze
    cmd=[tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error","-n",
         "-ss",f"{beat.start:.6f}","-t",f"{beat.end-beat.start:.6f}","-i",video.path]
    index=1
    if not video.has_audio:
        cmd+=["-f","lavfi","-i","anullsrc=r=48000:cl=stereo"];index+=1
    sound_idx=None
    if beat.sound:
        sound_idx=index;cmd+=["-i",str(Path(beat.sound).resolve())];index+=1
    overlay_idx=None
    if beat.text:
        overlay_idx=index;cmd+=["-i",str(work/"freeze-text.png")]
    filters=f"[0:v:0]setpts=(PTS-STARTPTS)/{beat.speed:.8f},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30"
    if beat.look!="neutral":filters+=","+LOOKS[beat.look]
    if beat.lut:filters+=",lut3d=file=look.cube"
    if beat.freeze:
        filters+=f",tpad=stop_mode=clone:stop_duration={beat.freeze:.6f}"
        if beat.zoom>1:
            # Static zoom on the held image only, preserving moving frames.
            cw=max(2,int(w/beat.zoom)//2*2);ch=max(2,int(h/beat.zoom)//2*2)
            filters+=f",crop=w={cw}:h={ch},scale={w}:{h}"
    filters+=",format=yuv420p[v0]"
    if overlay_idx is not None:
        filters+=f";[v0][{overlay_idx}:v:0]overlay=0:0:enable='gte(t,{active:.6f})'[v]"
    else:filters+=";[v0]null[v]"
    audio=f"[0:a:0]asetpts=PTS-STARTPTS,{atempo(beat.speed)}" if video.has_audio else "[1:a:0]anull"
    audio+=f",aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,apad,atrim=duration={d:.6f}[a0]"
    if sound_idx is not None:
        audio+=f";[{sound_idx}:a:0]asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,volume={beat.sound_gain:.2f}dB,atrim=duration={d:.6f}[s];[a0][s]amix=inputs=2:duration=first:normalize=0,alimiter=limit=.95[a]"
    else:audio+=";[a0]anull[a]"
    return cmd+["-filter_complex_threads","1","-filter_complex",filters+";"+audio,
                "-map","[v]","-map","[a]","-t",f"{d:.6f}",
                *encoder_options(encoder),"-c:a","aac","-b:a","160k","-ar","48000","-ac","2",
                "-movflags","+faststart",str(destination)]

def run_part(cmd,work,cancelled):
    with tempfile.TemporaryFile(mode="w+b") as err:
        proc=subprocess.Popen(cmd,cwd=work,stdout=subprocess.DEVNULL,stderr=err)
        try:
            while proc.poll() is None:
                if cancelled and cancelled():raise CancelledError("Montage abgebrochen")
                try:proc.wait(timeout=.2)
                except subprocess.TimeoutExpired:pass
            if proc.returncode:
                err.seek(0,os.SEEK_END);err.seek(max(0,err.tell()-2500))
                raise RuntimeError("Montage-FFmpeg: "+err.read().decode("utf-8","replace"))
        finally:_stop_process(proc)

def render_montage(video,plan,destination,*,cancelled=None,progress=None,notice=None):
    plan.validate(video.duration)
    dest=Path(destination).resolve()
    if dest.suffix.lower()!=".mp4":raise ValueError("MP4-Ausgabe erforderlich")
    if dest==Path(video.path).resolve():raise ValueError("Original darf nicht überschrieben werden")
    dest.parent.mkdir(parents=True,exist_ok=True)
    if cancelled and cancelled():raise CancelledError("Montage abgebrochen")
    video=probe_video(video.path)
    plan.validate(video.duration)
    enc=resolve_encoder(plan.encoder,tool_path("ffmpeg"))
    with tempfile.TemporaryDirectory(prefix=".montage-",dir=dest.parent) as temp:
        work=Path(temp)
        for profile in (enc.primary,)+((enc.fallback,) if enc.fallback else ()):
            parts=[]
            try:
                if notice:notice("Montage: "+profile)
                for i,beat in enumerate(plan.beats):
                    if cancelled and cancelled():raise CancelledError("Montage abgebrochen")
                    if beat.sound:probe_audio_duration(beat.sound)
                    if beat.lut:shutil.copyfile(beat.lut,work/"look.cube")
                    if beat.text:
                        from PIL import Image,ImageDraw,ImageFont
                        w,h=dimensions(plan.aspect);im=Image.new("RGBA",(w,h))
                        draw=ImageDraw.Draw(im)
                        try:font=ImageFont.truetype("DejaVuSans.ttf",max(24,w//24))
                        except OSError:font=ImageFont.load_default()
                        draw.multiline_text((w//2,int(h*.75)),beat.text,font=font,fill="white",stroke_width=3,stroke_fill="black",anchor="mm",align="center")
                        im.save(work/"freeze-text.png")
                    part=work/f"part-{i:03d}.mp4"
                    run_part(build_part(video,beat,plan.aspect,profile,work,part),work,cancelled)
                    actual=probe_video(part)
                    if abs(actual.duration-beat.duration)>.25 or (actual.width,actual.height)!=dimensions(plan.aspect) or not actual.has_audio:
                        raise ValueError("Montage-Teil hat ungültige Zeitbasis")
                    parts.append(part)
                    if progress:progress(min(95,round(95*(i+1)/len(plan.beats))))
                final=work/"montage.mp4"
                concatenate_scene_parts(parts,final,cancelled=cancelled)
                actual=probe_video(final)
                if abs(actual.duration-sum(b.duration for b in plan.beats))>max(.4,.08*len(parts)):
                    raise ValueError("Montage-Zeitbasis fehlerhaft")
                if cancelled and cancelled():raise CancelledError("Montage abgebrochen")
                result=_publish_without_overwrite(final,dest)
                if progress:progress(100)
                return result
            except CancelledError:raise
            except RuntimeError:
                if profile==enc.fallback or not enc.fallback:raise
                if notice:notice("NVENC fehlgeschlagen – kompletter CPU-Neuversuch")
                for part in work.glob("part-*.mp4"):part.unlink(missing_ok=True)
                (work/"montage.mp4").unlink(missing_ok=True)
    raise RuntimeError("Montage fehlgeschlagen")
