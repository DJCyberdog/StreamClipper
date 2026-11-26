"""Bounded explicit public-media URL parser. No credentials or playlist/channel imports."""
from dataclasses import dataclass
from urllib.parse import urlsplit,parse_qs,urlunsplit
import re
import ipaddress

@dataclass(frozen=True)
class Source:
    provider:str
    url:str
    expected_id:str|None

def parse_source(raw):
    if not isinstance(raw,str) or len(raw)>2048 or any(ord(c)<32 for c in raw):raise ValueError("Ungültige Video-URL")
    try:
        p=urlsplit(raw.strip())
        if p.scheme!="https" or not p.hostname or p.username or p.password or p.port is not None or "\\" in raw:raise ValueError
    except ValueError as exc:raise ValueError("Nur HTTPS-Video-URLs ohne Zugangsdaten") from exc
    h=p.hostname;path=p.path.rstrip("/")
    if h in ("youtube.com","www.youtube.com","m.youtube.com","youtu.be"):
        ident=(path[1:] if h=="youtu.be" else (parse_qs(p.query).get("v",[""])[0] if path=="/watch" else path.split("/")[-1] if re.fullmatch(r"/(?:shorts|live)/[^/]+",path) else ""))
        if re.fullmatch(r"[A-Za-z0-9_-]{11}",ident):return Source("youtube","https://www.youtube.com/watch?v="+ident,ident)
    elif h in ("twitch.tv","www.twitch.tv","m.twitch.tv","clips.twitch.tv"):
        m=re.fullmatch(r"/videos/([1-9][0-9]*)",path)
        if m and h!="clips.twitch.tv":return Source("twitch","https://www.twitch.tv/videos/"+m[1],m[1])
        m=re.fullmatch(r"/(?:[A-Za-z0-9_]+/clip/)?([A-Za-z0-9_-]+)",path)
        if m and (h=="clips.twitch.tv" or "/clip/" in path):return Source("twitch-clip","https://clips.twitch.tv/"+m[1],m[1])
    elif h in ("kick.com","www.kick.com"):
        m=re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)?videos/([A-Fa-f0-9-]{36})",path)
        if m:return Source("kick","https://kick.com"+path,m[1])
        m=re.fullmatch(r"/[A-Za-z0-9_-]+",path)
        clip=parse_qs(p.query).get("clip",[""])[0]
        if m and re.fullmatch(r"clip_[A-Za-z0-9_-]{8,100}",clip):return Source("kick-clip","https://kick.com"+path+"?clip="+clip,None)
    elif h in ("vimeo.com","www.vimeo.com","player.vimeo.com"):
        m=re.fullmatch(r"/(?:video/)?([0-9]+)",path)
        if m:return Source("vimeo","https://vimeo.com/"+m[1],m[1])
    elif h in ("dailymotion.com","www.dailymotion.com","dai.ly"):
        m=re.fullmatch(r"/(?:video/)?([A-Za-z0-9]+)",path)
        if m and (h=="dai.ly" or path.startswith("/video/")):return Source("dailymotion","https://www.dailymotion.com/video/"+m[1],m[1])
    elif not p.query and re.fullmatch(r"[A-Za-z0-9.-]+",h) and "." in h and re.search(r"\.(mp4|webm|mkv|mov)$",path,re.I):
        try:ipaddress.ip_address(h)
        except ValueError:return Source("direct",urlunsplit(("https",h,p.path,"","")),None)
    raise ValueError("Einzelvideo-URL erforderlich; keine Kanäle, Playlists, Live-Streams oder privaten Adressen")
