"""Qt smoke: optional HF token UI, auth, progress, cancellation (no network)."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox
from streamclipper.gui import MainWindow, ModelDownloadThread
import streamclipper.gui as gui


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        yield w
    finally:
        w.model_worker = None
        w.hf_check_worker = None
        w._autosave_timer.stop()
        w.close()
        app.processEvents()


def test_hf_session_token_never_saved_as_plaintext(window, monkeypatch):
    assert window.hf_token_input.echoMode() == QLineEdit.EchoMode.Password
    window.hf_token_input.setText("hf_test_only_session")
    assert window._apply_hf_token()
    assert window.hf_token_input.text() == ""
    assert window._active_hf_token() == "hf_test_only_session"
    assert "hf_test_only_session" not in window.hf_status.text()
    window._remove_hf_token()
    assert window._hf_session_token is None
    assert window.hf_token_input.text() == ""


def test_windows_persist_opt_in_never_calls_store_without_checkbox(window, monkeypatch):
    saved = []
    monkeypatch.setattr(gui, "save_hf_credential", lambda value: saved.append(value))
    monkeypatch.setattr(gui, "read_hf_credential", lambda: None)
    window.hf_token_input.setText("hf_test_notsaved")
    assert window._apply_hf_token()
    assert saved == []
    window.hf_persist_token.setEnabled(True)
    window.hf_persist_token.setChecked(True)
    window.hf_token_input.setText("hf_test_saved")
    assert window._apply_hf_token()
    assert saved == ["hf_test_saved"]
    assert window.hf_token_input.text() == ""
    window.hf_persist_token.setChecked(False)


def test_progress_display_busy_bytes_99_and_validated_100(window):
    worker = ModelDownloadThread("clip-vit-large-patch14", window)
    window.model_worker = worker  # fake scheduled thread, do not run
    window._model_download_progress(worker, ("clip-vit-large-patch14", None, 0, None, "metadata"))
    assert window.progress.minimum() == 0 and window.progress.maximum() == 0
    window._model_download_progress(worker, ("clip-vit-large-patch14", 43, 430, 1000, "download"))
    assert window.progress.maximum() == 100
    assert window.progress.value() == 43
    assert "430 B" in window.progress.format()
    window._model_download_progress(worker, ("clip-vit-large-patch14", None, 430, 1000, "validation"))
    assert window.progress.maximum() == 0
    window._model_download_progress(worker, ("clip-vit-large-patch14", 100, 500, 1000, "complete"))
    assert window.progress.value() == 100
    window.model_worker = None


def test_download_without_token_allowed_and_model_cancel_routes_correctly(window, monkeypatch):
    monkeypatch.setattr(gui.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(gui.ModelDownloadThread, "start", lambda self: None)
    window._hf_session_token = None
    window.download_selected_model("vision")
    worker = window.model_worker
    assert worker is not None and worker.token is None
    assert window.progress.maximum() == 0
    assert window.cancel_button.isEnabled()
    window.cancel_job()
    assert worker._cancelled.is_set()
    window.model_worker = None
    window._busy(False)
