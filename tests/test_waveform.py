"""Exercise streaming waveform decoder against synthetic FFmpeg audio."""
import shutil
import subprocess

import pytest

from streamclipper.media import CancelledError, probe_video, waveform_peaks


@pytest.fixture
def recorded(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg required')
    file = tmp_path / 'Game Musik ü.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                   '-f','lavfi','-i','color=c=black:s=320x180:r=10:d=5',
                   '-f','lavfi','-i','sine=frequency=440:duration=5',
                   '-c:v','mpeg4','-c:a','aac','-shortest',str(file)],
                   check=True,capture_output=True,timeout=25)
    return probe_video(file)


def test_waveform_is_bounded_and_not_silent(recorded):
    peaks = waveform_peaks(recorded, max_bins=250, sample_rate=600)
    assert 100 <= len(peaks) <= 250
    assert max(peaks) == pytest.approx(1.0)
    assert all(0 <= p <= 1 for p in peaks)


def test_waveform_cancel_does_not_leave_partial_result(recorded):
    with pytest.raises(CancelledError):
        waveform_peaks(recorded, cancelled=lambda: True)


def test_empty_audio_is_clean(recorded):
    from dataclasses import replace
    assert waveform_peaks(replace(recorded, has_audio=False)) == []
