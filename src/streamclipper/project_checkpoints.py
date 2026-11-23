"""M11c: source-bound, atomic, versioned editor checkpoints (offline only).

A checkpoint snapshots *metadata*, not media bytes. The video is never copied,
deleted or rewritten. Checksums detect accidental corruption, not malicious edits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4

from .editor_project import EditorProject, SCHEMA_VERSION, LEGACY_SCHEMA_VERSION, TimelineItem, Track
from .models import AnalysisResult, Candidate, TranscriptSegment, TranscriptWord, VideoInfo
from .portable import installation_directory
from .transcript_editor import validate_segments

FORMAT_VERSION = 1
MAX_CHECKPOINTS = 20
MAX_BYTES = 32 * 1024 * 1024
_CHECKPOINT_ID = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class CheckpointInfo:
    id: str
    name: str
    created_at: str
    has_analysis: bool


def checkpoint_dir(source: str | Path, *, root: Path | None = None) -> Path:
    absolute = os.path.normcase(os.path.abspath(os.fspath(source)))
    key = hashlib.sha256(absolute.encode("utf-8")).hexdigest()[:32]
    base = Path(root) if root is not None else (
        installation_directory() / "data" / "projects" / "checkpoints")
    return base / key


def _matches(left: VideoInfo, right: VideoInfo) -> bool:
    return (os.path.normcase(os.path.abspath(left.path)) ==
            os.path.normcase(os.path.abspath(right.path))
            and abs(left.duration - right.duration) <= 0.25
            and (left.width, left.height) == (right.width, right.height))


def _validate_analysis(analysis: AnalysisResult, video: VideoInfo) -> None:
    if not _matches(analysis.video, video):
        raise ValueError("Analyse gehört zu einer anderen Aufnahme")
    if not isinstance(analysis.method, str) or len(analysis.method) > 200:
        raise ValueError("Ungültige Analysemethode")
    if len(analysis.candidates) > 100000 or len(analysis.transcript) > 100000:
        raise ValueError("Analyse enthält zu viele Einträge")
    validate_segments(analysis.transcript, video.duration)
    for clip in analysis.candidates:
        if (not isinstance(clip, Candidate)
                or clip.origin not in {"auto", "manual"}
                or not all(isinstance(x, (int, float)) and math.isfinite(x)
                           for x in (clip.start, clip.end, clip.peak_at))
                or not 0 <= clip.start < clip.end <= video.duration + 0.1
                or not isinstance(clip.reason, str)):
            raise ValueError("Ungültiger Highlight-Eintrag")


def _hash(value: dict) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def create_checkpoint(project: EditorProject, name: str,
                      analysis: AnalysisResult | None = None, *,
                      root: Path | None = None,
                      max_count: int = MAX_CHECKPOINTS) -> CheckpointInfo:
    """Publish a complete snapshot first; only then prune older valid snapshots."""
    project.validate()
    label = name.strip() if isinstance(name, str) else ""
    if (not 1 <= len(label) <= 80 or
            any(ord(ch) < 32 or ord(ch) == 127 for ch in label)):
        raise ValueError("Projektstand benötigt einen Namen (maximal 80 Zeichen)")
    if not 1 <= max_count <= 100:
        raise ValueError("Ungültige Aufbewahrungsgrenze")
    if analysis is not None:
        _validate_analysis(analysis, project.source)

    info = CheckpointInfo(uuid4().hex, label,
                          datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                          analysis is not None)
    data = {"format_version": FORMAT_VERSION, "info": asdict(info),
            "project": asdict(project),
            "analysis": asdict(analysis) if analysis is not None else None}
    envelope = {"data": data, "sha256": _hash(data)}
    payload = json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise ValueError("Projektstand ist zu groß")
    folder = checkpoint_dir(project.source.path, root=root)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{info.id}.checkpoint.json"
    stage: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=folder, prefix=f".{info.id}.",
                suffix=".tmp", delete=False) as handle:
            stage = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, dest)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)

    # Corrupt or unknown files are never deleted automatically.
    for old in list_checkpoints(project.source, root=root)[max_count:]:
        (folder / f"{old.id}.checkpoint.json").unlink(missing_ok=True)
    return info


def load_checkpoint(video: VideoInfo, checkpoint_id: str, *,
                    root: Path | None = None) -> tuple[EditorProject, AnalysisResult | None]:
    if not isinstance(checkpoint_id, str) or not _CHECKPOINT_ID.fullmatch(checkpoint_id):
        raise ValueError("Ungültige Projektstand-ID")
    path = checkpoint_dir(video.path, root=root) / f"{checkpoint_id}.checkpoint.json"
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Projektstand ist zu groß")
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        data = envelope["data"]
        if (data["format_version"] != FORMAT_VERSION
                or envelope["sha256"] != _hash(data)):
            raise ValueError("Projektstand beschädigt oder unbekannte Version")
        info = CheckpointInfo(**data["info"])
        if info.id != checkpoint_id or not 1 <= len(info.name.strip()) <= 80:
            raise ValueError("Projektstand-Metadaten ungültig")
        datetime.fromisoformat(info.created_at)
        source = VideoInfo(**data["project"]["source"])
        project = EditorProject(
            SCHEMA_VERSION if data["project"]["schema_version"] in
            {SCHEMA_VERSION, LEGACY_SCHEMA_VERSION} else -1,
            source, tuple(Track(**t) for t in data["project"]["tracks"]),
            tuple(TimelineItem(**item) for item in data["project"]["items"]))
        project.validate()
        if not _matches(source, video):
            raise ValueError("Projektstand gehört zu einer anderen Aufnahme")
        a = data["analysis"]
        analysis = None
        if a is not None:
            cues = [TranscriptSegment(
                float(cue["start"]), float(cue["end"]), str(cue["text"]),
                tuple(TranscriptWord(**word) for word in cue.get("words", [])))
                for cue in a.get("transcript", [])]
            analysis = AnalysisResult(VideoInfo(**a["video"]),
                                      [Candidate(**clip) for clip in a.get("candidates", [])],
                                      str(a["method"]), cues)
            _validate_analysis(analysis, source)
        if info.has_analysis != (analysis is not None):
            raise ValueError("Projektstand ist unvollständig")
        return project, analysis
    except (KeyError, TypeError, AttributeError, OverflowError, ValueError,
            json.JSONDecodeError) as exc:
        raise ValueError(f"Projektstand nicht lesbar: {exc}") from exc


def list_checkpoints(video: VideoInfo, *, root: Path | None = None) -> list[CheckpointInfo]:
    folder = checkpoint_dir(video.path, root=root)
    if not folder.is_dir():
        return []
    result: list[CheckpointInfo] = []
    # Only regular, known-name files. Invalid files are not offered for restore.
    for path in folder.glob("*.checkpoint.json"):
        checkpoint_id = path.name.removesuffix(".checkpoint.json")
        if not _CHECKPOINT_ID.fullmatch(checkpoint_id) or not path.is_file():
            continue
        try:
            project, analysis = load_checkpoint(video, checkpoint_id, root=root)
            raw = json.loads(path.read_text(encoding="utf-8"))
            entry = CheckpointInfo(**raw["data"]["info"])
            if project and (analysis is not None) == entry.has_analysis:
                result.append(entry)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(result, key=lambda x: (x.created_at, x.id), reverse=True)
