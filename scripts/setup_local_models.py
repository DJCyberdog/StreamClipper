"""Explicit one-time model provisioning; NOT called by StreamClipper analysis."""
from __future__ import annotations

import argparse
from pathlib import Path

from streamclipper.portable import configure_portable_environment

configure_portable_environment()

from streamclipper.semantic import default_models_directory
from streamclipper.model_checks import validate_clip_model, CLIP_WEIGHTS

MODELS = {
    "speech": ("Systran/faster-whisper-small", "whisper-small"),
    "vision": ("openai/clip-vit-base-patch32", "clip-vit-base-patch32"),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="KI-Modelle einmalig aus dem Internet herunterladen. Die Videoanalyse bleibt offline.")
    parser.add_argument("--which", choices=["speech", "vision", "both"], default="both")
    parser.add_argument("--directory", type=Path, default=default_models_directory())
    options = parser.parse_args(argv)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit('Modell-Setup fehlt: pip install -e ".[models]"') from exc
    wanted = MODELS.keys() if options.which == "both" else [options.which]
    for which in wanted:
        repository, folder = MODELS[which]
        destination = options.directory.expanduser().resolve() / folder
        print(f"Lade {repository} nach {destination} (nur nach ausdrücklichem Aufruf) …")
        patterns = (["*.json", "model.bin", "vocabulary.*"] if which == "speech"
                    else ["*.json", "*.txt", "*.model", "*.safetensors", "vocab.json", "merges.txt"])
        snapshot_download(repo_id=repository, local_dir=str(destination),
                          allow_patterns=patterns)
        if which == "vision":
            if not any((destination / name).is_file() and
                       (destination / name).stat().st_size > 0
                       for name in CLIP_WEIGHTS):
                # The official CLIP main branch currently provides
                # pytorch_model.bin, not model.safetensors. Download it explicitly.
                print("CLIP-Gewichte fehlen; lade pytorch_model.bin ...")
                snapshot_download(repo_id=repository, local_dir=str(destination),
                                  allow_patterns=["pytorch_model.bin"])
            validate_clip_model(destination)
        elif which == "speech":
            if not (destination / "model.bin").is_file():
                raise FileNotFoundError(
                    f"Whisper-Modell unvollständig: model.bin fehlt in {destination}")
        print(f"Bereit und überprüft: {destination}")
    print("Nur die ausgewählten Modelle wurden geladen. Die Analyse benötigt keine Internetverbindung.")


if __name__ == "__main__":
    main()
