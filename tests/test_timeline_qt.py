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


def test_edit_single_whisper_word_directly_under_highlight_timeline():
    from streamclipper.models import TranscriptWord
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.source = 'dummy.mp4'
        window._source_duration = 21600
        window.timeline.set_duration(21600)
        result = AnalysisResult(
            VideoInfo('dummy.mp4', 21600, 1920, 1080, 60, True),
            [Candidate(99, 103, 0, 'Manuell', 101, origin='manual')],
            transcript=[TranscriptSegment(100, 101.3, 'Ich fahre', (
                TranscriptWord(100, 100.35, 'Ich'),
                TranscriptWord(100.5, 101.3, 'fahre')))]) 
        window.analysis_finished(result)
        assert (0, 1) in window._word_refs
        assert window.timeline.visible()[1] - window.timeline.visible()[0] < 120
        window.select_timeline_word(0, 1)
        window.word_text.setText('fliege')
        window.word_start.setValue(100.45)
        window.word_end.setValue(101.25)
        assert window.apply_word_editor()
        assert window.analysis.transcript[0].words[1].text == 'fliege'
        assert window.analysis.transcript[0].words[1].origin == 'manual'
        assert window.analysis.transcript[0].text == 'Ich fliege'
        assert window.transcript_dirty
        assert window.word_hint.text().startswith('✓')
        # Also verify the real export caption computation, not merely the GUI.
        from streamclipper.captioning import clip_captions
        assert clip_captions(window.analysis.transcript,99,103)[1][2] == 'Ich fliege'
        # Prevent the modified report from prompting in the test shutdown.
        window.transcript_dirty = False
    finally:
        window.close()
        app.processEvents()


def test_model_selection_is_explicit_and_keeps_original_presets():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.speech_select.count() >= 6
        assert window.speech_select.currentData() == 'whisper-small'
        assert window.vision_select.currentData() == 'clip-vit-base-patch32'
        assert window.detector_select.currentData() == 'detr-resnet-50'
        assert not window.detector_enabled.isChecked()  # no surprise compute/download
        window.speech_select.setCurrentIndex(window.speech_select.findData('whisper-large-v3-turbo'))
        assert window.speech_path.text().endswith('whisper-large-v3-turbo')
        window.vision_select.setCurrentIndex(window.vision_select.findData('clip-vit-large-patch14'))
        assert window.vision_path.text().endswith('clip-vit-large-patch14')
        window.detector_select.setCurrentIndex(window.detector_select.findData('rtdetr-r18vd'))
        assert window.detector_path.text().endswith('rtdetr-r18vd')
    finally:
        window.close()
        app.processEvents()
