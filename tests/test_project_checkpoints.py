"""M11c checkpoint contract: safe snapshots, source checks, retention and recovery."""
from dataclasses import replace
import json
import pytest

from streamclipper.editor_project import initial_project, add_track
from streamclipper.models import (
    AnalysisResult, Candidate, TranscriptSegment, TranscriptWord, VideoInfo)
from streamclipper.project_checkpoints import (
    checkpoint_dir, create_checkpoint, list_checkpoints, load_checkpoint)


def source(tmp_path):
    original = tmp_path / "Spiel & Stream üñïcødë.mkv"
    original.write_bytes(b"never modify the source")
    return VideoInfo(str(original), 21600, 1920, 1080, 60, True)


def analysis(video):
    return AnalysisResult(
        video, [Candidate(15, 30, 77, "Chat-Reaktion", 21, "manual")],
        "human-reviewed",
        [TranscriptSegment(15, 17, "Ein Test",
            (TranscriptWord(15, 15.4, "Ein"), TranscriptWord(15.5, 17, "Test")))])


def test_checkpoint_roundtrip_with_analysis_and_unicode(tmp_path):
    video = source(tmp_path)
    project = add_track(initial_project(video), "audio", "Sprache 🎤")
    snapshot = analysis(video)
    info = create_checkpoint(project, "Vor dem Schnitt 🧪", snapshot, root=tmp_path/"cp")
    assert info.has_analysis
    assert list_checkpoints(video, root=tmp_path/"cp") == [info]
    saved_project, saved_analysis = load_checkpoint(video, info.id, root=tmp_path/"cp")
    assert saved_project == project
    assert saved_analysis == snapshot
    assert (tmp_path/"Spiel & Stream üñïcødë.mkv").read_bytes() == b"never modify the source"


def test_retention_keeps_newest_and_never_touches_source(tmp_path):
    video = source(tmp_path)
    project = initial_project(video)
    ids = [create_checkpoint(project, f"Stand {i}", root=tmp_path/"cp", max_count=2).id
           for i in range(5)]
    kept = {entry.id for entry in list_checkpoints(video, root=tmp_path/"cp")}
    assert kept == set(ids[-2:])
    assert len(kept) == 2
    assert video.path and (tmp_path/"Spiel & Stream üñïcødë.mkv").is_file()


def test_corrupt_checkpoint_skipped_but_not_deleted(tmp_path):
    video = source(tmp_path)
    info = create_checkpoint(initial_project(video), "Korrekt", root=tmp_path/"cp")
    filename = checkpoint_dir(video.path, root=tmp_path/"cp") / f"{info.id}.checkpoint.json"
    envelope = json.loads(filename.read_text(encoding="utf-8"))
    envelope["data"]["info"]["name"] = "Nachträglich beschädigt"
    filename.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ValueError, match="beschädigt"):
        load_checkpoint(video, info.id, root=tmp_path/"cp")
    assert list_checkpoints(video, root=tmp_path/"cp") == []
    assert filename.is_file()


def test_rejects_different_source_invalid_name_and_traversal(tmp_path):
    video = source(tmp_path)
    project = initial_project(video)
    info = create_checkpoint(project, "Sicherung", root=tmp_path/"cp")
    with pytest.raises(ValueError, match="anderen Aufnahme"):
        load_checkpoint(replace(video, width=1280), info.id, root=tmp_path/"cp")
    with pytest.raises(ValueError, match="ID"):
        load_checkpoint(video, "../other", root=tmp_path/"cp")
    with pytest.raises(ValueError, match="Namen"):
        create_checkpoint(project, " ", root=tmp_path/"cp", max_count=1)
    assert list_checkpoints(video, root=tmp_path/"cp") == [info]
    with pytest.raises(ValueError, match="anderen Aufnahme"):
        create_checkpoint(project, "Falsche Analyse",
                          analysis(replace(video, width=800)), root=tmp_path/"cp")


def test_failed_atomic_publish_preserves_previous_snapshot(tmp_path, monkeypatch):
    import streamclipper.project_checkpoints as cp
    video = source(tmp_path)
    project = initial_project(video)
    first = create_checkpoint(project, "Vorher", root=tmp_path/"cp")
    def fail_replace(src, dest):
        raise OSError("simulierter Schreibfehler")
    monkeypatch.setattr(cp.os, "replace", fail_replace)
    with pytest.raises(OSError, match="Schreibfehler"):
        create_checkpoint(project, "Fehlversuch", root=tmp_path/"cp", max_count=1)
    assert [x.id for x in list_checkpoints(video, root=tmp_path/"cp")] == [first.id]
    assert not list(checkpoint_dir(video.path, root=tmp_path/"cp").glob("*.tmp"))
