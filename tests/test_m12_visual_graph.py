"""M12b2 core contract: backwards-compatible assets, deterministic visual layers."""
from dataclasses import asdict, replace
import json

import pytest

from streamclipper.editor_project import (
    AUDIO_SCHEMA_VERSION, SCHEMA_VERSION, add_item, add_track, edit_item,
    initial_project, load_project, project_path, save_project, toggle_track)
from streamclipper.models import VideoInfo
from streamclipper.render_graph import (
    MAX_VISUAL_LAYERS, RENDER_GRAPH_VERSION, build_render_graph)


def video(tmp_path):
    return VideoInfo(str(tmp_path / "game.mkv"), 180, 320, 180, 30, True)


def test_visual_project_v3_imports_v2_and_preserves_bytes_until_save(tmp_path):
    info = video(tmp_path)
    base = initial_project(info)
    raw = asdict(base)
    raw["schema_version"] = AUDIO_SCHEMA_VERSION
    for item in raw["items"]:
        for key in ("x", "y", "width", "height", "opacity"):
            item.pop(key)
    folder = tmp_path / "projects"
    path = project_path(info.path, root=folder)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(raw))
    before = path.read_bytes()
    restored = load_project(info, root=folder)
    assert SCHEMA_VERSION == 3
    assert restored.schema_version == 3
    assert restored.items[0].width == .28
    assert path.read_bytes() == before
    p = add_track(restored, "video", "Facecam")
    p = add_item(p, p.tracks[-1].id, 10, 15, 20, "Camera",
                 media_path=str(tmp_path / "camera.mp4"),
                 x=.6, y=.05, width=.35, height=.35, opacity=.7)
    p = add_item(p, "graphics", 0, 4, 21, "Logo",
                 media_path=str(tmp_path / "logo.png"),
                 x=.1, y=.7, width=.2, height=.2)
    save_project(p, root=folder)
    assert load_project(info, root=folder) == p
    assert json.loads(path.read_text())["schema_version"] == 3


def test_bad_visual_paths_and_geometry_fail_closed(tmp_path):
    p = initial_project(video(tmp_path))
    for path in ("../clip.mp4", "https://example.org/a.mp4", "/tmp/clip.wav"):
        with pytest.raises(ValueError):
            add_item(p, "gameplay", 0, 2, 5, media_path=path)
    with pytest.raises(ValueError):
        add_item(p, "graphics", 0, 2, 5, media_path=str(tmp_path / "logo.svg"))
    # Audio extensions remain backward-compatible with v2; FFprobe,
    # not filename guessing, checks whether the source actually has audio.
    legacy_audio = add_item(
        p, "mic", 0, 2, 5, media_path=str(tmp_path / "logo.png"))
    assert legacy_audio.items[-1].track_id == "mic"
    for geometry in (
        {"x": .9, "width": .3},
        {"height": 0},
        {"opacity": 1.1},
        {"y": float("nan")},
    ):
        with pytest.raises(ValueError):
            add_item(p, "graphics", 0, 2, 5,
                     media_path=str(tmp_path / "logo.png"), **geometry)
    assert p.items[0].media_path is None


def test_video_image_clip_windows_order_and_mute(tmp_path):
    info = video(tmp_path)
    p = initial_project(info)
    p = add_item(p, "graphics", 0, 4, 14, "Logo",
                 media_path=str(tmp_path / "logo.png"), x=.1, opacity=.6)
    p = add_track(p, "video", "Facecam")
    camera = p.tracks[-1].id
    p = add_item(p, camera, 90, 100, 10, "PiP",
                 media_path=str(tmp_path / "camera.mp4"), x=.5)
    p = toggle_track(p, camera, "hidden")
    p = toggle_track(p, camera, "locked")
    graph = build_render_graph(p, info, 15, 18)
    assert RENDER_GRAPH_VERSION == graph.schema_version == 2
    assert [x.kind for x in graph.visual_layers] == ["overlay", "video"]
    still, pip = graph.visual_layers
    assert (still.source_start, still.source_end, still.timeline_offset) == (1, 4, 0)
    assert (pip.source_start, pip.source_end, pip.timeline_offset) == (95, 98, 0)
    assert pip.x == .5
    node = next(x for x in graph.nodes if x.track_id == camera)
    assert node.hidden and node.locked
    assert graph == build_render_graph(p, info, 15, 18)
    muted = toggle_track(p, camera, "muted")
    assert [x.kind for x in build_render_graph(muted, info, 15, 18).visual_layers] == ["overlay"]
    assert build_render_graph(p, info, 100, 103).visual_layers == ()


def test_legacy_extra_metadata_clips_and_captions_are_still_rejected(tmp_path):
    info = video(tmp_path)
    p = initial_project(info)
    metadata = add_item(p, "gameplay", 1, 2, 10, "old manual highlight")
    with pytest.raises(ValueError, match="Videoclips"):
        build_render_graph(metadata, info, 10, 11)
    captions = add_item(p, "captions", 2, 3, 10, "caption")
    with pytest.raises(ValueError, match="Untertitelclips"):
        build_render_graph(captions, info, 10, 11)
    bad_base = edit_item(p, "source", timeline_start=1)
    with pytest.raises(ValueError, match="Basisspur|Basisvideo|Gameplay"):
        build_render_graph(bad_base, info, 1, 2)


def test_graph_visual_limit(tmp_path):
    info = video(tmp_path)
    p = initial_project(info)
    for index in range(MAX_VISUAL_LAYERS+1):
        p = add_item(p, "graphics", 0, 1, 10,
                     f"Logo {index}", media_path=str(tmp_path / "logo.png"))
    with pytest.raises(ValueError, match="Zu viele"):
        build_render_graph(p, info, 10, 11)


def test_v2_checkpoint_migrates_without_mutating_archive(tmp_path):
    from streamclipper.project_checkpoints import (
        _hash, checkpoint_dir, create_checkpoint, load_checkpoint)
    info = video(tmp_path)
    folder = tmp_path / "checkpoints"
    saved = create_checkpoint(initial_project(info), "M12b audio", root=folder)
    path = checkpoint_dir(info.path, root=folder) / f"{saved.id}.checkpoint.json"
    raw = json.loads(path.read_text())
    raw["data"]["project"]["schema_version"] = 2
    for item in raw["data"]["project"]["items"]:
        for key in ("x", "y", "width", "height", "opacity"):
            item.pop(key)
    raw["sha256"] = _hash(raw["data"])
    path.write_text(json.dumps(raw))
    prior = path.read_bytes()
    restored, _ = load_checkpoint(info, saved.id, root=folder)
    assert restored.schema_version == 3
    assert path.read_bytes() == prior
