"""Atomic, source-bound crash recovery using existing analysis JSON format."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from .models import AnalysisResult
from .portable import installation_directory
from .transcript_editor import load_analysis_report

def autosave_path(source: str | Path, *, root: Path | None = None) -> Path:
    canonical = os.path.normcase(os.path.abspath(os.fspath(source)))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    store = Path(root) if root is not None else installation_directory() / "data" / "projects" / "autosaves"
    return store / f"{digest}.highlights.json"

def save_autosave(result: AnalysisResult, *, root: Path | None = None) -> Path:
    path = autosave_path(result.video.path, root=root)
    result.save_json(path)  # same validated, atomic JSON as manual reports
    return path

def load_autosave(source: str | Path, *, root: Path | None = None,
                  duration: float | None = None,
                  size: tuple[int, int] | None = None) -> AnalysisResult:
    result = load_analysis_report(autosave_path(source, root=root), source)
    if duration is not None and abs(result.video.duration - duration) > 0.25:
        raise ValueError("Die automatisch gesicherte Aufnahme hat eine andere Dauer")
    if size is not None and (result.video.width, result.video.height) != size:
        raise ValueError("Die automatisch gesicherte Aufnahme hat eine andere Auflösung")
    return result

def clear_autosave(source: str | Path, *, root: Path | None = None) -> None:
    autosave_path(source, root=root).unlink(missing_ok=True)
