"""Offline, timestamped transcription export; never modify the source video.

SRT/VTT timestamps are relative to the original recording. Clip-specific
caption burning and speaker diarization are intentionally out of scope.
"""
from __future__ import annotations

import math
from pathlib import Path

from .models import TranscriptSegment

SUPPORTED_FORMATS = frozenset({"srt", "vtt", "txt"})


def _timestamp(seconds: float, *, srt: bool) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Ungültiger Transkript-Zeitstempel")
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{',' if srt else '.'}{ms:03d}"


def render_transcript(segments: list[TranscriptSegment], fmt: str = "srt") -> str:
    """Convert timed Whisper segments to UTF-8-friendly subtitle/text formats."""
    fmt = fmt.lower().lstrip(".")
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError("Transkriptformat muss srt, vtt oder txt sein")
    entries: list[tuple[float, float, str]] = []
    for segment in segments:
        if not (math.isfinite(segment.start) and math.isfinite(segment.end)):
            raise ValueError("Transkript enthält nicht-endliche Zeitstempel")
        if segment.start < 0 or segment.end <= segment.start:
            raise ValueError("Transkript enthält ungültige Zeitgrenzen")
        text = " ".join(segment.text.split())
        if text:
            entries.append((segment.start, segment.end, text))
    entries.sort(key=lambda item: (item[0], item[1]))
    if fmt == "txt":
        return "".join(f"[{_timestamp(start, srt=False)}] {text}\n"
                       for start, _, text in entries)
    lines = ["WEBVTT", ""] if fmt == "vtt" else []
    for idx, (start, end, text) in enumerate(entries, start=1):
        if fmt == "srt":
            lines.append(str(idx))
        lines.extend([f"{_timestamp(start, srt=fmt == 'srt')} --> "
                      f"{_timestamp(end, srt=fmt == 'srt')}", text, ""])
    return "\n".join(lines) + ("\n" if lines else "")


def save_transcript(segments: list[TranscriptSegment], destination: str | Path) -> Path:
    """Create a transcript exclusively; never overwrite an existing user file."""
    target = Path(destination).expanduser().resolve()
    fmt = target.suffix.lower().lstrip(".")
    payload = render_transcript(segments, fmt)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    return target
