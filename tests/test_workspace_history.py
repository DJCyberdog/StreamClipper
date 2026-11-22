"""M11c: mixed, compact, source-bound analysis + track undo history."""
from dataclasses import replace
import pytest

from streamclipper.editor_project import add_track, initial_project, rename_track
from streamclipper.edit_history import WorkspaceHistory
from streamclipper.manual_highlights import add_manual_highlight
from streamclipper.models import AnalysisResult, VideoInfo, TranscriptSegment
from streamclipper.transcript_editor import apply_segment_changes


def example():
    source = VideoInfo("example.mkv", 21600, 1920, 1080, 60, True)
    analysis = AnalysisResult(source, [], transcript=[
        TranscriptSegment(float(i), float(i) + 0.5, f"Wort {i}") for i in range(12000)])
    return source, analysis, initial_project(source)


def test_mixed_undo_redo_in_exact_edit_order():
    _, a0, p0 = example()
    a1 = add_manual_highlight(a0, 120, 141, "Manuell")
    p1 = add_track(p0, "audio", "Kommentar")
    a2 = apply_segment_changes(a1, 1000, "00:16:40.000", "00:16:40.600", "Korrigiert")
    h = WorkspaceHistory()
    assert h.record_analysis(a0, a1)
    assert h.record_project(p0, p1)
    assert h.record_analysis(a1, a2)
    assert h.undo_kind == "analysis"
    a, p = h.undo(a2, p1)
    assert (a, p) == (a1, p1)
    assert h.undo_kind == "project"
    a, p = h.undo(a, p)
    assert (a, p) == (a1, p0)
    a, p = h.undo(a, p)
    assert (a, p) == (a0, p0)
    assert not h.can_undo
    for expected_a, expected_p in ((a1, p0), (a1, p1), (a2, p1)):
        a, p = h.redo(a, p)
        assert (a, p) == (expected_a, expected_p)
    assert not h.can_redo


def test_future_is_cleared_on_new_edit_and_noops_ignored():
    _, a0, p0 = example()
    p1 = add_track(p0, "audio", "Voice")
    h = WorkspaceHistory()
    assert not h.record_project(p0, p0)
    assert h.record_project(p0, p1)
    assert h.undo(None, p1) == (None, p0)
    assert h.can_redo
    a1 = add_manual_highlight(a0, 30, 50)
    assert h.record_analysis(a0, a1)
    assert not h.can_redo
    assert h.undo(a1, p0) == (a0, p0)


def test_cross_source_and_divergence_do_not_consume_history():
    source, a0, p0 = example()
    h = WorkspaceHistory()
    p1 = add_track(p0, "audio", "Voice")
    h.record_project(p0, p1)
    other_video = replace(source, path="another.mkv")
    with pytest.raises(ValueError, match="Quelle"):
        h.record_analysis(AnalysisResult(other_video, []),
                          add_manual_highlight(AnalysisResult(other_video, []), 10, 20))
    with pytest.raises(ValueError, match="konsistent"):
        h.undo(None, p0)
    assert h.can_undo
    assert h.undo(None, p1) == (None, p0)
    with pytest.raises(ValueError, match="konsistent"):
        h.redo(None, p1)
    assert h.can_redo


def test_compact_delta_keeps_single_change_for_long_transcript():
    _, a0, _ = example()
    a1 = apply_segment_changes(a0, 11000, "03:03:20.000", "03:03:20.800", "Korrektur")
    h = WorkspaceHistory()
    assert h.record_analysis(a0, a1)
    delta = h._past[-1].analysis
    assert len(delta.transcript.removed) == 1
    assert len(delta.transcript.inserted) == 1
    assert h.undo(a1, None) == (a0, None)


def test_reset_discards_old_history_and_binds_fresh_source():
    source, a0, p0 = example()
    h = WorkspaceHistory()
    h.record_project(p0, add_track(p0, "audio", "Voice"))
    h.clear()
    assert not h.can_undo
    assert h.record_project(
        initial_project(replace(source, path="new.mkv")),
        add_track(initial_project(replace(source, path="new.mkv")), "audio", "Stereo"))
