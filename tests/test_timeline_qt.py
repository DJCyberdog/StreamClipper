"""Optional desktop smoke test when PySide6 is present (Windows build runners)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from streamclipper.gui import MainWindow
from streamclipper.models import AnalysisResult, Candidate, TranscriptSegment, VideoInfo


def test_timeline_and_subtitle_overlay_are_wired():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.timeline is not None
        window.source = "dummy.mp4"
        window._source_duration = 6 * 3600
        window.timeline.set_duration(window._source_duration)
        window.timeline.set_selection(123.456, 145.678, emit=True)
        assert window.timeline_in.value() == pytest.approx(123.456)
        assert window.timeline_out.value() == pytest.approx(145.678)
        window.timeline.set_zoom(60, center=130)
        assert window.timeline.visible()[1] - window.timeline.visible()[0] == pytest.approx(360)
        window.analysis = AnalysisResult(
            VideoInfo("dummy.mp4", 21600, 1920, 1080, 60, True), [],
            transcript=[TranscriptSegment(2.0, 6.0, "eins zwei drei vier fünf sechs")])
        window._update_caption_overlay(2.5)
        assert window.caption_overlay.text() == "eins zwei drei vier fünf sechs"
        window.caption_offset.setValue(1.0)
        window._update_caption_overlay(2.5)
        assert window.caption_overlay.isHidden()
        window.analysis = AnalysisResult(
            VideoInfo("dummy.mp4", 21600, 1920, 1080, 60, True),
            [Candidate(123.25, 145.75, 0, "Manueller Test", 134.5,
                       origin="manual")])
        window._busy(False)
        window.refresh_highlight_table()
        assert window.timeline.in_point == pytest.approx(123.25)
        assert window.timeline.out_point == pytest.approx(145.75)
        assert window.timeline_in.value() == pytest.approx(123.25)
        assert window.timeline_out.value() == pytest.approx(145.75)
        assert window.timeline_trim.isEnabled()
    finally:
        window.close()
        app.processEvents()
