"""Local data/cache contract: all application-managed paths follow the install."""
from __future__ import annotations

import os
from pathlib import Path

from streamclipper.portable import (configure_portable_environment,
                                    installation_directory, local_model_directory)
from streamclipper.semantic import default_models_directory


def test_portable_paths_inside_selected_root(monkeypatch, tmp_path):
    folder = tmp_path / "Spiel Clips mit ü"
    monkeypatch.setenv("STREAMCLIPPER_HOME", str(folder))
    keys = ("STREAMCLIPPER_MODELS_DIR", "HF_HOME", "HF_HUB_CACHE",
            "HF_XET_CACHE", "XDG_CACHE_HOME", "TORCH_HOME",
            "TORCH_EXTENSIONS_DIR", "TRITON_CACHE_DIR", "CUDA_CACHE_PATH",
            "PIP_CACHE_DIR", "TMP", "TEMP", "TMPDIR")
    for key in keys:
        monkeypatch.setenv(key, "would_be_outside_the_project")
    result = configure_portable_environment()
    assert result == folder.resolve()
    assert local_model_directory() == folder.resolve() / "data" / "models"
    assert default_models_directory() == local_model_directory()
    for key in keys:
        value = Path(os.environ[key])
        assert value.is_relative_to(folder.resolve()), (key, value)
    assert (folder / "data" / "tmp").is_dir()
    assert os.environ["TMP"] == os.environ["TEMP"]


def test_root_is_derived_from_repository_in_editable_source(monkeypatch):
    monkeypatch.delenv("STREAMCLIPPER_HOME", raising=False)
    assert (installation_directory() / "pyproject.toml").is_file()
    assert (installation_directory() / "run_windows.bat").is_file()
