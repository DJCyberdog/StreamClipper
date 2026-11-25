"""M11a recovery and compact history tests (real videos/models not needed)."""
from dataclasses import replace
import pytest
from streamclipper.autosave import autosave_path, clear_autosave, load_autosave, save_autosave
from streamclipper.edit_history import EditHistory
from streamclipper.manual_highlights import add_manual_highlight, remove_manual_highlight, trim_manual_highlight
from streamclipper.models import AnalysisResult, Candidate, TranscriptSegment, TranscriptWord, VideoInfo
from streamclipper.transcript_editor import apply_segment_changes
from streamclipper.word_editor import edit_word

def sample(video="test.mp4"):
    return AnalysisResult(
        VideoInfo(video,21600.0,1920,1080,60.0,True),
        [Candidate(60,80,55,"Audio",65)],
        transcript=[TranscriptSegment(100,101,"ich fahre",(
            TranscriptWord(100,100.25,"ich"),
            TranscriptWord(100.5,101.0,"fahre")))])

def test_undo_redo_clip_trim_word_and_transcript():
    h=EditHistory()
    original=sample()
    added=add_manual_highlight(original,200,220,"Unfall")
    trimmed=trim_manual_highlight(added,1,201,215)
    word=edit_word(trimmed,0,1,100.45,100.95,"fliege")
    segment=apply_segment_changes(word,0,"00:01:40.000","00:01:41.000","Wir fliegen")
    deleted=remove_manual_highlight(segment,1)
    states=[original,added,trimmed,word,segment,deleted]
    for before,after in zip(states,states[1:]):
        assert h.record(before,after)
    current=deleted
    for expected in reversed(states[:-1]):
        current=h.undo(current)
        assert current==expected
    assert not h.can_undo and h.can_redo
    for expected in states[1:]:
        current=h.redo(current)
        assert current==expected
    assert original.transcript[0].text=="ich fahre"

def test_redo_cleared_after_alternative_edit():
    h=EditHistory()
    before=sample()
    first=add_manual_highlight(before,200,220)
    assert not h.record(before,before)
    assert h.record(before,first)
    assert h.undo(first)==before
    assert h.can_redo
    another=add_manual_highlight(before,300,330)
    h.record(before,another)
    assert not h.can_redo
    assert h.undo(another)==before

def test_history_guards_cross_source_and_failed_undo_is_not_consumed():
    h=EditHistory()
    with pytest.raises(ValueError,match="Projekten"):
        h.record(sample(),sample("other.mkv"))
    before=sample()
    after=add_manual_highlight(before,200,220)
    h.record(before,after)
    with pytest.raises(ValueError,match="passt nicht"):
        h.undo(replace(after,candidates=[]))
    assert h.can_undo

def test_six_hour_history_stores_only_changed_item():
    original=replace(sample(),transcript=[TranscriptSegment(float(i),float(i)+.5,str(i))
                                          for i in range(12000)])
    changed=apply_segment_changes(original,11000,"03:03:20.000","03:03:20.800","Korrektur")
    h=EditHistory()
    h.record(original,changed)
    assert len(h._past[0].transcript.removed)==1
    assert len(h._past[0].transcript.inserted)==1
    assert h.undo(changed)==original

def test_autosave_persists_non_destructively(tmp_path):
    video=tmp_path/"video.mkv"
    video.write_bytes(b"source stays intact")
    state=sample(str(video))
    root=tmp_path/"private"
    filename=save_autosave(state,root=root)
    assert filename==autosave_path(video,root=root)
    assert load_autosave(video,root=root,duration=21600,size=(1920,1080))==state
    edited=add_manual_highlight(state,800,820)
    save_autosave(edited,root=root)
    assert load_autosave(video,root=root)==edited
    assert video.read_bytes()==b"source stays intact"
    clear_autosave(video,root=root)
    clear_autosave(video,root=root)
    assert not filename.exists()

def test_autosave_rejects_changed_source(tmp_path):
    video=tmp_path/"clip.mkv"
    video.write_bytes(b"source")
    save_autosave(sample(str(video)),root=tmp_path)
    with pytest.raises(ValueError,match="andere Dauer"):
        load_autosave(video,root=tmp_path,duration=10)
    with pytest.raises(ValueError,match="andere Auflösung"):
        load_autosave(video,root=tmp_path,size=(600,400))
    assert "clip.mkv" not in autosave_path(video,root=tmp_path).name
