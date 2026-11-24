"""Non-destructive local subtitle translation and export selection."""
from dataclasses import replace
import hashlib
import json
import re
from pathlib import Path

from .models import SubtitleTranslation, TranscriptSegment

LANGUAGE=re.compile(r"[a-z]{2,3}(?:-[A-Z]{2})?\Z")
DIGEST=re.compile(r"[0-9a-f]{64}\Z")


def cue_key(cue):
    # Exact source text and bounds; changed original invalidates its translation.
    return hashlib.sha256(json.dumps([cue.start+0.,cue.end+0.,cue.text],
                       ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def validate_translations(result):
    if not isinstance(result.caption_language,str) or (result.caption_language and not LANGUAGE.fullmatch(result.caption_language)):
        raise ValueError("Ungültige Untertitelsprache")
    if not isinstance(result.translations,tuple) or len(result.translations)>100000:
        raise ValueError("Zu viele Übersetzungen")
    seen=set()
    for t in result.translations:
        if (not isinstance(t,SubtitleTranslation) or not isinstance(t.language,str)
                or not LANGUAGE.fullmatch(t.language) or not isinstance(t.source_sha256,str)
                or not DIGEST.fullmatch(t.source_sha256) or not isinstance(t.text,str)
                or not 1<=len(t.text.strip())<=10000 or t.origin not in ("manual","model")):
            raise ValueError("Ungültige Übersetzung")
        key=(t.language,t.source_sha256)
        if key in seen:raise ValueError("Doppelte Übersetzung")
        seen.add(key)
    return result


def set_translations(result,language,entries,*,activate=True):
    """Commit all entries atomically. Entries: (source row, text, origin)."""
    if not isinstance(language,str) or not LANGUAGE.fullmatch(language):
        raise ValueError("Sprachcode benötigt z. B. de oder en")
    values={(t.language,t.source_sha256):t for t in result.translations}
    for row,text,origin in entries:
        if type(row) is not int or not 0<=row<len(result.transcript):
            raise ValueError("Ungültige Transkriptzeile")
        if not isinstance(text,str):raise ValueError("Ungültiger Übersetzungstext")
        key=cue_key(result.transcript[row])
        clean=" ".join(text.split())
        if clean:
            values[(language,key)]=SubtitleTranslation(language,key,clean,origin)
        else:
            values.pop((language,key),None)
    return validate_translations(replace(result,translations=tuple(values.values()),
                                         caption_language=language if activate else result.caption_language))


def select_language(result,language):
    return validate_translations(replace(result,caption_language=language))


def export_transcript(result,intervals=None,*,offset=0.):
    """Resolve selected language. Missing/stale translations fail closed for
    included intervals, never silently mix source and target languages."""
    if not result.caption_language:return tuple(result.transcript)
    lookup={t.source_sha256:t for t in result.translations if t.language==result.caption_language}
    resolved=[]
    for cue in result.transcript:
        if intervals is not None and not any(cue.end+offset>a and cue.start+offset<b for a,b in intervals):
            continue
        translated=lookup.get(cue_key(cue))
        if translated is None:
            raise ValueError(f"Übersetzung {result.caption_language} fehlt bei {cue.start:.3f} s; bitte ergänzen oder Original wählen.")
        resolved.append(TranscriptSegment(cue.start,cue.end,translated.text))
    return tuple(resolved)


def translate_local(texts,model_directory,*,cancelled=None,progress=None):
    """Explicit local Marian/OPUS checkpoint. No network, no remote code,
    no automatic download. User chooses the correct directional model."""
    folder=Path(model_directory).expanduser().resolve()
    if not (folder/"config.json").is_file() or not (folder/"model.safetensors").is_file():
        raise FileNotFoundError("Lokales Marian-Modell mit model.safetensors und config.json erforderlich")
    if json.loads((folder/"config.json").read_text(encoding="utf-8")).get("model_type")!="marian":
        raise ValueError("Bitte einen lokalen Marian-Übersetzungsmodellordner wählen")
    if len(texts)>500:raise ValueError("Maximal 500 Abschnitte pro Übersetzungslauf")
    from .media import CancelledError
    def check():
        if cancelled and cancelled():raise CancelledError("Übersetzung abgebrochen")
    check()
    try:
        import torch
        from transformers import MarianMTModel, MarianTokenizer
    except ImportError as exc:
        raise RuntimeError("Lokale Übersetzung benötigt optionale Abhängigkeiten .[translation]") from exc
    tokenizer=MarianTokenizer.from_pretrained(str(folder),local_files_only=True)
    model=MarianMTModel.from_pretrained(str(folder),local_files_only=True,use_safetensors=True).eval()
    device="cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    result=[]
    for i,text in enumerate(texts):
        check()
        tokens=tokenizer(text,return_tensors="pt",truncation=False)
        limit=min(512,model.config.max_position_embeddings)
        if tokens["input_ids"].shape[-1]>limit:
            raise ValueError(f"Abschnitt {i+1} zu lang; zuerst aufteilen")
        with torch.inference_mode():
            out=model.generate(**{k:v.to(device) for k,v in tokens.items()},max_new_tokens=limit,
                               num_beams=4,do_sample=False)
        translated=tokenizer.decode(out[0],skip_special_tokens=True).strip()
        if not translated:raise ValueError("Modell lieferte leere Übersetzung")
        result.append(translated)
        if progress:progress(i+1,len(texts))
    check()
    return tuple(result)
