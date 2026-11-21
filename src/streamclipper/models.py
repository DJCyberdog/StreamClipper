"""Serializable data models; no GUI dependencies."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json


@dataclass(frozen=True)
class VideoInfo:
    path: str
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


@dataclass(frozen=True)
class Candidate:
    start: float
    end: float
    score: int
    reason: str
    peak_at: float


@dataclass(frozen=True)
class TranscriptSegment:
    """Timestamped speech recognized by a local model (not speaker-labeled)."""
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class AnalysisResult:
    video: VideoInfo
    candidates: list[Candidate]
    method: str = "audio-rms-peaks-v1"
    transcript: list[TranscriptSegment] = field(default_factory=list)

    def save_json(self, filename: str | Path) -> None:
        destination = Path(filename)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
