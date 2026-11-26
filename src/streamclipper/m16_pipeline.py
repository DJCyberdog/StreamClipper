"""Opt-in M16 analysis pipeline; M10.5 baseline remains available unchanged."""
from dataclasses import asdict, replace
from pathlib import Path
import hashlib
import json
import math
import os
import tempfile
from importlib.metadata import version,PackageNotFoundError
from .gaming_intelligence import (PROFILES,adaptive_samples,rank,atomic_json,digest,
    speech_reaction_hints,checked_events)
from .models import AnalysisResult,TranscriptSegment,TranscriptWord
from .semantic import EventEvidence,transcript_cues,transcribe_video,recognize_gameplay
from .media import audio_levels,probe_video,CancelledError
from .gameplay import scan_temporal_activity
from .object_tracking import detect_and_track
from .highlight_lexicon import load_custom_rules,merged_rules
from .model_checks import validate_clip_model
from .model_catalog import validate_model_dir
from .transcript_editor import validate_segments
from .audio_separation import sha256_file

def package_version(name):
    try:return version(name)
    except PackageNotFoundError:return None

def fingerprint_model(path,cancelled):
    if path is None:return None
    root=Path(path).resolve(strict=True)
    files=sorted(x for x in root.rglob("*") if x.is_file())
    if not files or len(files)>512:raise ValueError("Invalid model inventory")
    return {str(f.relative_to(root)):sha256_file(f,cancelled=cancelled) for f in files}

def visual_retry(fn):
    """Retry only explicit CUDA runtime/memory failures; propagate other errors."""
    try:return fn(None)
    except (RuntimeError,OSError) as exc:
        msg=str(exc).lower()
        if not ("cuda" in msg and any(k in msg for k in ("out of memory","driver","not available","not compiled","initialization","no kernel image"))):
            raise
        import warnings
        warnings.warn("M16 visual CUDA failed; retrying on CPU",RuntimeWarning)
    import gc
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except (RuntimeError,ImportError):pass
    return fn("cpu")

def analyze_m16(path,clip_seconds=25,max_clips=8,*,progress=None,cancelled=None,
                speech_model=None,vision_model=None,max_visual_frames=180,
                detector_model=None,max_object_frames=90,speech_source=None,
                cache_root=None,profile="generic",preferences=None,chat_messages=None,
                fast_vision=False,reaction_model=None):
    from .analyze import find_candidates
    from .audio_sources import inventory,SpeechSource,extract_audio_stream,transcribe_selected_stream
    from .reconstructed_speech import ReconstructedSpeech,transcribe_reconstructed
    from functools import partial
    if clip_seconds<5 or not 1<=max_clips<=1000:raise ValueError('Invalid clip configuration')
    if profile not in PROFILES or not 5<=max_visual_frames<=2000 or not 3<=max_object_frames<=300:
        raise ValueError("Invalid M16 settings")
    if speech_source is not None and not speech_model:raise ValueError("Speech source requires Whisper")
    if vision_model:validate_clip_model(vision_model)
    if detector_model:validate_model_dir("detector",detector_model)
    if speech_model:validate_model_dir("speech",speech_model)
    rules=merged_rules(load_custom_rules()) if speech_model else ()
    video=probe_video(path)
    def check():
        if cancelled and cancelled():raise CancelledError("M16 Analyse abgebrochen")
    check()
    stat=Path(video.path).stat()
    source_stamp=(stat.st_size,stat.st_mtime_ns)
    if speech_source is not None:
        if Path(video.path).resolve()!=Path(speech_source.inventory.source).resolve() or inventory(video.path)!=speech_source.inventory:
            raise ValueError("Speech source mismatch")
        if isinstance(speech_source,ReconstructedSpeech):speech_source.validate(cancelled=cancelled)
        else:speech_source.validate()
    identity=None
    if cache_root is not None:
        identity={"schema":1,"engine":"m16-pilot-2","source":sha256_file(video.path,cancelled=cancelled),
                  "duration":video.duration,"speech_source":speech_source.method_suffix if speech_source else None,
                  "models":[fingerprint_model(m,cancelled) for m in (speech_model,vision_model,detector_model)],
                  "versions":{m:package_version(m) for m in ("faster-whisper","ctranslate2","torch","transformers","av")},
                  "requested_device":os.environ.get("STREAMCLIPPER_WHISPER_DEVICE","auto"),
                  "profile":profile,"fast_vision":bool(fast_vision),"reaction_model":fingerprint_model(reaction_model,cancelled),"visual_budget":max_visual_frames,"object_budget":max_object_frames,
                  "rules":[asdict(r) for r in rules]}
    stages=["audio"]+(["speech"] if speech_model else [])+["motion"]+(["reaction"] if isinstance(speech_source,SpeechSource) and speech_source.role=="microphone" else [])+(["visual"] if vision_model else [])+(["object"] if detector_model else [])
    def run(name,fn,dependency=None):
        check()
        number=stages.index(name)
        def tick(n):
            if progress:progress(min(99,round(100*(number+max(0,min(100,n))/100)/len(stages))))
        target=Path(cache_root)/ (digest([identity,name,dependency])+".json") if identity else None
        if target is not None and target.exists():
            if target.stat().st_size>64*1024*1024:raise ValueError("M16 cache exceeds limit")
            doc=json.loads(target.read_text(encoding="utf-8"))
            if doc.get("key")!=target.stem or doc.get("sha256")!=digest(doc["value"]):
                raise ValueError("M16 cache corrupt")
            value=doc["value"]
        else:
            value=fn(tick);check()
            current=Path(video.path).stat()
            if (current.st_size,current.st_mtime_ns)!=source_stamp:raise ValueError("Source changed during analysis")
            if target is not None:atomic_json(target,{"key":target.stem,"value":value,"sha256":digest(value)})
        tick(100);return value
    levels=run("audio",lambda p:audio_levels(video,progress=p,cancelled=cancelled))
    evidence=[EventEvidence(c.peak_at,"audio",min(.5,c.score/200),c.reason)
              for c in find_candidates(levels,video.duration,clip_seconds,max(24,max_clips*4)) if c.score>30]
    transcript=[]
    if speech_model:
        def speech(p):
            if speech_source is None:result=transcribe_video(video,speech_model,progress=p,cancelled=cancelled)
            else:
                engine=transcribe_reconstructed if isinstance(speech_source,ReconstructedSpeech) else transcribe_selected_stream
                result=engine(video,speech_model,speech_source,transcriber=partial(transcribe_video,model_cache={}),
                              progress=p,cancelled=cancelled)
            return [asdict(c) for c in result]
        raw=run("speech",speech)
        transcript=[TranscriptSegment(**{**c,"words":tuple(TranscriptWord(**w) for w in c.get("words",[]))}) for c in raw]
        validate_segments(transcript,video.duration)
        # Suppress weak or suspicious ASR cues rather than treating them as certain reactions.
        from .asr_quality import flags
        for cue in transcript:
            for e in transcript_cues([(cue.start,cue.end,cue.text)],rules=rules):
                uncertain=bool(flags(cue))
                evidence.append(replace(e,strength=e.strength*(.55 if uncertain else 1),
                    description=e.description+(" (ASR unsicher)" if uncertain else "")))
    def event_rows(events):return [asdict(e) for e in events]
    evidence.extend(EventEvidence(**e) for e in run("motion",lambda p:event_rows(scan_temporal_activity(video,progress=p,cancelled=cancelled))))
    if "reaction" in stages:
        def reaction(p):
            with tempfile.TemporaryDirectory(prefix="m16-mic-") as folder:
                wav=extract_audio_stream(speech_source.inventory,speech_source.index,folder,role="microphone",cancelled=cancelled)
                levels=audio_levels(replace(video,path=str(wav),has_audio=True),progress=p,cancelled=cancelled)
            return event_rows(speech_reaction_hints(levels,video.duration,designated_microphone=True))
        evidence.extend(EventEvidence(**e) for e in run("reaction",reaction))
    if vision_model:
        stamps=adaptive_samples(evidence,video.duration,max_visual_frames)
        evidence.extend(EventEvidence(**e) for e in run("visual",lambda p:event_rows(visual_retry(lambda device:recognize_gameplay(
            video,vision_model,max_frames=max_visual_frames,timestamps=stamps,profile=profile,progress=p,cancelled=cancelled,device_override=device,batch_size=(4 if fast_vision and device!="cpu" else 1),mixed_precision=fast_vision))),stamps))
    if detector_model:
        anchors=checked_events(evidence,video.duration)
        stamps=adaptive_samples(anchors,video.duration,max(5,max_object_frames))[:max_object_frames]
        evidence.extend(EventEvidence(**e) for e in run("object",lambda p:event_rows(visual_retry(lambda device:detect_and_track(
            video,detector_model,anchors=anchors,max_frames=max_object_frames,timestamps=stamps,progress=p,cancelled=cancelled,device_override=device,relative_motion=True,batch_size=(2 if fast_vision and device!="cpu" else 1),mixed_precision=fast_vision))),[event_rows(anchors),stamps]))
    if chat_messages is not None:
        from .gaming_intelligence import chat_hints
        evidence.extend(chat_hints(chat_messages,video.duration))
    check()
    if identity and sha256_file(video.path,cancelled=cancelled)!=identity["source"]:raise ValueError("Source hash changed")
    current=Path(video.path).stat()
    if (current.st_size,current.st_mtime_ns)!=source_stamp:raise ValueError("Source changed during analysis")
    candidates=rank(evidence,video.duration,clip_seconds,max_clips,profile,preferences)
    if progress:progress(100)
    return AnalysisResult(video,candidates,method="m16-experimental-"+profile+(speech_source.method_suffix if speech_source else ""),transcript=transcript)
