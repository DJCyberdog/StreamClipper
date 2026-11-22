"""Explicit, auditable model presets for the portable local installation.

No network calls on import or during analysis. Download only via an explicit
setup command or the corresponding user-initiated GUI action.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .model_checks import validate_clip_model
from .semantic import default_models_directory


@dataclass(frozen=True)
class ModelPreset:
    id: str
    kind: str  # speech, vision, detector
    label: str
    repository: str
    folder: str
    note: str


PRESETS: tuple[ModelPreset, ...] = (
    ModelPreset('whisper-tiny', 'speech', 'Whisper Tiny · sehr sparsam',
                'Systran/faster-whisper-tiny', 'whisper-tiny', 'Deutsch & Englisch; geringere Genauigkeit'),
    ModelPreset('whisper-base', 'speech', 'Whisper Base · schnell',
                'Systran/faster-whisper-base', 'whisper-base', 'Deutsch & Englisch'),
    ModelPreset('whisper-small', 'speech', 'Whisper Small · bisheriger Standard',
                'Systran/faster-whisper-small', 'whisper-small', 'Bewährte Standardeinstellung'),
    ModelPreset('whisper-medium', 'speech', 'Whisper Medium · genauer, langsamer',
                'Systran/faster-whisper-medium', 'whisper-medium', 'Größerer Speicherbedarf'),
    ModelPreset('whisper-large-v3-turbo', 'speech', 'Whisper Large-v3 Turbo · Testempfehlung',
                'mobiuslabsgmbh/faster-whisper-large-v3-turbo', 'whisper-large-v3-turbo',
                'Multilingual; Qualität am eigenen Material prüfen'),
    ModelPreset('whisper-large-v3', 'speech', 'Whisper Large-v3 · höchste Rechenlast',
                'Systran/faster-whisper-large-v3', 'whisper-large-v3', 'Multilingual; viel Speicher'),
    ModelPreset('clip-vit-base-patch32', 'vision', 'CLIP ViT-B/32 · bisheriger Standard',
                'openai/clip-vit-base-patch32', 'clip-vit-base-patch32', 'Relativ wenig Rechenlast'),
    ModelPreset('clip-vit-large-patch14', 'vision', 'CLIP ViT-L/14 · detailreicher',
                'openai/clip-vit-large-patch14', 'clip-vit-large-patch14', 'Deutlich mehr Rechenlast'),
    ModelPreset('detr-resnet-50', 'detector', 'DETR ResNet-50 · Objektspuren',
                'facebook/detr-resnet-50', 'detr-resnet-50', 'Apache-2.0; generische COCO-Objekte'),
    ModelPreset('rtdetr-r18vd', 'detector', 'RT-DETR R18 · kompakter Detektor',
                'PekingU/rtdetr_r18vd', 'rtdetr-r18vd', 'Apache-2.0; generische COCO-Objekte'),
)
_BY_ID = {m.id: m for m in PRESETS}
DEFAULTS = {'speech': 'whisper-small', 'vision': 'clip-vit-base-patch32', 'detector': 'detr-resnet-50'}


def presets_for(kind: str) -> tuple[ModelPreset, ...]:
    if kind not in DEFAULTS:
        raise ValueError('Unbekannte Modellgruppe')
    return tuple(m for m in PRESETS if m.kind == kind)


def preset(model_id: str) -> ModelPreset:
    try:
        return _BY_ID[model_id]
    except KeyError as exc:
        raise ValueError(f'Unbekanntes Modell: {model_id}') from exc


def preset_path(model_id: str, root: Path | None = None) -> Path:
    return (root if root is not None else default_models_directory()) / preset(model_id).folder


def validate_model_dir(kind: str, path: str | Path) -> Path:
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f'{kind}-Modellordner fehlt: {folder}')
    if kind == 'vision':
        return validate_clip_model(folder)
    if kind not in DEFAULTS:
        raise ValueError('Unbekannte Modellgruppe')
    required = ('model.bin', 'config.json') if kind == 'speech' else ('config.json', 'preprocessor_config.json')
    missing = [name for name in required if not (folder / name).is_file() or (folder / name).stat().st_size == 0]
    if kind == 'detector' and not any(
        (folder / name).is_file() and (folder / name).stat().st_size > 0
        for name in ('model.safetensors', 'pytorch_model.bin')
    ):
        missing.append('model.safetensors oder pytorch_model.bin')
    if missing:
        raise FileNotFoundError(
            f'{kind}-Modell unvollständig in {folder}: {", ".join(missing)}. '
            'Über „Modell herunterladen“ oder scripts/setup_local_models.py reparieren.')
    return folder


def is_installed(model_id: str, root: Path | None = None) -> bool:
    model = preset(model_id)
    try:
        validate_model_dir(model.kind, preset_path(model_id, root))
    except (ValueError, OSError):
        return False
    return True


def download_preset(model_id: str, root: Path | None = None) -> Path:
    """Only call from an explicit setup/download action. Never from inference."""
    model = preset(model_id)
    folder = preset_path(model_id, root)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError('Modell-Setup fehlt: pip install -e ".[models]"') from exc
    common = ['*.json', '*.txt', '*.model', 'vocabulary.*', 'merges.txt']
    weights = ['model.bin'] if model.kind == 'speech' else ['model.safetensors']
    snapshot_download(repo_id=model.repository, local_dir=str(folder),
                      allow_patterns=common + weights)
    if model.kind != 'speech':
        if not (folder / 'model.safetensors').is_file():
            snapshot_download(repo_id=model.repository, local_dir=str(folder),
                              allow_patterns=['pytorch_model.bin'])
    return validate_model_dir(model.kind, folder)
