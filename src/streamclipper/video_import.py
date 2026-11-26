"""M18 shared local importer. Public single video, explicit consent, no authentication."""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,math,os,queue,re,shutil,subprocess,sys,threading,time
from .video_sources import parse_source,Source
from .network_gate import guarded_proxy
from .media import CancelledError,tool_path,probe_video,_publish_without_overwrite
from .gaming_intelligence import atomic_json

MAX_BYTES=32*1024**3
EXT={".mp4",".mkv",".webm",".mov",".ts"}
PROTOCOLS={"https","m3u8_native","http_dash_segments"}
SAFE_ID=re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")

def number(v):
    return float(v) if type(v) in (int,float) and math.isfinite(v) and v>=0 else None

def clean(v,limit=200):
    return "".join(c for c in str(v or "") if c.isprintable())[:limit]

@dataclass(frozen=True)
class Format:
    id:str
    height:int|None
    ext:str
    video:bool
    audio:bool
    bytes:int|None
    language:str

@dataclass(frozen=True)
class Preflight:
    source:Source
    id:str
    title:str
    channel:str
    duration:float|None
    formats:tuple[Format,...]
    subtitles:tuple[str,...]

def sanitize_metadata(source,info):
    if not isinstance(info,dict) or info.get("_type","video")!="video" or "entries" in info:
        raise ValueError("Keine Einzelvideo-Metadaten")
    if info.get("is_live") or info.get("live_status") in ("is_live","is_upcoming","post_live"):
        raise ValueError("Nur abgeschlossene Aufnahmen")
    if info.get("availability") not in (None,"public","unlisted") or info.get("has_drm") or (number(info.get("age_limit")) or 0)>=18:
        raise ValueError("Zugangsbeschränkte Medien nicht unterstützt")
    ident=str(info.get("id",""))
    if ident in (".","..") or not SAFE_ID.fullmatch(ident) or (source.expected_id is not None and ident!=source.expected_id):
        raise ValueError("Video-ID stimmt nicht überein")
    formats=[]
    for f in info.get("formats",[])[:2000]:
        if not isinstance(f,dict) or f.get("has_drm") or f.get("protocol") not in PROTOCOLS:continue
        fid=str(f.get("format_id",""))
        if fid in (".","..") or not SAFE_ID.fullmatch(fid) or fid.startswith("-"):continue
        ext=str(f.get("ext",""))
        if not re.fullmatch(r"[a-z0-9]{2,5}",ext):continue
        size=number(f.get("filesize")) or number(f.get("filesize_approx"))
        height=number(f.get("height"))
        formats.append(Format(fid,int(height) if height else None,ext,
            f.get("vcodec") not in (None,"none"),f.get("acodec") not in (None,"none"),
            int(size) if size else None,clean(f.get("language"),30)))
    if not any(f.video for f in formats):raise ValueError("Kein unterstütztes Videoformat (HTTPS/native HLS/DASH)")
    subs=tuple(sorted(k for k in (info.get("subtitles") or {}) if re.fullmatch(r"[A-Za-z0-9_-]{1,30}",k)))[:100]
    return Preflight(source,ident,clean(info.get("title")),clean(info.get("channel") or info.get("uploader")),
                     number(info.get("duration")),tuple(formats),subs)

def choose_formats(meta,height=None,audio_id=None):
    candidates=[f for f in meta.formats if f.video and (height is None or f.height is not None and f.height<=height)]
    if audio_id is not None:candidates=[f for f in candidates if not f.audio]
    if not candidates:raise ValueError("Gewählte Auflösung / separate Tonspur nicht verfügbar")
    v=max(enumerate(candidates),key=lambda pair:(pair[1].height or 0,pair[0]))[1]
    audio=[f for f in meta.formats if f.audio and not f.video]
    if audio_id is not None:
        a=next((f for f in audio if f.id==audio_id),None)
        if a is None or v.audio:raise ValueError("Separate Audiospur nicht verfügbar")
    else:a=audio[-1] if audio and not v.audio else None
    return (v,a) if a else (v,)

def worker_env():
    env={k:v for k,v in os.environ.items() if k.upper() in
         {"SYSTEMROOT","WINDIR","COMSPEC","PATH","TEMP","TMP","TMPDIR","LANG","LC_ALL","HOME","USERPROFILE","APPDATA","LOCALAPPDATA","SYSTEMDRIVE","PATHEXT"}}
    env["PYTHONIOENCODING"]="utf-8"
    return env

def kill_tree(proc):
    if proc.poll() is not None:return
    try:
        import psutil
        children=psutil.Process(proc.pid).children(recursive=True)
        for child in children:
            try:child.kill()
            except psutil.Error:pass
    except (ImportError,OSError):pass
    except Exception:pass # Process may disappear between poll and child lookup
    try:proc.kill()
    except OSError:pass
    proc.wait(timeout=10)

def run_worker(source,args,*,budget,timeout,cancelled=None,on_line=None,cwd=None):
    if cancelled and cancelled():raise CancelledError("Import abgebrochen")
    with guarded_proxy(budget) as (proxy,gate):
        if getattr(sys,"frozen",False):raise RuntimeError("Videoimport erfordert die portable Python-Runtime")
        cmd=[sys.executable,"-m","streamclipper.import_worker",proxy,tool_path("ffmpeg"),tool_path("ffprobe"),"--ignore-config","--no-plugin-dirs","--no-remote-components","--no-js-runtimes","--no-cookies","--no-cookies-from-browser","--no-netrc","--proxy",proxy,
             "--no-playlist","--playlist-end","1","--no-cache-dir",
             "--socket-timeout","15","--retries","3","--fragment-retries","3","--downloader","native","--abort-on-unavailable-fragments","--downloader-args","ffmpeg_i:-protocol_whitelist file,pipe",
             "--ffmpeg-location",str(Path(tool_path("ffmpeg")).parent),"--no-warnings",
             *args,"--",source.url]
        proc=subprocess.Popen(cmd,cwd=cwd,env=worker_env(),stdin=subprocess.DEVNULL,
             stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,encoding="utf-8",errors="replace",
             creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        q=queue.Queue(maxsize=4);done=threading.Event()
        def read():
            try:
                while not done.is_set():
                    line=proc.stdout.readline(8*1024*1024+1)
                    if not line:break
                    while not done.is_set():
                        try:q.put(line,timeout=.2);break
                        except queue.Full:pass
            finally:
                while not done.is_set():
                    try:q.put(None,timeout=.2);break
                    except queue.Full:pass
        thread=threading.Thread(target=read,daemon=True);thread.start()
        deadline=time.monotonic()+timeout
        try:
            while True:
                if cancelled and cancelled():raise CancelledError("Import abgebrochen; Teildownload erhalten")
                if gate.stop.is_set():raise ValueError("Transferlimit erreicht")
                if time.monotonic()>deadline:raise RuntimeError("Zeitlimit beim Medienimport")
                try:line=q.get(timeout=.2)
                except queue.Empty:continue
                if line is None:break
                if len(line)>8*1024*1024:raise ValueError("Metadaten zu groß")
                if on_line:on_line(line.rstrip("\r\n"))
            if proc.wait(timeout=10) not in (0,101):
                raise RuntimeError("Quelle nicht verfügbar oder Download fehlgeschlagen (Netzwerk, Plattform, yt-dlp oder Zugriffsbeschränkung)")
        finally:
            done.set();kill_tree(proc);thread.join(2)
            if proc.stdout:proc.stdout.close()

def preflight(url,*,authorized=False,cancelled=None):
    if not authorized:raise ValueError("Ausdrückliche Berechtigung erforderlich")
    source=parse_source(url);rows=[]
    def collect(line):
        if line.startswith("{"):
            if rows:raise ValueError("Mehrere Metadatensätze")
            rows.append(json.loads(line))
    run_worker(source,["--quiet","--flat-playlist","--skip-download","--dump-single-json"],
               budget=64*1024**2,timeout=120,cancelled=cancelled,on_line=collect)
    if len(rows)!=1:raise ValueError("Keine Video-Metadaten verfügbar")
    return sanitize_metadata(source,rows[0])

def download(meta,directory,*,height=None,audio_id=None,subtitles=False,authorized=False,
             max_bytes=MAX_BYTES,progress=None,cancelled=None,container="native"):
    if container not in ("native","mkv","mp4"):raise ValueError("Ungültiger Ausgabecontainer")
    if not authorized or not 1024**2<=max_bytes<=MAX_BYTES:raise ValueError("Berechtigung oder Downloadlimit fehlt")
    # Revalidate current metadata and exact identity before starting any download.
    fresh=preflight(meta.source.url,authorized=True,cancelled=cancelled)
    if fresh.id!=meta.id or fresh.source!=meta.source:raise ValueError("Video-ID hat sich geändert")
    selected=choose_formats(meta,height,audio_id)
    formats=choose_formats(fresh,height,audio_id)
    def identity(f):return (f.id,f.ext,f.height,f.video,f.audio,f.language)
    if tuple(map(identity,formats))!=tuple(map(identity,selected)):
        raise ValueError("Verfügbare Formate haben sich geändert – Preflight erneut öffnen")
    estimate=sum(f.bytes or 0 for f in formats)
    folder=Path(directory).resolve(strict=True)
    if not folder.is_dir():raise ValueError("Zielordner fehlt")
    if estimate>max_bytes or shutil.disk_usage(folder).free<max(2*estimate,2*max_bytes)+512*1024**2:
        raise ValueError("Nicht genügend Speicher für Download und Merge; kleineres Limit wählen")
    fmt="+".join(f.id for f in formats)
    key=hashlib.sha256((fresh.source.url+"|"+fmt+"|"+str(subtitles)+"|"+container).encode()).hexdigest()[:24]
    staging=folder/(".sc-import-"+key)
    if staging.is_symlink():raise ValueError("Unsicheres Staging")
    staging.mkdir(exist_ok=True)
    from .render_queue import _lock_file,_unlock_file
    if (staging/".lock").is_symlink():raise ValueError("Unsicheres Staging-Lock")
    lock=(staging/".lock").open("a+b")
    acquired=False
    try:
        _lock_file(lock);acquired=True
        if any(p.is_symlink() for p in staging.iterdir()):raise ValueError("Unsicheres Staging")
        # IDs/formats are restricted to literal safe characters, not user templates.
        args=["--quiet","--progress","--newline","--no-overwrites","--continue","--part",
              "--max-filesize",str(max_bytes),"--format",fmt,
              "--break-match-filters",f"id = {fresh.id} & !is_live & !has_drm & age_limit <=? 17",
              "--max-downloads","1",
              "--merge-output-format","mp4" if container=="mp4" else "mkv","--windows-filenames","--output","video.%(ext)s",
              "--progress-template","download:SC_PROGRESS:%(progress)j",
              "--progress-template","postprocess:SC_MERGE:%(progress.status)s",
              "--print","after_move:SC_DONE:%(filepath)s"]
        if container!="native":args+=["--remux-video",container]
        if subtitles and fresh.subtitles:args+=["--write-subs","--sub-langs",",".join(fresh.subtitles),"--sub-format","vtt/srt/best"]
        finished=[]
        def report(line):
            if line.startswith("SC_DONE:"):finished.append(line[8:].strip())
            if line.startswith("SC_PROGRESS:"):
                row=json.loads(line[len("SC_PROGRESS:"):])
                if progress:progress({"stage":"download","done":number(row.get("downloaded_bytes")),"total":number(row.get("total_bytes")) or number(row.get("total_bytes_estimate")),"speed":number(row.get("speed")),"eta":number(row.get("eta"))})
            elif line.startswith("SC_MERGE:") and progress:progress({"stage":"merge"})
            used=sum(p.stat().st_size for p in staging.iterdir() if p.is_file())
            if used>2*max_bytes or shutil.disk_usage(folder).free<128*1024**2:raise ValueError("Lokales Speicherlimit erreicht")
        run_worker(fresh.source,args,budget=max_bytes+64*1024**2,timeout=8*3600,cancelled=cancelled,on_line=report,cwd=staging)
        if cancelled and cancelled():raise CancelledError("Import abgebrochen")
        if len(finished)!=1:raise ValueError("Kein eindeutiger fertiger Download")
        path=(staging/finished[0]).resolve()
        if path.parent!=staging.resolve() or path.suffix.lower() not in EXT or not path.is_file() or path.stat().st_size>max_bytes:
            raise ValueError("Ungültige Importdatei")
        # Reject manifest/playlist masquerading as a media container before probing.
        with path.open("rb") as stream:head=stream.read(4096)
        if path.suffix.lower() in (".mp4",".mov"):
            valid=len(head)>=12 and head[4:8] in (b"ftyp",b"moov",b"mdat",b"wide",b"free")
        elif path.suffix.lower() in (".mkv",".webm"):valid=head.startswith(bytes.fromhex("1a45dfa3"))
        elif path.suffix.lower()==".ts":valid=len(head)>=377 and head[0]==head[188]==head[376]==0x47
        else:valid=False
        if not valid:raise ValueError("Importdatei enthält keinen unterstützten lokalen Mediencontainer")
        # Restrict even local container probing to local protocols/demuxers.
        from .media import probe_video_local_container
        video=probe_video_local_container(path)
        # Verify an actual decoded frame from the start and near the end.
        for t in (0.,max(0.,video.duration-1.)):
            if cancelled and cancelled():raise CancelledError("Import abgebrochen")
            result=subprocess.run([tool_path("ffmpeg"),"-hide_banner","-nostdin","-v","error","-xerror",
                "-protocol_whitelist","file,pipe","-format_whitelist","mov,matroska,webm,mpegts",
                "-ss",f"{t:.3f}","-i",str(path),"-map","0:v:0","-frames:v","1","-f","null","-"],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=45)
            if result.returncode:raise ValueError("Importdatei lässt sich nicht zuverlässig dekodieren")
        if video.duration<=0 or video.width<=0 or video.height<=0:raise ValueError("Keine dekodierbare Videoquelle")
        if fresh.duration and abs(video.duration-fresh.duration)>max(3,fresh.duration*.02):raise ValueError("Importdauer stimmt nicht")
        if container!="native" and path.suffix.lower()!="."+container:raise ValueError("Gewünschtes Containerformat nicht erreichbar")
        target=folder/f"{fresh.source.provider}_{fresh.id}{path.suffix.lower()}"
        result=_publish_without_overwrite(path,target)
        record={"schema_version":1,"provider":fresh.source.provider,"url":fresh.source.url,"id":fresh.id,
                "title":fresh.title,"channel":fresh.channel,"duration":video.duration,"has_audio":video.has_audio,
                "formats":[f.id for f in formats],"container":path.suffix.lower()[1:],"downloaded_utc":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"subtitles":[]}
        for sidecar in sorted(staging.glob("video.*")):
            if sidecar.suffix.lower() in (".srt",".vtt",".ass",".ttml") and sidecar.is_file():
                suffix=sidecar.name.removeprefix("video.")
                if re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",suffix):
                    sub=_publish_without_overwrite(sidecar,result.with_name(result.stem+"."+suffix))
                    record["subtitles"].append(sub.name)
        receipt=result.with_name(result.name+".import.json")
        pending=staging/"receipt.json"
        atomic_json(pending,record)
        try:os.link(pending,receipt)
        except FileExistsError:raise RuntimeError("Importvideo gespeichert, aber vorhandene Belegdatei nicht überschrieben") from None
        finally:pending.unlink(missing_ok=True)
        if progress:progress({"stage":"complete"})
        return result
    finally:
        if acquired:_unlock_file(lock)
        lock.close()
