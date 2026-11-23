"""M12a Qt: render preview action must not mutate source/proxy player state."""
import os
import tempfile

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
import streamclipper.gui as gui
from streamclipper.models import VideoInfo
from streamclipper.render_contract import RenderRequest
from streamclipper.rendered_preview import RenderedPreview


def test_new_render_button_stays_in_export_tab_and_works_without_analysis(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = gui.MainWindow()
    try:
        labels = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert labels == ["Highlights", "Untertitel", "KI & Modelle", "Spuren", "Export"]
        assert not window.render_preview_button.isEnabled()
        source = tmp_path / "source.mkv"
        source.write_bytes(b"unchanged")
        window.source = str(source)
        window._video_info = VideoInfo(str(source), 3600, 1920, 1080, 60, True)
        window._source_duration = 3600
        window.timeline.set_duration(3600)
        window.timeline.set_selection(1800, 1840)
        window._busy(False)
        assert window.render_preview_button.isEnabled()
        started = []
        monkeypatch.setattr(gui.RenderPreviewThread, "start", lambda self: started.append(self))
        player_source = window.player.source()
        window.start_render_preview()
        assert len(started) == 1
        request = started[0].request
        assert request.video.path == str(source)
        assert (request.start, request.end) == (1800, 1840)
        assert request.mode == window.mode.currentData()
        assert not request.burn_subtitles
        assert window.progress.value() == 0
        assert window.cancel_button.isEnabled()
        assert not window.render_preview_button.isEnabled()
        assert window.player.source() == player_source
        window.cancel_job()
        assert started[0]._cancelled.is_set()
        assert source.read_bytes() == b"unchanged"
        window.worker = None
        window._busy(False)
        assert window.render_preview_button.isEnabled()
    finally:
        window.worker = None
        window._autosave_timer.stop()
        window.close()
        app.processEvents()


def test_rendered_preview_uses_separate_player_and_cleans_temp_files(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "game.mkv"
    source.write_bytes(b"original")
    original = gui.QMediaPlayer()
    temp = tempfile.TemporaryDirectory(dir=tmp_path)
    output = gui.Path(temp.name) / "sample.mp4"
    output.write_bytes(b"test-only")
    info = VideoInfo(str(source), 600, 320, 180, 30, False)
    request = RenderRequest(info, 120, 125, "crop")
    result = RenderedPreview(output, request, False)
    dialog = gui.RenderedClipDialog(result, temp)
    try:
        assert dialog.player is not original
        assert dialog.scope_label.text().find("120") == -1  # hh:mm:ss formatting
        assert "00:02:00" in dialog.scope_label.text()
        assert dialog.player.source().toLocalFile() == str(output)
    finally:
        dialog.close()
        app.processEvents()
        original.deleteLater()
    assert source.read_bytes() == b"original"
    assert not output.exists()


def test_rendered_preview_excerpt_label_is_truthful(tmp_path):
    app = QApplication.instance() or QApplication([])
    info = VideoInfo(str(tmp_path / "source.mp4"), 200, 320, 180, 30, False)
    temp = tempfile.TemporaryDirectory(dir=tmp_path)
    mp4 = gui.Path(temp.name) / "short.mp4"
    mp4.write_bytes(b"dummy")
    rendered = RenderedPreview(mp4, RenderRequest(info, 50, 70, "crop"), True)
    viewer = gui.RenderedClipDialog(rendered, temp)
    try:
        assert "erste 20 Sekunden" in viewer.scope_label.text()
    finally:
        viewer.close()
        app.processEvents()
