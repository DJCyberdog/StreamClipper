"""Persist explicit speech-source choice per recording; stale choices fail closed.
No voice reference, speaker embedding, or model enrollment is stored.
"""
from pathlib import Path
from dataclasses import asdict
import json
import os
import hashlib
import tempfile
from .portable import installation_directory
from .audio_sources import SpeechSource,inventory
from .reconstructed_speech import ReconstructedSpeech,select_reconstructed

def selection_path(source,root=None):
    base=Path(root) if root is not None else installation_directory()/"data"/"projects"/"speech_sources"
    key=hashlib.sha256(os.path.normcase(os.path.abspath(source)).encode("utf-8")).hexdigest()
    return base/(key+".json")

def save_selection(source,selection,*,root=None):
    path=selection_path(source,root)
    if selection is None:
        path.unlink(missing_ok=True);return
    if Path(source).resolve()!=Path(selection.inventory.source).resolve():raise ValueError("Sprachquelle gehört zu anderer Aufnahme")
    selection.validate(hash_bytes=False) if isinstance(selection,ReconstructedSpeech) else selection.validate()
    doc={"schema_version":1,"source":asdict(selection.inventory),"stream_index":selection.index,"role":selection.role}
    if isinstance(selection,ReconstructedSpeech):
        doc.update({"kind":"reconstructed","estimate_path":selection.path,"estimate_sha256":selection.sha256})
    else:doc["kind"]="original"
    path.parent.mkdir(parents=True,exist_ok=True)
    stage=None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,delete=False) as f:
            stage=Path(f.name);json.dump(doc,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(stage,path)
    finally:
        if stage is not None:stage.unlink(missing_ok=True)

def load_selection(source,*,root=None):
    path=selection_path(source,root)
    if not path.exists():return None
    if path.stat().st_size>128*1024:raise ValueError("Sprachquellenwahl zu groß")
    doc=json.loads(path.read_text(encoding="utf-8"))
    current=inventory(source)
    if doc.get("schema_version")!=1 or doc.get("source")!=json.loads(json.dumps(asdict(current))):
        raise ValueError("Gespeicherte Sprachquelle veraltet; bitte erneut wählen")
    if doc.get("kind")=="original":
        return SpeechSource(current,doc["stream_index"],doc["role"]).validate()
    if doc.get("kind")=="reconstructed":
        selection=select_reconstructed(current,doc["estimate_path"])
        if (selection.sha256,selection.index,selection.role)!=(doc["estimate_sha256"],doc["stream_index"],doc["role"]):
            raise ValueError("Gespeicherte KI-Sprachspur verändert; bitte erneut wählen")
        return selection
    raise ValueError("Unbekannte Sprachquellenwahl")
