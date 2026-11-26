"""Opt-in raw window transcript cache. Private local text, no voiceprint."""
from dataclasses import asdict
from pathlib import Path
from importlib.metadata import version
import hashlib
import json
import os
import tempfile
from .audio_separation import sha256_file
from .media import CancelledError
from .models import TranscriptSegment,TranscriptWord
from .transcript_editor import validate_segments

MAX_BYTES=16*1024*1024

def canonical(doc):
    return json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def model_identity(model,*,cancelled=None):
    root=Path(model).resolve(strict=True)
    files=sorted(p for p in root.rglob("*") if p.is_file())
    if not root.is_dir() or not files or len(files)>256 or not (root/"model.bin").is_file():
        raise ValueError("Whisper-Modellordner unvollständig oder zu groß")
    return {str(p.relative_to(root)):sha256_file(p,cancelled=cancelled) for p in files}

class ASRWindowCache:
    def __init__(self,root,identity):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.identity=canonical({"schema":1,"identity":identity})
        self.hits=0;self.misses=0
    @classmethod
    def for_whisper(cls,root,model,*,cancelled=None):
        return cls(root,{"files":model_identity(model,cancelled=cancelled),
            "faster_whisper":version("faster-whisper"),"ctranslate2":version("ctranslate2"),
            "device_request":os.environ.get("STREAMCLIPPER_WHISPER_DEVICE","auto"),
            "settings":{"beam_size":2,"vad_filter":True,"condition_on_previous_text":False,"word_timestamps":True}})
    def path(self,file,*,cancelled=None):
        # Hash decoded samples and geometry, not WAV metadata timestamps.
        import soundfile as sf
        h=hashlib.sha256(self.identity)
        with sf.SoundFile(file) as f:
            h.update(canonical([f.samplerate,f.channels,f.frames]))
            for block in f.blocks(blocksize=65536,dtype="float32",always_2d=True):
                if cancelled and cancelled():raise CancelledError("ASR abgebrochen")
                h.update(block.astype("<f4",copy=False).tobytes())
        return self.root/(h.hexdigest()+".json")
    def load(self,file,duration,*,cancelled=None):
        path=self.path(file,cancelled=cancelled)
        if not path.exists():
            self.misses+=1;return None
        if path.stat().st_size>MAX_BYTES:raise ValueError("ASR-Cache zu groß")
        doc=json.loads(path.read_text(encoding="utf-8"))
        data=doc.get("data")
        if not isinstance(data,dict) or data.get("key")!=path.stem or data.get("duration")!=duration or doc.get("sha256")!=hashlib.sha256(canonical(data)).hexdigest():
            raise ValueError("ASR-Cache beschädigt")
        cues=[TranscriptSegment(**{**c,"words":tuple(TranscriptWord(**w) for w in c.get("words",[]))}) for c in data["cues"]]
        validate_segments(cues,duration)
        if any(c.review_origin!="asr" or any(w.origin!="whisper" for w in c.words) for c in cues):
            raise ValueError("ASR-Cache enthält bearbeitete Zeilen")
        self.hits+=1
        return cues
    def save(self,file,duration,cues,*,cancelled=None):
        validate_segments(cues,duration)
        if any(c.review_origin!="asr" or any(w.origin!="whisper" for w in c.words) for c in cues):
            raise ValueError("Nur rohe ASR-Zeilen dürfen in den Cache")
        path=self.path(file,cancelled=cancelled)
        data={"key":path.stem,"duration":duration,"cues":[asdict(c) for c in cues]}
        payload=canonical({"data":data,"sha256":hashlib.sha256(canonical(data)).hexdigest()})
        if len(payload)>MAX_BYTES:raise ValueError("ASR-Cache zu groß")
        if cancelled and cancelled():raise CancelledError("ASR abgebrochen")
        stage=None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root,delete=False) as handle:
                stage=Path(handle.name);handle.write(payload);handle.flush();os.fsync(handle.fileno())
            if path.exists():
                self.load(file,duration,cancelled=cancelled);return
            from .media import _publish_without_overwrite
            actual=_publish_without_overwrite(stage,path)
            if actual!=path:
                actual.unlink(missing_ok=True);self.load(file,duration,cancelled=cancelled)
        finally:
            if stage is not None:stage.unlink(missing_ok=True)
