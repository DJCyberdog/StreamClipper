"""Explicitly authorized per-channel polling. No startup/background service."""
from dataclasses import dataclass,asdict,replace
from urllib.parse import urlsplit
from pathlib import Path
import json,re,time
from .video_sources import Source,parse_source
from .video_import import preflight,download,run_worker,MAX_BYTES
from .gaming_intelligence import atomic_json

@dataclass(frozen=True)
class Channel:
    url:str
    provider:str
    target:str
    interval_minutes:int=60
    max_items:int=1
    max_bytes:int=4*1024**3
    seen:tuple[str,...]=()
    initialized:bool=False
    next_check:float=0.
    paused:bool=True
    def validate(self):
        src=parse_channel(self.url)
        if src.provider!=self.provider or not 15<=self.interval_minutes<=1440 or not 1<=self.max_items<=5:
            raise ValueError("Ungültige Kanal-Konfiguration")
        if not 1024**2<=self.max_bytes<=MAX_BYTES or not Path(self.target).is_dir():raise ValueError("Ziel oder Limit ungültig")
        if len(self.seen)>10000:raise ValueError("Kanalarchiv voll – manuelle Prüfung nötig")
        return self

def parse_channel(raw):
    p=urlsplit(raw.strip());path=p.path.rstrip("/")
    if p.scheme!="https" or p.username or p.password or p.port or p.query or p.fragment:raise ValueError("Öffentliche Kanal-URL erforderlich")
    if p.hostname in ("youtube.com","www.youtube.com") and re.fullmatch(r"/(?:@[A-Za-z0-9_.-]+|channel/UC[A-Za-z0-9_-]+)(?:/videos)?",path):
        return Source("youtube","https://www.youtube.com"+path.removesuffix("/videos")+"/videos",None)
    if p.hostname in ("twitch.tv","www.twitch.tv") and re.fullmatch(r"/[A-Za-z0-9_]+(?:/videos)?",path):
        return Source("twitch","https://www.twitch.tv"+path.removesuffix("/videos")+"/videos",None)
    if p.hostname in ("kick.com","www.kick.com") and re.fullmatch(r"/[A-Za-z0-9_-]+(?:/videos)?",path):
        return Source("kick","https://kick.com"+path.removesuffix("/videos")+"/videos",None)
    raise ValueError("Kanalquelle nicht unterstützt")

def load(path):
    p=Path(path)
    if not p.exists():return []
    if p.stat().st_size>4*1024**2:raise ValueError("Kanalarchiv zu groß")
    doc=json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema_version")!=1 or len(doc["channels"])>20:raise ValueError("Kanalarchiv ungültig")
    return [Channel(**{**row,"seen":tuple(row["seen"])}).validate() for row in doc["channels"]]

def save(path,channels):
    if len(channels)>20:raise ValueError("Maximal 20 Kanäle")
    atomic_json(Path(path),{"schema_version":1,"channels":[asdict(c.validate()) for c in channels]})

def discover(channel,cancelled=None):
    source=parse_channel(channel.url);rows=[]
    def collect(line):
        if line.startswith("{"):rows.append(json.loads(line))
    run_worker(source,["--quiet","--yes-playlist","--flat-playlist","--playlist-end","20","--skip-download","--dump-single-json"],
               budget=64*1024**2,timeout=120,cancelled=cancelled,on_line=collect)
    if len(rows)!=1 or not isinstance(rows[0].get("entries"),list):raise ValueError("Kanalauflistung nicht unterstützt")
    found={}
    for e in rows[0]["entries"][:20]:
        if not isinstance(e,dict) or e.get("is_live") or e.get("live_status") in ("is_live","is_upcoming","post_live"):continue
        ident=str(e.get("id",""))
        if channel.provider=="youtube":url="https://www.youtube.com/watch?v="+ident
        elif channel.provider=="twitch":url="https://www.twitch.tv/videos/"+ident.removeprefix("v")
        else:url=e.get("webpage_url") or e.get("url") or ""
        try:s=parse_source(url)
        except (ValueError,TypeError):continue
        if s.provider!=channel.provider:continue
        found[s.expected_id or ident]=s.url
    return found

def poll(channel,*,persist,cancelled=None,progress=None,now=None):
    """First observation is a baseline; only later new IDs can be downloaded.
    Persist after each success; receipt discovery handles interrupted state save.
    """
    channel.validate();now=time.time() if now is None else now
    if channel.paused or now<channel.next_check:return channel
    updated=replace(channel,next_check=now+channel.interval_minutes*60)
    persist(updated)
    found=discover(channel,cancelled)
    known=set(channel.seen)
    if not channel.initialized:
        updated=replace(updated,initialized=True,seen=tuple(sorted(known|set(found))))
        persist(updated);return updated
    # Count only completed imports; no infinite retries, next scheduled poll.
    for ident,url in [(k,v) for k,v in found.items() if k not in known][:channel.max_items]:
        from .media import CancelledError
        if cancelled and cancelled():raise CancelledError("Kanalaufnahme abgebrochen")
        imported=False
        for p in Path(channel.target).glob(f"{channel.provider}_{ident}*.import.json"):
            try:
                d=json.loads(p.read_text(encoding="utf-8"))
                media=p.with_name(p.name.removesuffix(".import.json"))
                if d.get("id")==ident and d.get("url")==url and media.is_file():imported=True;break
            except (OSError,ValueError):continue
        if not imported:
            meta=preflight(url,authorized=True,cancelled=cancelled)
            download(meta,channel.target,authorized=True,max_bytes=channel.max_bytes,
                     progress=progress,cancelled=cancelled)
        known.add(ident);updated=replace(updated,seen=tuple(sorted(known)));persist(updated)
    return updated
