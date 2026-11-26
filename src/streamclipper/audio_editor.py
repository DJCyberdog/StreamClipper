"""Explicit source-bound stem import and immutable processed-mix assets."""
from dataclasses import dataclass,asdict,replace
from pathlib import Path
import json
import math
import shutil
import tempfile
from .audio_sources import inventory
from .reconstructed_speech import select_reconstructed
from .audio_separation import sha256_file
from .editor_project import add_track,add_item
from .media import process_stem_mix,measure_loudness,CancelledError

@dataclass(frozen=True)
class MixOptions:
    voice_gain:float=0.
    background_gain:float=0.
    cleanup:bool=False
    ducking:bool=False
    normalize:bool=False

def prepare_stems(project,voice,*,cancelled=None):
    import soundfile as sf
    snapshot=inventory(project.source.path)
    chosen=select_reconstructed(snapshot,voice).validate(cancelled=cancelled)
    path=Path(chosen.path)
    residual=path.parent/"residual.wav"
    manifest=json.loads((path.parent/"provenance.json").read_text(encoding="utf-8"))
    record=manifest["outputs"].get("residual.wav",{})
    info=sf.info(residual)
    if (info.frames,info.samplerate,info.channels,info.subtype)!=(round(snapshot.duration*48000),48000,chosen.channels,"FLOAT") or record.get("frames")!=info.frames or record.get("sha256")!=sha256_file(residual,cancelled=cancelled):
        raise ValueError("Restton beschädigt oder Zeitbasis ungültig")
    if abs(project.source.duration-snapshot.duration)>.1:raise ValueError("Projekt-Zeitbasis abweichend")
    return chosen,residual

def _add_audio(project,path,label,gain):
    if any(i.media_path==str(path) for i in project.items):raise ValueError("Audiodatei bereits auf der Timeline")
    result=add_track(project,"audio",label)
    return add_item(result,result.tracks[-1].id,0.,project.source.duration,0.,label,media_path=str(path),gain_db=gain)

def import_pair(project,voice,options=MixOptions(),*,cancelled=None):
    if options.cleanup or options.ducking or options.normalize:raise ValueError('Effekte erfordern gerenderten Mix')
    chosen,residual=prepare_stems(project,voice,cancelled=cancelled)
    result=_add_audio(project,Path(chosen.path),"KI-Stimme (Schätzung)",options.voice_gain)
    result=_add_audio(result,residual,"KI-Restton (Schätzung)",options.background_gain)
    result=replace(result,base_audio_enabled=False);result.validate()
    return result

def create_processed_mix(project,voice,folder,options=MixOptions(),*,cancelled=None):
    from dataclasses import replace
    chosen,residual=prepare_stems(project,voice,cancelled=cancelled)
    root=Path(folder).resolve();root.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(root).free<round(chosen.inventory.duration*48000)*chosen.channels*4+64*1024*1024:
        raise OSError("Nicht genügend Speicherplatz für Audiomix")
    stage=Path(tempfile.mkdtemp(prefix=".mix-",dir=root))
    final=root/("mix-"+stage.name.removeprefix(".mix-"))
    try:
        out=process_stem_mix(chosen.path,residual,stage/"processed_mix.wav",duration=chosen.inventory.duration,
                             channels=chosen.channels,cancelled=cancelled,**asdict(options))
        chosen.validate(cancelled=cancelled)
        if sha256_file(residual,cancelled=cancelled)!=json.loads((Path(chosen.path).parent/"provenance.json").read_text(encoding="utf-8"))["outputs"]["residual.wav"]["sha256"]:
            raise ValueError("Restton während Verarbeitung verändert")
        measured=measure_loudness(out,duration=chosen.inventory.duration,cancelled=cancelled)
        digest=sha256_file(out,cancelled=cancelled)
        (stage/"mix.json").write_text(json.dumps({"schema_version":1,"source":asdict(chosen.inventory),"voice_sha256":chosen.sha256,
            "options":asdict(options),"measured_wav_loudness":measured,"output_sha256":digest,"duration":chosen.inventory.duration},ensure_ascii=False,allow_nan=False),encoding="utf-8")
        if cancelled and cancelled():raise CancelledError("Audiomix abgebrochen")
        if final.exists():raise FileExistsError(final)
        result=_add_audio(project,final/"processed_mix.wav","KI-Audiomix (bearbeitet)",0.)
        result=replace(result,base_audio_enabled=False);result.validate()
        stage.rename(final)
        return result
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True);raise

def pause_suggestions(spans,duration,*,minimum=1.0):
    """Gaps between speech islands only; no automatic edit to video."""
    if not math.isfinite(duration) or duration<=0 or not .25<=minimum<=60:raise ValueError("Ungültige Pausenparameter")
    previous=0.;gaps=[]
    for start,end in spans:
        if not previous<=start<end<=duration:raise ValueError("Ungültige Sprachintervalle")
        if previous>0 and start-previous>=minimum:gaps.append((previous,start))
        previous=end
    return tuple(gaps)
