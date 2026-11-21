"""Windows desktop UI; analysis and export run off the UI thread."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSlider, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .analyze import analyze
from .media import CancelledError, export_clip, safe_destination, tool_path
from .models import AnalysisResult, Candidate


def display_time(seconds: float) -> str:
    amount = int(seconds)
    return f"{amount // 3600:02d}:{amount // 60 % 60:02d}:{amount % 60:02d}"


class AnalysisThread(QThread):
    progress_changed = Signal(int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, source: str, length: int, parent=None):
        super().__init__(parent)
        self.source = source
        self.length = length
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            result = analyze(self.source, clip_seconds=self.length,
                             progress=self.progress_changed.emit,
                             cancelled=self._cancelled.is_set)
            if self._cancelled.is_set():
                raise CancelledError("Analyse abgebrochen")
            self.done.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportThread(QThread):
    progress_changed = Signal(int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, analysis: AnalysisResult, items: list[Candidate], directory: str,
                 mode: str, parent=None):
        super().__init__(parent)
        self.analysis = analysis
        self.items = items
        self.directory = directory
        self.mode = mode
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            outputs: list[str] = []
            stem = Path(self.analysis.video.path).stem
            for i, clip in enumerate(self.items, start=1):
                if self._cancelled.is_set():
                    raise CancelledError("Export abgebrochen")
                target = safe_destination(self.directory, f"{stem}_clip_{i:02d}.mp4")
                export_clip(self.analysis.video, clip.start, clip.end, target,
                            self.mode, cancelled=self._cancelled.is_set)
                outputs.append(str(target))
                self.progress_changed.emit(round(i / len(self.items) * 100))
            self.done.emit(outputs)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StreamClipper – Gaming Highlights 0.1")
        self.resize(1200, 760)
        self.source: str | None = None
        self.analysis: AnalysisResult | None = None
        self.worker: AnalysisThread | ExportThread | None = None
        self.preview_end: float | None = None

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.65)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)

        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setSpacing(12)

        toolbar = QHBoxLayout()
        self.open_button = QPushButton("📂 Aufnahme öffnen")
        self.open_button.clicked.connect(self.open_video)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(QLabel("Cliplänge"))
        self.length = QSpinBox()
        self.length.setRange(10, 60)
        self.length.setValue(25)
        self.length.setSuffix(" s")
        toolbar.addWidget(self.length)
        self.analyze_button = QPushButton("Highlights analysieren")
        self.analyze_button.clicked.connect(self.start_analysis)
        self.analyze_button.setEnabled(False)
        toolbar.addWidget(self.analyze_button)
        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.clicked.connect(self.cancel_job)
        self.cancel_button.setEnabled(False)
        toolbar.addWidget(self.cancel_button)
        toolbar.addStretch()
        main.addLayout(toolbar)

        self.source_label = QLabel("Noch kein Video geladen. Videos bleiben lokal auf deinem Rechner.")
        self.source_label.setWordWrap(True)
        main.addWidget(self.source_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(320)
        self.player.setVideoOutput(self.video_widget)
        preview_layout.addWidget(self.video_widget, 1)
        playback = QHBoxLayout()
        self.play_button = QPushButton("▶ Wiedergabe / Pause")
        self.play_button.clicked.connect(self.toggle_play)
        playback.addWidget(self.play_button)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 1)
        self.seek.sliderMoved.connect(self.seek_to)
        playback.addWidget(self.seek, 1)
        self.time_label = QLabel("00:00:00")
        playback.addWidget(self.time_label)
        preview_layout.addLayout(playback)
        preview_layout.addWidget(QLabel(
            "Vorschau zeigt das Original; Ausgabe ist vertikal 1080 × 1920."
        ))
        splitter.addWidget(preview_container)

        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(QLabel("Automatisch gefundene Vorschläge (Audio-Heuristik)"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Start", "Ende", "Score", "Erkennungsgrund"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.preview_selected)
        results_layout.addWidget(self.table, 1)
        results_layout.addWidget(QLabel("Score = relative Lautstärkeauffälligkeit, keine Viralitätsprognose."))
        splitter.addWidget(results_container)
        splitter.setSizes([580, 620])
        main.addWidget(splitter, 1)

        actions = QHBoxLayout()
        actions.addWidget(QLabel("Bildformat"))
        self.mode = QComboBox()
        self.mode.addItem("Gameplay komplett, unscharfer Hintergrund", "blur")
        self.mode.addItem("Hochformat-Ausschnitt (Mitte)", "crop")
        actions.addWidget(self.mode)
        self.single_export = QPushButton("Ausgewählten Clip exportieren")
        self.single_export.clicked.connect(lambda: self.start_export(False))
        self.single_export.setEnabled(False)
        actions.addWidget(self.single_export)
        self.all_export = QPushButton("Alle Clips exportieren")
        self.all_export.clicked.connect(lambda: self.start_export(True))
        self.all_export.setEnabled(False)
        actions.addWidget(self.all_export)
        self.report_button = QPushButton("Analyse als JSON speichern")
        self.report_button.clicked.connect(self.save_report)
        self.report_button.setEnabled(False)
        actions.addWidget(self.report_button)
        main.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        main.addWidget(self.progress)
        self.statusBar().showMessage("Bereit")
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #151922; color: #edf2fa; font-size: 13px; }
            QPushButton { background: #26344a; border: 1px solid #41516a;
                          border-radius: 7px; padding: 9px 12px; }
            QPushButton:hover { background: #345070; }
            QPushButton:disabled { color: #8290a4; background: #202632; }
            QTableWidget, QSpinBox, QComboBox { background: #202938;
                 color: #edf2fa; border: 1px solid #3b4b61; border-radius: 5px; }
            QTableWidget::item:selected { background: #285e91; }
            QHeaderView::section { background: #293449; color: white;
                                    padding: 8px; border: 0; }
            QProgressBar { background: #202938; border-radius: 5px; height: 15px; }
            QProgressBar::chunk { background: #338dce; border-radius: 5px; }
        """)

    def _busy(self, busy: bool) -> None:
        self.open_button.setEnabled(not busy)
        self.analyze_button.setEnabled(bool(self.source) and not busy)
        self.cancel_button.setEnabled(busy)
        ready = self.analysis is not None and not busy
        self.single_export.setEnabled(ready and bool(self.table.selectedItems()))
        self.all_export.setEnabled(ready and bool(self.analysis.candidates if self.analysis else []))
        self.report_button.setEnabled(ready)

    def open_video(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Aufnahme öffnen", "",
            "Videos (*.mp4 *.mkv *.mov *.webm *.avi);;Alle Dateien (*)")
        if not source:
            return
        self.source = source
        self.analysis = None
        self.preview_end = None
        self.table.setRowCount(0)
        self.source_label.setText(source)
        self.player.setSource(QUrl.fromLocalFile(source))
        self.progress.setValue(0)
        self._busy(False)
        self.statusBar().showMessage("Aufnahme geladen – Analyse starten")

    def start_analysis(self) -> None:
        if not self.source:
            return
        try:
            tool_path("ffprobe")
            tool_path("ffmpeg")
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "FFmpeg fehlt", str(exc))
            return
        self.analysis = None
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.worker = AnalysisThread(self.source, self.length.value(), self)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.done.connect(self.analysis_finished)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(lambda: self._busy(False))
        self._busy(True)
        self.statusBar().showMessage("Audiospur wird lokal analysiert …")
        self.worker.start()

    def analysis_finished(self, result: AnalysisResult) -> None:
        self.analysis = result
        self.table.setRowCount(len(result.candidates))
        for row, clip in enumerate(result.candidates):
            for column, value in enumerate((display_time(clip.start), display_time(clip.end),
                                            str(clip.score), clip.reason)):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setForeground(QColor("#77c7ff"))
                self.table.setItem(row, column, item)
        if result.candidates:
            self.table.selectRow(0)
        self._busy(False)
        self.statusBar().showMessage(f"{len(result.candidates)} Clip-Vorschläge gefunden")

    def job_failed(self, message: str) -> None:
        self._busy(False)
        if "abgebrochen" in message.lower():
            self.statusBar().showMessage(message)
        else:
            QMessageBox.critical(self, "Verarbeitung fehlgeschlagen", message)
            self.statusBar().showMessage("Fehler – Details im Dialog")

    def selected_candidate(self) -> Candidate | None:
        if not self.analysis:
            return None
        row = self.table.currentRow()
        if 0 <= row < len(self.analysis.candidates):
            return self.analysis.candidates[row]
        return None

    def preview_selected(self) -> None:
        clip = self.selected_candidate()
        if not clip:
            self.single_export.setEnabled(False)
            return
        self.preview_end = clip.end
        self.player.pause()
        self.player.setPosition(round(clip.start * 1000))
        self.single_export.setEnabled(not bool(self.worker and self.worker.isRunning()))

    def toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _position_changed(self, pos: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        self.time_label.setText(display_time(pos / 1000))
        if self.preview_end is not None and pos >= int(self.preview_end * 1000):
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()

    def _duration_changed(self, duration: int) -> None:
        self.seek.setRange(0, max(1, duration))

    def seek_to(self, pos: int) -> None:
        self.preview_end = None  # manual scrubbing may leave suggested time span
        self.player.setPosition(pos)

    def start_export(self, all_clips: bool) -> None:
        if not self.analysis:
            return
        items = self.analysis.candidates if all_clips else [self.selected_candidate()]
        items = [item for item in items if item is not None]
        if not items:
            return
        directory = QFileDialog.getExistingDirectory(self, "Exportordner wählen")
        if not directory:
            return
        self.progress.setValue(0)
        self.worker = ExportThread(self.analysis, items, directory,
                                   str(self.mode.currentData()), self)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.done.connect(self.export_finished)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(lambda: self._busy(False))
        self._busy(True)
        self.statusBar().showMessage(f"Exportiere {len(items)} Clip(s) …")
        self.worker.start()

    def export_finished(self, outputs: list[str]) -> None:
        self._busy(False)
        self.statusBar().showMessage(f"{len(outputs)} MP4-Clip(s) erfolgreich exportiert")
        QMessageBox.information(self, "Export abgeschlossen",
            "Exportiert:\n" + "\n".join(outputs[:10]))

    def save_report(self) -> None:
        if not self.analysis:
            return
        default = str(Path(self.analysis.video.path).with_suffix(".highlights.json"))
        filename, _ = QFileDialog.getSaveFileName(self, "Analyse speichern", default,
                                                  "JSON (*.json)")
        if filename:
            self.analysis.save_json(filename)
            self.statusBar().showMessage("Analyse gespeichert: " + filename)

    def cancel_job(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.statusBar().showMessage("Abbruch angefordert …")

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Verarbeitung läuft",
                                    "Bitte laufenden Job zuerst abbrechen und abschließen lassen.")
            event.ignore()
            return
        self.player.stop()
        event.accept()


def main() -> None:
    application = QApplication(sys.argv)
    application.setApplicationName("StreamClipper")
    window = MainWindow()
    window.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
