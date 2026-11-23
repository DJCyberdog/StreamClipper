"""Versioned, offline editor track metadata (M11 and M12b).

The v2 schema optionally references local audio files for the explicit M12b
render path. Older v1 plans/checkpoints migrate in memory; never rewrite video
or audio sources. Qt and ML dependencies are intentionally absent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from .models import VideoInfo
from .portable import installation_directory

SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
_KINDS = frozenset({"video", "audio", "captions", "overlay"})
_ID = re.compile(r"[a-zA-Z0-9_-]{1,64}\Z")
_MAX_ITEMS = 5000
_MAX_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class Track:
    id: str
    kind: str
    name: str
    muted: bool = False
    locked: bool = False
    hidden: bool = False


@dataclass(frozen=True)
class TimelineItem:
    id: str
    track_id: str
    source_start: float
    source_end: float
    timeline_start: float
    label: str = ""
    media_path: str | None = None  # external local audio, never network URL
    gain_db: float = 0.0  # per-clip relative level (no side effects on source)


@dataclass(frozen=True)
class EditorProject:
    schema_version: int
    source: VideoInfo
    tracks: tuple[Track, ...]
    items: tuple[TimelineItem, ...]

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("Unbekannte Projektformat-Version")
        if not isinstance(self.source.path, str) or not self.source.path:
            raise ValueError("Projektquelle fehlt")
        if not math.isfinite(self.source.duration) or self.source.duration <= 0:
            raise ValueError("Projekt hat keine gültige Aufnahmedauer")
        if self.source.width < 1 or self.source.height < 1:
            raise ValueError("Ungültige Videoauflösung")
        if not 1 <= len(self.tracks) <= 100 or len(self.items) > _MAX_ITEMS:
            raise ValueError("Zu viele oder keine Spuren / Clips")
        ids = set()
        for track in self.tracks:
            if (not _ID.fullmatch(track.id) or track.id in ids
                    or track.kind not in _KINDS or not isinstance(track.name, str)
                    or not 1 <= len(track.name.strip()) <= 80
                    or not all(isinstance(flag, bool)
                               for flag in (track.muted, track.locked, track.hidden))):
                raise ValueError("Ungültige oder doppelte Spur")
            ids.add(track.id)
        if not any(track.kind == "video" for track in self.tracks):
            raise ValueError("Mindestens eine Videospur erforderlich")
        clip_ids = set()
        for item in self.items:
            if (not _ID.fullmatch(item.id) or item.id in clip_ids
                    or item.track_id not in ids or not isinstance(item.label, str)
                    or len(item.label) > 120
                    or not isinstance(item.gain_db, (int, float))
                    or not math.isfinite(item.gain_db)
                    or not -60 <= item.gain_db <= 12):
                raise ValueError("Ungültiger oder doppelter Clip")
            clip_ids.add(item.id)
            a, b, t = item.source_start, item.source_end, item.timeline_start
            track = next(x for x in self.tracks if x.id == item.track_id)
            if item.media_path is not None:
                if (track.kind != "audio" or not isinstance(item.media_path, str)
                        or not item.media_path or len(item.media_path) > 4096
                        or not Path(item.media_path).is_absolute()
                        or any(ord(ch) < 32 for ch in item.media_path)
                        or "://" in item.media_path):
                    raise ValueError("Externe Audiodatei muss ein absoluter lokaler Pfad sein")
            limit = 24 * 3600 if item.media_path else self.source.duration + .10
            if (not all(isinstance(n, (int, float)) and math.isfinite(n)
                        for n in (a, b, t))
                    or not (0 <= a < b <= limit)
                    or t < 0 or t + b - a > 24 * 3600):
                raise ValueError("Clip-Zeitbereich außerhalb der Aufnahme")


def initial_project(video: VideoInfo) -> EditorProject:
    tracks = (
        Track("gameplay", "video", "Gameplay"),
        Track("mic", "audio", "Mikrofon"),
        Track("music", "audio", "Musik"),
        Track("captions", "captions", "Untertitel"),
        Track("graphics", "overlay", "Grafiken"),
    )
    project = EditorProject(
        SCHEMA_VERSION, video, tracks,
        (TimelineItem("source", "gameplay", 0, video.duration, 0, "Originalaufnahme"),))
    project.validate()
    return project


def _replace_track(project: EditorProject, track_id: str, **changes) -> EditorProject:
    found = False
    tracks = []
    for track in project.tracks:
        if track.id == track_id:
            found = True
            track = replace(track, **changes)
        tracks.append(track)
    if not found:
        raise ValueError("Spur nicht gefunden")
    updated = replace(project, tracks=tuple(tracks))
    updated.validate()
    return updated


def rename_track(project: EditorProject, track_id: str, name: str) -> EditorProject:
    return _replace_track(project, track_id, name=name.strip())


def toggle_track(project: EditorProject, track_id: str, field: str) -> EditorProject:
    if field not in {"muted", "locked", "hidden"}:
        raise ValueError("Ungültige Spureigenschaft")
    track = next((t for t in project.tracks if t.id == track_id), None)
    if not track:
        raise ValueError("Spur nicht gefunden")
    return _replace_track(project, track_id, **{field: not getattr(track, field)})


def add_track(project: EditorProject, kind: str, name: str) -> EditorProject:
    if kind not in _KINDS:
        raise ValueError("Unbekannter Spurtyp")
    ids = {t.id for t in project.tracks}
    index = 1
    while f"{kind}_{index}" in ids:
        index += 1
    track = Track(f"{kind}_{index}", kind, name.strip())
    updated = replace(project, tracks=(*project.tracks, track))
    updated.validate()
    return updated


def remove_track(project: EditorProject, track_id: str) -> EditorProject:
    track = next((t for t in project.tracks if t.id == track_id), None)
    if track is None:
        raise ValueError("Spur nicht gefunden")
    if track.id == "gameplay" or any(item.track_id == track_id for item in project.items):
        raise ValueError("Diese Spur enthält Clips oder ist die Hauptvideospur")
    updated = replace(project, tracks=tuple(t for t in project.tracks if t.id != track_id))
    updated.validate()
    return updated


def move_track(project: EditorProject, track_id: str, direction: int) -> EditorProject:
    tracks = list(project.tracks)
    index = next((i for i, t in enumerate(tracks) if t.id == track_id), None)
    if index is None or direction not in {-1, 1} or not 0 <= index + direction < len(tracks):
        raise ValueError("Spur kann nicht verschoben werden")
    tracks[index], tracks[index + direction] = tracks[index + direction], tracks[index]
    return replace(project, tracks=tuple(tracks))


def _item_index(project: EditorProject, item_id: str) -> int:
    idx = next((i for i, item in enumerate(project.items) if item.id == item_id), None)
    if idx is None:
        raise ValueError("Clip nicht gefunden")
    return idx


def edit_item(project: EditorProject, item_id: str, *,
              track_id: str | None = None, source_start: float | None = None,
              source_end: float | None = None,
              timeline_start: float | None = None) -> EditorProject:
    i = _item_index(project, item_id)
    before = project.items[i]
    destination = track_id or before.track_id
    locked = {t.id for t in project.tracks if t.locked}
    if before.track_id in locked or destination in locked:
        raise ValueError("Gesperrte Spur kann nicht bearbeitet werden")
    candidate = replace(
        before, track_id=destination,
        source_start=before.source_start if source_start is None else source_start,
        source_end=before.source_end if source_end is None else source_end,
        timeline_start=before.timeline_start if timeline_start is None else timeline_start)
    items = list(project.items)
    items[i] = candidate
    updated = replace(project, items=tuple(items))
    updated.validate()
    return updated


def add_item(project: EditorProject, track_id: str, start: float,
             end: float, timeline_start: float, label: str = "",
             *, media_path: str | None = None, gain_db: float = 0.0) -> EditorProject:
    track = next((t for t in project.tracks if t.id == track_id), None)
    if not track or track.locked:
        raise ValueError("Zielspur fehlt oder ist gesperrt")
    ids = {item.id for item in project.items}
    index = 1
    while f"clip_{index}" in ids:
        index += 1
    updated = replace(
        project, items=(*project.items,
                        TimelineItem(f"clip_{index}", track_id, start, end,
                                     timeline_start, label, media_path,
                                     gain_db)))
    updated.validate()
    return updated


class ProjectHistory:
    """Undo/redo lightweight project metadata, not waveform or media bytes."""
    def __init__(self) -> None:
        self._past: list[tuple[EditorProject, EditorProject]] = []
        self._future: list[tuple[EditorProject, EditorProject]] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._past)

    @property
    def can_redo(self) -> bool:
        return bool(self._future)

    def record(self, before: EditorProject, after: EditorProject) -> None:
        if before.source != after.source:
            raise ValueError("Verlauf darf nicht zwischen Quellen wechseln")
        if before != after:
            self._past.append((before, after))
            self._future.clear()

    def undo(self, current: EditorProject) -> EditorProject:
        if not self._past:
            return current
        before, after = self._past[-1]
        if current != after:
            raise ValueError("Spurenverlauf ist nicht konsistent")
        self._past.pop()
        self._future.append((before, after))
        return before

    def redo(self, current: EditorProject) -> EditorProject:
        if not self._future:
            return current
        before, after = self._future[-1]
        if current != before:
            raise ValueError("Spurenverlauf ist nicht konsistent")
        self._future.pop()
        self._past.append((before, after))
        return after


def project_path(source: str | Path, *, root: Path | None = None) -> Path:
    canonical = os.path.normcase(os.path.abspath(os.fspath(source)))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    directory = (Path(root) if root is not None else
                 installation_directory() / "data" / "projects" / "editor")
    return directory / f"{fingerprint}.project.json"


def save_project(project: EditorProject, *, root: Path | None = None) -> Path:
    project.validate()
    destination = project_path(project.source.path, root=root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(project), ensure_ascii=False, indent=2)
    stage: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False,
            dir=destination.parent, prefix=f".{destination.name}.",
            suffix=".tmp") as handle:
            stage = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, destination)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
    return destination


def load_project(video: VideoInfo, *, root: Path | None = None) -> EditorProject:
    path = project_path(video.path, root=root)
    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("Projektdatei ist zu groß")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(doc, dict)
                or doc.get("schema_version") not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}):
            raise ValueError("Unbekannte Projektformat-Version")
        project = EditorProject(
            SCHEMA_VERSION, VideoInfo(**doc["source"]),
            tuple(Track(**record) for record in doc["tracks"]),
            tuple(TimelineItem(**record) for record in doc["items"]))
        project.validate()
        a, b = project.source, video
        if (os.path.normcase(os.path.abspath(a.path))
                != os.path.normcase(os.path.abspath(b.path))
                or abs(a.duration - b.duration) > 0.25
                or (a.width, a.height) != (b.width, b.height)):
            raise ValueError("Projekt gehört zu einer anderen Videoaufnahme")
        return project
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Spurenprojekt ist ungültig: {exc}") from exc
