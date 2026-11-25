"""Deterministic Qt lifetime in desktop tests; never suppress native exit errors."""
import gc
import os
import pytest


@pytest.fixture(scope="session")
def qt_session_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication, QEvent
    import shiboken6
    app = QApplication.instance() or QApplication([])
    yield app
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    # Destroy the application explicitly while Python and Qt modules are
    # alive, rather than leaving destruction to arbitrary interpreter order.
    if shiboken6.isValid(app):
        shiboken6.delete(app)


@pytest.fixture(autouse=True)
def release_qt_test_objects(request):
    if not request.node.path.name.endswith("_qt.py"):
        yield
        return
    pytest.importorskip("PySide6")
    app = request.getfixturevalue("qt_session_app")
    from PySide6.QtCore import QCoreApplication, QEvent, QThread, QUrl
    from PySide6.QtMultimedia import QMediaPlayer
    import shiboken6
    yield
    # Tests exercise actual widgets and native multimedia objects; tear them
    # down between cases. Do not force-delete any running worker.
    for widget in list(app.topLevelWidgets()):
        if not shiboken6.isValid(widget):
            continue
        assert not any(t.isRunning() for t in widget.findChildren(QThread)), "Qt test leaked a running worker"
        for player in widget.findChildren(QMediaPlayer):
            if shiboken6.isValid(player):
                player.stop()
                player.setSource(QUrl())
                player.setVideoOutput(None)
                player.setAudioOutput(None)
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
