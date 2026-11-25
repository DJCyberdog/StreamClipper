"""Compact undo/redo for non-destructive changes; no Qt or models loaded."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Generic, Sequence, TypeVar
import os
from .editor_project import EditorProject
from .models import AnalysisResult, Candidate, TranscriptSegment, VideoInfo

T = TypeVar("T")

@dataclass(frozen=True)
class _Splice(Generic[T]):
    start: int
    removed: tuple[T, ...]
    inserted: tuple[T, ...]

    def apply(self, items: Sequence[T], *, reverse: bool = False) -> list[T]:
        expected = self.inserted if reverse else self.removed
        replacement = self.removed if reverse else self.inserted
        end = self.start + len(expected)
        if tuple(items[self.start:end]) != expected:
            raise ValueError("Bearbeitungsverlauf passt nicht mehr zum Projekt")
        return [*items[:self.start], *replacement, *items[end:]]

def _diff(old: Sequence[T], new: Sequence[T]) -> _Splice[T] | None:
    if old == new:
        return None
    offset = 0
    boundary = min(len(old), len(new))
    while offset < boundary and old[offset] == new[offset]:
        offset += 1
    suffix = 0
    while (suffix < len(old)-offset and suffix < len(new)-offset
           and old[len(old)-suffix-1] == new[len(new)-suffix-1]):
        suffix += 1
    return _Splice(offset,
                   tuple(old[offset:len(old)-suffix if suffix else len(old)]),
                   tuple(new[offset:len(new)-suffix if suffix else len(new)]))

@dataclass(frozen=True)
class _Command:
    candidates: _Splice[Candidate] | None
    transcript: _Splice[TranscriptSegment] | None

    def apply(self, current: AnalysisResult, *, reverse: bool = False) -> AnalysisResult:
        clips = self.candidates.apply(current.candidates, reverse=reverse) if self.candidates else current.candidates
        cues = self.transcript.apply(current.transcript, reverse=reverse) if self.transcript else current.transcript
        return replace(current, candidates=clips, transcript=cues)

class EditHistory:
    """Unbounded number of commands; each stores just the changed clip/cue slice."""
    def __init__(self) -> None:
        self._past: list[_Command] = []
        self._future: list[_Command] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._past)

    @property
    def can_redo(self) -> bool:
        return bool(self._future)

    def clear(self) -> None:
        self._past.clear()
        self._future.clear()

    def record(self, before: AnalysisResult, after: AnalysisResult) -> bool:
        if before.video != after.video or before.method != after.method:
            raise ValueError("Bearbeitungsverlauf darf nicht zwischen Projekten wechseln")
        clips, cues = _diff(before.candidates, after.candidates), _diff(before.transcript, after.transcript)
        if clips is None and cues is None:
            return False
        self._past.append(_Command(clips, cues))
        self._future.clear()
        return True

    def undo(self, current: AnalysisResult) -> AnalysisResult:
        if not self._past:
            return current
        item = self._past[-1]
        previous = item.apply(current, reverse=True)
        self._past.pop()
        self._future.append(item)
        return previous

    def redo(self, current: AnalysisResult) -> AnalysisResult:
        if not self._future:
            return current
        item = self._future[-1]
        following = item.apply(current)
        self._future.pop()
        self._past.append(item)
        return following


@dataclass(frozen=True)
class _WorkspaceStep:
    """Exactly one edit domain; analysis changes retain compact splice deltas."""
    kind: str
    source: VideoInfo
    analysis: _Command | None = None
    analysis_method: str | None = None
    project_before: EditorProject | None = None
    project_after: EditorProject | None = None


class WorkspaceHistory:
    """One ordered undo/redo stack across analysis, subtitles and track metadata.

    Core-only; callers persist project metadata before publishing the returned
    state in the GUI. Failed validation never consumes an undo/redo entry.
    The history is session-local and is reset when an external report,
    checkpoint, reanalysis or source is loaded.
    """
    def __init__(self) -> None:
        self._past: list[_WorkspaceStep] = []
        self._future: list[_WorkspaceStep] = []
        self._source: VideoInfo | None = None

    @property
    def can_undo(self) -> bool:
        return bool(self._past)

    @property
    def can_redo(self) -> bool:
        return bool(self._future)

    @property
    def undo_kind(self) -> str | None:
        return self._past[-1].kind if self._past else None

    @property
    def redo_kind(self) -> str | None:
        return self._future[-1].kind if self._future else None

    def clear(self) -> None:
        self._past.clear()
        self._future.clear()
        self._source = None

    def _guard_source(self, video: VideoInfo) -> None:
        if self._source is None:
            self._source = video
        else:
            older = self._source
            if (os.path.normcase(os.path.abspath(older.path)) !=
                    os.path.normcase(os.path.abspath(video.path))
                    or abs(older.duration - video.duration) > .25
                    or (older.width, older.height) != (video.width, video.height)):
                raise ValueError("Bearbeitungsverlauf gehört zu einer anderen Quelle")

    def record_analysis(self, before: AnalysisResult, after: AnalysisResult) -> bool:
        if before.video != after.video or before.method != after.method:
            raise ValueError("Bearbeitungsverlauf darf nicht zwischen Quellen wechseln")
        clips = _diff(before.candidates, after.candidates)
        cues = _diff(before.transcript, after.transcript)
        if clips is None and cues is None:
            return False
        self._guard_source(before.video)
        self._past.append(_WorkspaceStep(
            "analysis", before.video, _Command(clips, cues), before.method))
        self._future.clear()
        return True

    def record_project(self, before: EditorProject, after: EditorProject) -> bool:
        if before.source != after.source:
            raise ValueError("Bearbeitungsverlauf darf nicht zwischen Quellen wechseln")
        if before == after:
            return False
        before.validate()
        after.validate()
        self._guard_source(before.source)
        self._past.append(_WorkspaceStep(
            "project", before.source, project_before=before, project_after=after))
        self._future.clear()
        return True

    def _apply(self, entry: _WorkspaceStep, analysis: AnalysisResult | None,
               project: EditorProject | None, *, reverse: bool
               ) -> tuple[AnalysisResult | None, EditorProject | None]:
        if entry.kind == "analysis":
            if (analysis is None or analysis.video != entry.source
                    or analysis.method != entry.analysis_method
                    or entry.analysis is None):
                raise ValueError("Analyse-Verlauf ist nicht konsistent")
            return entry.analysis.apply(analysis, reverse=reverse), project
        if entry.kind == "project":
            expected = entry.project_after if reverse else entry.project_before
            updated = entry.project_before if reverse else entry.project_after
            if project != expected or updated is None:
                raise ValueError("Spurenverlauf ist nicht konsistent")
            return analysis, updated
        raise ValueError("Unbekannte Bearbeitungsaktion")

    def undo(self, analysis: AnalysisResult | None,
             project: EditorProject | None
             ) -> tuple[AnalysisResult | None, EditorProject | None]:
        if not self._past:
            return analysis, project
        step = self._past[-1]
        next_state = self._apply(step, analysis, project, reverse=True)
        self._past.pop()
        self._future.append(step)
        return next_state

    def redo(self, analysis: AnalysisResult | None,
             project: EditorProject | None
             ) -> tuple[AnalysisResult | None, EditorProject | None]:
        if not self._future:
            return analysis, project
        step = self._future[-1]
        next_state = self._apply(step, analysis, project, reverse=False)
        self._future.pop()
        self._past.append(step)
        return next_state
