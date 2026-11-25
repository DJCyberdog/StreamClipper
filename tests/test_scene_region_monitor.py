import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF, QRectF
from streamclipper.scene_region_monitor import normalized_region


def test_letterbox_normalization():
    rect = QRectF(0, 100, 800, 450)
    assert normalized_region(rect, QPointF(200, 190), QPointF(600, 460)) == (.25,.2,.5,.6)


def test_reverse_drag_and_clamping():
    rect = QRectF(100, 0, 400, 300)
    assert normalized_region(rect, QPointF(600, 400), QPointF(0, -10)) == (0,0,1,1)


def test_tiny_region_rejected():
    rect = QRectF(0, 0, 1000, 1000)
    with pytest.raises(ValueError):
        normalized_region(rect, QPointF(0, 0), QPointF(1, 1))
