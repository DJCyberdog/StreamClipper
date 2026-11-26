"""Cuts-only NLE interchange. No fabricated effects or unsupported track mapping."""
from fractions import Fraction
from pathlib import Path
import math,xml.etree.ElementTree as ET
from .media import _publish_without_overwrite
import tempfile

def frame_rate(fps):
    if not math.isfinite(fps) or fps<=0:raise ValueError("Ungültige Bildrate")
    for r in (Fraction(24000,1001),Fraction(30000,1001),Fraction(60000,1001),*map(Fraction,(24,25,30,50,60))):
        if abs(float(r)-fps)<.02:return r
    raise ValueError("NLE: Bildrate nicht unterstützt")

def cuts(video,intervals):
    r=frame_rate(video.fps)
    rows=[]
    for a,z in intervals:
        if not 0<=a<z<=video.duration:raise ValueError("Ungültiger Schnitt")
        start,end=round(a*r),round(z*r)
        if start>=end:raise ValueError("Schnitt kürzer als ein Bild")
        rows.append((start,end))
    if not 1<=len(rows)<=999:raise ValueError("1–999 Schnitte erforderlich")
    return r,rows

def edl(video,intervals):
    r,rows=cuts(video,intervals)
    if r.denominator!=1 or r.numerator not in (24,25,30):raise ValueError("CMX3600 nur 24/25/30 fps NDF; sonst FCPXML nutzen")
    fps=r.numerator
    def tc(f):
        if not 0<=f<24*3600*fps:raise ValueError("EDL-Zeitcode außerhalb 24h")
        s,f=divmod(f,fps);m,s=divmod(s,60);h,m=divmod(m,60)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"
    lines=["TITLE: STREAMCLIPPER","FCM: NON-DROP FRAME",""];offset=0
    safe="".join(c for c in Path(video.path).name if c.isprintable())[:160]
    for i,(a,z) in enumerate(rows,1):
        lines.append(f"{i:03d}  SC000001 V     C        {tc(a)} {tc(z)} {tc(offset)} {tc(offset+z-a)}")
        if video.has_audio:
            lines.append(f"{i:03d}  SC000001 A     C        {tc(a)} {tc(z)} {tc(offset)} {tc(offset+z-a)}")
        lines.extend(["* FROM CLIP NAME: "+safe,""]);offset+=z-a
    return "\n".join(lines)+"\n"

def fcpxml(video,intervals):
    r,rows=cuts(video,intervals)
    def t(frames):return str(Fraction(frames,1)/r)+"s"
    root=ET.Element("fcpxml",version="1.10");resources=ET.SubElement(root,"resources")
    ET.SubElement(resources,"format",id="r1",frameDuration=t(1),width=str(video.width),height=str(video.height))
    asset=ET.SubElement(resources,"asset",id="r2",name=Path(video.path).name,start="0s",
        duration=t(round(video.duration*r)),hasVideo="1",hasAudio="1" if video.has_audio else "0",format="r1")
    ET.SubElement(asset,"media-rep",kind="original-media",src=Path(video.path).resolve().as_uri())
    lib=ET.SubElement(root,"library");event=ET.SubElement(lib,"event",name="StreamClipper")
    project=ET.SubElement(event,"project",name="Highlights")
    sequence=ET.SubElement(project,"sequence",format="r1",duration=t(sum(z-a for a,z in rows)),tcStart="0s",tcFormat="NDF")
    spine=ET.SubElement(sequence,"spine");offset=0
    for a,z in rows:
        ET.SubElement(spine,"asset-clip",ref="r2",name=Path(video.path).name,offset=t(offset),start=t(a),duration=t(z-a))
        offset+=z-a
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n'+ET.tostring(root,encoding="unicode")+"\n"

def export_nle(video,intervals,destination):
    target=Path(destination).resolve()
    suffix=target.suffix.lower()
    if suffix not in (".edl",".fcpxml"):raise ValueError("EDL oder FCPXML erforderlich")
    payload=(edl if suffix==".edl" else fcpxml)(video,intervals)
    if target==Path(video.path).resolve():raise ValueError("Original geschützt")
    with tempfile.TemporaryDirectory(dir=target.parent) as work:
        partial=Path(work)/("export"+suffix);partial.write_text(payload,encoding="utf-8")
        return _publish_without_overwrite(partial,target)
