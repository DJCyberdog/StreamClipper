"""Review/edit Whisper text and timing without running inference again.

Persistent corrections use the existing AnalysisResult JSON schema, which is
also consumed by the CLI MP4 exporter. The original media is never changed.
"""
from __future__ import annotations

from dataclasses import replace
import json
import math
import os
from pathlib import Path
import re

from .models import AnalysisResult, Candidate, TranscriptSegment, TranscriptWord, VideoInfo, SubtitleTranslation
from .subtitle_translation import validate_translations

_TIME_RE = re.compile(r"(?P<h>\d+):(?P<m>[0-5]\d):(?P<s>[0-5]\d)(?:[.,](?P<ms>\d{1,3}))?")


def format_timestamp(seconds: float) -> str:
    """Show milliseconds so users can make small synchronization corrections."""
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Ungültiger Zeitstempel")
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    whole, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d}.{millis:03d}"


def parse_timestamp(text: str) -> float:
    """Accept HH:MM:SS.mmm, HH:MM:SS, or raw seconds (locale comma OK)."""
    value = text.strip()
    match = _TIME_RE.fullmatch(value)
    if match:
        seconds = (int(match['h']) * 3600 + int(match['m']) * 60
                   + int(match['s']) + int((match['ms'] or '').ljust(3, '0') or 0) / 1000)
    else:
        try:
            seconds = float(value.replace(',', '.'))
        except ValueError as exc:
            raise ValueError('Zeit bitte als HH:MM:SS.mmm eingeben') from exc
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Zeitstempel muss eine positive, endliche Zahl sein')
    return round(seconds, 3)


def validate_segments(segments: list[TranscriptSegment], duration: float) -> None:
    """Allow natural overlap but reject malformed/out-of-video cues."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Video hat keine gültige Dauer')
    for i, cue in enumerate(segments, start=1):
        if not (math.isfinite(cue.start) and math.isfinite(cue.end)
                and 0 <= cue.start < cue.end <= duration + 0.1):
            raise ValueError(f'Abschnitt {i}: Start/Ende liegen außerhalb des Videos')
        if not isinstance(cue.text, str) or not cue.text.strip():
            raise ValueError(f'Abschnitt {i}: Untertitel darf nicht leer sein')
        if len(cue.text) > 10000:
            raise ValueError(f'Abschnitt {i}: Text zu lang')
        if cue.review_origin not in {"legacy","asr","manual","vad"}:
            raise ValueError("Ungültige Untertitelherkunft")
        for value in (cue.avg_logprob,cue.no_speech_prob,cue.compression_ratio):
            if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value)):
                raise ValueError("Ungültiger ASR-Messwert")
        if cue.no_speech_prob is not None and not 0<=cue.no_speech_prob<=1:
            raise ValueError("Ungültige No-Speech-Wahrscheinlichkeit")
        for j, word in enumerate(cue.words, start=1):
            if not (isinstance(word, TranscriptWord) and
                    math.isfinite(word.start) and math.isfinite(word.end) and
                    0 <= word.start < word.end <= duration + .1 and
                    isinstance(word.text, str) and bool(word.text.strip()) and
                    word.origin in {'whisper', 'estimated', 'manual'}):
                raise ValueError(f'Abschnitt {i}, Wort {j}: ungültige Zeit oder Text')


def edit_segment(result: AnalysisResult, row: int, column: int, text: str) -> AnalysisResult:
    """Return a fresh snapshot; failed validation does not mutate the old result."""
    if not 0 <= row < len(result.transcript) or column not in (0, 1, 2):
        raise ValueError('Ungültige Transkript-Zelle')
    old = result.transcript[row]
    if column == 0:
        new = replace(old, start=parse_timestamp(text))
    elif column == 1:
        new = replace(old, end=parse_timestamp(text))
    else:
        clean = ' '.join(text.split())
        new = replace(old, text=clean)
    cues = list(result.transcript)
    cues[row] = _preserve_word_times(old,new)
    validate_segments(cues, result.video.duration)
    return replace(result, transcript=cues)


def load_analysis_report(filename: str | Path, expected_video: str | Path) -> AnalysisResult:
    """Load editable project JSON only when it identifies the open recording.

    Uses the current (already existing) report format, not a new proprietary
    file. No execution, video write, or model inference is performed.
    """
    report = Path(filename)
    if report.stat().st_size > 30 * 1024 * 1024:
        raise ValueError('Analysebericht ist ungewöhnlich groß (>30 MB)')
    try:
        data = json.loads(report.read_text(encoding='utf-8'))
        video = VideoInfo(**data['video'])
        if os.path.normcase(os.path.abspath(video.path)) != os.path.normcase(os.path.abspath(expected_video)):
            raise ValueError('Der Bericht gehört zu einer anderen Aufnahme')
        if not Path(video.path).is_file():
            raise ValueError('Die zugehörige Videoaufnahme existiert nicht mehr')
        if not (math.isfinite(video.duration) and video.duration > 0):
            raise ValueError('Ungültige Videodauer im Bericht')
        candidates = [Candidate(**entry) for entry in data.get('candidates', [])]
        if any(c.origin not in {"auto", "manual"} for c in candidates):
            raise ValueError("Unbekannte Highlight-Herkunft")
        transcript = [TranscriptSegment(
            float(entry['start']), float(entry['end']), str(entry['text']),
            tuple(TranscriptWord(**word) for word in entry.get('words', [])),
            entry.get('review_origin','legacy'),entry.get('avg_logprob'),entry.get('no_speech_prob'),entry.get('compression_ratio'))
            for entry in data.get('transcript', [])]
        validate_segments(transcript, video.duration)
        for candidate in candidates:
            if not (math.isfinite(candidate.start) and math.isfinite(candidate.end)
                    and 0 <= candidate.start < candidate.end <= video.duration + 0.1):
                raise ValueError('Ungültiger Highlight-Zeitraum im Bericht')
        return validate_translations(AnalysisResult(video, candidates, method=str(data.get('method', 'loaded-report')),
                              transcript=transcript, translations=tuple(SubtitleTranslation(**t) for t in data.get('translations', [])),
                              caption_language=data.get('caption_language', '')))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OverflowError) as exc:
        raise ValueError(f'Analysebericht ist nicht lesbar oder ungültig: {exc}') from exc


def apply_segment_changes(result: AnalysisResult, row: int,
                          start_text: str, end_text: str, speech_text: str) -> AnalysisResult:
    """Update all three fields atomically so adjusted windows can cross old bounds."""
    if not 0 <= row < len(result.transcript):
        raise ValueError("Bitte eine gültige Transkriptzeile auswählen")
    clean = " ".join(speech_text.split())
    segment = TranscriptSegment(parse_timestamp(start_text), parse_timestamp(end_text), clean)
    segment = _preserve_word_times(result.transcript[row],segment)
    if segment == result.transcript[row]:
        return result
    updated = list(result.transcript)
    updated[row] = segment
    validate_segments(updated, result.video.duration)
    return replace(result, transcript=updated)


def _preserve_word_times(old,new):
    """Preserve exact timings for unchanged bounds and unambiguous single-word edits.
    For a changed token count or changed segment bounds do not invent alignment.
    """
    if (old.start,old.end,old.text)==(new.start,new.end,new.text):
        return old
    new=replace(new,review_origin='manual' if old.review_origin!='legacy' else 'legacy',
                avg_logprob=None,no_speech_prob=None,compression_ratio=None)
    if not old.words or (old.start,old.end)!=(new.start,new.end):
        return replace(new,words=())
    tokens=new.text.split()
    if len(tokens)!=len(old.words) or any(len(w.text.split())!=1 for w in old.words):
        return replace(new,words=())
    # Only one positional correction is automatically attributable; multiple
    # edits may represent reordered words rather than a spelling correction.
    if sum(t!=w.text for t,w in zip(tokens,old.words))>1:
        return replace(new,words=())
    return replace(new,words=tuple(w if t==w.text else replace(w,text=t,origin="manual")
                                   for t,w in zip(tokens,old.words)))
