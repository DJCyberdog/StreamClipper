"""Regression: DETR backbones need timm in the Windows vision extra."""
from pathlib import Path
import tomllib

import pytest

from streamclipper.object_tracking import _load_detector_model


def test_vision_extra_includes_timm():
    project = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(project.read_text(encoding="utf-8"))
    vision = data["project"]["optional-dependencies"]["vision"]
    assert any(package.lower().startswith("timm") for package in vision)


def test_detector_reports_missing_timm_with_local_runtime_command(tmp_path):
    class RequiresTimm:
        @staticmethod
        def from_pretrained(path, *, local_files_only):
            assert local_files_only is True
            raise RuntimeError(
                "TimmBackbone requires the timm library but it was not found "
                "in your environment."
            )

    with pytest.raises(RuntimeError, match="pip install") as caught:
        _load_detector_model(RequiresTimm, tmp_path)

    assert "timm" in str(caught.value)
    assert r".\runtime\python.exe" in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_other_detector_errors_remain_visible(tmp_path):
    class BrokenWeights:
        @staticmethod
        def from_pretrained(path, *, local_files_only):
            raise RuntimeError("bad model weights")

    with pytest.raises(RuntimeError, match="bad model weights"):
        _load_detector_model(BrokenWeights, tmp_path)


def test_detector_keeps_strictly_local_loading(tmp_path):
    class Working:
        @staticmethod
        def from_pretrained(path, *, local_files_only):
            assert path == str(tmp_path)
            assert local_files_only is True
            return "loaded"

    assert _load_detector_model(Working, tmp_path) == "loaded"
