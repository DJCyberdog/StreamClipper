"""CLIP installation regression: missing weights must fail before long jobs."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest

from streamclipper import analyze as analyzer
from streamclipper.model_checks import validate_clip_model


def test_clip_directory_with_only_config_is_not_a_model(tmp_path):
    folder = tmp_path / "clip-vit-base-patch32"
    folder.mkdir()
    (folder / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="model.safetensors oder pytorch_model.bin"):
        validate_clip_model(folder)


@pytest.mark.parametrize("filename", ["model.safetensors", "pytorch_model.bin"])
def test_clip_weight_file_is_accepted(tmp_path, filename):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / filename).write_bytes(b"test")
    assert validate_clip_model(tmp_path) == tmp_path


def test_clip_missing_config_is_rejected(tmp_path):
    (tmp_path / "model.safetensors").write_bytes(b"test")
    with pytest.raises(FileNotFoundError, match="config.json"):
        validate_clip_model(tmp_path)


def test_multimodal_analysis_fails_before_video_or_whisper(tmp_path, monkeypatch):
    partial_model = tmp_path / "clip"
    partial_model.mkdir()
    (partial_model / "config.json").write_text("{}", encoding="utf-8")
    called = []
    monkeypatch.setattr(analyzer, "probe_video", lambda *_: called.append("probe"))
    monkeypatch.setattr(analyzer, "audio_levels", lambda *_args, **_kw: called.append("audio"))
    monkeypatch.setattr(analyzer, "transcribe_video", lambda *_args, **_kw: called.append("whisper"))
    with pytest.raises(FileNotFoundError, match="CLIP-Modell unvollständig"):
        analyzer.analyze("long-recording.mp4", speech_model="whisper-small",
                         vision_model=str(partial_model))
    assert called == []


def _load_setup(monkeypatch, downloader):
    fake_hf = ModuleType("huggingface_hub")
    fake_hf.snapshot_download = downloader
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)
    path = Path(__file__).resolve().parents[1] / "scripts" / "setup_local_models.py"
    spec = importlib.util.spec_from_file_location("streamclipper_test_model_setup", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_setup_recovers_pytorch_weights_when_safetensors_missing(tmp_path, monkeypatch):
    patterns = []
    def downloader(*, repo_id, local_dir, allow_patterns):
        patterns.append(allow_patterns)
        dest = Path(local_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text("{}", encoding="utf-8")
        if "pytorch_model.bin" in allow_patterns:
            (dest / "pytorch_model.bin").write_bytes(b"test")
    setup = _load_setup(monkeypatch, downloader)
    setup.main(["--which", "vision", "--directory", str(tmp_path)])
    assert len(patterns) == 2
    assert (tmp_path / "clip-vit-base-patch32" / "pytorch_model.bin").is_file()


def test_setup_does_not_claim_success_if_weights_absent(tmp_path, monkeypatch):
    def downloader(*, repo_id, local_dir, allow_patterns):
        dest = Path(local_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text("{}", encoding="utf-8")
    setup = _load_setup(monkeypatch, downloader)
    with pytest.raises(FileNotFoundError, match="CLIP-Modell unvollständig"):
        setup.main(["--which", "vision", "--directory", str(tmp_path)])
