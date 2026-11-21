"""Manual highlights never require AI models or media decoding."""
from dataclasses import replace
import json

import pytest

from streamclipper.manual_highlights import add_manual_highlight, remove_manual_highlight
from streamclipper.models import AnalysisResult, Candidate, VideoInfo
from streamclipper.transcript_editor import load_analysis_report


@pytest.fixture
def report(tmp_path):
    file = tmp_path / "spieleabend.mp4"
    file.write_bytes(b"fake")
    return AnalysisResult(
        VideoInfo(str(file), 6 * 3600, 1920, 1080, 60, True),
        [Candidate(30, 55, 65, "Audiopeak", 35)],
        method="audio-rms-peaks-v1",
    )


def test_manual_clip_can_be_added_without_models_and_saved(report, tmp_path):
    updated = add_manual_highlight(report, 23500 if False else 1800.123, 1820.555,
                                   "  Verkehrsunfall    im  RP ")
    assert updated.candidates[-1].origin == "manual"
    assert updated.candidates[-1].reason == "Verkehrsunfall im RP"
    assert updated.candidates[-1].score == 0  # not a fictional AI confidence
    assert len(report.candidates) == 1
    path = tmp_path / "highlights.json"
    updated.save_json(path)
    loaded = load_analysis_report(path, report.video.path)
    assert loaded == updated
    assert json.loads(path.read_text(encoding="utf-8"))["candidates"][-1]["origin"] == "manual"


def test_old_analysis_without_origin_is_still_readable(report, tmp_path):
    path = tmp_path / "old.json"
    report.save_json(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["candidates"]:
        del entry["origin"]
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_analysis_report(path, report.video.path)
    assert loaded.candidates[0].origin == "auto"


def test_remove_only_manual_highlights(report):
    updated = add_manual_highlight(report, 5, 18, "Test")
    with pytest.raises(ValueError, match="Automatisch"):
        remove_manual_highlight(updated, 0)
    assert remove_manual_highlight(updated, 1) == report


@pytest.mark.parametrize("start,end", [(-1, 5), (20, 19), (3, 3), (0, 21601),
                                         (float("nan"), 7), (0, float("inf"))])
def test_invalid_manual_range_rejected(report, start, end):
    with pytest.raises(ValueError, match="Highlight"):
        add_manual_highlight(report, start, end)
