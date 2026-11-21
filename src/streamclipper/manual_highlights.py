"""Deterministic, model-free manual highlight editing on local recordings."""
from __future__ import annotations

from dataclasses import replace
import math

from .models import AnalysisResult, Candidate


def add_manual_highlight(result: AnalysisResult, start: float, end: float,
                         label: str = "Manuelles Highlight") -> AnalysisResult:
    if not (math.isfinite(start) and math.isfinite(end)
            and 0 <= start < end <= result.video.duration + 0.1):
        raise ValueError("Highlight muss innerhalb der Aufnahme liegen (Start vor Ende).")
    cleaned = " ".join(label.split())[:100] or "Manuelles Highlight"
    candidate = Candidate(round(start, 3), round(end, 3), 0, cleaned,
                          round((start + end) / 2, 3), origin="manual")
    return replace(result, candidates=[*result.candidates, candidate])


def remove_manual_highlight(result: AnalysisResult, index: int) -> AnalysisResult:
    if not 0 <= index < len(result.candidates):
        raise ValueError("Kein Highlight ausgewählt.")
    if result.candidates[index].origin != "manual":
        raise ValueError("Automatisch erkannte Highlights lassen sich hier nicht löschen.")
    return replace(result, candidates=[c for i, c in enumerate(result.candidates) if i != index])
