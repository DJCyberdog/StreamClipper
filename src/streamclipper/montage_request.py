"""Versioned montage request shared by direct render, saved plans and queue."""
from dataclasses import dataclass,asdict
from pathlib import Path
import json
import os
import math
from .models import VideoInfo
from .montage import Beat,Montage,render_montage,dimensions
from .render_contract import RenderRequest
from .gaming_intelligence import atomic_json,digest

def signature(path):
    p=Path(path).resolve(strict=True)
    s=p.stat()
    if not p.is_file() or s.st_size<=0:raise ValueError("Montage-Medium fehlt")
    return (str(p),s.st_size,s.st_mtime_ns)

def bindings(video,plan,compositions):
    paths={video.path}
    for b in plan.beats:
        paths.update(p for p in (b.sound,b.lut) if p)
    # Existing render graph resolves project media. Bind only used layers.
    from .render_graph import build_render_graph
    for req in compositions:
        if req.project is None:continue
        intervals=[(s.start,s.end) for s in req.scene_plan.output_scenes] if req.scene_plan else [(req.start,req.end)]
        for a,z in intervals:
            g=build_render_graph(req.project,video,a,z)
            paths.update(x.source_path for x in (*g.audio_layers,*g.visual_layers) if x.source_path and getattr(x,"callout",None) is None)
    return tuple(sorted({signature(p) for p in paths}))

@dataclass(frozen=True)
class MontageRequest:
    video:VideoInfo
    plan:Montage
    compositions:tuple[RenderRequest,...]=()
    media_bindings:tuple[tuple[str,int,int],...]=()
    def validate(self,*,verify_media=False):
        self.plan.validate(self.video.duration,verify_media=verify_media)
        if self.compositions and len(self.compositions)!=len(self.plan.beats):
            raise ValueError("Montage-Kompositionen fehlen")
        for beat,req in zip(self.plan.beats,self.compositions):
            req.validate()
            if req.video!=self.video or (req.start,req.end)!=(beat.start,beat.end):
                raise ValueError("Montage-Komposition gehört zu anderem Abschnitt")
            if req.duration<.2 or req.preview_composition or req.preview_audio:
                raise ValueError("Ungültige Montage-Kompositionsdauer")
            if (req.width,req.height)!=dimensions(self.plan.aspect):
                raise ValueError("Montage-Komposition hat anderes Zielformat")
        if not self.media_bindings:raise ValueError("Montage-Medienbindung fehlt")
        if verify_media and bindings(self.video,self.plan,self.compositions)!=self.media_bindings:
            raise ValueError("Montage-Medien wurden geändert oder verschoben")
        return self
    @classmethod
    def create(cls,video,plan,compositions=()):
        compositions=tuple(compositions)
        return cls(video,plan,compositions,bindings(video,plan,compositions)).validate(verify_media=True)
    def render(self,destination,*,cancelled=None,progress=None,encoder_notice=None):
        self.validate(verify_media=True)
        return render_montage(self.video,self.plan,destination,cancelled=cancelled,
            progress=progress,notice=encoder_notice,compositions=self.compositions or None,
            verify_sources=lambda:self.validate(verify_media=True))

def snapshot(request):
    request.validate()
    return {"kind":"montage-v1","video":asdict(request.video),"plan":asdict(request.plan),
            "compositions":[asdict(r) for r in request.compositions],
            "media_bindings":request.media_bindings}

def rehydrate(doc):
    from .render_queue import _rehydrate
    if doc.get("kind")!="montage-v1":raise ValueError("Unbekannter Montageplan")
    p=doc["plan"]
    plan=Montage(tuple(Beat(**b) for b in p["beats"]),p["aspect"],p["encoder"])
    if any(r.get("kind") for r in doc["compositions"]):raise ValueError("Verschachtelte Montage verboten")
    return MontageRequest(VideoInfo(**doc["video"]),plan,tuple(_rehydrate(r) for r in doc["compositions"]),
                          tuple(tuple(x) for x in doc["media_bindings"])).validate()

def save_plan(path,request):
    path=Path(path).resolve()
    if path.suffix.lower()!=".json":raise ValueError("JSON-Montageplan erforderlich")
    request.validate(verify_media=True)
    if path.exists():
        if not path.is_file() or path.stat().st_size>20*1024*1024:raise ValueError("Bestehende Datei nicht als Montageplan erkannt")
        old=json.loads(path.read_text(encoding="utf-8"))
        if old.get("schema")!="streamclipper-montage-1":raise ValueError("Keine Montageplandatei: Überschreiben verweigert")
    doc=snapshot(request)
    payload={"schema":"streamclipper-montage-1","request":doc,"sha256":digest(doc)}
    if len(json.dumps(payload,ensure_ascii=False).encode("utf-8"))>20*1024*1024:raise ValueError("Montageplan zu groß")
    atomic_json(path,payload)

def load_plan(path):
    path=Path(path)
    if path.stat().st_size>20*1024*1024:raise ValueError("Montageplan zu groß")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema")!="streamclipper-montage-1" or doc.get("sha256")!=digest(doc["request"]):
        raise ValueError("Montageplan beschädigt")
    return rehydrate(doc["request"]).validate(verify_media=True)
