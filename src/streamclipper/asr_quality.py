"""Opt-in ASR review: model metrics are not calibrated confidence.
A second pass is a proposed replacement, never an automatic correction.
"""
from dataclasses import dataclass,replace
from pathlib import Path
import math
import re
import tempfile
from contextlib import contextmanager
from .media import CancelledError
from .audio_sources import extract_audio_stream,inventory
from .reconstructed_speech import ReconstructedSpeech
from .transcript_editor import validate_segments

@dataclass(frozen=True)
class ASROptions:
    language:str|None=None
    glossary:str=""
    beam_size:int=5
    def whisper_kwargs(self):
        if self.language not in (None,"de","en") or not 1<=self.beam_size<=8 or len(self.glossary)>1000:
            raise ValueError("Ungültige ASR-Optionen")
        result={"beam_size":self.beam_size}
        if self.language:result["language"]=self.language
        if self.glossary.strip():result["hotwords"]=self.glossary.strip()
        return result

def flags(cue):
    if cue.review_origin not in ("asr","vad"):return ()
    issues=[]
    if cue.avg_logprob is not None and cue.avg_logprob < -1:issues.append("niedriger Logprob")
    if cue.no_speech_prob is not None and cue.no_speech_prob > .6:issues.append("No-Speech-Signal")
    if cue.compression_ratio is not None and cue.compression_ratio > 2.4:issues.append("hohe Wiederholung")
    tokens=re.findall(r"\w+",cue.text.casefold())
    if any(tokens[i:i+n]==tokens[i+n:i+2*n]==tokens[i+2*n:i+3*n] for n in range(1,5) for i in range(max(0,len(tokens)-3*n+1))):
        issues.append("Textwiederholung")
    if not cue.words:issues.append("keine Wortzeiten")
    return tuple(issues)

@contextmanager
def aligned_path(selection,*,cancelled=None):
    if isinstance(selection,ReconstructedSpeech):
        selection.validate(cancelled=cancelled)
        yield Path(selection.path)
        selection.validate(cancelled=cancelled)
    else:
        selection.validate()
        with tempfile.TemporaryDirectory(prefix="asr-review-") as folder:
            path=extract_audio_stream(selection.inventory,selection.index,folder,role=selection.role,cancelled=cancelled)
            yield path
            if inventory(selection.inventory.source)!=selection.inventory:raise ValueError("Originalaufnahme verändert")

def retry_cue(result,row,selection,model,*,transcriber,options=ASROptions(),cancelled=None):
    """Retry one flagged cue (<=60 s), context +/- 1 s, no automatic adoption."""
    import soundfile as sf
    if not 0<=row<len(result.transcript):raise ValueError("Ungültige Zeile")
    cue=result.transcript[row]
    if not flags(cue) or any(w.origin=="manual" for w in cue.words):
        raise ValueError("Nur auffällige, nicht manuell bearbeitete Zeilen")
    if not result.method.endswith(selection.method_suffix) or Path(result.video.path).resolve()!=Path(selection.inventory.source).resolve():
        raise ValueError("Abweichende Sprachquelle")
    if cue.end-cue.start>60:raise ValueError("ASR-Nachprüfung maximal 60 Sekunden pro Zeile")
    options.whisper_kwargs()
    with aligned_path(selection,cancelled=cancelled) as path, tempfile.TemporaryDirectory(prefix="asr-retry-") as folder:
        with sf.SoundFile(path) as src:
            rate=src.samplerate
            a=max(0,round((cue.start-1)*rate));b=min(src.frames,round((cue.end+1)*rate))
            src.seek(a);samples=src.read(b-a,dtype="float32",always_2d=True)
            if len(samples)!=b-a:raise ValueError("ASR-Nachprüfungsfenster unvollständig")
        window=Path(folder)/"window.wav";sf.write(window,samples,rate,subtype="FLOAT")
        output=transcriber(replace(result.video,path=str(window),duration=(b-a)/rate),model,
                           cancelled=cancelled,quality_options=options)
        if cancelled and cancelled():raise CancelledError("ASR-Nachprüfung abgebrochen")
        selected=[c for c in output if cue.start<=(c.start+c.end)/2+a/rate<cue.end]
        if not selected:raise ValueError("Keine passende Zweittranskription; Original bleibt erhalten")
        # Keep the original reviewed interval. Do not import words that extend
        # outside that interval or silently merge across neighbouring cues.
        return " ".join(c.text for c in selected)

def accept_retry(result,row,before,text):
    if not 0<=row<len(result.transcript) or result.transcript[row]!=before or not flags(before) or any(w.origin=="manual" for w in before.words):
        raise ValueError("ASR-Vorschlag veraltet oder geschützt")
    from .transcript_editor import apply_segment_changes
    return apply_segment_changes(result,row,str(before.start),str(before.end),text)

def archive_raw(result,root):
    """Content-addressed independent raw snapshot; never overwrite edits."""
    import json,hashlib,os
    from dataclasses import asdict
    from .media import _publish_without_overwrite
    payload=json.dumps(asdict(result),ensure_ascii=False,sort_keys=True,allow_nan=False).encode("utf-8")
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    target=root/(hashlib.sha256(payload).hexdigest()+".raw.json")
    if target.exists():
        if target.read_bytes()!=payload:raise ValueError("Rohtranskript-Archiv beschädigt")
        return target
    stage=None
    try:
        with tempfile.NamedTemporaryFile(dir=root,delete=False) as f:
            stage=Path(f.name);f.write(payload);f.flush();os.fsync(f.fileno())
        actual=_publish_without_overwrite(stage,target)
        if actual!=target:
            actual.unlink(missing_ok=True)
            if target.read_bytes()!=payload:raise ValueError("Rohtranskript-Archiv beschädigt")
        return target
    finally:
        if stage is not None:stage.unlink(missing_ok=True)
