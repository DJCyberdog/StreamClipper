"""Strict bounded SRT/VTT import. Source times only; no invented word timestamps."""
from pathlib import Path
import re
from .models import TranscriptSegment

STAMP=re.compile(r"(?:(\d{1,3}):)?(\d{2}):(\d{2})[.,](\d{3})\Z")
def seconds(raw):
    m=STAMP.fullmatch(raw)
    if not m:raise ValueError("Ungültiger Untertitel-Zeitstempel")
    h,mi,s,ms=(int(x or 0) for x in m.groups())
    if mi>=60 or s>=60:raise ValueError("Ungültiger Untertitel-Zeitstempel")
    return h*3600+mi*60+s+ms/1000

def load_subtitles(path,duration):
    p=Path(path)
    if p.suffix.lower() not in (".srt",".vtt") or p.stat().st_size>16*1024**2:raise ValueError("SRT/VTT maximal 16 MiB")
    text=p.read_text(encoding="utf-8-sig").replace("\r\n","\n").replace("\r","\n")
    if p.suffix.lower()==".vtt" and not text.startswith("WEBVTT"):raise ValueError("WEBVTT-Kopf fehlt")
    rows=[]
    for block in re.split(r"\n[ \t]*\n",text.strip()):
        lines=block.splitlines()
        if not lines or lines[0].startswith(("WEBVTT","NOTE","STYLE","REGION")):continue
        i=next((i for i,l in enumerate(lines[:2]) if " --> " in l),None)
        if i is None:raise ValueError("Untertitelblock ohne Zeitangaben")
        a,z=lines[i].split(" --> ",1);a,z=seconds(a.strip()),seconds(z.split()[0])
        if not 0<=a<z<=duration+.1:raise ValueError("Untertitel liegt außerhalb der Aufnahme")
        cue=" ".join(lines[i+1:]).strip()
        # VTT/SRT markup is not interpreted as HTML.
        cue=re.sub(r"<[^>]{1,200}>","",cue)
        if cue:rows.append(TranscriptSegment(a,min(z,duration),cue,review_origin="manual"))
        if len(rows)>100000:raise ValueError("Zu viele Untertitel")
    if not rows:raise ValueError("Keine Untertitel gefunden")
    rows.sort(key=lambda r:(r.start,r.end))
    return rows
