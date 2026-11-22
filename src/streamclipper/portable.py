"""Per-installation paths for the self-contained source and portable Windows app.

This touches *process-local* environment variables only. It never modifies
Windows user or system environment settings and does not delete other caches.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def installation_directory() -> Path:
    configured = os.environ.get("STREAMCLIPPER_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/streamclipper/portable.py -> repository root, for editable installs
    return Path(__file__).resolve().parents[2]


def local_model_directory() -> Path:
    return installation_directory() / "data" / "models"


def configure_portable_environment() -> Path:
    """Confine first-party and known ML caches to data/ below the install.

    Caller must invoke this before importing Torch/Transformers/Hugging Face.
    External Python, FFmpeg installations and exported MP4s are not managed.
    """
    root = installation_directory()
    data = root / "data"
    paths = {
        "STREAMCLIPPER_HOME": root,
        "STREAMCLIPPER_MODELS_DIR": data / "models",
        "HF_HOME": data / "cache" / "huggingface",
        "HF_HUB_CACHE": data / "cache" / "huggingface" / "hub",
        "HF_XET_CACHE": data / "cache" / "huggingface" / "xet",
        "XDG_CACHE_HOME": data / "cache" / "xdg",
        "TORCH_HOME": data / "cache" / "torch",
        "TORCH_EXTENSIONS_DIR": data / "cache" / "torch_extensions",
        "TRITON_CACHE_DIR": data / "cache" / "triton",
        "CUDA_CACHE_PATH": data / "cache" / "cuda",
        "PIP_CACHE_DIR": data / "cache" / "pip",
        "TMP": data / "tmp",
        "TEMP": data / "tmp",
        "TMPDIR": data / "tmp",
    }
    (data / "tmp").mkdir(parents=True, exist_ok=True)
    for key, path in paths.items():
        os.environ[key] = str(path)
    return root
