import pytest
from streamclipper.inpainting_metrics import evaluate_restoration


def test_perfect_restoration():
    clean=[bytes([10]*6),bytes([30]*6)]
    m=evaluate_restoration(clean,clean,[bytes([255,0])]*2)
    assert m.masked_mae==m.outside_mae==m.temporal_error_mae==0
    assert m.masked_pixels==2 and m.temporal_pixels==1


def test_temporal_flicker_and_context_damage():
    clean=[bytes([100]*6)]*2
    result=[bytes([110]*3+[120]*3),bytes([90]*3+[120]*3)]
    m=evaluate_restoration(clean,result,[bytes([255,0])]*2)
    assert m.masked_mae==pytest.approx(10/255)
    assert m.outside_mae==pytest.approx(20/255)
    assert m.temporal_error_mae==pytest.approx(20/255)


def test_requires_temporal_overlap():
    with pytest.raises(ValueError):
        evaluate_restoration([bytes(6)]*2,[bytes(6)]*2,[bytes([255,0]),bytes([0,255])])
