"""Offline regression tests for Whisper CUDA runtime DLL errors on Windows."""
import sys
from types import ModuleType, SimpleNamespace
import pytest

from streamclipper.models import VideoInfo
from streamclipper.semantic import transcribe_video, _missing_cuda_library


@pytest.fixture
def info_and_model(tmp_path):
    folder = tmp_path / "whisper-small"
    folder.mkdir()
    return VideoInfo("stream mit ü.mp4", 7200.0, 1920, 1080, 60.0, True), str(folder)


def _install_whisper(monkeypatch, cls):
    module = ModuleType("faster_whisper")
    module.WhisperModel = cls
    monkeypatch.setitem(sys.modules, "faster_whisper", module)


def test_cuda_dll_error_is_recognized():
    assert _missing_cuda_library(
        RuntimeError("Library cublas64_12.dll is not found or cannot be loaded"))
    assert _missing_cuda_library(
        OSError("Could not locate cudnn_ops64_9.dll"))
    assert not _missing_cuda_library(RuntimeError("CUDA out of memory"))
    assert not _missing_cuda_library(RuntimeError("Unrelated decoder failure"))


def test_gpu_error_during_lazy_iteration_retries_cpu(monkeypatch, info_and_model):
    video, directory = info_and_model
    calls = []
    class FakeWhisperModel:
        def __init__(self, path, **kwargs):
            calls.append(kwargs)
        def transcribe(self, path, **kwargs):
            device = calls[-1]["device"]
            def generate():
                if device == "auto":
                    raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
                yield SimpleNamespace(start=11.0, end=15.0, text="Was ist denn hier los?!")
            return generate(), None
    _install_whisper(monkeypatch, FakeWhisperModel)
    monkeypatch.delenv("STREAMCLIPPER_WHISPER_DEVICE", raising=False)
    with pytest.warns(RuntimeWarning, match="CPU"):
        segments = transcribe_video(video, directory)
    assert len(segments) == 1
    assert segments[0].start == 11.0
    assert "Was" in segments[0].text
    assert [call["device"] for call in calls] == ["auto", "cpu"]
    assert calls[1]["compute_type"] == "int8"
    assert all(call["local_files_only"] for call in calls)


def test_missing_library_at_model_construction_retries_cpu(monkeypatch, info_and_model):
    video, directory = info_and_model
    calls = []
    class FakeWhisperModel:
        def __init__(self, path, **kwargs):
            calls.append(kwargs["device"])
            if kwargs["device"] == "auto":
                raise OSError("Library cudnn64_9.dll is not found or cannot be loaded")
        def transcribe(self, path, **kwargs):
            return iter([SimpleNamespace(start=0.1, end=1.0, text="Hi!")]), None
    _install_whisper(monkeypatch, FakeWhisperModel)
    monkeypatch.delenv("STREAMCLIPPER_WHISPER_DEVICE", raising=False)
    with pytest.warns(RuntimeWarning):
        result = transcribe_video(video, directory)
    assert calls == ["auto", "cpu"]
    assert result[0].text == "Hi!"


def test_non_library_gpu_failure_is_not_retried(monkeypatch, info_and_model):
    video, directory = info_and_model
    calls = []
    class FakeWhisperModel:
        def __init__(self, path, **kwargs):
            calls.append(kwargs["device"])
        def transcribe(self, path, **kwargs):
            def generate():
                raise RuntimeError("CUDA out of memory")
                yield None
            return generate(), None
    _install_whisper(monkeypatch, FakeWhisperModel)
    monkeypatch.delenv("STREAMCLIPPER_WHISPER_DEVICE", raising=False)
    with pytest.raises(RuntimeError, match="out of memory"):
        transcribe_video(video, directory)
    assert calls == ["auto"]


def test_force_cpu_skips_cuda(monkeypatch, info_and_model):
    video, directory = info_and_model
    calls = []
    class FakeWhisperModel:
        def __init__(self, path, **kwargs):
            calls.append(kwargs)
        def transcribe(self, path, **kwargs):
            return iter([SimpleNamespace(start=1.0, end=2.0, text="Test")]), None
    _install_whisper(monkeypatch, FakeWhisperModel)
    monkeypatch.setenv("STREAMCLIPPER_WHISPER_DEVICE", "cpu")
    spans = transcribe_video(video, directory)
    assert len(spans) == 1
    assert len(calls) == 1
    assert calls[0]["device"] == "cpu"
    assert calls[0]["compute_type"] == "int8"
