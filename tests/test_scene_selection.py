import pytest
from streamclipper.models import VideoInfo
from streamclipper.scene_selection import initial_selection, load_selection, save_selection


def test_split_trim_order_inclusion_and_manual_region():
    plan = initial_selection(10, 30).split(0, 20)
    plan = plan.edit(0, end=19, mode="manual", region=(.1,.2,.4,.5))
    plan = plan.move(0, 1).edit(0, included=False)
    assert [(s.start,s.end) for s in plan.scenes] == [(20,30),(10,19)]
    assert len(plan.output_scenes) == 1
    assert plan.output_scenes[0].region == (.1,.2,.4,.5)
    assert plan.output_scenes[0].mode == "manual"


def test_split_preserves_manual_settings():
    plan = initial_selection(0, 10).edit(0, mode="fixed", region=(0,0,.5,1))
    split = plan.split(0, 5)
    assert all(s.mode == "fixed" and s.region == (0,0,.5,1) for s in split.scenes)
    assert split.scenes[0].id != split.scenes[1].id


@pytest.mark.parametrize("changes", [
    {"end": 11}, {"start": -1}, {"mode": "unknown"},
    {"region": (.8,0,.5,1)}, {"region": (0,0,float("nan"),1)},
    {"included": 1},
])
def test_invalid_edit(changes):
    with pytest.raises(ValueError):
        initial_selection(0, 10).edit(0, **changes)


def test_overlap_rejected():
    with pytest.raises(ValueError):
        initial_selection(0, 10).split(0, 5).edit(0, end=6)


def test_roundtrip_and_highlight_isolation(tmp_path):
    video = VideoInfo(str(tmp_path/"test.mp4"), 60, 1920, 1080, 30, True)
    plan = initial_selection(10, 30).split(0, 20).move(0, 1).edit(0, included=False)
    save_selection(video, plan, root=tmp_path)
    assert load_selection(video, 10, 30, root=tmp_path) == plan
    assert len(load_selection(video, 0, 30, root=tmp_path).scenes) == 1


def test_corrupt_file_not_silently_replaced(tmp_path):
    video = VideoInfo(str(tmp_path/"test.mp4"), 60, 1920, 1080, 30, True)
    path = save_selection(video, initial_selection(0, 10), root=tmp_path)
    path.write_text("bad", encoding="utf-8")
    with pytest.raises(ValueError):
        load_selection(video, 0, 10, root=tmp_path)
    assert path.read_text() == "bad"


def test_saved_plan_cannot_be_silently_ignored(tmp_path):
    from streamclipper.scene_selection import require_unplanned_highlight
    video = VideoInfo(str(tmp_path/"test.mp4"), 60, 1920, 1080, 30, True)
    require_unplanned_highlight(video, 0, 10, root=tmp_path)
    save_selection(video, initial_selection(0, 10), root=tmp_path)
    with pytest.raises(ValueError, match="Szenenplan"):
        require_unplanned_highlight(video, 0, 10, root=tmp_path)
    require_unplanned_highlight(video, 10, 20, root=tmp_path)
