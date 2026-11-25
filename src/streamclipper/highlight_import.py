"""Explicit, idempotent migration of analysis candidates into an M11 track plan.

The result describes original-source cuts only. It never reads, mixes,
renders or replaces the source video, and never auto-imports on reanalysis.
Imported item IDs are stable per source and millisecond range; they are kept
when the user subsequently edits or moves an imported item.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import math
import os

from .editor_project import EditorProject, TimelineItem, Track
from .models import AnalysisResult, Candidate

IMPORT_TRACK_ID = "highlights_import"
IMPORT_TRACK_NAME = "Highlights (Import)"
_MAX_CANDIDATES = 5000


def _source_key(source: str) -> str:
    return os.path.normcase(os.path.abspath(source))


def _milliseconds(value: float) -> int:
    return round(value * 1000)


def _candidate_range(candidate: Candidate, duration: float) -> tuple[int, int]:
    if (not isinstance(candidate, Candidate)
            or candidate.origin not in {"auto", "manual"}
            or not isinstance(candidate.reason, str)
            or len(candidate.reason) > 4096
            or not isinstance(candidate.score, (int, float))
            or not all(isinstance(n, (int, float)) and math.isfinite(n)
                       for n in (candidate.start, candidate.end, candidate.peak_at,
                                 candidate.score))
            or not (0 <= candidate.start < candidate.end <= duration + .1)):
        raise ValueError("Highlight enthält ungültige Herkunft, Werte oder Zeitgrenzen")
    start, end = _milliseconds(candidate.start), _milliseconds(candidate.end)
    if start >= end:
        raise ValueError("Highlight-Zeitfenster ist zu kurz für Millisekundenauflösung")
    return start, end


def _clip_id(source: str, start: int, end: int) -> str:
    payload = f"streamclipper-import-v1|{source}|{start}|{end}"
    return "hl_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def import_analysis_candidates(
        project: EditorProject, analysis: AnalysisResult, *,
        track_id: str | None = None) -> EditorProject:
    """Copy validated candidate *metadata* onto a video track, atomically.

    With track_id=None the existing dedicated 'Highlights (Import)' video
    track is used, or created only if at least one clip needs importing.
    Providing track_id explicitly targets an already existing video track.
    Existing imported IDs are never overwritten, even after user edits.
    Exact pre-existing source/timeline ranges on the chosen track are
    considered duplicates, including clips created manually.
    """
    project.validate()
    if (not isinstance(analysis, AnalysisResult)
            or not isinstance(analysis.video.path, str)
            or not isinstance(analysis.video.duration, (int, float))
            or not math.isfinite(analysis.video.duration)
            or _source_key(project.source.path) != _source_key(analysis.video.path)
            or abs(project.source.duration - analysis.video.duration) > .25
            or (project.source.width, project.source.height) !=
               (analysis.video.width, analysis.video.height)):
        raise ValueError("Analyse gehört zu einer anderen Aufnahme")
    if not isinstance(analysis.candidates, list) or len(analysis.candidates) > _MAX_CANDIDATES:
        raise ValueError("Zu viele Highlights für den Import")

    requested_id = IMPORT_TRACK_ID if track_id is None else track_id
    if not isinstance(requested_id, str):
        raise ValueError("Zielspur ist ungültig")
    destination = next((t for t in project.tracks if t.id == requested_id), None)
    if destination is None and track_id is not None:
        raise ValueError("Zielspur nicht vorhanden")
    if destination is not None:
        if destination.kind != "video":
            raise ValueError("Highlights können nur in eine Videospur importiert werden")
        if destination.locked:
            raise ValueError("Zielspur ist gesperrt")

    # Validate all candidates before changing any project item, even if one
    # already exists or has been manually altered after an earlier import.
    normalized = [
        (_candidate_range(candidate, project.source.duration), candidate)
        for candidate in analysis.candidates
    ]
    if not normalized:
        return project

    existing_ids = {item.id for item in project.items}
    existing_ranges = {
        (_milliseconds(item.source_start), _milliseconds(item.source_end),
         _milliseconds(item.timeline_start))
        for item in project.items if item.track_id == requested_id
    }
    new_items: list[TimelineItem] = []
    for (start, end), candidate in normalized:
        candidate_id = _clip_id(_source_key(project.source.path), start, end)
        source_range = (start, end, start)
        if candidate_id in existing_ids or source_range in existing_ranges:
            continue
        prefix = "Manuell · " if candidate.origin == "manual" else "Vorschlag · "
        detail = " ".join(candidate.reason.split()) or "Highlight"
        label = (prefix + detail)[:120]
        new_items.append(TimelineItem(
            candidate_id, requested_id, start / 1000.0, end / 1000.0,
            start / 1000.0, label))
        existing_ids.add(candidate_id)
        existing_ranges.add(source_range)

    if not new_items:
        return project
    tracks = project.tracks
    if destination is None:
        if len(tracks) >= 100:
            raise ValueError("Zu viele Spuren für den Highlight-Import")
        tracks += (Track(IMPORT_TRACK_ID, "video", IMPORT_TRACK_NAME),)
    updated = replace(project, tracks=tracks, items=(*project.items, *new_items))
    updated.validate()  # includes clip-count and 24h timeline limits
    return updated
