"""Offline model-integrity checks, before costly media analysis.

A directory's existence alone does not mean the Hugging Face model weights
were downloaded. These checks never access the network.
"""
from __future__ import annotations

from pathlib import Path


CLIP_WEIGHTS = ("model.safetensors", "pytorch_model.bin")


def validate_clip_model(directory: str | Path) -> Path:
    """Return usable local CLIP model dir or raise an actionable error.

    CLIP ViT-B/32 distributed by openai/clip-vit-base-patch32 has a single
    weights file. Sharded models would need a separate integrity check.
    """
    folder = Path(directory).expanduser()
    if not folder.is_dir():
        raise FileNotFoundError(f"CLIP-Modellordner fehlt: {folder}")
    present = [name for name in CLIP_WEIGHTS
               if (folder / name).is_file() and (folder / name).stat().st_size > 0]
    if not present:
        raise FileNotFoundError(
            f"CLIP-Modell unvollständig: Gewichtsdatei fehlt in {folder}. "
            "Erwartet: model.safetensors oder pytorch_model.bin. "
            "Schließe StreamClipper und führe in D:\\StreamClipper diesen Befehl aus: "
            r'.\\.venv\\Scripts\\python.exe scripts\\setup_local_models.py --which vision'
        )
    if not (folder / "config.json").is_file():
        raise FileNotFoundError(
            f"CLIP-Modell unvollständig: config.json fehlt in {folder}. "
            r'Reparatur: .\\.venv\\Scripts\\python.exe scripts\\setup_local_models.py --which vision'
        )
    return folder
