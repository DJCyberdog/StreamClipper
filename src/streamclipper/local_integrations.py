"""Local integration contracts: OBS markers, Stream Deck spool and watch folders."""
from pathlib import Path
import hashlib,json,math,os,time,uuid
from .gaming_intelligence import atomic_json
from .portable import installation_directory

COMMANDS={"marker","play-pause","manual-in","manual-out","manual-create"}
EXT={".mp4",".mkv",".webm",".mov",".ts"}
def root():
    return installation_directory()/"data"/"integrations"
def post_command(command,folder=None):
    if command not in COMMANDS:raise ValueError("Unbekannter Stream-Deck-Befehl")
    folder=Path(folder or root()/"commands");folder.mkdir(parents=True,exist_ok=True)
    if len(list(folder.glob("*.json")))>=100:raise ValueError("Lokale Befehlswarteschlange voll")
    dest=folder/(uuid.uuid4().hex+".json")
    atomic_json(dest,{"schema_version":1,"command":command,"created":time.time()})
    return dest
def take_commands(folder=None,now=None):
    folder=Path(folder or root()/"commands");now=time.time() if now is None else now
    result=[]
    for p in sorted(folder.glob("*.json"),key=lambda p:p.stat().st_mtime)[:100]:
        try:
            if p.is_symlink() or p.stat().st_size>4096:continue
            doc=json.loads(p.read_text(encoding="utf-8"))
            created=doc.get("created")
            if doc.get("schema_version")==1 and doc.get("command") in COMMANDS and isinstance(created,(int,float)) and 0<=now-created<=30:
                result.append(doc["command"])
        except (OSError,ValueError,TypeError):pass
        finally:p.unlink(missing_ok=True)
    return result

def record_marker(session,seconds,kind="source",folder=None):
    if not isinstance(session,str) or not session.strip() or len(session)>2048 or kind not in ("source","obs-record","obs-stream"):
        raise ValueError("Marker-Sitzung ungültig")
    if not math.isfinite(seconds) or not 0<=seconds<=86400*7:raise ValueError("Markerzeit ungültig")
    folder=Path(folder or root()/"markers");folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+".json")
    atomic_json(path,{"schema_version":1,"session":session,"at":round(seconds,3),"kind":kind,"created":time.time()})
    return path
def markers(session,kind="source",folder=None):
    folder=Path(folder or root()/"markers");result=[]
    for p in folder.glob("*.json"):
        try:
            if p.stat().st_size>8192 or p.is_symlink():continue
            doc=json.loads(p.read_text(encoding="utf-8"))
            if doc.get("session")==session and doc.get("kind")==kind and 0<=float(doc["at"])<=86400*7:
                result.append(float(doc["at"]))
        except (OSError,ValueError,KeyError,TypeError):pass
    return sorted(set(result))

def obs_seconds(password,kind="obs-record",port=4455):
    """Use OBS WebSocket v5 via explicit local authenticated request.
    No remote host option; no secrets in persisted metadata.
    """
    if kind not in ("obs-record","obs-stream") or not 1024<=port<=65535:raise ValueError("OBS-Konfiguration ungültig")
    try:import obsws_python
    except ImportError as exc:raise RuntimeError("OBS-Integration benötigt das optionale Paket obsws-python.") from exc
    client=None
    try:
        client=obsws_python.ReqClient(host="127.0.0.1",port=port,password=password,timeout=3)
        status=client.get_record_status() if kind=="obs-record" else client.get_stream_status()
        if not status.output_active:raise ValueError("OBS-Ausgabe läuft nicht")
        return float(status.output_duration)/1000
    except ValueError:raise
    except Exception as exc:raise RuntimeError("OBS nicht erreichbar oder Authentifizierung fehlgeschlagen") from exc
    finally:
        if client is not None:
            try:client.disconnect()
            except Exception:pass

class WatchFolder:
    """Recognize stable files only; never opens or deletes automatically."""
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True)
        if not self.path.is_dir():raise ValueError("Ordner fehlt")
        self.last={};self.reported=set()
    def scan(self,now=None):
        now=time.monotonic() if now is None else now
        current={};ready=[]
        for p in sorted(self.path.iterdir())[:10000]:
            if p.is_symlink() or p.suffix.lower() not in EXT or not p.is_file():continue
            try:s=p.stat()
            except OSError:continue
            if not s.st_size:continue
            signature=(s.st_size,s.st_mtime_ns)
            old=self.last.get(p)
            since=old[1] if old and old[0]==signature else now
            current[p]=(signature,since)
            key=(str(p),signature)
            if now-since>=15 and key not in self.reported:
                self.reported.add(key);ready.append(p)
        self.last=current
        # Keep bounded set, dedup active files only.
        self.reported={key for key in self.reported if Path(key[0]) in current and current[Path(key[0])][0]==key[1]}
        return ready
