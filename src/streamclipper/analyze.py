"""Deterministic baseline analyzer; high score is not a virality prediction."""
from __future__ import annotations

import math
import statistics
from typing import Callable

from .media import audio_levels, probe_video
from .model_checks import validate_clip_model
from .models import AnalysisResult, Candidate
from .semantic import EventEvidence, fuse_events, recognize_gameplay, transcribe_video, transcript_cues


def _bounds(center: float, duration: float, clip_seconds: int, preroll: float = 8.0) -> tuple[float, float]:
    length = min(clip_seconds, duration)
    start = max(0.0, min(center - preroll, duration - length))
    return round(start, 3), round(min(duration, start + length), 3)


def find_candidates(levels: list[float], duration: float, clip_seconds: int = 25,
                    max_clips: int = 8) -> list[Candidate]:
    if duration <= 0 or clip_seconds < 5 or max_clips < 1:
        raise ValueError("Ungültige Analysedaten oder Parameter")
    if not levels or max(levels) <= -75:
        # No audio: time samples, clearly marked as low-confidence suggestions.
        n = min(max_clips, max(1, int(math.ceil(duration / max(clip_seconds * 2, 1)))))
        return [Candidate(*_bounds(duration * (i + 0.5) / n, duration, clip_seconds),
                          score=0, reason="Zeitstichprobe – keine verwertbare Audiospur",
                          peak_at=round(duration * (i + 0.5) / n, 3)) for i in range(n)]

    baseline = statistics.median(levels)
    # Candidate timestamp is the center of the one-second RMS bucket.
    loudest = sorted(range(len(levels)), key=lambda i: levels[i], reverse=True)
    picks: list[Candidate] = []
    separation = max(10.0, clip_seconds * 0.75)
    for i in loudest:
        center = min(duration, i + 0.5)
        delta = levels[i] - baseline
        # Audio peak is a rough proxy, not an understanding of the actual gameplay.
        score = int(max(1, min(99, round(30 + 7 * delta))))
        start, end = _bounds(center, duration, clip_seconds)
        if any(not (end <= p.start or start >= p.end) for p in picks):
            continue
        if any(abs(center - p.peak_at) < separation for p in picks):
            continue
        picks.append(Candidate(start, end, score,
                               f"Audio-Peak: {delta:+.1f} dB gegenüber Median",
                               round(center, 3)))
        if len(picks) >= max_clips:
            break
    # Preserve loudest-first ranking; deterministic tie-break at earlier timestamps.
    return picks


def analyze(path: str, clip_seconds: int = 25, max_clips: int = 8,
            progress: Callable[[int], None] | None = None,
            cancelled: Callable[[], bool] | None = None,
            speech_model: str | None = None, vision_model: str | None = None,
            max_visual_frames: int = 180) -> AnalysisResult:
    """Analyze audio and, when requested, local transcript / gameplay images.

    No model downloads and no external API calls. Model paths are opt-in.
    """
    # Missing CLIP weights must fail before decoding hours of audio or running Whisper.
    if vision_model:
        validate_clip_model(vision_model)
    video = probe_video(path)
    use_models = bool(speech_model or vision_model)
    def stage(base: int, portion: int):
        return (lambda value: progress(base + round(value * portion / 100))) if progress else None

    levels = audio_levels(video, progress=stage(0, 35 if use_models else 100),
                          cancelled=cancelled)
    baseline = find_candidates(levels, video.duration, clip_seconds, max_clips)
    if not use_models:
        return AnalysisResult(video, baseline)

    # Baseline peak scores are only heuristic proxies. Keep them as weak
    # evidence so language and image matches can take precedence.
    peak_candidates = find_candidates(levels, video.duration, clip_seconds,
                                      max(24, max_clips * 4))
    evidence = [EventEvidence(c.peak_at, "audio", 0.28,
                              c.reason) for c in peak_candidates if c.score > 30]
    transcript = []
    if speech_model:
        transcript = transcribe_video(video, speech_model,
                         progress=stage(35, 35 if vision_model else 65),
                         cancelled=cancelled)
        evidence.extend(transcript_cues((s.start, s.end, s.text) for s in transcript))
    if vision_model:
        evidence.extend(recognize_gameplay(video, vision_model,
                         max_frames=max_visual_frames, progress=stage(70 if speech_model else 35,
                         30 if speech_model else 65), cancelled=cancelled))
    ranked = fuse_events(evidence, video.duration, clip_seconds, max_clips)
    if progress:
        progress(100)
    return AnalysisResult(video, ranked or baseline,
                          method="multimodal-evidence-v1", transcript=transcript)
