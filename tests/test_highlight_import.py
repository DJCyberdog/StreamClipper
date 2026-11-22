"""M11c-3: deterministic, explicit analysis-to-timeline import, no media copy."""
from dataclasses import replace
import math
import pytest

from streamclipper.editor_project import (
    Track, add_item, add_track, edit_item, initial_project, toggle_track,
    save_project, load_project,
)
from streamclipper.highlight_import import import_analysis_candidates
from streamclipper.models import AnalysisResult, Candidate, VideoInfo


def sample(tmp_path):
    video_file = tmp_path / "6h gaming ü.mkv"
    video_file.write_bytes(b"untouched-source")
    info = VideoInfo(str(video_file), 21600, 1920, 1080, 60, True)
    analysis = AnalysisResult(info, [
        Candidate(120, 142, 80, "Audioreaktion (nur Hinweis)", 132),
        Candidate(500.125, 520.550, 0, "Eigene Markierung", 510, "manual")])
    return info, analysis, initial_project(info), video_file


def test_dedicated_track_is_explicit_and_reimport_idempotent(tmp_path):
    video, analysis, project, source = sample(tmp_path)
    assert [t.id for t in project.tracks] == [
        "gameplay", "mic", "music", "captions", "graphics"]
    imported = import_analysis_candidates(project, analysis)
    assert len(imported.tracks) == len(project.tracks) + 1
    assert imported.tracks[-1].id == "highlights_import"
    assert imported.tracks[-1].kind == "video"
    assert len(imported.items) == len(project.items) + 2
    assert all(c.id.startswith("hl_") for c in imported.items[1:])
    assert [c.timeline_start for c in imported.items[1:]] == [120, 500.125]
    assert imported.items[0] == project.items[0]
    assert import_analysis_candidates(imported, analysis) == imported
    file = save_project(imported, root=tmp_path / "projects")
    assert load_project(video, root=tmp_path / "projects") == imported
    assert file.is_file()
    assert source.read_bytes() == b"untouched-source"


def test_reimport_preserves_manual_trim_and_move_of_imported_item(tmp_path):
    _, analysis, original, _ = sample(tmp_path)
    imported = import_analysis_candidates(original, analysis)
    edited = edit_item(imported, imported.items[1].id,
                       timeline_start=1000, source_start=122)
    assert import_analysis_candidates(edited, analysis) == edited
    changed_scores = replace(analysis, candidates=[
        replace(analysis.candidates[0], score=5, reason="Score changed"),
        analysis.candidates[1]])
    assert import_analysis_candidates(edited, changed_scores) == edited


def test_duplicates_include_existing_manual_clips_and_repeated_candidates(tmp_path):
    _, analysis, original, _ = sample(tmp_path)
    custom = add_track(original, "video", "Custom")
    target = custom.tracks[-1].id
    custom = add_item(custom, target, 120, 142, 120, "User already added")
    repeated = replace(analysis, candidates=[
        analysis.candidates[0], analysis.candidates[0], analysis.candidates[1]])
    imported = import_analysis_candidates(custom, repeated, track_id=target)
    assert imported.tracks == custom.tracks
    assert len(imported.items) == len(custom.items) + 1
    assert custom.items[-1] == imported.items[1]
    assert import_analysis_candidates(imported, repeated, track_id=target) == imported


def test_locked_target_and_incompatible_track_rejected(tmp_path):
    _, analysis, p, _ = sample(tmp_path)
    with pytest.raises(ValueError, match="Videospur"):
        import_analysis_candidates(p, analysis, track_id="mic")
    with pytest.raises(ValueError, match="Zielspur"):
        import_analysis_candidates(p, analysis, track_id="absent")
    locked = toggle_track(import_analysis_candidates(p, analysis),
                          "highlights_import", "locked")
    with pytest.raises(ValueError, match="gesperrt"):
        import_analysis_candidates(locked, analysis)
    assert locked.tracks[-1].locked
    bad = replace(p, tracks=p.tracks + (
        Track("highlights_import", "audio", "Not a video track"),))
    with pytest.raises(ValueError, match="Videospur"):
        import_analysis_candidates(bad, analysis)


def test_reject_other_source_invalid_ranges_and_capacity(tmp_path):
    video, analysis, original, _ = sample(tmp_path)
    for replacement in (
        replace(video, path=str(tmp_path/"other.mkv")),
        replace(video, width=800),
        replace(video, duration=600),
    ):
        with pytest.raises(ValueError, match="anderen Aufnahme"):
            import_analysis_candidates(
                original, replace(analysis, video=replacement))
    for broken in (
        replace(analysis.candidates[0], start=math.nan),
        replace(analysis.candidates[0], end=21601),
        replace(analysis.candidates[0], end=0),
        replace(analysis.candidates[0], reason=None),
    ):
        with pytest.raises(ValueError, match="Highlight"):
            import_analysis_candidates(
                original, replace(analysis, candidates=[analysis.candidates[1], broken]))
    assert original.items[0].source_end == 21600


def test_empty_import_does_not_create_track(tmp_path):
    _, analysis, p, _ = sample(tmp_path)
    assert import_analysis_candidates(p, replace(analysis, candidates=[])) == p


def test_overlapping_highlights_keep_distinct_nonidentical_ranges(tmp_path):
    _, analysis, p, _ = sample(tmp_path)
    candidates = [
        Candidate(100, 110, 30, "first", 105),
        Candidate(100, 111, 40, "second", 105),
        Candidate(100, 110, 0, "same bounds manual", 105, "manual"),
    ]
    imported = import_analysis_candidates(p, replace(analysis,candidates=candidates))
    assert len(imported.items) == 3  # main footage + two distinct ranges
    assert [item.source_end for item in imported.items[1:]] == [110, 111]
