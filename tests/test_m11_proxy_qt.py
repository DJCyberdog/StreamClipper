"""M11c-4 Qt offscreen preview source mapping, selection and busy guards."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
import streamclipper.gui as gui
from streamclipper.models import VideoInfo
from streamclipper.proxy import ProxyState, ProxyTiming


def test_proxy_controls_source_time_and_transcript_seek(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    src = tmp_path / "gaming.mkv"
    src.write_bytes(b"original bytes")
    info = VideoInfo(str(src), 300, 1920, 1080, 60, False)
    window = gui.MainWindow()
    try:
        assert window.proxy_mode.count() == 2
        assert not window.proxy_create.isEnabled()
        window.source = str(src)
        window._source_duration = 300
        window._video_info = info
        window.timeline.set_duration(300)
        window._duration_changed(300000)
        window._update_proxy_controls()
        assert window.proxy_create.isEnabled()
        assert not window.proxy_mode.isEnabled()
        proxy_file = tmp_path / "fake.mp4"
        proxy_file.write_bytes(b"mocked verified media")
        state = ProxyState(proxy_file, ProxyTiming(300, 300.02, .070, 0.0), "test-key")
        monkeypatch.setattr(gui, "cached_proxy", lambda _: state)
        window._proxy_ready(str(src), state)
        assert window.proxy_progress.value() == 100
        assert window.proxy_mode.isEnabled()
        assert not window.proxy_create.isEnabled()
        window._proxy_active = True
        assert window._media_position_ms(120000) == 119930
        window._position_changed(119930)
        assert window.seek.value() == 120000
        assert window.time_label.text() == "00:02:00"
        assert window.seek.maximum() == 300000
        window._busy(True)
        assert not window.proxy_mode.isEnabled()
        assert not window.proxy_create.isEnabled()
        window._busy(False)
        assert window.proxy_mode.isEnabled()
        assert src.read_bytes() == b"original bytes"
    finally:
        window._proxy_active = False
        window._autosave_timer.stop()
        window.close()
        app.processEvents()


def test_stale_proxy_worker_result_ignored(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = gui.MainWindow()
    try:
        source = tmp_path / "this.mkv"
        source.write_bytes(b"video")
        window.source = str(source)
        window._video_info = VideoInfo(str(source), 30, 1920, 1080, 30, False)
        other = ProxyState(tmp_path / "other.mp4", ProxyTiming(30, 30, 0, 0), "other")
        window._proxy_ready("another-video.mkv", other)
        assert window._proxy_state is None
        assert window.proxy_progress.value() == 0
        assert source.read_bytes() == b"video"
    finally:
        window._autosave_timer.stop()
        window.close()
        app.processEvents()
