"""Explicit, auditable model presets for the portable local installation.

No network calls on import or during analysis. Download only via an explicit
setup command or the corresponding user-initiated GUI action.
"""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable

from .model_download_progress import ModelDownloadProgress, ProgressEvent
from .media import CancelledError

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


def _expected_model_bytes(api, model: ModelPreset, patterns: list[str],
                          *, token: str | None) -> int | None:
    """Compute real aggregate bytes from the repository file metadata.

    Missing sizes imply a busy progress indicator; never invent totals from
    number of files. The fallback weight choice is included only when needed.
    """
    try:
        info = api.model_info(model.repository, files_metadata=True, token=token)
        siblings = list(info.siblings or [])
        present = {f.rfilename for f in siblings}
        selected = set()
        for sibling in siblings:
            name = sibling.rfilename
            if any(fnmatch(name, pattern) for pattern in patterns):
                selected.add(name)
        if model.kind != 'speech' and 'model.safetensors' not in present:
            if 'pytorch_model.bin' in present:
                selected.add('pytorch_model.bin')
        if not selected:
            return None
        lengths = {f.rfilename: f.size for f in siblings if f.rfilename in selected}
        if any(not isinstance(lengths.get(name), int) or lengths[name] <= 0
               for name in selected):
            return None
        return sum(lengths[name] for name in selected)
    except Exception:
        # Metadata preflight may be unsupported, private, or rate-limited;
        # actual download errors remain observable via snapshot_download.
        return None


def safe_hf_error(exc: Exception) -> str:
    """Do not surface raw HF exceptions that may contain tokens or headers."""
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None)
    if status == 401:
        return 'Hugging Face: Token ungültig oder abgelaufen (401).'
    if status == 403:
        return 'Hugging Face: Keine Berechtigung für dieses Modell (403).'
    if status == 404:
        return 'Hugging Face: Modell nicht gefunden oder nicht zugänglich (404).'
    if isinstance(exc, (FileNotFoundError, PermissionError)):
        return 'Lokaler Modellordner fehlt, ist unvollständig oder nicht beschreibbar.'
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return 'Verbindung zu Hugging Face fehlgeschlagen. Erneut versuchen.'
    return f'Modellvorgang fehlgeschlagen ({type(exc).__name__}); bitte Verbindung, Rechte und Installation prüfen.'


def download_preset(
        model_id: str, root: Path | None = None, *,
        token: str | None = None,
        progress: ProgressEvent | None = None,
        cancelled: Callable[[], bool] | None = None) -> Path:
    """Explicit, cancellable snapshot download with real network byte tracking.

    The opt-in token never enters logs, environment variables, CLI arguments
    or local metadata. 100% is emitted only after validated model weights.
    """
    model = preset(model_id)
    folder = preset_path(model_id, root)
    if cancelled and cancelled():
        raise CancelledError('Modelldownload abgebrochen')
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError('Modell-Setup fehlt: pip install -e ".[models]"') from exc
    common = ['*.json', '*.txt', '*.model', 'vocabulary.*', 'merges.txt']
    weights = ['model.bin'] if model.kind == 'speech' else ['model.safetensors']
    patterns = common + weights
    tracker = ModelDownloadProgress(progress, cancelled=cancelled) if progress else None
    if tracker:
        tracker.report('metadata')
        try:
            from huggingface_hub import HfApi
            expected = _expected_model_bytes(HfApi(), model, patterns, token=token)
        except ImportError:
            expected = None
        tracker.set_total(expected)
    options = dict(repo_id=model.repository, local_dir=str(folder))
    if token is not None:
        options['token'] = token
    if tracker:
        options['tqdm_class'] = tracker.tqdm_class()
    if cancelled and cancelled():
        raise CancelledError('Modelldownload abgebrochen')
    snapshot_download(**options, allow_patterns=patterns)
    if cancelled and cancelled():
        raise CancelledError('Modelldownload abgebrochen')
    if model.kind != 'speech' and not (folder / 'model.safetensors').is_file():
        if tracker:
            tracker.report('fallback')
        snapshot_download(**options, allow_patterns=['pytorch_model.bin'])
    if cancelled and cancelled():
        raise CancelledError('Modelldownload abgebrochen')
    if tracker:
        tracker.report('validation')
    verified = validate_model_dir(model.kind, folder)
    if tracker:
        tracker.finish()
    return verified
