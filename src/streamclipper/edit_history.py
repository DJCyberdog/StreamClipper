"""Compact undo/redo for non-destructive changes; no Qt or models loaded."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Generic, Sequence, TypeVar
from .models import AnalysisResult, Candidate, TranscriptSegment

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
