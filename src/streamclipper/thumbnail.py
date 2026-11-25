"""M14 thumbnail rendering from the actual composed video, never source proxies."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import math
import tempfile

from .callouts import Callout,rasterize
from .media import tool_path,probe_video,CancelledError,_publish_without_overwrite
from .render_contract import render_request

SIZES=((1280,720),(1920,1080),(1080,1920),(1080,1080))
MAX_SECONDS=60


@dataclass(frozen=True)
class ThumbnailDesign:
    width:int=1280
    height:int=720
    fit:str="crop"
    title:str=""
    foreground:str="#FFFFFF"
    background:str="#182036"
    accent:str="#F5CF52"
    x:float=.05
    y:float=.65
    box_width:float=.90
    box_height:float=.30

    def validate(self):
        if (self.width,self.height) not in SIZES or self.fit not in ("crop","fit"):
            raise ValueError("Unbekanntes Thumbnail-Format")
        Callout(text=self.title or " ",foreground=self.foreground,background=self.background,
                accent=self.accent,kind="rectangle").validate()
        if not all(math.isfinite(n) for n in (self.x,self.y,self.box_width,self.box_height)):
            raise ValueError("Ungültige Thumbnail-Position")
        if not (0<=self.x<=1 and 0<=self.y<=1 and .05<=self.box_width<=1 and .05<=self.box_height<=1
                and self.x+self.box_width<=1.000001 and self.y+self.box_height<=1.000001):
            raise ValueError("Titelbox außerhalb des Thumbnails")
        return self


def compose_thumbnail(frame,design):
    from PIL import Image,ImageOps
    design.validate()
    size=(design.width,design.height)
    frame=frame.convert("RGB")
    if design.fit=="crop":
        base=ImageOps.fit(frame,size,method=Image.Resampling.LANCZOS).convert("RGBA")
    else:
        base=Image.new("RGBA",size,design.background)
        contained=ImageOps.contain(frame,size,method=Image.Resampling.LANCZOS)
        base.paste(contained,((size[0]-contained.width)//2,(size[1]-contained.height)//2))
    if design.title.strip():
        w,h=max(2,round(size[0]*design.box_width)),max(2,round(size[1]*design.box_height))
        layer=rasterize(Callout(text=design.title,foreground=design.foreground,
                        background=design.background,accent=design.accent),w,h)
        base.alpha_composite(layer,(round(size[0]*design.x),round(size[1]*design.y)))
    return base.convert("RGB")


def capture_composed_frame(request,at,*,cancelled=None,progress=None,temp_root=None):
    """At is in output time, after scene reordering. Render entire bounded clip.
    No shorter request or different camera-analysis horizon is substituted."""
    request.validate()
    from .media import video_dimensions
    width,height=video_dimensions(request.mode,request.width,request.height)
    if max(width,height)>4096 or width*height>12_000_000:
        raise ValueError('Thumbnail-Quellbild zu groß')
    if request.duration>MAX_SECONDS:
        raise ValueError("Thumbnail Designer: Highlight auf maximal 60 Sekunden begrenzen")
    if not math.isfinite(at) or not 0<=at<request.duration:
        raise ValueError("Bildzeit liegt außerhalb des gerenderten Clips")
    root=Path(temp_root) if temp_root is not None else None
    if root is not None:root.mkdir(parents=True,exist_ok=True)
    def check():
        if cancelled and cancelled():raise CancelledError("Thumbnail abgebrochen")
    check()
    with tempfile.TemporaryDirectory(prefix="thumbnail-",dir=root) as folder:
        video=render_request(request,Path(folder)/"clip.mp4",cancelled=cancelled,progress=progress)
        check()
        info=probe_video(video)
        # Keep sampling before the final decoded frame at rounded duration.
        seek=min(at,max(0.,info.duration-1/max(1.,info.fps)))
        from .scene_restoration import run_bounded
        data=run_bounded([tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error",
            "-ss",f"{seek:.6f}","-i",str(video),"-map","0:v:0","-frames:v","1",
            "-an","-c:v","png","-f","image2pipe","pipe:1"],cancelled=cancelled,timeout=90)
        check()
        from PIL import Image
        with Image.open(BytesIO(data)) as raw:
            if raw.width*raw.height>12_000_000:raise ValueError("Thumbnail-Quellbild zu groß")
            result=raw.convert("RGB")
        return result


def save_thumbnail(frame,design,destination):
    """Publish a complete PNG/JPEG; never overwrite a previous image."""
    path=Path(destination).resolve()
    suffix=path.suffix.lower()
    if suffix not in (".png",".jpg",".jpeg"):raise ValueError("PNG oder JPEG wählen")
    if path.exists():raise FileExistsError(path)
    result=compose_thumbnail(frame,design)
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".thumbnail-",dir=path.parent) as temp:
        stage=Path(temp)/("image"+suffix)
        result.save(stage,format="PNG" if suffix==".png" else "JPEG",quality=95)
        return _publish_without_overwrite(stage,path)
