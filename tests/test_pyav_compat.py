"""Regression: the speech extra must not resolve an incompatible PyAV.

faster-whisper <= 1.2.1 calls av.open(metadata_errors=...), removed in PyAV 18+.
"""
from pathlib import Path
from types import ModuleType
import sys
import tomllib

import pytest

from streamclipper.models import VideoInfo
from streamclipper.semantic import transcribe_video


def test_speech_dependency_excludes_pyav_18_and_later():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = project["project"]["optional-dependencies"]["speech"]
    assert "av>=11,<18" in requirements


def test_old_dependency_error_is_actionable(monkeypatch, tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    fake_module = ModuleType("faster_whisper")

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            def broken():
                raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")
                yield  # make it a generator like faster-whisper
            return broken(), None

    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    recording = VideoInfo("aufnahme.mp4", 60.0, 1920, 1080, 30.0, True)
    with pytest.raises(RuntimeError, match="av==17.1.0"):
        transcribe_video(recording, str(model))
