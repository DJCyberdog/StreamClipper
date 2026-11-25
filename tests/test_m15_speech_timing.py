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
