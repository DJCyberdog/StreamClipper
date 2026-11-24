"""M13b/c/d: immutable camera and overlay decisions in source coordinates.

All timestamps are absolute source seconds; preview excerpts therefore retain
the same curve as full export. No model downloads or inferred semantic labels.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from .scene_camera import CameraKeyframe

KINDS = ("hud", "topbar", "chat", "facecam", "alert", "graphic")
MAX_ZONES = 24
MAX_KEYS = 40
Rect = tuple[float,float,float,float]


def valid_rect(rect):
    return (isinstance(rect, tuple) and len(rect)==4
            and all(type(v) in (int,float) and math.isfinite(v) for v in rect)
            and 0 <= rect[0] < 1 and 0 <= rect[1] < 1
            and .01 <= rect[2] <= 1 and .01 <= rect[3] <= 1
            and rect[0]+rect[2] <= 1.000000001 and rect[1]+rect[3] <= 1.000000001)


@dataclass(frozen=True)
class OverlayZone:
    kind: str
    region: Rect
    start: float | None = None
    end: float | None = None
    enabled: bool = True
    mask: bool = False

    def validate(self):
        if self.kind not in KINDS or not valid_rect(self.region):
            raise ValueError("Ungültige Overlay-Zone")
        if type(self.enabled) is not bool or type(self.mask) is not bool:
            raise ValueError("Ungültige Overlay-Einstellung")
        if (self.start is None) != (self.end is None):
            raise ValueError("Overlay-Zeitfenster unvollständig")
        if self.start is not None and not (
            all(type(v) in (int,float) and math.isfinite(v) for v in (self.start,self.end))
            and 0 <= self.start < self.end):
            raise ValueError("Ungültige Overlay-Zeit")

    def active(self, start, end):
        return self.enabled and (self.start is None or self.start < end and self.end > start)


@dataclass(frozen=True)
class Director:
    manual: tuple[CameraKeyframe,...] = ()
    tracked: tuple[CameraKeyframe,...] = ()
    zones: tuple[OverlayZone,...] = ()
    avoid_overlays: bool = False
    caption_safe: str = "bottom"  # bottom / top
    removal_enabled: bool = False

    def validate(self):
        for keys in (self.manual,self.tracked):
            if not isinstance(keys,tuple) or len(keys)>MAX_KEYS:
                raise ValueError("Zu viele Kamera-Keyframes")
            previous=-1.
            for key in keys:
                key.validate()
                if key.at-previous < .001:
                    raise ValueError("Keyframes müssen zeitlich aufsteigend sein")
                previous=key.at
        if not isinstance(self.zones,tuple) or len(self.zones)>MAX_ZONES:
            raise ValueError("Zu viele Sperrzonen")
        for zone in self.zones:
            zone.validate()
        if (type(self.avoid_overlays) is not bool or type(self.removal_enabled) is not bool
                or self.caption_safe not in ("top","bottom")):
            raise ValueError("Ungültige Director-Konfiguration")

    @property
    def keys(self):
        return self.manual or self.tracked


def director_from_dict(doc):
    if doc is None:
        return Director()
    if not isinstance(doc,dict):
        raise ValueError("Ungültiger Director")
    data=dict(doc)
    for name in ("manual","tracked"):
        data[name]=tuple(CameraKeyframe(**k) for k in data.get(name,()))
    data["zones"]=tuple(OverlayZone(**{**z,"region":tuple(z["region"])})
                        for z in data.get("zones",()))
    result=Director(**data)
    result.validate()
    return result


def overlap(a,b):
    x,y,w,h=a
    u,v,p,q=b
    return max(0.,min(x+w,u+p)-max(x,u))*max(0.,min(y+h,v+q)-max(y,v))


def contains(a,b):
    x,y,w,h=a
    u,v,p,q=b
    return x<=u+1e-9 and y<=v+1e-9 and x+w>=u+p-1e-9 and y+h>=v+q-1e-9


def safe_crop(zones, source_width, source_height, output_width, output_height,
              *, protected=None):
    """Largest target-aspect rectangle excluding all active zones.

    Candidate edges derive from obstacle boundaries. Protect a manually
    specified region if provided; return None for an unsatisfiable conflict.
    """
    zones=tuple(zones)
    if any(not valid_rect(z) for z in zones):
        raise ValueError("Ungültige Sperrzone")
    if protected is not None and not valid_rect(protected):
        raise ValueError("Ungültige Schutzregion")
    ratio=(output_width/output_height)/(source_width/source_height)
    xs=sorted({0.,1.,*(edge for x,y,w,h in zones for edge in (x,x+w))})
    best=None
    score=-1.
    for i,x in enumerate(xs[:-1]):
        for right in xs[i+1:]:
            blocked=sorted((y,y+h) for u,y,w,h in zones
                           if min(right,u+w)-max(x,u)>1e-9)
            gaps=[]
            cursor=0.
            for low,high in blocked:
                if low>cursor:
                    gaps.append((cursor,low))
                cursor=max(cursor,high)
            if cursor<1:
                gaps.append((cursor,1.))
            for y,bottom in gaps:
                w=min(right-x,(bottom-y)*ratio)
                h=w/ratio
                if min(w,h)<.01 or w*h<score-1e-12:
                    continue
                a=max(x,min(right-w,.5-w/2))
                b=max(y,min(bottom-h,.5-h/2))
                if protected:
                    a=max(x,min(right-w,protected[0]+protected[2]/2-w/2))
                    b=max(y,min(bottom-h,protected[1]+protected[3]/2-h/2))
                rect=(a,b,w,h)
                if protected and not contains(rect,protected):
                    continue
                if any(overlap(rect,z)>1e-9 for z in zones):
                    continue
                area=w*h
                if area>score+1e-12 or (best is not None and abs(area-score)<1e-12
                    and abs(a+w/2-.5)+abs(b+h/2-.5)<abs(best[0]+best[2]/2-.5)+abs(best[1]+best[3]/2-.5)):
                    best,score=rect,area
    return best


def crop_for_scene(scene, video, width, height):
    d=scene.director
    zones=tuple(z.region for z in d.zones if z.active(scene.start,scene.framing_end or scene.end))
    if not d.avoid_overlays or not zones:
        return None
    if d.manual or (d.tracked and scene.mode=="automatic"):
        keys=d.manual or d.tracked
        # A conservative swept rectangle checks all explicit positions. If
        # the envelope meets an obstacle, require an explicit user decision.
        rects=[key_crop(k,video,width,height) for k in keys]
        x=min(r[0] for r in rects); y=min(r[1] for r in rects)
        envelope=(x,y,max(r[0]+r[2] for r in rects)-x,max(r[1]+r[3] for r in rects)-y)
        if any(overlap(envelope,z)>1e-9 for z in zones):
            raise ValueError("Overlay-Konflikt: Kamerafahrt hat Vorrang; Sperrzonen prüfen.")
        return None
    if scene.mode != "automatic":
        if any(overlap(scene.region,z)>1e-9 for z in zones):
            raise ValueError("Overlay-Konflikt: manuelle Region hat Vorrang; Sperrzonen prüfen.")
        return None
    protected=scene.region if scene.region != (0.,0.,1.,1.) else None
    result=safe_crop(zones,video.width,video.height,width,height,protected=protected)
    if result is None:
        raise ValueError("Kein overlayfreier Crop im Zielformat möglich")
    return result


def key_crop(key,video,width,height):
    ratio=(width/height)/(video.width/video.height)
    w=min(1.,ratio)/key.zoom
    h=w/ratio
    return (max(0.,min(1-w,key.x-w/2)),max(0.,min(1-h,key.y-h/2)),w,h)


def _curve(keys, attr, start):
    """Smoothstep interpolation, clamped outside the keyframe range."""
    last=f"{getattr(keys[-1],attr):.8f}"
    for a,b in reversed(tuple(zip(keys,keys[1:]))):
        t0,t1=a.at-start,b.at-start
        u=f"clip((ot-({t0:.6f}))/{t1-t0:.6f},0,1)"
        va,vb=getattr(a,attr),getattr(b,attr)
        last=f"if(lt(ot,{t1:.6f}),{va:.8f}+({vb-va:.8f})*({u})*({u})*(3-2*({u})),{last})"
    return last


def camera_filter(keys, video, width, height, start):
    """Source-aspect canvas + fixed-size output zoompan. Bounded CFR camera path."""
    if not keys:
        raise ValueError("Kamerapfad fehlt")
    if not math.isfinite(video.fps) or not 1<=video.fps<=120:
        raise ValueError("Ungültige Bildrate für Kameraführung")
    ratio=width/height
    # Keep intermediate surface bounded, including portrait output of landscape.
    scale=min(1., 1920/max(video.width,video.height))
    sw=max(2,int(video.width*scale)//2*2)
    sh=max(2,int(video.height*scale)//2*2)
    pw=max(sw,math.ceil(sh*ratio/2)*2)
    ph=max(sh,math.ceil(sw/ratio/2)*2)
    base=max(pw/sw,ph/sh)
    if base*max(k.zoom for k in keys)>10 or pw*ph>12_000_000:
        raise ValueError("Kamera-Zoom/Seitenverhältnis außerhalb der Rendergrenze")
    ox=(pw-sw)//2
    oy=(ph-sh)//2
    z=f"({base:.8f})*({_curve(keys,'zoom',start)})"
    x=f"clip({ox}+{sw}*({_curve(keys,'x',start)})-iw/zoom/2,{ox},max({ox},{ox+sw}-iw/zoom))"
    y=f"clip({oy}+{sh}*({_curve(keys,'y',start)})-ih/zoom/2,{oy},max({oy},{oy+sh}-ih/zoom))"
    return (f"setpts=PTS-STARTPTS,scale={sw}:{sh},pad={pw}:{ph}:{ox}:{oy},"
            f"fps={video.fps:.6f},zoompan=z='{z}':x='{x}':y='{y}':d=1:"
            f"s={width}x{height}:fps={video.fps:.6f},setsar=1,format=yuv420p")


def mask_filters(director, video, start, end):
    """Explicit opaque masking in source coordinates, before camera transforms."""
    if not director.removal_enabled:
        return ""
    filters=[]
    for zone in director.zones:
        if not zone.mask or not zone.active(start,end):
            continue
        x,y,w,h=zone.region
        left,top=int(x*video.width),int(y*video.height)
        right,bottom=math.ceil((x+w)*video.width),math.ceil((y+h)*video.height)
        time=""
        if zone.start is not None:
            time=f":enable='gte(t,{max(0.,zone.start-start):.6f})*lt(t,{min(end,zone.end)-start:.6f})'"
        filters.append(f"drawbox=x={left}:y={top}:w={right-left}:h={bottom-top}:color=black:t=fill{time}")
    return ",".join(filters)
