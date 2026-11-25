"""M12b: project-v2 migration, track-to-rendergraph timing, safe composition."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from streamclipper.editor_project import (
    SCHEMA_VERSION, TimelineItem, add_item, add_track, edit_item,
    initial_project, load_project, project_path, save_project, toggle_track)
from streamclipper.models import VideoInfo
from streamclipper.render_graph import (
    MAX_MIXED_AUDIO_CLIPS, RENDER_GRAPH_VERSION, build_render_graph)


def info(tmp_path):
    return VideoInfo(str(tmp_path / "game.mkv"), 200.0, 320, 180, 30, True)


def test_project_v3_accepts_external_audio_and_migrates_v1(tmp_path):
    original = info(tmp_path)
    p = initial_project(original)
    assert SCHEMA_VERSION == 3
    old = asdict(p)
    old["schema_version"] = 1
    old["items"][0].pop("media_path", None)
    old["items"][0].pop("gain_db", None)
    folder = tmp_path / "projects"
    path = project_path(original.path, root=folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(old))
    migrated = load_project(original, root=folder)
    assert migrated.schema_version == 3
    assert migrated.items[0].gain_db == 0
    assert migrated.items[0].media_path is None
    imported = add_item(
        migrated, "music", 0, 4, 20, "Song",
        media_path=str(tmp_path / "sound.wav"), gain_db=-6)
    assert imported.items[-1].media_path.endswith("sound.wav")
    assert imported.items[-1].gain_db == -6
    adjusted = edit_item(imported, imported.items[-1].id, gain_db=-12)
    save_project(adjusted, root=folder)
    assert load_project(original, root=folder) == adjusted
    assert json.loads(path.read_text())["schema_version"] == 3


def test_external_path_and_gain_restrictions(tmp_path):
    p = initial_project(info(tmp_path))
    for data in (
        {"media_path": "https://attacker.com/audio.mp3"},
        {"media_path": "../relative.wav"},
        {"media_path": str(tmp_path / "x.wav"), "gain_db": 99},
        {"media_path": str(tmp_path / "x.wav"), "gain_db": float("nan")},
    ):
        with pytest.raises(ValueError):
            add_item(p, "music", 0, 3, 10, **data)
    with pytest.raises(ValueError, match="Video"):
        add_item(p, "gameplay", 0, 3, 10, media_path=str(tmp_path / "x.wav"))
    assert p.items[0].media_path is None


def test_graph_determinism_mute_hidden_lock_and_clipped_source_time(tmp_path):
    v = info(tmp_path)
    p = add_item(
        initial_project(v), "music", 100, 110, 20, "Intro",
        media_path=str(tmp_path / "music.wav"), gain_db=-3)
    p = add_item(p, "mic", 50, 57, 26, "Mic",
                 media_path=str(tmp_path / "voice.wav"), gain_db=0)
    p = toggle_track(p, "music", "hidden")
    p = toggle_track(p, "music", "locked")
    graph = build_render_graph(p, v, 24, 30)
    assert graph.schema_version == RENDER_GRAPH_VERSION
    assert tuple(x.track_id for x in graph.audio_layers) == ("mic", "music")
    mic, music = graph.audio_layers
    assert (mic.source_start, mic.source_end, mic.timeline_offset) == (50,54,2)
    assert (music.source_start, music.source_end, music.timeline_offset) == (104,110,0)
    assert music.gain_db == -3
    assert next(n for n in graph.nodes if n.track_id == "music").hidden
    assert next(n for n in graph.nodes if n.track_id == "music").locked
    assert graph == build_render_graph(p, v, 24, 30)
    muted = toggle_track(p, "music", "muted")
    assert len(build_render_graph(muted, v, 24, 30).audio_layers) == 1
    assert len(build_render_graph(p, v, 30, 32).audio_layers) == 1  # mic only: 26..33


def test_graph_fail_closed_for_extra_video_and_overlays(tmp_path):
    v = info(tmp_path)
    p = initial_project(v)
    with pytest.raises(ValueError, match="anderen Quellaufnahme"):
        build_render_graph(p, replace(v, width=123), 1, 2)
    extra = add_item(p, "gameplay", 1, 3, 1, "Duplicate video")
    with pytest.raises(ValueError, match="Videoclips"):
        build_render_graph(extra, v, 1, 3)
    graphics = add_item(p, "graphics", 2, 3, 2, "Logo")
    with pytest.raises(ValueError, match="Grafik"):
        build_render_graph(graphics, v, 2, 3)
    no_base = replace(p, items=tuple(x for x in p.items if x.id != "source"))
    with pytest.raises(ValueError, match="Basisspur"):
        build_render_graph(no_base, v, 2, 3)
    assert not build_render_graph(p, v, 1, 3).audio_layers


def test_graph_source_audio_clip_works_but_without_source_audio_refuses(tmp_path):
    v = info(tmp_path)
    p = add_item(initial_project(v), "mic", 50, 55, 11, "Source sample")
    graph = build_render_graph(p, v, 12, 14)
    assert graph.audio_layers[0].source_path == v.path
    assert graph.audio_layers[0].source_start == 51
    without_audio = replace(v, has_audio=False)
    p2 = initial_project(without_audio)
    p2 = add_item(p2, "music", 2, 4, 4)
    with pytest.raises(ValueError, match="keine Audiospur"):
        build_render_graph(p2, without_audio, 4, 6)


def test_graph_limits_overlapping_layers(tmp_path):
    v = info(tmp_path)
    p = initial_project(v)
    for i in range(MAX_MIXED_AUDIO_CLIPS+1):
        p = add_item(p, "music", 0, 1, 5, f"Layer {i}")
    with pytest.raises(ValueError, match="Zu viele"):
        build_render_graph(p, v, 5, 6)


def test_legacy_v1_checkpoint_restores_as_v2_without_modifying_checkpoint(tmp_path):
    from streamclipper.project_checkpoints import (
        _hash, checkpoint_dir, create_checkpoint, load_checkpoint)
    v = info(tmp_path)
    root = tmp_path/"checkpoints"
    checkpoint = create_checkpoint(initial_project(v), "Before M12b", root=root)
    path = checkpoint_dir(v.path, root=root)/f"{checkpoint.id}.checkpoint.json"
    doc = json.loads(path.read_text())
    doc["data"]["project"]["schema_version"] = 1
    for item in doc["data"]["project"]["items"]:
        item.pop("media_path", None)
        item.pop("gain_db", None)
    doc["sha256"] = _hash(doc["data"])
    path.write_text(json.dumps(doc))
    exact = path.read_bytes()
    restored, analysis = load_checkpoint(v, checkpoint.id, root=root)
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.items[0].media_path is None
    assert analysis is None
    assert path.read_bytes() == exact  # no silent rewrite of old snapshots
