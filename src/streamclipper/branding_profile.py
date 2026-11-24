"""Reusable local branding profiles. Explicit application to one highlight."""
from dataclasses import dataclass,asdict,replace
from pathlib import Path
import json
import math
import tempfile
import subprocess

from .caption_style import CaptionStyle,caption_style_from_dict
from .editor_project import add_item,set_caption_style
from .media import probe_still_image,_publish_without_overwrite


@dataclass(frozen=True)
class BrandProfile:
    name:str
    captions:CaptionStyle=CaptionStyle()
    logo:str=""
    x:float=.76
    y:float=.04
    width:float=.20
    height:float=.15
    opacity:float=1.

    def validate(self):
        if not isinstance(self.name,str) or not 1<=len(self.name.strip())<=80 or any(ord(c)<32 for c in self.name):
            raise ValueError("Ungültiger Branding-Profilname")
        self.captions.validate()
        if not isinstance(self.logo,str) or len(self.logo)>4096 or (self.logo and (
            not Path(self.logo).is_absolute() or "://" in self.logo or
            Path(self.logo).suffix.lower() not in (".png",".jpg",".jpeg",".webp")
            or any(ord(c)<32 for c in self.logo))):
            raise ValueError("Logo muss eine lokale Bilddatei sein")
        if not all(math.isfinite(n) for n in (self.x,self.y,self.width,self.height,self.opacity)):
            raise ValueError("Ungültige Logo-Geometrie")
        if not (0<=self.x<=1 and 0<=self.y<=1 and .05<=self.width<=1 and .05<=self.height<=1
                and self.x+self.width<=1.000001 and self.y+self.height<=1.000001 and 0<=self.opacity<=1):
            raise ValueError("Logo außerhalb des Ausgabebildes")
        return self


def save_profile(profile,destination):
    profile.validate()
    path=Path(destination).resolve()
    if path.suffix.lower()!=".json":raise ValueError("Branding-Profil benötigt .json")
    if path.exists():raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".branding-",dir=path.parent) as folder:
        stage=Path(folder)/"profile.json"
        stage.write_text(json.dumps({"version":1,"profile":asdict(profile)},ensure_ascii=False,
                                    indent=2,allow_nan=False),encoding="utf-8")
        return _publish_without_overwrite(stage,path)


def load_profile(path):
    path=Path(path)
    if path.stat().st_size>64*1024:raise ValueError("Branding-Profil zu groß")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc,dict) or doc.get("version")!=1 or not isinstance(doc.get("profile"),dict):
        raise ValueError("Unbekanntes Branding-Profil")
    fields=doc["profile"]
    try:return BrandProfile(**{**fields,"captions":caption_style_from_dict(fields["captions"])}).validate()
    except (TypeError,KeyError,AttributeError) as exc:raise ValueError("Branding-Profil ungültig") from exc


def apply_profile(project,profile,start,end,track_id=None):
    """One immutable edit: caption style + optional logo on selected interval.
    Never copy/delete assets. Exact repeated application is idempotent."""
    profile.validate()
    if not 0<=start<end<=project.source.duration+.001:raise ValueError("Ungültiger Branding-Zeitbereich")
    result=set_caption_style(project,profile.captions)
    if not profile.logo:return result
    try:
        probe_still_image(profile.logo)
    except subprocess.SubprocessError as exc:
        raise ValueError('Logo konnte nicht geprüft werden') from exc
    track=next((t for t in project.tracks if t.id==track_id and t.kind=="overlay" and not t.locked and not t.muted),None)
    if track is None:raise ValueError("Entsperrte, aktive Grafikspur für Logo auswählen")
    match=lambda i:(i.track_id==track.id and i.media_path==profile.logo and i.source_start==0
        and abs(i.source_end-(end-start))<1e-6 and abs(i.timeline_start-start)<1e-6
        and (i.x,i.y,i.width,i.height,i.opacity)==(profile.x,profile.y,profile.width,profile.height,profile.opacity))
    if any(match(i) for i in project.items):return result
    return add_item(result,track.id,0,end-start,start,profile.name[:120],
                    media_path=profile.logo,x=profile.x,y=profile.y,width=profile.width,height=profile.height,
                    opacity=profile.opacity)
