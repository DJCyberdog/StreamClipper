"""Clip-local word annotations and immutable manual corrections.

Whisper native word timings are used as-is. Old three-field transcripts have
proportional *estimates*, explicitly labelled as such; never pretend they are
word-aligned. No video decoding or model loading is required to edit a word.
"""
from __future__ import annotations

from dataclasses import replace
import math
from typing import Sequence

from .models import AnalysisResult, TranscriptSegment, TranscriptWord
from .transcript_editor import validate_segments


def effective_words(segment: TranscriptSegment) -> tuple[TranscriptWord, ...]:
    if segment.words:
        return segment.words
    tokens = segment.text.strip().split()
    if not tokens or not 0 <= segment.start < segment.end:
        return ()
    step = (segment.end - segment.start) / len(tokens)
    return tuple(TranscriptWord(round(segment.start + step * i, 3),
                                round(segment.start + step * (i + 1), 3),
                                text, 'estimated')
                 for i, text in enumerate(tokens)
                 if round(segment.start + step * (i + 1), 3) >
                 round(segment.start + step * i, 3))


def words_in_clip(segments: Sequence[TranscriptSegment], start: float,
                  end: float) -> list[tuple[int, int, TranscriptWord]]:
    """Only materialize words in current highlight; bounded by clip content."""
    if not (math.isfinite(start) and math.isfinite(end) and start < end):
        return []
    result: list[tuple[int, int, TranscriptWord]] = []
    for i, segment in enumerate(segments):
        if segment.end <= start or segment.start >= end:
            continue
        for j, word in enumerate(effective_words(segment)):
            if word.end > start and word.start < end:
                result.append((i, j, word))
    return result


def edit_word(result: AnalysisResult, segment_index: int, word_index: int,
              start: float, end: float, text: str) -> AnalysisResult:
    """Edit one exact or estimated word, without changing other annotations."""
    if not 0 <= segment_index < len(result.transcript):
        raise ValueError('Untertitelabschnitt nicht gefunden')
    if not all(math.isfinite(v) for v in (start, end)):
        raise ValueError('Wortzeiten müssen endlich sein')
    start, end = round(start, 3), round(end, 3)
    clean = ' '.join(text.split())
    if not (0 <= start < end <= result.video.duration + .1):
        raise ValueError('Wort benötigt einen gültigen Anfang und ein Ende im Video')
    if not clean or len(clean) > 200:
        raise ValueError('Worttext muss zwischen 1 und 200 Zeichen lang sein')
    segment = result.transcript[segment_index]
    previous = effective_words(segment)
    if not 0 <= word_index < len(previous):
        raise ValueError('Wort nicht gefunden')
    words = list(previous)
    words[word_index] = TranscriptWord(start, end, clean, 'manual')
    # Parent encloses all words. Keep its original edges if they were wider,
    # preserving pauses and previous manual segment edits.
    parent = replace(segment,
                     start=min(segment.start, *(w.start for w in words)),
                     end=max(segment.end, *(w.end for w in words)),
                     text=' '.join(w.text for w in words),
                     words=tuple(words))
    updated = list(result.transcript)
    updated[segment_index] = parent
    validate_segments(updated, result.video.duration)
    return replace(result, transcript=updated)
