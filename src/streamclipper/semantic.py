"""Explainable, offline speech / visual gaming evidence and candidate ranking.

Optional ML models are **not** downloaded during an analysis. These are
relative similarity and keyword signals, not verified in-game event labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import math
import os
import warnings
import re
from typing import Callable, Iterable

from .models import Candidate, TranscriptSegment, VideoInfo

Cancelled = Callable[[], bool]
Progress = Callable[[int], None]


@dataclass(frozen=True)
class EventEvidence:
    at: float
    kind: str
    strength: float  # heuristic, NOT a calibrated probability
    description: str


# Literal phrases in transcribed speech. No emotional state is inferred.
_REACTIONS = (
    re.compile(r"\b(?:oh\s+(?:mein\s+)?gott|ach\s+du\s+scheiße|was\s+zum\s+teufel|wtf|no\s+way|holy\s+shit|oh\s+my\s+god)\b", re.I),
    re.compile(r"\b(?:alter|krass|unfassbar|wahnsinn|scheiße|scheisse|shit|fuck|wow|aua|heftig|unglaublich)\b", re.I),
    re.compile(r"\b(?:lach(?:e|en|t)?|haha(?:ha)*|lol|lmao)\b", re.I),
)


def transcript_cues(segments: Iterable[tuple[float, float, str]]) -> list[EventEvidence]:
    """Extract explicit *wording* cues; silence and ordinary speech do not score."""
    evidence = []
    for start, end, raw in segments:
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
            continue
        phrase = ' '.join(raw.split())
        if not phrase:
            continue
        matches = sum(bool(pattern.search(phrase)) for pattern in _REACTIONS)
        punctuation = bool(re.search(r"[!?]{2,}", phrase))
        if not (matches or punctuation):
            continue
        strength = min(0.86, 0.57 + 0.11 * max(0, matches - 1) + (0.09 if punctuation else 0))
        display = phrase[:88] + ("…" if len(phrase) > 88 else "")
        evidence.append(EventEvidence(round((start + end) / 2, 3), "speech", strength,
                                      f"Transkript-Hinweis: „{display}“"))
    return evidence


def _missing_cuda_library(exc: BaseException) -> bool:
    """Only retry errors indicating missing CUDA runtime libraries."""
    message = str(exc).lower()
    return any(name in message for name in (
        "cublas64_12.dll", "cublaslt64_12.dll", "cudnn64_9.dll",
        "cudnn_ops64_9.dll", "cudart64_12.dll",
        "libcublas.so", "libcudnn.so", "libcudart.so",
    )) and any(term in message for term in (
        "not found", "cannot be loaded", "could not load",
        "could not locate", "failed to load", "not available",
    ))


def transcribe_video(video: VideoInfo, model_directory: str, *,
                     progress: Progress | None = None,
                     cancelled: Cancelled | None = None) -> list[TranscriptSegment]:
    """Transcribe locally, retrying on CPU only for missing NVIDIA DLLs.

    A CTranslate2 model may construct successfully and fail *during generator
    iteration*, so the retry spans both construction and transcription.
    No automatic downloads or system-level CUDA changes are made.
    """
    from .media import CancelledError
    folder = Path(model_directory).expanduser()
    if not folder.is_dir():
        raise FileNotFoundError(f"Whisper-Modellordner fehlt: {folder}")
    if not video.has_audio:
        return []
    # Expose NVIDIA wheel DLLs to CTranslate2 before it imports native libraries.
    # Only the current process is affected; no global CUDA installation.
    from .gpu_runtime import enable_local_cuda_runtime
    enable_local_cuda_runtime()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError('Sprachmodul fehlt. Python: pip install -e ".[speech]"') from exc
    if cancelled and cancelled():
        raise CancelledError("Analyse abgebrochen")

    device = os.environ.get("STREAMCLIPPER_WHISPER_DEVICE", "auto").lower()
    if device not in {"auto", "cuda", "cpu"}:
        raise ValueError("STREAMCLIPPER_WHISPER_DEVICE: auto, cuda oder cpu erwartet")

    def transcribe_on(chosen_device: str) -> list[TranscriptSegment]:
        if cancelled and cancelled():
            raise CancelledError("Analyse abgebrochen")
        model = WhisperModel(str(folder), device=chosen_device,
                             compute_type="int8" if chosen_device == "cpu" else "default",
                             local_files_only=True)
        segments, _ = model.transcribe(
            video.path, beam_size=2, vad_filter=True,
            condition_on_previous_text=False,
        )
        spans: list[TranscriptSegment] = []
        try:
            for seg in segments:
                if cancelled and cancelled():
                    raise CancelledError("Analyse abgebrochen")
                start, end = float(seg.start), float(seg.end)
                phrase = " ".join(str(seg.text).split())
                if math.isfinite(start) and math.isfinite(end) and 0 <= start < end and phrase:
                    spans.append(TranscriptSegment(start, end, phrase))
                if progress:
                    progress(min(100, int(100 * seg.end / video.duration)))
        except TypeError as exc:
            if "metadata_errors" not in str(exc):
                raise
            raise RuntimeError(
                "Whisper/PyAV inkompatibel: bitte in der StreamClipper-Umgebung "
                r'.\\.venv\\Scripts\\python.exe -m pip install "av==17.1.0" ausführen.'
            ) from exc
        return spans

    try:
        spans = transcribe_on(device)
    except (RuntimeError, OSError) as exc:
        if device == "cpu" or not _missing_cuda_library(exc):
            raise
        if cancelled and cancelled():
            raise CancelledError("Analyse abgebrochen") from exc
        warnings.warn(
            "Whisper: CUDA-Bibliothek fehlt. Wechsle für diese Transkription auf CPU "
            "(langsamer). GPU-Betrieb benötigt CUDA 12 und passende cuDNN-Bibliotheken.",
            RuntimeWarning, stacklevel=2,
        )
        spans = transcribe_on("cpu")

    if progress:
        progress(100)
    return spans


def transcribe_reactions(video: VideoInfo, model_directory: str, *,
                         progress: Progress | None = None,
                         cancelled: Cancelled | None = None) -> list[EventEvidence]:
    """Compatibility adapter for existing speech-highlight callers."""
    segments = transcribe_video(video, model_directory, progress=progress,
                                cancelled=cancelled)
    return transcript_cues((s.start, s.end, s.text) for s in segments)


# Paired with neutral controls. These are image-level resemblance prompts, not
# event detectors: a screenshot cannot prove a collision or a chase occurred.
_VISUAL_LABELS: tuple[tuple[str, str, bool], ...] = (
    ("crash", "A screenshot of crashed cars and collision damage in a driving video game", True),
    ("explosion", "A screenshot of a large explosion or burning vehicle in a video game", True),
    ("chase", "A screenshot of a fast police pursuit in an open world driving video game", True),
    ("combat", "A screenshot of a dramatic shootout with weapons in a video game", True),
    ("ordinary", "A screenshot of normal peaceful driving in a video game", False),
    ("menu", "A screenshot of a video game menu interface or map", False),
    ("dialogue", "A screenshot of two video game characters having an ordinary conversation", False),
)
_VISUAL_NAMES = {
    "crash": "Fahrzeugkollision/Schaden",
    "explosion": "Explosion/Feuer",
    "chase": "Verfolgung",
    "combat": "Kampfszene",
}


def visual_match(scores: dict[str, float], at: float) -> EventEvidence | None:
    """Filter CLIP *relative scores*: reject frames dominated by neutral labels."""
    active = [(name, value) for name, value in scores.items() if name in _VISUAL_NAMES
              and math.isfinite(value)]
    neutral = [value for name, value in scores.items() if name not in _VISUAL_NAMES
               and math.isfinite(value)]
    if not active or not neutral:
        return None
    name, value = max(active, key=lambda entry: entry[1])
    # Probabilities from CLIP softmax are conditional on *this prompt set*.
    # Treat them strictly as relative image similarity, never as confidence.
    if value < 0.28 or value - max(neutral) < 0.08:
        return None
    return EventEvidence(at, "visual", min(0.78, 0.42 + (value - max(neutral)) * 0.6),
                         f"Bildähnlichkeit: {_VISUAL_NAMES[name]} (nicht verifiziert)")


def recognize_gameplay(video: VideoInfo, model_directory: str, *,
                       max_frames: int = 180,
                       progress: Progress | None = None,
                       cancelled: Cancelled | None = None) -> list[EventEvidence]:
    """Local CLIP zero-shot resemblance on a bounded sample of JPEG video frames."""
    from .media import CancelledError, sampled_jpeg_frames
    from .model_checks import validate_clip_model
    folder = validate_clip_model(model_directory)
    if max_frames < 1 or max_frames > 2000:
        raise ValueError("max_frames muss zwischen 1 und 2000 liegen")
    try:
        import torch
        from PIL import Image
        from transformers import AutoProcessor, CLIPModel
    except ImportError as exc:
        raise RuntimeError('Bildmodell fehlt. Python: pip install -e ".[vision]"') from exc
    if cancelled and cancelled():
        raise CancelledError("Analyse abgebrochen")
    processor = AutoProcessor.from_pretrained(str(folder), local_files_only=True)
    model = CLIPModel.from_pretrained(str(folder), local_files_only=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    labels = [name for name, _, _ in _VISUAL_LABELS]
    prompts = [prompt for _, prompt, _ in _VISUAL_LABELS]
    results = []
    for index, (at, data) in enumerate(sampled_jpeg_frames(video, max_frames=max_frames,
                                                          cancelled=cancelled)):
        if cancelled and cancelled():
            raise CancelledError("Analyse abgebrochen")
        with Image.open(BytesIO(data)) as image:
            inputs = processor(text=prompts, images=image.convert("RGB"),
                               return_tensors="pt", padding=True)
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.no_grad():
            probability = model(**inputs).logits_per_image.softmax(dim=1)[0].tolist()
        hit = visual_match(dict(zip(labels, probability)), at)
        if hit:
            results.append(hit)
        if progress:
            progress(min(100, int(100 * (index + 1) / max_frames)))
    if progress:
        progress(100)
    return results


def fuse_events(events: Iterable[EventEvidence], duration: float,
                clip_seconds: int = 25, max_clips: int = 8) -> list[Candidate]:
    """Rank context windows with explicit evidence; combination is a heuristic."""
    if duration <= 0 or clip_seconds < 5 or max_clips < 1:
        raise ValueError("Ungültige Analysedaten oder Parameter")
    from .analyze import _bounds
    valid = [ev for ev in events if math.isfinite(ev.at) and 0 <= ev.at <= duration
             and math.isfinite(ev.strength) and ev.kind in {"audio", "speech", "visual"}]
    if not valid:
        return []
    valid.sort(key=lambda ev: (ev.at, ev.kind, ev.description))
    proposed = []
    for anchor in valid:
        nearby = [event for event in valid if abs(event.at - anchor.at) <= 5.0]
        kinds = {event.kind for event in nearby}
        strongest = max(nearby, key=lambda e: (e.strength, e.kind))
        # Multiple independent modalities are more useful than many nearby
        # frames of the same moment. Do not present score as probability.
        strength = min(1.0, max(0.0, strongest.strength))
        score = min(99, round(18 + 56 * strength + 17 * (len(kinds) - 1)))
        ordering = sorted(nearby, key=lambda e: (-e.strength, e.kind))
        explanations = []
        for evidence in ordering:
            if evidence.kind not in explanations:
                explanations.append(evidence.kind)
        reasons = []
        for kind in explanations[:3]:
            example = next(ev for ev in ordering if ev.kind == kind)
            reasons.append(example.description)
        start, end = _bounds(anchor.at, duration, clip_seconds)
        proposed.append(Candidate(start, end, score, " | ".join(reasons), round(anchor.at, 3)))
    proposed.sort(key=lambda c: (-c.score, c.peak_at))
    chosen = []
    for candidate in proposed:
        if any(candidate.start < earlier.end and earlier.start < candidate.end for earlier in chosen):
            continue
        chosen.append(candidate)
        if len(chosen) == max_clips:
            break
    return chosen


def default_models_directory() -> Path:
    """User-owned, untracked directory for separately licensed model weights."""
    from .portable import local_model_directory
    return local_model_directory()
