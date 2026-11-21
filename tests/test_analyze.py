from streamclipper.analyze import _bounds, find_candidates


def test_detects_injected_loud_event():
    levels = [-40.0] * 120
    levels[67:70] = [-5.0, -4.0, -5.0]
    levels[23] = -9.0
    candidates = find_candidates(levels, 120.0, clip_seconds=25, max_clips=3)
    assert any(c.start <= 68.5 <= c.end for c in candidates)
    assert candidates[0].score > 30
    assert all(0 <= c.start < c.end <= 120 for c in candidates)
    assert all(a.end <= b.start or b.end <= a.start for i,a in enumerate(candidates) for b in candidates[i+1:])


def test_no_sound_fallback_is_explicit():
    clips = find_candidates([], 91.0, clip_seconds=25, max_clips=5)
    assert clips
    assert all(c.score == 0 and "Zeitstichprobe" in c.reason for c in clips)


def test_silent_audio_fallback():
    assert find_candidates([-100.0] * 20, 20.0, 25)[0].score == 0


def test_short_video_bounds():
    assert _bounds(8.0, 12.0, 25) == (0, 12)


def test_bad_parameters():
    import pytest
    with pytest.raises(ValueError):
        find_candidates([0], 10.0, clip_seconds=4)
