"""Local user-owned/licensed sound library. No bundled copyrighted sounds."""
from pathlib import Path
import hashlib,json,shutil,tempfile,os
from .portable import installation_directory
from .media import probe_audio_duration
from .gaming_intelligence import atomic_json

EXT={".wav",".mp3",".ogg",".flac",".m4a"}
def library_root():
    return installation_directory()/"data"/"sounds"
def entries(root=None):
    root=Path(root or library_root())
    out=[]
    for p in sorted(root.glob("*.json")):
        try:
            if p.stat().st_size>8192:continue
            d=json.loads(p.read_text(encoding="utf-8"))
            file=root/d["file"]
            if file.parent!=root or file.is_symlink() or not file.is_file() or file.suffix.lower() not in EXT:continue
            if p.stem!=d["sha256"] or file.stem!=p.stem:continue
            out.append({**d,"path":str(file.resolve())})
        except (ValueError,KeyError,OSError,TypeError):continue
    return out
def import_sound(source,label,license_note,*,root=None):
    source=Path(source).resolve(strict=True);root=Path(root or library_root())
    if source.suffix.lower() not in EXT or not source.is_file() or not 0<source.stat().st_size<=64*1024*1024:
        raise ValueError("Soundformat oder Dateigröße ungültig")
    if not label.strip() or len(label)>100 or not license_note.strip() or len(license_note)>500:
        raise ValueError("Name und Rechtehinweis erforderlich")
    duration=probe_audio_duration(source)
    if not 0<duration<=120:raise ValueError("Soundeffekte maximal 120 Sekunden")
    root.mkdir(parents=True,exist_ok=True)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
    target=root/(sha+source.suffix.lower());meta=root/(sha+".json")
    if meta.exists():
        found=next((x for x in entries(root) if x["sha256"]==sha),None)
        if found is None:raise ValueError("Soundbibliothek beschädigt")
        return found
    # Unique content-addressed file; existing bytes must agree.
    if target.exists():
        if target.read_bytes()!=data:raise ValueError("Sound-Prüfsumme stimmt nicht")
    else:
        with tempfile.NamedTemporaryFile(dir=root,delete=False) as f:
            tmp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
        try:
            try:os.link(tmp,target)
            except FileExistsError:
                if target.read_bytes()!=data:raise ValueError("Sound-Prüfsumme stimmt nicht")
        finally:tmp.unlink(missing_ok=True)
    record={"schema_version":1,"sha256":sha,"file":target.name,"name":label.strip(),"rights":license_note.strip(),"duration":duration}
    atomic_json(meta,record)
    return {**record,"path":str(target.resolve())}
