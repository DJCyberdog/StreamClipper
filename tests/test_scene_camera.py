import math
import pytest
from streamclipper.scene_camera import CameraKeyframe as K, Scene, ScenePlan, fixed_zoom_crop


def test_manual_priority_survives_new_suggestions():
    scene = Scene("s", 10, 20).with_manual((K(0, .2, .3), K(10, .8, .7)))
    updated = scene.with_suggestion((K(0, .9, .9),))
    assert updated.manual == scene.manual
    assert updated.camera_at(15).x == pytest.approx(.5)
    assert updated.with_manual(()).camera_at(15).x == .9


def test_excerpt_preserves_absolute_camera_timing():
    scene = Scene("s", 10, 20, (K(0, 0, .5, 1.2), K(10, 1, .5, 1.2)))
    points, zoom = fixed_zoom_crop(scene, 12, 16)
    assert [p.at for p in points] == [0, 4]
    assert [p.x for p in points] == pytest.approx([.2, .6])
    assert zoom == 1.2


def test_dynamic_zoom_fails_closed_at_render_bridge():
    scene = Scene("s", 0, 10, (K(0), K(10, zoom=1.5)))
    assert scene.camera_at(5).zoom == 1.25
    with pytest.raises(ValueError, match="Dynamischer Zoom"):
        fixed_zoom_crop(scene, 0, 10)


def test_scene_boundary_and_gaps():
    plan = ScenePlan(30, (Scene("a", 0, 10), Scene("b", 10, 20)))
    assert plan.scene_at(10).id == "b"
    assert plan.scene_at(25) is None
    assert plan.scene_at(30) is None


@pytest.mark.parametrize("keys", [
    (K(0, math.nan),), (K(0, 1.1),), (K(0, zoom=.9),),
    (K(11),), (K(1), K(1)), (K(2), K(1)),
])
def test_invalid_keys(keys):
    with pytest.raises(ValueError):
        Scene("s", 0, 10, keys).validate()


def test_overlaps_and_duplicate_ids_rejected():
    plan = ScenePlan(20, (Scene("a", 0, 10),))
    with pytest.raises(ValueError):
        plan.with_scene(Scene("b", 9, 12))
    with pytest.raises(ValueError):
        ScenePlan(20, (Scene("a", 0, 10), Scene("a", 10, 20))).validate()
    assert plan.with_scene(Scene("a", 1, 8)).scenes[0].start == 1
