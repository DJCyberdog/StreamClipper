"""Pure timeline geometry and subtitle lookup for long recordings.

No Qt, decoding, ML, filesystem or network dependency. All times in seconds.
"""
from __future__ import annotations

import bisect
import math
from typing import Sequence

from .models import TranscriptSegment


def clamp_time(value: float, duration: float) -> float:
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Ungültige Aufnahmedauer")
    if not math.isfinite(value):
        raise ValueError("Ungültiger Zeitpunkt")
    return max(0.0, min(duration, value))


def validate_range(start: float, end: float, duration: float,
                   min_duration: float = 0.05) -> tuple[float, float]:
    """Validate a user's in/out points; do not silently change their order."""
    a, b = clamp_time(start, duration), clamp_time(end, duration)
    if not (0 <= start < end <= duration + 0.10) or b - a < min_duration:
        raise ValueError("Schnittbereich benötigt Anfang vor Ende innerhalb des Videos")
    return round(a, 3), round(b, 3)


def visible_range(duration: float, zoom: float, offset: float) -> tuple[float, float]:
    if not math.isfinite(zoom) or zoom < 1:
        raise ValueError("Zoom muss mindestens 1 sein")
    span = duration / zoom
    start = max(0.0, min(max(0.0, duration - span), offset))
    return start, min(duration, start + span)


def time_at_x(x: float, width: float, duration: float,
              zoom: float = 1.0, offset: float = 0.0) -> float:
    if width <= 0:
        raise ValueError("Timeline-Breite muss positiv sein")
    start, end = visible_range(duration, zoom, offset)
    return start + (end - start) * max(0.0, min(1.0, x / width))


def x_at_time(t: float, width: float, duration: float,
              zoom: float = 1.0, offset: float = 0.0) -> float:
    if width <= 0:
        raise ValueError("Timeline-Breite muss positiv sein")
    start, end = visible_range(duration, zoom, offset)
    return (t - start) / (end - start) * width


def waveform_window(peaks: Sequence[float], duration: float, view_start: float,
                    view_end: float, columns: int) -> list[float]:
    """Resample precomputed bounded waveform peaks to a pixel width.

    Only intersects the visible region. For zoomed-out overviews, use max of
    contributing buckets so short loud transients don't vanish by averaging.
    """
    if columns <= 0 or duration <= 0 or view_end <= view_start:
        return []
    count = len(peaks)
    if count == 0:
        return [0.0] * columns
    result: list[float] = []
    for px in range(columns):
        a = max(0, min(count - 1, math.floor((view_start + (view_end - view_start) * px / columns) / duration * count)))
        b = max(a + 1, min(count, math.ceil((view_start + (view_end - view_start) * (px + 1) / columns) / duration * count)))
        result.append(max(0.0, min(1.0, max(peaks[a:b]))))
    return result


def caption_at_time(segments: Sequence[TranscriptSegment], position: float,
                    offset: float = 0.0) -> int | None:
    """Find the currently active caption, including an export timing offset."""
    if not math.isfinite(position) or not math.isfinite(offset):
        return None
    for index, cue in enumerate(segments):
        if cue.start + offset <= position < cue.end + offset:
            return index
    return None
