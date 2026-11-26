from streamclipper.models import TranscriptSegment,TranscriptWord,VideoInfo,AnalysisResult
from streamclipper.speech_timing import propose_timings,apply_proposals
import pytest

def test_trailing_and_leading_silence():
    cue=TranscriptSegment(0,5,"Hallo")
    p=propose_timings([cue],[(1,3)],duration=6)
    assert len(p)==1
    assert (p[0].after.start,p[0].after.end)==(.88,3.12)
    original=AnalysisResult(VideoInfo("x",6,320,240,25,True),[],transcript=[cue])
    corrected=apply_proposals(original,p)
    assert original.transcript==[cue]
    assert corrected.transcript==[p[0].after]
    with pytest.raises(ValueError):apply_proposals(corrected,p)

def test_protect_manual_and_missing_evidence():
    cues=[TranscriptSegment(0,5,"A"),TranscriptSegment(5,9,"B",(TranscriptWord(6,7,"B","manual"),)),
          TranscriptSegment(9,12,"C")]
    assert not propose_timings(cues,[(1,2),(6,7)],duration=12,protected_rows=[0])

def test_preserve_word_bounds_and_multiple_islands():
    cue=TranscriptSegment(0,6,"Hello world",(TranscriptWord(.5,1.2,"Hello"),TranscriptWord(3,4.5,"world")))
    p=propose_timings([cue],[(1,2),(3,4)],duration=6)[0]
    assert (p.after.start,p.after.end)==(.5,4.5)
    assert p.after.words==cue.words

def test_invalid_evidence():
    with pytest.raises(ValueError):propose_timings([],[(0,2),(1,3)],duration=5)


def test_reviewed_pause_split_preserves_words_and_protects_manual_translation(tmp_path):
    from dataclasses import replace
    from streamclipper.models import VideoInfo,AnalysisResult,TranscriptSegment,TranscriptWord
    from streamclipper.speech_timing import propose_pause_splits,apply_pause_splits
    from streamclipper.subtitle_translation import set_translations
    from streamclipper.edit_history import WorkspaceHistory
    video=VideoInfo(str(tmp_path/"source.mp4"),10,320,240,25,True)
    cue=TranscriptSegment(0,6,"Hallo Welt. Weiter gehts!",(
        TranscriptWord(.5,1,"Hallo"),TranscriptWord(1,1.5,"Welt."),
        TranscriptWord(3.5,4,"Weiter"),TranscriptWord(4,4.5,"gehts!")),"asr")
    result=AnalysisResult(video,[],transcript=[cue])
    spans=[(.3,1.6),(3.3,4.7)]
    p=propose_pause_splits(result,spans)[0]
    assert [c.text for c in p.parts]==["Hallo Welt.","Weiter gehts!"]
    assert p.parts[0].end==1.62 and p.parts[1].start==3.38
    updated=apply_pause_splits(result,[p])
    assert tuple(w for c in updated.transcript for w in c.words)==cue.words
    history=WorkspaceHistory();assert history.record_analysis(result,updated)
    assert history.undo(updated,None)[0]==result
    assert not propose_pause_splits(result,[(.3,4.7)])
    assert not propose_pause_splits(replace(result,transcript=[replace(cue,review_origin="manual")]),spans)
    translated=set_translations(result,"en",[(0,"Hello world. Let's go!","manual")])
    assert not propose_pause_splits(translated,spans)
    import pytest
    with pytest.raises(ValueError):apply_pause_splits(translated,[p])
