"""Windows desktop UI; analysis and export run off the UI thread."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from .portable import configure_portable_environment

configure_portable_environment()

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSlider, QSpinBox, QDoubleSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .analyze import analyze
from .media import CancelledError, export_clip, probe_video, safe_destination, tool_path
from .models import AnalysisResult, Candidate
from .transcript_editor import edit_segment, format_timestamp, load_analysis_report
from .semantic import default_models_directory
from .transcript import save_transcript


def display_time(seconds: float) -> str:
    amount = int(seconds)
    return f"{amount // 3600:02d}:{amount // 60 % 60:02d}:{amount % 60:02d}"


class AnalysisThread(QThread):
    progress_changed = Signal(int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, source: str, length: int, parent=None,
                 speech_model: str | None = None, vision_model: str | None = None):
        super().__init__(parent)
        self.source = source
        self.length = length
        self.speech_model = speech_model
        self.vision_model = vision_model
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            result = analyze(self.source, clip_seconds=self.length,
                             progress=self.progress_changed.emit,
                             cancelled=self._cancelled.is_set,
                             speech_model=self.speech_model,
                             vision_model=self.vision_model)
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
                 mode: str, parent=None, burn_subtitles: bool = False,
                 subtitle_offset: float = 0.0):
        super().__init__(parent)
        self.analysis = analysis
        self.items = items
        self.directory = directory
        self.mode = mode
        self.burn_subtitles = burn_subtitles
        self.subtitle_offset = subtitle_offset
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
                actual = export_clip(
                    self.analysis.video, clip.start, clip.end, target,
                    self.mode, cancelled=self._cancelled.is_set,
                    transcript=self.analysis.transcript,
                    burn_subtitles=self.burn_subtitles,
                    subtitle_offset=self.subtitle_offset,
                    progress=lambda value, i=i: self.progress_changed.emit(
                        round(((i - 1) + value / 100) / len(self.items) * 100)
                    ),
                )
                outputs.append(str(actual))
            self.done.emit(outputs)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StreamClipper – Gaming Highlights 0.4 (experimentell)")
        self.resize(1200, 760)
        self.source: str | None = None
        self.analysis: AnalysisResult | None = None
        self.worker: AnalysisThread | ExportThread | None = None
        self.preview_end: float | None = None
        self.transcript_dirty = False
        self.report_path: str | None = None

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

        models = QHBoxLayout()
        self.speech_enabled = QCheckBox("Sprache + Transkript (lokales Whisper)")
        models.addWidget(self.speech_enabled)
        self.speech_path = QLineEdit()
        self.speech_path.setPlaceholderText("Whisper-Modellordner")
        speech_default = default_models_directory() / "whisper-small"
        if speech_default.is_dir():
            self.speech_path.setText(str(speech_default))
            self.speech_enabled.setChecked(True)
        models.addWidget(self.speech_path, 2)
        speech_browse = QPushButton("…")
        speech_browse.clicked.connect(lambda: self.choose_model(self.speech_path))
        models.addWidget(speech_browse)
        self.vision_enabled = QCheckBox("Spielbilder (lokales CLIP)")
        models.addWidget(self.vision_enabled)
        self.vision_path = QLineEdit()
        self.vision_path.setPlaceholderText("CLIP-Modellordner")
        vision_default = default_models_directory() / "clip-vit-base-patch32"
        if vision_default.is_dir():
            self.vision_path.setText(str(vision_default))
        models.addWidget(self.vision_path, 2)
        vision_browse = QPushButton("…")
        vision_browse.clicked.connect(lambda: self.choose_model(self.vision_path))
        models.addWidget(vision_browse)
        main.addLayout(models)

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
            "Vorschau zeigt das Original; Ausgabeformat und Untertitel wirken erst beim Export."
        ))
        splitter.addWidget(preview_container)

        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        results_layout.addWidget(self.tabs, 1)
        highlights_tab = QWidget()
        highlights_layout = QVBoxLayout(highlights_tab)
        highlights_layout.addWidget(QLabel("Highlight-Vorschläge (Audio / Sprache / Spielbilder)"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Start", "Ende", "Score", "Erkennungsgrund"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.preview_selected)
        highlights_layout.addWidget(self.table, 1)
        highlights_layout.addWidget(QLabel("Score = nicht kalibrierte Evidenz-Heuristik, keine Viralitätsprognose."))
        self.tabs.addTab(highlights_tab, "Highlights")
        transcript_tab = QWidget()
        transcript_layout = QVBoxLayout(transcript_tab)
        transcript_layout.addWidget(QLabel(
            "Whisper-Korrektur: Doppelklick bearbeitet Text oder Zeit (HH:MM:SS.mmm). "
            "Zeile auswählen, um zur Stelle zu springen."))
        self.transcript_table = QTableWidget(0, 3)
        self.transcript_table.setHorizontalHeaderLabels(["Start", "Ende", "Erkannter Text"])
        self.transcript_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.transcript_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.transcript_table.horizontalHeader().setStretchLastSection(True)
        self.transcript_table.verticalHeader().hide()
        self.transcript_table.itemSelectionChanged.connect(self.jump_selected_transcript)
        self.transcript_table.itemChanged.connect(self.transcript_item_changed)
        transcript_layout.addWidget(self.transcript_table)
        transcript_actions = QHBoxLayout()
        self.transcript_jump_button = QPushButton("Zur Stelle springen")
        self.transcript_jump_button.clicked.connect(self.jump_selected_transcript)
        transcript_actions.addWidget(self.transcript_jump_button)
        transcript_actions.addWidget(QLabel("Änderungen wirken sofort auf den nächsten Export."))
        transcript_actions.addStretch()
        transcript_layout.addLayout(transcript_actions)
        self.tabs.addTab(transcript_tab, "Transkript")
        splitter.addWidget(results_container)
        splitter.setSizes([580, 620])
        main.addWidget(splitter, 1)

        actions = QHBoxLayout()
        actions.addWidget(QLabel("Exportformat"))
        self.mode = QComboBox()
        self.mode.addItem("16:9 – dynamische Kamera (sanfter Zoom)", "smart16")
        self.mode.addItem("9:16 – dynamischer Ausschnitt für TikTok", "smart9")
        self.mode.addItem("9:16 – ganzes Bild / unscharfer Hintergrund", "blur")
        self.mode.addItem("9:16 – fester Mittel-Ausschnitt", "crop")
        actions.addWidget(self.mode)
        self.burn_subtitles = QCheckBox("Untertitel direkt ins Video")
        self.burn_subtitles.setChecked(True)
        self.burn_subtitles.setToolTip("Benötigt eine durch Whisper transkribierte Aufnahme.")
        actions.addWidget(self.burn_subtitles)
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
        self.load_report_button = QPushButton("Analyse laden (JSON)")
        self.load_report_button.clicked.connect(self.load_report)
        self.load_report_button.setEnabled(False)
        actions.addWidget(self.load_report_button)
        self.transcript_button = QPushButton("Transkript speichern (SRT/TXT/VTT)")
        self.transcript_button.clicked.connect(self.save_transcript_dialog)
        self.transcript_button.setEnabled(False)
        actions.addWidget(self.transcript_button)
        main.addLayout(actions)

        caption_options = QHBoxLayout()
        caption_options.addWidget(QLabel("Untertitelversatz"))
        self.caption_offset = QDoubleSpinBox()
        self.caption_offset.setRange(-3.0, 3.0)
        self.caption_offset.setDecimals(1)
        self.caption_offset.setSingleStep(0.1)
        self.caption_offset.setValue(0.4)
        self.caption_offset.setSuffix(" s")
        self.caption_offset.setToolTip("Positive Werte: Untertitel erscheinen später. Negative: früher.")
        caption_options.addWidget(self.caption_offset)
        caption_options.addWidget(QLabel("+ = später, − = früher · ohne erneute Transkription"))
        caption_options.addStretch()
        main.addLayout(caption_options)

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
        self.load_report_button.setEnabled(bool(self.source) and not busy)
        self.transcript_jump_button.setEnabled(ready and bool(self.analysis.transcript if self.analysis else []))
        self.transcript_table.setEnabled(not busy)
        self.transcript_button.setEnabled(ready and bool(self.analysis.transcript if self.analysis else []))
        self.burn_subtitles.setEnabled(ready and bool(self.analysis.transcript if self.analysis else []))
        self.caption_offset.setEnabled(ready and bool(self.analysis.transcript if self.analysis else []))

    def open_video(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Aufnahme öffnen", "",
            "Videos (*.mp4 *.mkv *.mov *.webm *.avi);;Alle Dateien (*)")
        if not source or not self.confirm_discard_edits():
            return
        self.source = source
        self.transcript_dirty = False
        self.report_path = None
        self.analysis = None
        self.preview_end = None
        self.table.setRowCount(0)
        self.transcript_table.setRowCount(0)
        self.tabs.setCurrentIndex(0)
        self.source_label.setText(source)
        self.player.setSource(QUrl.fromLocalFile(source))
        self.progress.setValue(0)
        self._busy(False)
        self.statusBar().showMessage("Aufnahme geladen – Analyse starten")

    def choose_model(self, target: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Lokales Modellverzeichnis auswählen")
        if directory:
            target.setText(directory)

    def start_analysis(self) -> None:
        if not self.source or not self.confirm_discard_edits():
            return
        try:
            tool_path("ffprobe")
            tool_path("ffmpeg")
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "FFmpeg fehlt", str(exc))
            return
        speech = self.speech_path.text().strip() if self.speech_enabled.isChecked() else None
        vision = self.vision_path.text().strip() if self.vision_enabled.isChecked() else None
        if (self.speech_enabled.isChecked() and not speech) or (self.vision_enabled.isChecked() and not vision):
            QMessageBox.warning(self, "Modellordner fehlt",
                                "Für ausgewählte KI-Detektoren bitte einen lokalen Modellordner angeben.")
            return
        self.analysis = None
        self.transcript_dirty = False
        self.report_path = None
        self.table.setRowCount(0)
        self.transcript_table.setRowCount(0)
        self.progress.setValue(0)
        self.worker = AnalysisThread(self.source, self.length.value(), self,
                                     speech_model=speech, vision_model=vision)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.done.connect(self.analysis_finished)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(lambda: self._busy(False))
        self._busy(True)
        self.statusBar().showMessage("Analyse läuft lokal (Audio / optionale Modelle) …")
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
        self.transcript_table.blockSignals(True)
        try:
            self.transcript_table.setRowCount(len(result.transcript))
            for row, segment in enumerate(result.transcript):
                for column, value in enumerate((format_timestamp(segment.start),
                                                format_timestamp(segment.end), segment.text)):
                    self.transcript_table.setItem(row, column, QTableWidgetItem(value))
        finally:
            self.transcript_table.blockSignals(False)
        self.transcript_dirty = False
        self._busy(False)
        self.statusBar().showMessage(
            f"{len(result.candidates)} Clips, {len(result.transcript)} Transkript-Abschnitte")

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

    def jump_selected_transcript(self) -> None:
        self.jump_to_transcript(self.transcript_table.currentRow(), 0)

    def transcript_item_changed(self, item: QTableWidgetItem) -> None:
        if not self.analysis:
            return
        row, column = item.row(), item.column()
        if not 0 <= row < len(self.analysis.transcript):
            return
        old = self.analysis.transcript[row]
        original = (format_timestamp(old.start), format_timestamp(old.end), old.text)[column]
        try:
            updated = edit_segment(self.analysis, row, column, item.text())
        except ValueError as exc:
            self.transcript_table.blockSignals(True)
            try:
                item.setText(original)
            finally:
                self.transcript_table.blockSignals(False)
            QMessageBox.warning(self, "Ungültige Transkriptkorrektur", str(exc))
            return
        if updated.transcript[row] == old:
            return
        self.analysis = updated
        current = updated.transcript[row]
        canonical = (format_timestamp(current.start), format_timestamp(current.end), current.text)[column]
        if item.text() != canonical:
            self.transcript_table.blockSignals(True)
            try:
                item.setText(canonical)
            finally:
                self.transcript_table.blockSignals(False)
        self.transcript_dirty = True
        self.statusBar().showMessage(
            "Transkript korrigiert – bitte Analyse als JSON speichern; "
            "neuer Export verwendet die Korrektur")

    def jump_to_transcript(self, row: int, _column: int) -> None:
        if not self.analysis or row < 0 or row >= len(self.analysis.transcript):
            return
        self.preview_end = None
        self.player.pause()
        self.player.setPosition(round(self.analysis.transcript[row].start * 1000))

    def save_transcript_dialog(self) -> None:
        if not self.analysis or not self.analysis.transcript:
            return
        default = str(Path(self.analysis.video.path).with_suffix(".transkript.srt"))
        destination, _ = QFileDialog.getSaveFileName(
            self, "Transkript exportieren", default,
            "SubRip (*.srt);;WebVTT (*.vtt);;Text (*.txt)")
        if not destination:
            return
        try:
            target = save_transcript(self.analysis.transcript, destination)
        except (FileExistsError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Transkript konnte nicht gespeichert werden", str(exc))
            return
        self.statusBar().showMessage("Transkript gespeichert: " + str(target))

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
                                   str(self.mode.currentData()), self,
                                   burn_subtitles=self.burn_subtitles.isChecked()
                                   and bool(self.analysis.transcript),
                                   subtitle_offset=self.caption_offset.value())
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

    def save_report(self) -> bool:
        if not self.analysis:
            return False
        default = self.report_path or str(Path(self.analysis.video.path).with_suffix(".highlights.json"))
        filename, _ = QFileDialog.getSaveFileName(self, "Analyse speichern", default,
                                                  "JSON (*.json)")
        if not filename:
            return False
        try:
            self.analysis.save_json(filename)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Analyse nicht gespeichert", str(exc))
            return False
        self.report_path = filename
        self.transcript_dirty = False
        self.statusBar().showMessage("Korrigierte Analyse gespeichert: " + filename)
        return True

    def confirm_discard_edits(self) -> bool:
        if not self.transcript_dirty:
            return True
        answer = QMessageBox.question(
            self, "Ungespeicherte Transkriptkorrekturen",
            "Deine Korrekturen sind noch nicht gespeichert. Jetzt als Analyse-JSON speichern?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_report()
        return answer == QMessageBox.StandardButton.Discard

    def load_report(self) -> None:
        if not self.source:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Korrigierte Analyse öffnen", str(Path(self.source).parent),
            "Analyse-Bericht (*.json)")
        if not filename or not self.confirm_discard_edits():
            return
        try:
            result = load_analysis_report(filename, self.source)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Analyse konnte nicht geladen werden", str(exc))
            return
        try:
            actual = probe_video(self.source)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Video kann nicht geprüft werden", str(exc))
            return
        if (abs(actual.duration - result.video.duration) > 0.25
                or (actual.width, actual.height) != (result.video.width, result.video.height)):
            QMessageBox.warning(self, "Video stimmt nicht überein",
                                "Die Aufnahme am gespeicherten Pfad hat eine andere Dauer oder Auflösung.")
            return
        self.analysis_finished(result)
        self.report_path = filename
        self.statusBar().showMessage("Analyse mit Transkript geladen – ohne Whisper-Neuanalyse")

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
        if not self.confirm_discard_edits():
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
