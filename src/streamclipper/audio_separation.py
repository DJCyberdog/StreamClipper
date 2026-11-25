"""M15b pilot: local foreground voice estimate plus exact aligned residual.

The model is not a target-speaker selector. Original mix is never replaced.
Only the published offline safetensors checkpoint is accepted by the adapter.
"""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import time
from .audio_sources import inventory,extract_audio_stream
from .media import CancelledError

RATE=48000
CHUNK=8*RATE
OVERLAP=2*RATE
MAX_DURATION=6*3600


def output_format(samples,channels):
    # Leave ample room for RIFF headers and metadata. RF64 supports >4 GiB.
    return 'RF64' if samples*channels*4>=2**32-65536 else 'WAV'
MODEL_SHA256="647335a6aeb4dc706b895532c209d51e0e84a4849d17b339f00d4392a050ae53"
MODEL_ID="inworld/voice-isolator/denoiser.safetensors"


def sha256_file(path,*,cancelled=None):
    h=hashlib.sha256()
    with open(path,"rb") as stream:
        while block:=stream.read(1024*1024):
            if cancelled and cancelled():raise CancelledError("Audiotrennung abgebrochen")
            h.update(block)
    return h.hexdigest()


class InworldBackend:
    def __init__(self,checkpoint,device="auto",*,cancelled=None):
        from importlib.metadata import version
        path=Path(checkpoint).resolve(strict=True)
        if not path.is_file() or path.suffix.lower()!=".safetensors":
            raise ValueError("Lokale Offline-Safetensors-Datei erforderlich")
        if sha256_file(path,cancelled=cancelled)!=MODEL_SHA256:
            raise ValueError("Modellprüfsumme stimmt nicht mit dem freigegebenen Kandidaten überein")
        if device not in ("auto","cpu","cuda"):raise ValueError("Unbekanntes Inferenzgerät")
        if version("inworld-voice-isolation")!="1.0.0":raise ValueError("Inworld-Paketversion 1.0.0 erforderlich")
        import torch
        from inworld import voice_isolation
        actual="cuda" if device=="auto" and torch.cuda.is_available() else "cpu" if device=="auto" else device
        if actual=="cuda" and not torch.cuda.is_available():raise ValueError("CUDA ist nicht verfügbar")
        self.model=voice_isolation.VoiceIsolator(str(path),device=actual,mode="offline")
        self.metadata={"backend":"inworld-voice-isolation","version":"1.0.0","model":MODEL_ID,
                       "sha256":MODEL_SHA256,"device":actual,"speaker_targeted":False}

    def __call__(self,mono):
        import torch
        with torch.inference_mode():
            result=self.model.isolate(torch.from_numpy(mono.copy()),RATE)
        return result.detach().cpu().numpy()


def separate_stream(selection,folder,*,backend,progress=None,cancelled=None,use_cache=False):
    """Bounded 8s/2s overlap, float32 WAV; input mono/stereo 48kHz only.
    Speech estimate broadcast equally to each original channel. Residual =
    input minus estimate; no peak normalization/clipping or identity claim.
    Cancellation is cooperative between model calls, not inside inference.
    """
    import numpy as np
    import soundfile as sf
    selection.validate()
    if selection.role not in ("mix","unspecified"):
        raise ValueError("Für die KI-Trennung bitte eine gemischte Spur auswählen")
    source=selection.inventory
    if source.duration>MAX_DURATION:raise ValueError("Maximal sechs Stunden pro Trennlauf")
    stream=next(s for s in source.streams if s.index==selection.index)
    if stream.sample_rate!=RATE or stream.channels not in (1,2):
        raise ValueError("Pilot unterstützt 48 kHz Mono/Stereo; andere Formate folgen")
    def check():
        if cancelled and cancelled():raise CancelledError("Audiotrennung abgebrochen")
    check()
    if type(use_cache) is not bool or (use_cache and backend.metadata.get("speaker_targeted") is not False):
        raise ValueError("Persistenter Cache nur für Vordergrundsprache ohne Stimmreferenz")
    root=Path(folder).resolve();root.mkdir(parents=True,exist_ok=True)
    count=round(source.duration*RATE)
    file_format=output_format(count,stream.channels)
    cache_budget=(count+((count+CHUNK-OVERLAP-1)//(CHUNK-OVERLAP))*OVERLAP)*4 if use_cache else 0
    if shutil.disk_usage(root).free<count*stream.channels*4*3+cache_budget+64*1024*1024:
        raise OSError("Nicht genügend Speicherplatz für drei PCM-Spuren")
    cache=WindowCache(root/".streamclipper-separation-cache",backend.metadata) if use_cache else None
    staging=Path(tempfile.mkdtemp(prefix=".separation-",dir=root))
    final=root/("separation-"+staging.name.removeprefix(".separation-"))
    began=time.monotonic()
    reused=0;computed=0
    try:
        with tempfile.TemporaryDirectory(prefix="input-",dir=staging) as temp:
            wav=extract_audio_stream(source,selection.index,temp,role=selection.role,cancelled=cancelled)
            with sf.SoundFile(wav) as src, sf.SoundFile(staging/"voice_estimate.wav","w",RATE,
                stream.channels,subtype="FLOAT",format=file_format) as voice, sf.SoundFile(staging/"residual.wav","w",RATE,
                stream.channels,subtype="FLOAT",format=file_format) as residual:
                if src.frames!=count or src.samplerate!=RATE or src.channels!=stream.channels:
                    raise ValueError("PCM-Zeitbasis ungültig")
                start=0;written=0;tail=None
                while start<count:
                    check()
                    src.seek(start)
                    mix=src.read(min(CHUNK,count-start),dtype="float32",always_2d=True)
                    if not np.isfinite(mix).all():raise ValueError("Nicht endliche PCM-Eingabe")
                    mono=mix.mean(axis=1,dtype=np.float32)
                    estimate=cache.load(mono) if cache else None
                    if estimate is None:
                        estimate=np.asarray(backend(mono),dtype=np.float32)
                        computed+=1
                        if cache and estimate.shape==(len(mix),) and np.isfinite(estimate).all():cache.save(mono,estimate)
                    else:reused+=1
                    check()
                    if estimate.shape!=(len(mix),) or not np.isfinite(estimate).all():
                        raise ValueError("Modell lieferte ungültige Sample-Anzahl oder Werte")
                    if tail is not None:
                        n=len(tail)
                        if n>len(estimate):raise ValueError("Überlappung ungültig")
                        fade=np.linspace(0.,1.,n,dtype=np.float32)
                        estimate=estimate.copy()
                        estimate[:n]=tail*(1-fade)+estimate[:n]*fade
                    last=start+len(mix)==count
                    n=len(mix) if last else len(mix)-OVERLAP
                    if n<=0:raise ValueError("Chunk zu kurz")
                    v=np.repeat(estimate[:n,None],stream.channels,axis=1)
                    rem=mix[:n]-v
                    if not np.isfinite(rem).all():raise ValueError("Residual ungültig")
                    voice.write(v);residual.write(rem)
                    written+=n
                    if progress:progress(min(99,round(99*written/count)))
                    if last:break
                    tail=estimate[n:].copy()
                    start+=n
                if written!=count:raise ValueError("Ausgabezeitbasis stimmt nicht")
        check()
        if inventory(source.source)!=source:raise ValueError("Originalaufnahme während Trennung verändert")
        outputs={}
        for name in ("voice_estimate.wav","residual.wav"):
            path=staging/name
            info=sf.info(path)
            if (info.frames,info.samplerate,info.channels,info.subtype)!=(count,RATE,stream.channels,"FLOAT"):
                raise ValueError("Ausgabeprüfung fehlgeschlagen")
            outputs[name]={"sha256":sha256_file(path,cancelled=cancelled),"frames":count}
        manifest={"schema_version":1,"kind":("reconstructed_target_voice_and_residual" if backend.metadata.get("speaker_targeted") is True else "reconstructed_foreground_voice_and_residual"),
            "source":asdict(source),"selected_stream":asdict(stream),"role_user_selected":selection.role,
            "backend":backend.metadata,"sample_rate":RATE,"channels":stream.channels,"samples":count,
            "timeline_origin":"container_start","container_format":file_format,"chunk_samples":CHUNK,"overlap_samples":OVERLAP,
            "voice_projection":"mono_equal_channels","residual_definition":"original_pcm_minus_voice_estimate",
            "outputs":outputs,"cache":{"enabled":use_cache,"reused_windows":reused,"computed_windows":computed},"elapsed_seconds":time.monotonic()-began}
        (staging/"provenance.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
        check()
        if final.exists():raise FileExistsError(final)
        staging.rename(final)
        if progress:progress(100)
        return final
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True)
        raise


class WindowCache:
    """Local opt-in foreground inference cache. Contains reconstructed audio.
    Key binds input bytes, model identity and pipeline revision. Verify size
    and payload checksum on every hit; no pickle or executable deserialization.
    """
    def __init__(self,root,metadata):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.key=json.dumps({"schema":1,"rate":RATE,"chunk":CHUNK,"overlap":OVERLAP,"backend":metadata},
                            sort_keys=True,allow_nan=False).encode("utf-8")
    def path(self,mono):
        import numpy as np
        raw=np.asarray(mono,dtype="<f4").tobytes()
        return self.root/(hashlib.sha256(self.key+b"\0"+raw).hexdigest()+".pcm")
    def load(self,mono):
        import numpy as np
        path=self.path(mono)
        if not path.exists():return None
        if path.stat().st_size!=32+4*len(mono):raise ValueError("Audio-Cache beschädigt; Cache deaktivieren oder lokal löschen")
        with path.open("rb") as f:
            digest=f.read(32);raw=f.read(4*len(mono)+1)
        if len(raw)!=4*len(mono) or hashlib.sha256(raw).digest()!=digest:raise ValueError("Audio-Cache beschädigt")
        estimate=np.frombuffer(raw,dtype="<f4").copy()
        if not np.isfinite(estimate).all():raise ValueError("Audio-Cache ungültig")
        return estimate
    def save(self,mono,estimate):
        import numpy as np
        from .media import _publish_without_overwrite
        raw=np.asarray(estimate,dtype="<f4").tobytes()
        path=self.path(mono);stage=None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root,delete=False) as f:
                stage=Path(f.name);f.write(hashlib.sha256(raw).digest()+raw);f.flush()
            if path.exists():
                if self.load(mono) is None:raise ValueError("Audio-Cache nicht lesbar")
                return
            actual=_publish_without_overwrite(stage,path)
            if actual!=path:
                actual.unlink(missing_ok=True)
                if self.load(mono) is None:raise ValueError("Audio-Cache nicht lesbar")
        finally:
            if stage is not None:stage.unlink(missing_ok=True)
