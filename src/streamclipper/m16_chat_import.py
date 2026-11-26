"""Explicit, optional VOD chat import from a locally installed helper.
No credentials, no private endpoints in StreamClipper, no background fetch.
"""
import json
import math
from pathlib import Path
import subprocess
import tempfile
import time
from .media import CancelledError
from .twitch_import import parse_twitch_vod_url

def parse_chat_export(path,duration,*,vod_id=None):
    path=Path(path)
    if path.stat().st_size>256*1024*1024:raise ValueError("Chat export exceeds 256 MB")
    doc=json.loads(path.read_text(encoding="utf-8-sig"))
    comments=doc.get("comments",doc.get("Comments"))
    video=doc.get("video",doc.get("Video",{}))
    if not isinstance(comments,list) or not isinstance(video,dict):
        raise ValueError("Unsupported TwitchDownloader JSON export")
    if len(comments)>1_000_000:raise ValueError("Chat message limit exceeded")
    if vod_id is not None:
        ident=video.get("id",video.get("Id",video.get("_id")))
        if str(ident)!=str(vod_id):raise ValueError("Chat export does not identify the requested VOD")
    rows=[]
    for comment in comments:
        if not isinstance(comment,dict):raise ValueError("Invalid comment")
        t=comment.get("content_offset_seconds",comment.get("ContentOffsetSeconds"))
        if not isinstance(t,(int,float)) or isinstance(t,bool) or not math.isfinite(t):
            raise ValueError("Invalid chat timestamp")
        if 0<=t<duration:rows.append({"at":float(t)})
    return rows

def download_chat(helper,url,video,*,cancelled=None,timeout=1800):
    canonical,vod_id=parse_twitch_vod_url(url)
    source=Path(video.path)
    # Automatic association only with the application's full-VOD import name.
    if source.stem!=f"twitch_{vod_id}":
        raise ValueError("Chat-Import benötigt die unveränderte vollständige Twitch-VOD-Aufnahme mit passender ID")
    helper=Path(helper).resolve(strict=True)
    if not helper.is_file() or helper.suffix.lower()!=".exe":
        raise ValueError("Select a local TwitchDownloaderCLI.exe")
    if cancelled and cancelled():raise CancelledError("Chat-Import abgebrochen")
    with tempfile.TemporaryDirectory(prefix="sc-chat-") as folder:
        out=Path(folder)/"chat.json"
        # Do not persist chat messages or account identities. Never request
        # login cookies, tokens, access-restricted VODs or embedded images.
        proc=subprocess.Popen([str(helper),"chatdownload","--id",vod_id,"-o",str(out)],
                  cwd=folder,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=time.monotonic()+timeout
        try:
            while proc.poll() is None:
                if cancelled and cancelled():raise CancelledError("Chat-Import abgebrochen")
                if time.monotonic()>deadline:raise RuntimeError("Chat-Import: Zeitlimit")
                if out.exists() and out.stat().st_size>256*1024*1024:raise ValueError("Chat-Export zu groß")
                time.sleep(.2)
            if proc.returncode or not out.is_file() or not out.stat().st_size:
                raise RuntimeError("Chat nicht verfügbar; lokale JSONL-Datei verwenden oder ohne Chat analysieren")
            return parse_chat_export(out,video.duration,vod_id=vod_id)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
