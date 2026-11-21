"""CLIP local-model integrity: fail early, offline, no fake success."""
from pathlib import Path
from types import ModuleType
import importlib.util
import sys
import pytest

from streamclipper import analyze as analyzer
from streamclipper.model_checks import validate_clip_model


def test_only_config_fails(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    with pytest.raises(FileNotFoundError, match="model.safetensors oder pytorch_model.bin"):
        validate_clip_model(tmp_path)


@pytest.mark.parametrize("filename", ["model.safetensors", "pytorch_model.bin"])
def test_weights_accepted(tmp_path, filename):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / filename).write_bytes(b"test")
    assert validate_clip_model(tmp_path) == tmp_path


def test_missing_config_fails(tmp_path):
    (tmp_path / "model.safetensors").write_bytes(b"test")
    with pytest.raises(FileNotFoundError, match="config.json"):
        validate_clip_model(tmp_path)


def test_early_preflight_no_expensive_processing(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}")
    called = []
    monkeypatch.setattr(analyzer, "probe_video", lambda *args: called.append("probe"))
    monkeypatch.setattr(analyzer, "audio_levels", lambda *args, **kwargs: called.append("audio"))
    monkeypatch.setattr(analyzer, "transcribe_video", lambda *args, **kwargs: called.append("whisper"))
    with pytest.raises(FileNotFoundError, match="CLIP-Modell unvollständig"):
        analyzer.analyze("6-hour-recording.mp4", speech_model="whisper", vision_model=str(tmp_path))
    assert called == []


def _load_setup(monkeypatch, downloader):
    fake_hf = ModuleType("huggingface_hub")
    fake_hf.snapshot_download = downloader
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)
    path = Path(__file__).resolve().parents[1] / "scripts" / "setup_local_models.py"
    spec = importlib.util.spec_from_file_location("test_streamclipper_model_setup", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_setup_fetches_pytorch_weights_from_official_main(tmp_path, monkeypatch):
    patterns = []
    def downloader(*, repo_id, local_dir, allow_patterns):
        patterns.append(allow_patterns)
        dest = Path(local_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text("{}")
        if "pytorch_model.bin" in allow_patterns:
            (dest / "pytorch_model.bin").write_bytes(b"fake")
    setup = _load_setup(monkeypatch, downloader)
    setup.main(["--which", "vision", "--directory", str(tmp_path)])
    assert len(patterns) == 2
    assert patterns[1] == ["pytorch_model.bin"]


def test_setup_missing_weight_not_success(tmp_path, monkeypatch):
    def downloader(*, repo_id, local_dir, allow_patterns):
        dest = Path(local_dir)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.json").write_text("{}")
    setup = _load_setup(monkeypatch, downloader)
    with pytest.raises(FileNotFoundError, match="CLIP-Modell unvollständig"):
        setup.main(["--which", "vision", "--directory", str(tmp_path)])
