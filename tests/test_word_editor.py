"""Regression tests for exact words, legacy estimates, timeline clip scope and MP4."""
import json
import math
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

from streamclipper.captioning import clip_captions, render_ass, subtitle_text_at_time
from streamclipper.models import AnalysisResult, Candidate, TranscriptSegment, TranscriptWord, VideoInfo
from streamclipper.transcript_editor import apply_segment_changes, load_analysis_report
from streamclipper.word_editor import edit_word, effective_words, words_in_clip


def video(tmp_path):
    path = tmp_path / 'stream.mp4'
    path.write_bytes(b'test')
    return VideoInfo(str(path), 21600, 1920, 1080, 60, True)


def words():
    return (TranscriptWord(100.00, 100.40, 'Ich'),
            TranscriptWord(100.50, 100.90, 'fahre'),
            TranscriptWord(101.00, 101.40, 'jetzt!'))


def test_exact_words_export_each_spoken_word_with_real_times():
    transcript = [TranscriptSegment(100, 101.4, 'Ich fahre jetzt!', words())]
    cues = clip_captions(transcript, 99, 103)
    assert [(round(a, 2), round(b, 2), text) for a,b,text in cues] == [
        (1.0, 1.4, 'Ich'), (1.5, 1.9, 'Ich fahre'),
        (2.0, 2.4, 'Ich fahre jetzt!')]
    assert subtitle_text_at_time(transcript, 100.6) == 'Ich fahre'
    assert subtitle_text_at_time(transcript, 100.46) is None
    assert 'Dialogue: 0,0:00:01.50,0:00:01.90' in render_ass(transcript, 99, 103)


def test_manual_correction_changes_only_one_word_and_export(tmp_path):
    initial = AnalysisResult(video(tmp_path), [Candidate(99,103,0,'Manual',100,'manual')],
                             transcript=[TranscriptSegment(100,101.4,'Ich fahre jetzt!',words())])
    final = edit_word(initial, 0, 1, 100.47, 100.92, 'fliege')
    assert initial.transcript[0].words[1].text == 'fahre'
    assert final.transcript[0].words[1] == TranscriptWord(100.47,100.92,'fliege','manual')
    assert final.transcript[0].text == 'Ich fliege jetzt!'
    cues = clip_captions(final.transcript, 99, 103)
    assert cues[1] == (pytest.approx(1.47),pytest.approx(1.92),'Ich fliege')
    assert final.candidates == initial.candidates


def test_legacy_estimates_are_not_misrepresented_as_precise(tmp_path):
    old = TranscriptSegment(5, 7, 'eins zwei drei vier')
    estimated = effective_words(old)
    assert len(estimated) == 4
    assert {word.origin for word in estimated} == {'estimated'}
    result = AnalysisResult(video(tmp_path), [], transcript=[old])
    corrected = edit_word(result, 0, 2, 6.05, 6.55, 'DREI')
    assert corrected.transcript[0].words[2].origin == 'manual'
    assert corrected.transcript[0].words[0].origin == 'estimated'
    assert corrected.transcript[0].text == 'eins zwei DREI vier'


def test_no_word_timing_old_json_is_still_compatible(tmp_path):
    old = AnalysisResult(video(tmp_path), [], transcript=[TranscriptSegment(1,3,'Alt und neu')])
    target = tmp_path / 'report.json'
    old.save_json(target)
    data = json.loads(target.read_text())
    assert 'words' not in data['transcript'][0]
    assert load_analysis_report(target, old.video.path) == old


def test_word_timings_survive_json_roundtrip(tmp_path):
    original = AnalysisResult(video(tmp_path), [], transcript=[TranscriptSegment(100,101.4,'Ich fahre jetzt!',words())])
    edited = edit_word(original, 0, 2, 101.03, 101.45, 'schon!')
    target = tmp_path/'words.highlights.json'
    edited.save_json(target)
    reloaded = load_analysis_report(target, edited.video.path)
    assert reloaded == edited
    assert reloaded.transcript[0].words[2].origin == 'manual'
    assert 'Ich fahre schon!' in render_ass(reloaded.transcript, 99,103)


def test_legacy_segment_edit_invalidates_word_alignment(tmp_path):
    result = AnalysisResult(video(tmp_path), [], transcript=[TranscriptSegment(100,101.4,'Ich fahre jetzt!',words())])
    changed = apply_segment_changes(result,0,'100','101.4','Ich fliege jetzt')
    assert changed.transcript[0].words == ()
    assert all(w.origin == 'estimated' for w in effective_words(changed.transcript[0]))


@pytest.mark.parametrize('start,end,text', [
    (2,2,'x'), (-1,1,'x'), (3,2,'x'), (math.inf,3,'x'), (1, 25000,'x'), (1,2,'')])
def test_invalid_word_rejected_without_mutating_source(tmp_path,start,end,text):
    report = AnalysisResult(video(tmp_path), [], transcript=[TranscriptSegment(100,101.4,'Ich fahre jetzt!',words())])
    with pytest.raises(ValueError):
        edit_word(report, 0, 1, start, end, text)
    assert report.transcript[0].text == 'Ich fahre jetzt!'


def test_only_words_overlapping_selected_highlight(tmp_path):
    segs = [TranscriptSegment(1,3,'vorher'),
            TranscriptSegment(100,101.4,'Ich fahre jetzt!',words()),
            TranscriptSegment(20000,20001,'später')]
    match = words_in_clip(segs,100.2,101.2)
    assert [(i,j) for i,j,_ in match] == [(1,0),(1,1),(1,2)]
    assert words_in_clip(segs,123,128) == []


def test_whisper_requests_word_timestamps_and_preserves_native_offsets(monkeypatch,tmp_path):
    class FakeWhisperModel:
        def __init__(self,*args,**kwargs):
            assert kwargs.get('local_files_only') is True
        def transcribe(self,*args,**kwargs):
            assert kwargs['word_timestamps'] is True
            return iter([SimpleNamespace(start=2,end=4,text=' Hello world',words=[
                SimpleNamespace(start=2.2,end=2.7,word=' Hello'),
                SimpleNamespace(start=3.0,end=3.5,word=' world')])]), None
    module = ModuleType('faster_whisper')
    module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, 'faster_whisper', module)
    monkeypatch.setenv('STREAMCLIPPER_WHISPER_DEVICE', 'cpu')
    from streamclipper.semantic import transcribe_video
    result = transcribe_video(video(tmp_path), str(tmp_path))
    assert result[0].words == (TranscriptWord(2.2,2.7,'Hello'),TranscriptWord(3,3.5,'world'))


def test_word_offset_applies_only_to_rendering_not_timing_source():
    seg = TranscriptSegment(100,101.4,'Ich fahre jetzt!',words())
    cues = clip_captions([seg],99,103,offset_seconds=.3)
    assert cues[0][0] == pytest.approx(1.3)
    assert subtitle_text_at_time([seg],100.15,offset_seconds=.3) is None
    assert subtitle_text_at_time([seg],100.35,offset_seconds=.3) == 'Ich'
    assert seg.words[0].start == 100
