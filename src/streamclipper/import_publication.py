"""Recoverable local import publication; never overwrite media or receipts.

A journal binds exact staged bytes and output names before the first file is
published. A restart can finish a partially published bundle without downloading
again. A competing or modified output is a conflict, never silently replaced.
"""
from pathlib import Path
import hashlib,json,os,re
from .gaming_intelligence import atomic_json,digest
from .media import CancelledError

def fingerprint(path,cancelled=None):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError("Unsichere Importdatei")
    before=path.stat();h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            if cancelled and cancelled():raise CancelledError("Importprüfung abgebrochen")
            h.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError("Importdatei während Prüfung geändert")
    return {"bytes":after.st_size,"sha256":h.hexdigest()}

def name(value):
    if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}",value) or value in (".",".."):
        raise ValueError("Unsicherer Importdateiname")
    return value

def choose_target(folder,requested,subtitles):
    for i in range(1,100001):
        target=requested if i==1 else requested.with_name(f"{requested.stem}_{i}{requested.suffix}")
        candidates=[target,target.with_name(target.name+".import.json")]
        candidates.extend(target.with_name(target.stem+"."+suffix) for suffix in subtitles)
        if all(not p.exists() and not p.is_symlink() for p in candidates):return target
    raise FileExistsError("Kein freier Importdateiname")

def begin(staging,folder,path,requested,record,sidecars,identity,cancelled=None):
    staging=Path(staging);folder=Path(folder);path=Path(path)
    suffixes=[suffix for _,suffix in sidecars]
    if len(suffixes)!=len(set(suffixes)):raise ValueError("Mehrdeutige Untertitel")
    target=choose_target(folder,requested,suffixes)
    files=[{"source":name(path.name),"target":name(target.name),**fingerprint(path,cancelled)}]
    for source,suffix in sidecars:
        files.append({"source":name(source.name),"target":name(target.stem+"."+suffix),**fingerprint(source,cancelled)})
    record={**record,"subtitles":[f["target"] for f in files[1:]],"file_bytes":files[0]["bytes"],
            "file_sha256":files[0]["sha256"]}
    body={"schema":1,"identity":identity,"files":files,"record":record}
    journal=staging/"publication.json"
    if journal.exists() or journal.is_symlink():raise ValueError("Importjournal bereits vorhanden")
    atomic_json(journal,{"body":body,"sha256":digest(body)})
    return finish(staging,folder,identity,cancelled)

def finish(staging,folder,identity,cancelled=None):
    staging=Path(staging);folder=Path(folder);journal=staging/"publication.json"
    if not journal.exists():return None
    if journal.is_symlink() or journal.stat().st_size>256*1024:raise ValueError("Importjournal ungültig")
    doc=json.loads(journal.read_text(encoding="utf-8"));body=doc["body"]
    if doc["sha256"]!=digest(body) or body["schema"]!=1 or body["identity"]!=identity:
        raise ValueError("Importjournal passt nicht zur Anfrage")
    files=body["files"]
    if not 1<=len(files)<=101:raise ValueError("Importjournal ungültig")
    record=body["record"];media=folder/name(files[0]["target"])
    if record["file_sha256"]!=files[0]["sha256"] or record["file_bytes"]!=files[0]["bytes"]:
        raise ValueError("Importjournal ungültig")
    if record["subtitles"]!=[f["target"] for f in files[1:]]:raise ValueError("Importjournal ungültig")
    # Check the entire transaction before making additional visible changes.
    for f in files:
        source=staging/name(f["source"]);target=folder/name(f["target"])
        if target.is_symlink() or source.is_symlink():raise ValueError("Unsichere Importdatei")
        expected={"bytes":f["bytes"],"sha256":f["sha256"]}
        if target.exists():
            if fingerprint(target,cancelled)!=expected:raise FileExistsError("Importziel geändert – keine Überschreibung")
        elif fingerprint(source,cancelled)!=expected:raise ValueError("Import-Zwischendatei geändert")
    receipt=media.with_name(media.name+".import.json")
    if receipt.is_symlink():raise ValueError("Unsicherer Importbeleg")
    if receipt.exists():
        if receipt.stat().st_size>256*1024 or json.loads(receipt.read_text(encoding="utf-8"))!=record:
            raise FileExistsError("Importbeleg geändert – keine Überschreibung")
    if cancelled and cancelled():raise CancelledError("Importprüfung abgebrochen")
    for f in files:
        source=staging/f["source"];target=folder/f["target"]
        if target.exists():continue
        try:os.link(source,target)
        except FileExistsError:raise
        except OSError:
            if os.name!="nt":raise
            os.rename(source,target) # Windows exclusive rename, no replacement
    if not receipt.exists():
        pending=staging/"receipt.json";atomic_json(pending,record)
        try:os.link(pending,receipt)
        except FileExistsError:raise
        except OSError:
            if os.name!="nt":raise
            os.rename(pending,receipt)
        finally:pending.unlink(missing_ok=True)
    # Keep the small journal for dedup/recovery; no retained large hardlinks.
    for f in files:
        (staging/f["source"]).unlink(missing_ok=True)
    return media
