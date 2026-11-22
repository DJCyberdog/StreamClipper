"""No GPU or Qt required: precise timeline math, editing and 6h recordings."""
import math

import pytest

from streamclipper.timeline import (caption_at_time, clamp_time, time_at_x,
                                    visible_range, waveform_window, x_at_time,
                                    validate_range)
from streamclipper.models import AnalysisResult, Candidate, TranscriptSegment, VideoInfo
from streamclipper.manual_highlights import trim_manual_highlight, add_manual_highlight


def test_six_hours_zoom_and_bidirectional_time_mapping():
    duration = 6 * 3600
    start, end = visible_range(duration, 60, 10999)
    assert end - start == pytest.approx(360)
    for t in (start, start + 1.001, end - 1.25, end):
        x = x_at_time(t, 1030, duration, 60, start)
        assert time_at_x(x, 1030, duration, 60, start) == pytest.approx(t)
    assert visible_range(duration, 1, 2000) == (0, duration)
    assert visible_range(duration, 120, duration) == (duration - 180, duration)


def test_waveform_aggregate_max_preserves_transients():
    peaks = [.01] * 10000
    peaks[5432] = 1.0
    window = waveform_window(peaks, 21600, 0, 21600, 400)
    assert len(window) == 400
    assert max(window) == 1
    assert min(window) >= 0
    a, b = visible_range(21600, 40, 10000)
    close = waveform_window(peaks, 21600, a, b, 200)
    assert len(close) == 200


def test_caption_alignment_matches_global_offset():
    segments = [TranscriptSegment(3, 5, "Wort A"), TranscriptSegment(7, 9, "Wort B")]
    assert caption_at_time(segments, 3.25) == 0
    assert caption_at_time(segments, 3.25, 0.4) is None
    assert caption_at_time(segments, 3.45, 0.4) == 0
    assert caption_at_time(segments, 9.4, 0.4) is None


def test_manual_trim_only_user_highlight_preserves_audio_and_name():
    info = VideoInfo("test.mp4", 21600.0, 1920, 1080, 60, True)
    report = AnalysisResult(info, [Candidate(10, 12, 55, "AI", 11)])
    new = add_manual_highlight(report, 100.123, 130.555, "Super Szene")
    trimmed = trim_manual_highlight(new, 1, 110.111, 120.222)
    assert trimmed.candidates[1].reason == "Super Szene"
    assert trimmed.candidates[1].peak_at == pytest.approx((110.111+120.222)/2, abs=.001)
    assert trimmed.candidates[0] == report.candidates[0]
    assert new.candidates[1].start == 100.123
    with pytest.raises(ValueError, match="Nur manuelle"):
        trim_manual_highlight(new, 0, 10, 11)


@pytest.mark.parametrize('start,end', [(2,2), (4,3),(-1,5),(1,21601),
                                       (float('nan'),3), (2,float('inf'))])
def test_invalid_selection_rejected(start,end):
    with pytest.raises(ValueError):
        validate_range(start,end,21600)


def test_range_millisecond_accuracy():
    assert validate_range(4321.234, 4350.678, 21600) == (4321.234, 4350.678)
