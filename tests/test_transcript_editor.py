"""Human correction layer: portable, offline and without re-running Whisper."""
import json

import pytest

from streamclipper.captioning import render_ass
from streamclipper.models import AnalysisResult, Candidate, TranscriptSegment, VideoInfo
from streamclipper.transcript_editor import (
    edit_segment, format_timestamp, load_analysis_report, parse_timestamp,
)


@pytest.fixture
def report(tmp_path):
    recording = tmp_path / "gta vi Übung.mp4"
    recording.write_bytes(b"Not a real video; this module never decodes it")
    video = VideoInfo(str(recording), 3 * 3600 + 29.66, 1920, 1080, 60, True)
    return AnalysisResult(
        video, [Candidate(10, 35, 73, "Audio", 18)],
        transcript=[TranscriptSegment(12.5, 14.1, "Wisper sagt Auto"),
                    TranscriptSegment(17, 19, "Äh oh mein Gott")],
    )


@pytest.mark.parametrize('s,expected', [
    ('00:00:12.345', 12.345),
    ('02:56:29,660', 10589.66),
    ('00:01:00', 60.0),
    ('10.25', 10.25),
    ('12,4', 12.4),
    ('0:00:01.2', 1.2),
])
def test_time_format_parse(s, expected):
    assert parse_timestamp(s) == pytest.approx(expected)
    assert parse_timestamp(format_timestamp(expected)) == pytest.approx(expected)


@pytest.mark.parametrize('bad', ['-1', 'nan', 'inf', '12:99:00', '12:00:99', '00:00:01.1234', 'x', ''])
def test_invalid_time(bad):
    with pytest.raises(ValueError):
        parse_timestamp(bad)


def test_correct_text_and_two_timestamps_applies_to_burned_caption(report):
    first = edit_segment(report, 0, 2, '  Was   zum   Teufel?!  ')
    second = edit_segment(first, 0, 0, '00:00:13.000')
    last = edit_segment(second, 0, 1, '00:00:15.000')
    assert report.transcript[0].text == 'Wisper sagt Auto'  # immutable old snapshot
    assert last.transcript[0] == TranscriptSegment(13, 15, 'Was zum Teufel?!')
    ass = render_ass(last.transcript, 11, 16)
    assert 'Was zum Teufel?!' in ass
    assert 'Wisper sagt Auto' not in ass
    assert 'Dialogue: 0,0:00:02.00,0:00:04.00' in ass


@pytest.mark.parametrize('row,col,text', [
    (0, 0, '16'), (0, 1, '12'), (0, 0, '9999999'), (0, 2, '  '), (5, 2, 'x')
])
def test_invalid_edit_does_not_mutate_report(report, row, col, text):
    snapshot = list(report.transcript)
    with pytest.raises(ValueError):
        edit_segment(report, row, col, text)
    assert report.transcript == snapshot


def test_save_reload_without_inference_and_video_match(report, tmp_path):
    corrected = edit_segment(report, 1, 2, 'Jetzt sitzt der Text richtig!')
    corrected = edit_segment(corrected, 1, 0, '00:00:17.400')
    destination = tmp_path / 'mein-clip.highlights.json'
    corrected.save_json(destination)
    reopened = load_analysis_report(destination, report.video.path)
    assert reopened == corrected
    with pytest.raises(ValueError, match='anderen Aufnahme'):
        load_analysis_report(destination, tmp_path / 'other.mp4')


def test_invalid_report_rejected(report, tmp_path):
    target = tmp_path / 'broken.json'
    report.save_json(target)
    data = json.loads(target.read_text(encoding='utf-8'))
    data['transcript'][0]['end'] = -1
    target.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='ungültig'):
        load_analysis_report(target, report.video.path)
    target.write_text('{not json', encoding='utf-8')
    with pytest.raises(ValueError, match='ungültig'):
        load_analysis_report(target, report.video.path)


def test_editor_can_adjust_both_boundaries_atomically(report):
    from streamclipper.transcript_editor import apply_segment_changes
    # Old cue is 12.5-14.1. Both bounds can be moved past that range at once.
    updated = apply_segment_changes(report, 0, '00:00:15.100', '00:00:16.200',
                                    '  Nicht    das Auto! ')
    assert updated.transcript[0] == TranscriptSegment(15.1, 16.2, 'Nicht das Auto!')
    assert report.transcript[0] == TranscriptSegment(12.5, 14.1, 'Wisper sagt Auto')


def test_editor_rejects_invalid_without_partial_state(report):
    from streamclipper.transcript_editor import apply_segment_changes
    with pytest.raises(ValueError, match='außerhalb'):
        apply_segment_changes(report, 0, '00:00:20.000', '00:00:10.000', 'hey')
    with pytest.raises(ValueError, match='leer'):
        apply_segment_changes(report, 0, '00:00:13.000', '00:00:14.000', '  ')
    assert report.transcript[0].text == 'Wisper sagt Auto'


def test_editor_corrected_subtitle_export_text(report):
    from streamclipper.transcript_editor import apply_segment_changes
    from streamclipper.transcript import render_transcript
    updated = apply_segment_changes(report, 0, '12.7', '14.2', 'Hoppla, das war knapp!')
    srt = render_transcript(updated.transcript, 'srt')
    assert 'Hoppla, das war knapp!' in srt
    assert '00:00:12,700 --> 00:00:14,200' in srt
