"""Source-bound selection of a reconstructed speech estimate.

Verification checks provenance, geometry, and byte integrity, not neural
quality or authenticity of a user-supplied manifest. Never accept residual
as speech and never silently fall back to the original mix.
"""
from dataclasses import asdict,dataclass,replace
from pathlib import Path
import json
import math
import re
import tempfile

from .audio_sources import AudioInventory,inventory
from .audio_separation import sha256_file,RATE
from .media import CancelledError

KINDS=("reconstructed_foreground_voice_and_residual","reconstructed_target_voice_and_residual")
BLOCK_SECONDS=300
CONTEXT_SECONDS=2

@dataclass(frozen=True)
class ReconstructedSpeech:
    inventory:AudioInventory
    index:int
    path:str
    sha256:str
    kind:str
    channels:int

    @property
    def role(self):
        return "target_voice_estimate" if self.kind==KINDS[1] else "foreground_voice_estimate"

    @property
    def method_suffix(self):
        return f"|asr:reconstructed={self.role},stream={self.index},sha256={self.sha256}"

    @property
    def label(self):
        return "KI-Zielstimmschätzung" if self.kind==KINDS[1] else "KI-Vordergrundsprache"

    def validate(self,*,cancelled=None,hash_bytes=True):
        import soundfile as sf
        if self.kind not in KINDS or not re.fullmatch(r"[0-9a-f]{64}",self.sha256):
            raise ValueError("Ungültige KI-Sprachprovenienz")
        if inventory(self.inventory.source)!=self.inventory:
            raise ValueError("Originalaufnahme verändert")
        path=Path(self.path).resolve(strict=True)
        if path.name!="voice_estimate.wav" or not any(s.index==self.index and s.channels==self.channels and 8000<=s.sample_rate<=192000 for s in self.inventory.streams):
            raise ValueError("Ungültige rekonstruierte Sprachspur")
        info=sf.info(path)
        if (info.frames,info.samplerate,info.channels,info.subtype)!=(round(self.inventory.duration*RATE),RATE,self.channels,"FLOAT"):
            raise ValueError("KI-Sprachspur: Zeitbasis oder Audioformat verändert")
        if hash_bytes and sha256_file(path,cancelled=cancelled)!=self.sha256:
            raise ValueError("KI-Sprachspur: Prüfsumme verändert")
        return self


def select_reconstructed(snapshot,path):
    """Load bounded metadata only; expensive full hash runs in analysis worker."""
    wav=Path(path).resolve(strict=True)
    sidecar=wav.parent/"provenance.json"
    if sidecar.stat().st_size>128*1024:raise ValueError("KI-Sprachprovenienz zu groß")
    m=json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(m,dict) or m.get("schema_version")!=1 or m.get("kind") not in KINDS:
        raise ValueError("Keine unterstützte KI-Sprachprovenienz")
    if m.get("source")!=json.loads(json.dumps(asdict(snapshot))):
        raise ValueError("KI-Sprachspur gehört zu einer anderen Aufnahme")
    stream=next((s for s in snapshot.streams if asdict(s)==m.get("selected_stream")),None)
    if stream is None:raise ValueError("Unbekannte Originalspur")
    outputs=m.get("outputs")
    record=outputs.get("voice_estimate.wav") if isinstance(outputs,dict) else None
    if (wav.name!="voice_estimate.wav" or not isinstance(record,dict)
            or m.get("timeline_origin")!="container_start" or m.get("sample_rate")!=RATE
            or m.get("channels")!=stream.channels or m.get("samples")!=round(snapshot.duration*RATE)
            or record.get("frames")!=m["samples"] or not isinstance(record.get("sha256"),str)):
        raise ValueError("KI-Sprachspur: ungültige Ausgabemetadaten")
    return ReconstructedSpeech(snapshot,stream.index,str(wav),record["sha256"],m["kind"],stream.channels).validate(hash_bytes=False)


def audio_windows(path,*,duration,block_seconds=BLOCK_SECONDS,context_seconds=CONTEXT_SECONDS,cancelled=None,temp_root=None):
    """Yield (WAV, origin, central_start, central_end, duration) using bounded RAM.
    Context overlaps only for inference. Each central interval owns its results.
    Temporary WAVs are removed when the iterator advances or is closed.
    """
    import soundfile as sf
    if not 1<=block_seconds<=600 or not 0<=context_seconds<block_seconds/2:
        raise ValueError("Ungültige Analysefenster")
    def check():
        if cancelled and cancelled():raise CancelledError("Sprachanalyse abgebrochen")
    with sf.SoundFile(path) as src, tempfile.TemporaryDirectory(prefix="speech-windows-",dir=temp_root) as folder:
        rate=src.samplerate
        count=src.frames
        if abs(count/rate-duration)>.002:raise ValueError("Sprachfenster: falsche Dauer")
        block=round(block_seconds*rate);context=round(context_seconds*rate)
        for start in range(0,count,block):
            check()
            end=min(count,start+block)
            a=max(0,start-context);b=min(count,end+context)
            src.seek(a)
            samples=src.read(b-a,dtype="float32",always_2d=True)
            if len(samples)!=b-a:raise ValueError("Sprachfenster unvollständig")
            file=Path(folder)/"window.wav"
            sf.write(file,samples,rate,subtype="FLOAT")
            try:yield file,a/rate,start/rate,end/rate,(b-a)/rate
            finally:file.unlink(missing_ok=True)


def transcribe_reconstructed(video,model,selection,*,transcriber,progress=None,cancelled=None,temp_root=None):
    if Path(video.path).resolve()!=Path(selection.inventory.source).resolve() or abs(video.duration-selection.inventory.duration)>.1:
        raise ValueError("KI-Sprachspur gehört zu einer anderen Aufnahme")
    selection.validate(cancelled=cancelled)
    result=[]
    from contextlib import closing
    with closing(audio_windows(selection.path,duration=selection.inventory.duration,cancelled=cancelled,temp_root=temp_root)) as windows:
        for file,origin,a,b,duration in windows:
            aligned=replace(video,path=str(file),duration=duration,has_audio=True)
            def step(v):
                if progress:progress(min(99,round(100*(a+(b-a)*max(0,min(100,v))/100)/selection.inventory.duration)))
            cues=transcriber(aligned,model,progress=step,cancelled=cancelled)
            for cue in cues:
                start,end=cue.start+origin,cue.end+origin
                if not math.isfinite(start) or not math.isfinite(end) or not 0<=cue.start<cue.end<=duration+.1:
                    raise ValueError("ASR lieferte ungültige Fensterzeiten")
                if not a<=(start+end)/2<b:continue
                words=tuple(replace(w,start=round(w.start+origin,3),end=round(w.end+origin,3)) for w in cue.words)
                result.append(replace(cue,start=round(start,3),end=round(min(end,video.duration),3),words=words))
    selection.validate(cancelled=cancelled)
    from .transcript_editor import validate_segments
    result.sort(key=lambda cue:(cue.start,cue.end))
    validate_segments(result,video.duration)
    if progress:progress(100)
    return result
