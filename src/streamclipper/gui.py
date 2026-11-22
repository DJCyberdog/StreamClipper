"""Windows desktop UI; analysis and export run off the UI thread."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from .portable import configure_portable_environment

configure_portable_environment()

from PySide6.QtCore import QEvent, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSlider, QSpinBox,
    QInputDialog,
    QDoubleSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from .analyze import analyze
from .media import CancelledError, export_clip, probe_video, safe_destination, tool_path, waveform_peaks
from .model_checks import validate_clip_model
from .models import AnalysisResult, Candidate
from .manual_highlights import add_manual_highlight, remove_manual_highlight, trim_manual_highlight
from .twitch_import import download_twitch_vod, parse_twitch_vod_url
from .portable import installation_directory
from .transcript_editor import (apply_segment_changes, format_timestamp,
                                load_analysis_report, parse_timestamp)
from .semantic import default_models_directory
from .transcript import save_transcript
from .timeline import caption_at_time
from .timeline_widget import TimelineWidget
from .word_editor import edit_word, effective_words, words_in_clip
from .captioning import subtitle_text_at_time


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


class TwitchImportThread(QThread):
    progress_changed = Signal(int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, directory: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.directory = directory
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            output = download_twitch_vod(
                self.url, self.directory, progress=self.progress_changed.emit,
                cancelled=self._cancelled.is_set)
            self.done.emit(str(output))
        except Exception as exc:
            self.failed.emit(str(exc))


class WaveformThread(QThread):
    """Decode the audio overview in the background, without Whisper."""
    done = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.filename = filename
        self._cancelled = threading.Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        try:
            video = probe_video(self.filename)
            peaks = waveform_peaks(video, cancelled=self._cancelled.is_set)
            if not self._cancelled.is_set():
                self.done.emit(self.filename, (video, peaks))
        except CancelledError:
            pass
        except (OSError, ValueError, RuntimeError) as exc:
            self.failed.emit(self.filename, str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StreamClipper – Timeline M6 (experimentell)")
        self.resize(1440, 920)
        self.source: str | None = None
        self.analysis: AnalysisResult | None = None
        self.worker: AnalysisThread | ExportThread | TwitchImportThread | None = None
        self.preview_end: float | None = None
        self.transcript_dirty = False
        self.report_path: str | None = None
        self._editor_row: int | None = None
        self._manual_from: float | None = None
        self._manual_to: float | None = None
        self._manual_pending: list[Candidate] = []
        self._waveform_workers: list[WaveformThread] = []
        self._source_duration: float = 0.0
        self._active_caption: str | None = None
        self._word_ref: tuple[int, int] | None = None
        self._word_refs: list[tuple[int, int]] = []
        self._last_timeline_range: tuple[float, float] = (0.0, 25.0)

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
        self.twitch_button = QPushButton("🌐 Twitch-VOD importieren")
        self.twitch_button.clicked.connect(self.import_twitch_video)
        self.twitch_button.setToolTip("Öffentliche Twitch-Aufnahme per Video-URL herunterladen und laden")
        toolbar.addWidget(self.twitch_button)
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
        self.video_widget.setMinimumHeight(290)
        self.player.setVideoOutput(self.video_widget)
        self.caption_overlay = QLabel(self.video_widget)
        self.caption_overlay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.caption_overlay.setWordWrap(True)
        self.caption_overlay.setStyleSheet(
            "color: white; background-color: rgba(0,0,0,165); font-size: 19px; "
            "font-weight: bold; border-radius: 5px; padding: 7px;")
        self.caption_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.caption_overlay.hide()
        self.video_widget.installEventFilter(self)
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
            "Vorschau: Originalvideo + zeitlich passende Untertitel. "
            "Dynamischer 16:9/9:16-Bildausschnitt erst im Export."
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
        manual_actions = QHBoxLayout()
        self.manual_quick = QPushButton("★ Highlight ab hier")
        self.manual_quick.setToolTip("Erstellt ab der aktuellen Videoposition einen Clip in gewählter Länge – ohne KI")
        self.manual_quick.clicked.connect(self.add_quick_highlight)
        manual_actions.addWidget(self.manual_quick)
        self.manual_mark_start = QPushButton("[ Start setzen")
        self.manual_mark_start.clicked.connect(self.mark_highlight_start)
        manual_actions.addWidget(self.manual_mark_start)
        self.manual_mark_end = QPushButton("Ende setzen ]")
        self.manual_mark_end.clicked.connect(self.mark_highlight_end)
        manual_actions.addWidget(self.manual_mark_end)
        self.manual_create = QPushButton("Bereich hinzufügen")
        self.manual_create.clicked.connect(self.add_marked_highlight)
        manual_actions.addWidget(self.manual_create)
        highlights_layout.addLayout(manual_actions)
        manual_bottom = QHBoxLayout()
        self.manual_label = QLineEdit()
        self.manual_label.setMaxLength(100)
        self.manual_label.setPlaceholderText("Optionaler Name, z. B. 'LKW-Unfall'")
        manual_bottom.addWidget(self.manual_label, 1)
        self.manual_marks_label = QLabel("Start/Ende noch nicht gesetzt")
        manual_bottom.addWidget(self.manual_marks_label)
        self.manual_delete = QPushButton("Manuelles Highlight entfernen")
        self.manual_delete.clicked.connect(self.delete_selected_manual_highlight)
        manual_bottom.addWidget(self.manual_delete)
        highlights_layout.addLayout(manual_bottom)
        highlights_layout.addWidget(QLabel(
            "Manuelle Highlights benötigen keine KI. Änderungen im Analyseprojekt speichern."))
        highlights_layout.addWidget(QLabel("Score = nicht kalibrierte Evidenz-Heuristik, keine Viralitätsprognose."))
        self.tabs.addTab(highlights_tab, "Highlights")
        transcript_tab = QWidget()
        transcript_layout = QVBoxLayout(transcript_tab)
        transcript_layout.addWidget(QLabel(
            "1. Untertitel anklicken  ·  2. Text oder Zeiten ändern  ·  "
            "3. Übernehmen und Projekt speichern"))
        self.transcript_table = QTableWidget(0, 3)
        self.transcript_table.setHorizontalHeaderLabels(["Beginn", "Ende", "Whisper-Text"])
        self.transcript_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.transcript_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.transcript_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.transcript_table.horizontalHeader().setStretchLastSection(True)
        self.transcript_table.verticalHeader().hide()
        self.transcript_table.itemSelectionChanged.connect(self.transcript_selection_changed)
        self.transcript_table.setToolTip("Zeile anklicken: Video springt an diese Stelle")
        transcript_layout.addWidget(self.transcript_table, 1)

        transcript_nav = QHBoxLayout()
        self.transcript_prev = QPushButton("◀ Vorheriger")
        self.transcript_prev.clicked.connect(lambda: self.navigate_transcript(-1))
        transcript_nav.addWidget(self.transcript_prev)
        self.transcript_next = QPushButton("Nächster ▶")
        self.transcript_next.clicked.connect(lambda: self.navigate_transcript(1))
        transcript_nav.addWidget(self.transcript_next)
        self.transcript_play = QPushButton("▶ Stelle anhören")
        self.transcript_play.clicked.connect(self.play_transcript_segment)
        transcript_nav.addWidget(self.transcript_play)
        self.transcript_from_highlight = QPushButton("Zum markierten Highlight")
        self.transcript_from_highlight.clicked.connect(self.jump_to_highlight_transcript)
        self.transcript_from_highlight.setToolTip(
            "Sucht den ersten Transkriptabschnitt zum markierten Highlight")
        transcript_nav.addWidget(self.transcript_from_highlight)
        transcript_layout.addLayout(transcript_nav)

        transcript_layout.addWidget(QLabel("Gesprochenen Text korrigieren"))
        self.transcript_edit_text = QPlainTextEdit()
        self.transcript_edit_text.setPlaceholderText("Untertitelzeile auswählen …")
        self.transcript_edit_text.setMinimumHeight(75)
        self.transcript_edit_text.setMaximumHeight(110)
        self.transcript_edit_text.textChanged.connect(self.transcript_pending_changed)
        transcript_layout.addWidget(self.transcript_edit_text)

        timing = QHBoxLayout()
        self.transcript_edit_start = QLineEdit()
        self.transcript_edit_end = QLineEdit()
        for title, field, column in (("Beginn", self.transcript_edit_start, 0),
                                      ("Ende", self.transcript_edit_end, 1)):
            timing.addWidget(QLabel(title))
            field.setPlaceholderText("hh:mm:ss.mmm")
            field.setToolTip("Zeitgenau bis zu einer Millisekunde; Beispiel 00:01:23.450")
            field.setMinimumWidth(118)
            field.textChanged.connect(self.transcript_pending_changed)
            timing.addWidget(field, 1)
            back = QPushButton("−0,1")
            back.setToolTip(f"{title} um 0,1 Sekunden früher")
            back.clicked.connect(lambda _=False, col=column: self.nudge_transcript(col, -0.1))
            timing.addWidget(back)
            forward = QPushButton("+0,1")
            forward.setToolTip(f"{title} um 0,1 Sekunden später")
            forward.clicked.connect(lambda _=False, col=column: self.nudge_transcript(col, 0.1))
            timing.addWidget(forward)
        transcript_layout.addLayout(timing)

        editor_actions = QHBoxLayout()
        self.transcript_apply = QPushButton("✓ Korrektur übernehmen")
        self.transcript_apply.setToolTip("Korrektur übernehmen (Strg+Enter)")
        self.transcript_apply.clicked.connect(self.apply_transcript_editor)
        editor_actions.addWidget(self.transcript_apply)
        self.transcript_reset = QPushButton("Änderungen verwerfen")
        self.transcript_reset.clicked.connect(self.reset_transcript_editor)
        editor_actions.addWidget(self.transcript_reset)
        self.transcript_save = QPushButton("💾 Projekt speichern")
        self.transcript_save.clicked.connect(self.save_report)
        self.transcript_save.setToolTip("Korrigiertes Transkript als Analyse-JSON sichern (Strg+S)")
        editor_actions.addWidget(self.transcript_save)
        transcript_layout.addLayout(editor_actions)
        self.transcript_editor_hint = QLabel("Nach der Analyse hier eine Zeile auswählen.")
        self.transcript_editor_hint.setWordWrap(True)
        transcript_layout.addWidget(self.transcript_editor_hint)
        self.tabs.addTab(transcript_tab, "Transkript bearbeiten")
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply_transcript_editor)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_report)
        splitter.addWidget(results_container)
        splitter.setSizes([580, 620])
        main.addWidget(splitter, 1)

        # M6: zoomable waveform editing. Waveform is decoded on a background
        # thread and has a fixed upper bound independent of VOD duration.
        timeline_header = QHBoxLayout()
        timeline_header.addWidget(QLabel("TIMELINE · Audio / Highlights / Untertitel"))
        timeline_header.addStretch()
        timeline_header.addWidget(QLabel("Zoom"))
        self.timeline_zoom = QComboBox()
        for label, amount in (("Gesamt", 1), ("5×", 5), ("15×", 15),
                              ("30×", 30), ("60×", 60), ("120×", 120),
                              ("360×", 360), ("720×", 720),
                              ("1440×", 1440), ("2880×", 2880)):
            self.timeline_zoom.addItem(label, amount)
        self.timeline_zoom.currentIndexChanged.connect(self.change_timeline_zoom)
        timeline_header.addWidget(self.timeline_zoom)
        self.timeline_zoom_hint = QLabel("1×")
        timeline_header.addWidget(self.timeline_zoom_hint)
        self.timeline_status = QLabel("Keine Aufnahme geladen")
        timeline_header.addWidget(self.timeline_status)
        main.addLayout(timeline_header)

        self.timeline = TimelineWidget()
        self.timeline.playheadMoved.connect(self.timeline_seek)
        self.timeline.selectionChanged.connect(self.timeline_range_changed)
        self.timeline.subtitleSelected.connect(self.timeline_select_subtitle)
        self.timeline.wordSelected.connect(self.select_timeline_word)
        self.timeline.wordBoundaryCommitted.connect(self.commit_timeline_word_edge)
        main.addWidget(self.timeline)
        self.timeline_scroll = QSlider(Qt.Orientation.Horizontal)
        self.timeline_scroll.setMinimum(0)
        self.timeline_scroll.setMaximum(0)
        self.timeline_scroll.valueChanged.connect(self.timeline_scroll_changed)
        main.addWidget(self.timeline_scroll)

        # Integrated word editor: active highlight only, directly below the
        # waveform and word track. No separate transcription tab required.
        word_top = QHBoxLayout()
        word_top.addWidget(QLabel("WORTGENAUE UNTERTITEL · aktives Highlight"))
        self.word_hint = QLabel("Highlight wählen; Wörter erscheinen in der violetten Spur")
        word_top.addWidget(self.word_hint, 1)
        self.word_previous = QPushButton("◀ Wort")
        self.word_previous.clicked.connect(lambda: self.navigate_word(-1))
        word_top.addWidget(self.word_previous)
        self.word_next = QPushButton("Wort ▶")
        self.word_next.clicked.connect(lambda: self.navigate_word(1))
        word_top.addWidget(self.word_next)
        main.addLayout(word_top)
        word_controls = QHBoxLayout()
        self.word_text = QLineEdit()
        self.word_text.setPlaceholderText("Wort in der Timeline anklicken und hier korrigieren")
        self.word_text.setMaxLength(200)
        self.word_text.returnPressed.connect(self.apply_word_editor)
        word_controls.addWidget(self.word_text, 3)
        word_controls.addWidget(QLabel("Wortbeginn"))
        self.word_start = QDoubleSpinBox()
        self.word_start.setRange(0, 24 * 3600)
        self.word_start.setDecimals(3)
        self.word_start.setSingleStep(.05)
        self.word_start.setSuffix(" s")
        word_controls.addWidget(self.word_start)
        word_controls.addWidget(QLabel("Wortende"))
        self.word_end = QDoubleSpinBox()
        self.word_end.setRange(0, 24 * 3600)
        self.word_end.setDecimals(3)
        self.word_end.setSingleStep(.05)
        self.word_end.setSuffix(" s")
        word_controls.addWidget(self.word_end)
        self.word_preview = QPushButton("▶ Anhören")
        self.word_preview.clicked.connect(self.play_selected_word)
        word_controls.addWidget(self.word_preview)
        self.word_apply = QPushButton("✓ Wort übernehmen")
        self.word_apply.clicked.connect(self.apply_word_editor)
        word_controls.addWidget(self.word_apply)
        main.addLayout(word_controls)

        clip_tools = QHBoxLayout()
        clip_tools.addWidget(QLabel("IN"))
        self.timeline_in = QDoubleSpinBox()
        self.timeline_in.setDecimals(3)
        self.timeline_in.setSingleStep(.1)
        self.timeline_in.setSuffix(" s")
        self.timeline_in.setMaximum(24 * 3600)
        self.timeline_in.valueChanged.connect(self.timeline_fields_changed)
        clip_tools.addWidget(self.timeline_in)
        clip_tools.addWidget(QLabel("OUT"))
        self.timeline_out = QDoubleSpinBox()
        self.timeline_out.setDecimals(3)
        self.timeline_out.setSingleStep(.1)
        self.timeline_out.setSuffix(" s")
        self.timeline_out.setMaximum(24 * 3600)
        self.timeline_out.valueChanged.connect(self.timeline_fields_changed)
        clip_tools.addWidget(self.timeline_out)
        self.timeline_selection_label = QLabel("00:00:00.000 – 00:00:25.000")
        clip_tools.addWidget(self.timeline_selection_label)
        self.timeline_play = QPushButton("▶ Auswahl abspielen")
        self.timeline_play.clicked.connect(self.preview_timeline_selection)
        clip_tools.addWidget(self.timeline_play)
        self.timeline_add = QPushButton("★ Auswahl als Highlight")
        self.timeline_add.clicked.connect(self.add_timeline_highlight)
        clip_tools.addWidget(self.timeline_add)
        self.timeline_trim = QPushButton("✂ Markiertes Highlight trimmen")
        self.timeline_trim.clicked.connect(self.trim_timeline_highlight)
        clip_tools.addWidget(self.timeline_trim)
        clip_tools.addStretch()
        main.addLayout(clip_tools)

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
        self.caption_offset.setValue(0.0)
        self.caption_offset.setSuffix(" s")
        self.caption_offset.valueChanged.connect(self.caption_offset_changed)
        self.timeline.set_caption_offset(self.caption_offset.value())
        self.caption_offset.setToolTip("Positive Werte: Untertitel erscheinen später. Negative: früher.\nVorschau und Export verwenden denselben Versatz.")
        caption_options.addWidget(self.caption_offset)
        caption_options.addWidget(QLabel("+ = später, − = früher · ohne erneute Transkription"))
        caption_options.addStretch()
        main.addLayout(caption_options)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        main.addWidget(self.progress)
        self.statusBar().showMessage("Bereit")
        self._timeline_buttons = (self.timeline_in, self.timeline_out,
                                  self.timeline_play, self.timeline_add,
                                  self.timeline_trim, self.timeline_zoom,
                                  self.timeline_scroll)
        self._busy(False)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #151922; color: #edf2fa; font-size: 13px; }
            QPushButton { background: #26344a; border: 1px solid #41516a;
                          border-radius: 7px; padding: 9px 12px; }
            QPushButton:hover { background: #345070; }
            QPushButton:disabled { color: #8290a4; background: #202632; }
            QTableWidget, QSpinBox, QComboBox, QLineEdit, QPlainTextEdit { background: #202938;
                 color: #edf2fa; border: 1px solid #3b4b61; border-radius: 5px; }
            QTableWidget::item:selected { background: #285e91; }
            QHeaderView::section { background: #293449; color: white;
                                    padding: 8px; border: 0; }
            QProgressBar { background: #202938; border-radius: 5px; height: 15px; }
            QProgressBar::chunk { background: #338dce; border-radius: 5px; }
        """)

    def _busy(self, busy: bool) -> None:
        self.open_button.setEnabled(not busy)
        self.twitch_button.setEnabled(not busy)
        for control in self._timeline_buttons:
            control.setEnabled(bool(self.source) and not busy)
        clip = self.selected_candidate()
        self.timeline_trim.setEnabled(bool(self.source) and not busy
                                      and clip is not None and clip.origin == "manual")
        self.analyze_button.setEnabled(bool(self.source) and not busy)
        self.cancel_button.setEnabled(busy)
        ready = self.analysis is not None and not busy
        self.single_export.setEnabled(ready and bool(self.table.selectedItems()))
        self.all_export.setEnabled(ready and bool(self.analysis.candidates if self.analysis else []))
        self.report_button.setEnabled(ready)
        self.load_report_button.setEnabled(bool(self.source) and not busy)
        for button in (self.manual_quick, self.manual_mark_start, self.manual_mark_end,
                       self.manual_create):
            button.setEnabled(bool(self.source) and not busy)
        self.manual_delete.setEnabled(ready and bool(self.selected_candidate() and
                                         self.selected_candidate().origin == "manual"))
        editable = ready and bool(self.analysis.transcript if self.analysis else [])
        self.transcript_table.setEnabled(not busy)
        for control in (self.transcript_prev, self.transcript_next, self.transcript_play,
                        self.transcript_edit_text, self.transcript_edit_start,
                        self.transcript_edit_end, self.transcript_reset,
                        self.transcript_apply, self.transcript_save):
            control.setEnabled(editable)
        self.transcript_from_highlight.setEnabled(editable and bool(self.table.currentRow() >= 0))
        word_editable = editable and self._word_ref is not None
        for control in (self.word_text, self.word_start, self.word_end,
                        self.word_apply, self.word_preview):
            control.setEnabled(word_editable)
        self.word_previous.setEnabled(editable and bool(self._word_refs))
        self.word_next.setEnabled(editable and bool(self._word_refs))
        self.transcript_button.setEnabled(ready and bool(self.analysis.transcript if self.analysis else []))
        self.burn_subtitles.setEnabled(ready and bool(self.analysis.transcript if self.analysis else []))
        self.caption_offset.setEnabled(ready and bool(self.analysis.transcript if self.analysis else []))

    def open_video(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Aufnahme öffnen", "",
            "Videos (*.mp4 *.mkv *.mov *.webm *.avi);;Alle Dateien (*)")
        if source:
            self.load_video_source(source)

    def load_video_source(self, source: str) -> bool:
        if not self.confirm_discard_edits():
            return False
        for old in self._waveform_workers:
            old.cancel()
        self.source = source
        self._source_duration = 0.0
        self.caption_overlay.hide()
        self._active_caption = None
        self.transcript_dirty = False
        self.report_path = None
        self.analysis = None
        self.preview_end = None
        self.table.setRowCount(0)
        self.transcript_table.setRowCount(0)
        self._editor_row = None
        self._word_ref = None
        self._word_refs = []
        self._last_timeline_range = (0.0, 25.0)
        self.word_text.clear()
        self.timeline.set_selected_word(None)
        self._manual_from = None
        self._manual_to = None
        self._manual_pending = []
        self.update_manual_mark_label()
        self.reset_transcript_editor()
        self.tabs.setCurrentIndex(0)
        self.source_label.setText(source)
        self.player.setSource(QUrl.fromLocalFile(source))
        self.timeline.set_duration(1)
        self.timeline.set_annotations([], [])
        self.timeline_status.setText("Wellenform wird berechnet …")
        # A different file can be opened while the old worker shuts down;
        # stale results are ignored by the exact source-path comparison.
        worker = WaveformThread(source, self)
        self._waveform_workers.append(worker)
        worker.done.connect(self.waveform_finished)
        worker.failed.connect(self.waveform_failed)
        worker.finished.connect(lambda w=worker: self._cleanup_waveform_thread(w))
        worker.start()
        self.progress.setValue(0)
        self._busy(False)
        self.statusBar().showMessage("Aufnahme geladen – Analyse starten")
        return True

    def _cleanup_waveform_thread(self, worker: WaveformThread):
        if worker in self._waveform_workers:
            self._waveform_workers.remove(worker)
        worker.deleteLater()

    def waveform_finished(self, filename: str, result: object):
        if filename != self.source:
            return
        video, peaks = result
        preserve = self._source_duration > 0
        current_selection = (self.timeline.in_point, self.timeline.out_point)
        self._source_duration = video.duration
        self.timeline.set_duration(video.duration)
        self.timeline.set_peaks(peaks)
        if preserve:
            self.timeline.set_selection(*current_selection)
        else:
            self.timeline.set_selection(0, min(video.duration, self.length.value()))
        self.timeline_range_changed(self.timeline.in_point, self.timeline.out_point)
        self._sync_timeline_scroll()
        if self.analysis:
            self.timeline.set_annotations(self.analysis.candidates, self.analysis.transcript)
        self.timeline_status.setText(
            f"{format_timestamp(video.duration)} · {len(peaks)} Audio-Punkte")

    def waveform_failed(self, filename: str, reason: str):
        if filename == self.source:
            self.timeline_status.setText("Keine Wellenform verfügbar")
            self.statusBar().showMessage("Wellenform: " + reason)

    def change_timeline_zoom(self):
        if self._source_duration <= 0:
            return
        zoom = float(self.timeline_zoom.currentData() or 1.0)
        self.timeline.set_zoom(zoom, center=self.player.position() / 1000)
        self.timeline_zoom_hint.setText(f"{self.timeline.zoom:.0f}×")
        self._sync_timeline_scroll()

    def _sync_timeline_scroll(self):
        start, end = self.timeline.visible()
        limit = max(0, round(self.timeline.duration - (end - start)))
        self.timeline_scroll.blockSignals(True)
        try:
            self.timeline_scroll.setRange(0, limit)
            self.timeline_scroll.setPageStep(max(1, round(end-start)))
            self.timeline_scroll.setValue(round(start))
        finally:
            self.timeline_scroll.blockSignals(False)

    def timeline_scroll_changed(self, value: int):
        self.timeline.set_offset(float(value))

    def timeline_seek(self, second: float):
        self.preview_end = None
        self.player.setPosition(round(second * 1000))

    def timeline_range_changed(self, start: float, end: float):
        if not self.apply_word_editor():
            # A malformed edit must not get lost when changing highlights.
            self.timeline.set_selection(*self._last_timeline_range)
            return
        self._last_timeline_range = (start, end)
        self._refresh_word_refs()
        self.timeline_in.blockSignals(True)
        self.timeline_out.blockSignals(True)
        try:
            self.timeline_in.setValue(start)
            self.timeline_out.setValue(end)
            self.timeline_selection_label.setText(
                f"{format_timestamp(start)} – {format_timestamp(end)}")
        finally:
            self.timeline_in.blockSignals(False)
            self.timeline_out.blockSignals(False)

    def timeline_fields_changed(self):
        if not self.source or self._source_duration <= 0:
            return
        start, end = self.timeline_in.value(), self.timeline_out.value()
        if end <= start or start >= self.timeline.duration:
            return
        # Reuse the same commit/validation path as dragging a marker.
        # Pending word edits must never disappear when changing the IN/OUT boxes.
        self.timeline.set_selection(start, end, emit=True)

    def _refresh_word_refs(self):
        if not hasattr(self, 'word_text'):
            return
        old_ref = self._word_ref
        self._word_refs = ([(i, j) for i, j, _ in words_in_clip(
            self.analysis.transcript, self.timeline.in_point, self.timeline.out_point)]
            if self.analysis else [])
        if old_ref is not None and old_ref not in self._word_refs:
            self._word_ref = None
            self.timeline.set_selected_word(None)
            self.word_text.clear()
        if not self._word_refs:
            self.word_hint.setText("Kein Transkript im Ausschnitt – Whisper aktivieren oder Analyse laden")
        elif self._word_ref is None:
            self.word_hint.setText(
                f"{len(self._word_refs)} Wörter · violette Wortspur anklicken (gelb = geschätzt)")

    def timeline_select_subtitle(self, index: int):
        if not self.analysis or not 0 <= index < len(self.analysis.transcript):
            return
        matches = [(i, j) for i, j in self._word_refs if i == index]
        if matches:
            self.select_timeline_word(*matches[0])

    def select_timeline_word(self, segment: int, word: int):
        if not self.analysis or (segment, word) not in self._word_refs:
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            if self._word_ref is None:
                self.timeline.set_selected_word(None)
            else:
                self.timeline.set_selected_word(*self._word_ref)
            return
        self._word_ref = (segment, word)
        cue = effective_words(self.analysis.transcript[segment])[word]
        self.word_text.blockSignals(True)
        self.word_start.blockSignals(True)
        self.word_end.blockSignals(True)
        try:
            self.word_text.setText(cue.text)
            self.word_start.setValue(cue.start)
            self.word_end.setValue(cue.end)
        finally:
            self.word_text.blockSignals(False)
            self.word_start.blockSignals(False)
            self.word_end.blockSignals(False)
        self.timeline.set_selected_word(segment, word)
        source = {"estimated": "Geschätzt (Altprojekt) – Zeiten manuell prüfen",
                  "manual": "Manuell korrigiert",
                  "whisper": "Whisper-Wortzeit – bei Bedarf korrigieren"}[cue.origin]
        self.word_hint.setText(
            f"Wort {self._word_refs.index((segment,word)) + 1}/{len(self._word_refs)} · {source}")
        self.player.pause()
        self.preview_end = None
        self.player.setPosition(round(max(0, cue.start - .15) * 1000))
        self._busy(False)

    def navigate_word(self, step: int):
        if not self._word_refs or not self.apply_word_editor():
            return
        try:
            index = self._word_refs.index(self._word_ref)
        except ValueError:
            index = -1 if step > 0 else len(self._word_refs)
        index = max(0, min(len(self._word_refs) - 1, index + step))
        self.select_timeline_word(*self._word_refs[index])

    def _word_has_pending(self) -> bool:
        if not self.analysis or self._word_ref is None:
            return False
        i, j = self._word_ref
        if i >= len(self.analysis.transcript):
            return False
        words = effective_words(self.analysis.transcript[i])
        if j >= len(words):
            return False
        old = words[j]
        return (self.word_text.text().strip() != old.text or
                abs(self.word_start.value() - old.start) > .0005 or
                abs(self.word_end.value() - old.end) > .0005)

    def apply_word_editor(self) -> bool:
        if self._word_ref is None or not self._word_has_pending():
            return True
        if not self.analysis:
            return True
        i, j = self._word_ref
        try:
            self.analysis = edit_word(self.analysis, i, j,
                                      self.word_start.value(), self.word_end.value(),
                                      self.word_text.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Wortkorrektur prüfen", str(exc))
            return False
        cue = self.analysis.transcript[i]
        self.transcript_table.blockSignals(True)
        try:
            for column, value in enumerate((format_timestamp(cue.start),
                                            format_timestamp(cue.end), cue.text)):
                if self.transcript_table.item(i, column):
                    self.transcript_table.item(i, column).setText(value)
        finally:
            self.transcript_table.blockSignals(False)
        if self._editor_row == i:
            self.fill_transcript_editor(i)
        self.transcript_dirty = True
        self.timeline.set_annotations(self.analysis.candidates, self.analysis.transcript)
        self._refresh_word_refs()
        if (i, j) in self._word_refs:
            self.timeline.set_selected_word(i, j)
        self._active_caption = None
        self._update_caption_overlay(self.player.position()/1000)
        self.word_hint.setText("✓ Wort korrigiert · Projekt speichern (Strg+S)")
        self.statusBar().showMessage("Wortkorrektur im Highlight übernommen – Export nutzt neue Zeiten")
        return True

    def commit_timeline_word_edge(self, i: int, j: int, edge: str, value: float):
        if self._word_ref != (i, j) or edge not in {'start', 'end'}:
            return
        target = self.word_start if edge == 'start' else self.word_end
        target.setValue(value)
        self.apply_word_editor()

    def play_selected_word(self):
        if not self.analysis or self._word_ref is None or not self.apply_word_editor():
            return
        i, j = self._word_ref
        cue = effective_words(self.analysis.transcript[i])[j]
        self.player.pause()
        self.player.setPosition(round(max(0, cue.start - .2) * 1000))
        self.preview_end = min(self.analysis.video.duration, cue.end + .3)
        self.player.play()

    def add_timeline_highlight(self):
        if self._source_duration > 0:
            self.add_manual_interval(self.timeline.in_point, self.timeline.out_point)

    def trim_timeline_highlight(self):
        if not self.analysis:
            return
        index = self.table.currentRow()
        try:
            self.analysis = trim_manual_highlight(
                self.analysis, index, self.timeline.in_point, self.timeline.out_point)
        except ValueError as exc:
            QMessageBox.warning(self, "Schnittbereich ungültig", str(exc))
            return
        self.transcript_dirty = True
        self.refresh_highlight_table()
        self.table.selectRow(index)
        self.statusBar().showMessage("Highlight getrimmt – Projekt speichern")

    def preview_timeline_selection(self):
        if not self.source:
            return
        self.player.pause()
        self.preview_end = self.timeline.out_point
        self.player.setPosition(round(self.timeline.in_point * 1000))
        self.player.play()

    def eventFilter(self, watched, event):
        if watched is self.video_widget and event.type() == QEvent.Type.Resize:
            width = max(10, self.video_widget.width() - 32)
            height = 90
            self.caption_overlay.setGeometry(
                16, max(0, self.video_widget.height() - height - 30), width, height)
            self.caption_overlay.raise_()
        return super().eventFilter(watched, event)

    def caption_offset_changed(self, value: float):
        self.timeline.set_caption_offset(value)
        self._active_caption = None
        self._update_caption_overlay(self.player.position()/1000)

    def _update_caption_overlay(self, seconds: float):
        segments = self.analysis.transcript if self.analysis else []
        phrase = subtitle_text_at_time(segments, seconds, self.caption_offset.value())
        if not phrase or not self.burn_subtitles.isChecked():
            self._active_caption = None
            self.caption_overlay.hide()
            return
        if phrase != self._active_caption:
            self._active_caption = phrase
            self.caption_overlay.setText(phrase)
            self.caption_overlay.show()
            self.caption_overlay.raise_()

    def import_twitch_video(self) -> None:
        url, accepted = QInputDialog.getText(
            self, "Twitch-VOD importieren", "Öffentliche Twitch-Video-URL eingeben:")
        if not accepted or not url.strip():
            return
        try:
            canonical, _ = parse_twitch_vod_url(url)
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültige Twitch-URL", str(exc))
            return
        # VODs can be hours long and occupy many GB. Let the user choose the location.
        default = installation_directory() / "data" / "imports"
        default.mkdir(parents=True, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Twitch-VOD speichern unter", str(default))
        if not folder or not self.confirm_discard_edits():
            return
        self.progress.setValue(0)
        self.worker = TwitchImportThread(canonical, folder, self)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.done.connect(self.twitch_import_finished)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(lambda: self._busy(False))
        self._busy(True)
        self.statusBar().showMessage("Twitch-VOD wird heruntergeladen …")
        self.worker.start()

    def twitch_import_finished(self, filename: str) -> None:
        if self.load_video_source(filename):
            self.statusBar().showMessage("Twitch-VOD importiert: " + filename)

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
        if vision:
            try:
                validate_clip_model(vision)
            except FileNotFoundError as exc:
                QMessageBox.warning(self, "CLIP-Modell unvollständig", str(exc)
                                    + "\n\nDu kannst Spielbilder vorerst deaktivieren "
                                      "und die Analyse nur mit Whisper starten.")
                return
        self._manual_pending = [c for c in self.analysis.candidates if c.origin == "manual"] if self.analysis else []
        self.analysis = None
        self.transcript_dirty = False
        self.report_path = None
        self._editor_row = None
        self.table.setRowCount(0)
        self.transcript_table.setRowCount(0)
        self.reset_transcript_editor()
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

    def refresh_highlight_table(self) -> None:
        if not self.analysis:
            self.table.setRowCount(0)
            return
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.analysis.candidates))
            for row, clip in enumerate(self.analysis.candidates):
                values = (display_time(clip.start), display_time(clip.end),
                          "★ Manuell" if clip.origin == "manual" else str(clip.score), clip.reason)
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 2:
                        item.setForeground(QColor("#ffd27d" if clip.origin == "manual" else "#77c7ff"))
                    self.table.setItem(row, col, item)
        finally:
            self.table.blockSignals(False)
        if self.analysis.candidates:
            self.table.selectRow(0)
        self.timeline.set_annotations(self.analysis.candidates, self.analysis.transcript)

    def analysis_finished(self, result: AnalysisResult) -> None:
        preserved_manual = bool(self._manual_pending)
        if self._manual_pending and self.source and Path(result.video.path).resolve() == Path(self.source).resolve():
            from dataclasses import replace
            result = replace(result, candidates=result.candidates + self._manual_pending)
            self._manual_pending = []
        self._word_ref = None
        self._word_refs = []
        self.timeline.set_selected_word(None)
        self.word_text.clear()
        self.analysis = result
        self.refresh_highlight_table()
        self.transcript_table.blockSignals(True)
        try:
            self.transcript_table.setRowCount(len(result.transcript))
            for row, segment in enumerate(result.transcript):
                for column, value in enumerate((format_timestamp(segment.start),
                                                format_timestamp(segment.end), segment.text)):
                    self.transcript_table.setItem(row, column, QTableWidgetItem(value))
        finally:
            self.transcript_table.blockSignals(False)
        self.transcript_dirty = preserved_manual
        self.timeline.set_annotations(result.candidates, result.transcript)
        self._word_ref = None
        self._refresh_word_refs()
        self._active_caption = None
        self._update_caption_overlay(self.player.position()/1000)
        self._editor_row = None
        self._busy(False)
        if result.transcript:
            self.transcript_table.selectRow(0)
        self.statusBar().showMessage(
            f"{len(result.candidates)} Clips, {len(result.transcript)} Transkript-Abschnitte")

    def job_failed(self, message: str) -> None:
        # Preserve manual markers even if a subsequent AI pass fails.
        if self._manual_pending and self.source:
            try:
                info = probe_video(self.source)
                self.analysis = AnalysisResult(info, self._manual_pending,
                                               method="manual-only")
                self._manual_pending = []
                self.refresh_highlight_table()
                self.transcript_dirty = True
            except (OSError, RuntimeError, ValueError):
                pass
        self._busy(False)
        if "abgebrochen" in message.lower():
            self.statusBar().showMessage(message)
        else:
            QMessageBox.critical(self, "Verarbeitung fehlgeschlagen", message)
            self.statusBar().showMessage("Fehler – Details im Dialog")

    def _ensure_manual_result(self) -> bool:
        if self.analysis:
            return True
        if not self.source:
            return False
        try:
            info = probe_video(self.source)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Aufnahme prüfen", str(exc))
            return False
        self.analysis = AnalysisResult(info, [], method="manual-only", transcript=[])
        self.report_path = None
        return True

    def _current_video_second(self) -> float:
        return max(0.0, self.player.position() / 1000)

    def update_manual_mark_label(self) -> None:
        a = "–" if self._manual_from is None else format_timestamp(self._manual_from)
        b = "–" if self._manual_to is None else format_timestamp(self._manual_to)
        self.manual_marks_label.setText(f"Start: {a} · Ende: {b}")

    def mark_highlight_start(self) -> None:
        self._manual_from = self._current_video_second()
        self.update_manual_mark_label()

    def mark_highlight_end(self) -> None:
        self._manual_to = self._current_video_second()
        self.update_manual_mark_label()

    def add_quick_highlight(self) -> None:
        if not self._ensure_manual_result():
            return
        start = min(self._current_video_second(), max(0.0, self.analysis.video.duration - 0.1))
        end = min(self.analysis.video.duration, start + self.length.value())
        self.add_manual_interval(start, end)

    def add_marked_highlight(self) -> None:
        if self._manual_from is None or self._manual_to is None:
            QMessageBox.information(self, "Start und Ende setzen",
                                    "Markiere zuerst Start und Ende während der Wiedergabe.")
            return
        self.add_manual_interval(self._manual_from, self._manual_to)

    def add_manual_interval(self, start: float, end: float) -> None:
        if not self._ensure_manual_result():
            return
        try:
            self.analysis = add_manual_highlight(self.analysis, start, end,
                                                  self.manual_label.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Highlight-Zeit prüfen", str(exc))
            return
        self.refresh_highlight_table()
        self.table.selectRow(len(self.analysis.candidates) - 1)
        self.timeline.set_selection(start, end)
        self._manual_from = self._manual_to = None
        self.update_manual_mark_label()
        self.manual_label.clear()
        self.transcript_dirty = True
        self._busy(False)
        self.statusBar().showMessage("Manuelles Highlight hinzugefügt – Projekt speichern")

    def delete_selected_manual_highlight(self) -> None:
        if not self.analysis:
            return
        try:
            self.analysis = remove_manual_highlight(self.analysis, self.table.currentRow())
        except ValueError as exc:
            QMessageBox.warning(self, "Highlight kann nicht gelöscht werden", str(exc))
            return
        self.refresh_highlight_table()
        self.transcript_dirty = True
        self._busy(False)
        self.statusBar().showMessage("Manuelles Highlight entfernt – Projekt speichern")

    def selected_candidate(self) -> Candidate | None:
        if not self.analysis:
            return None
        row = self.table.currentRow()
        if 0 <= row < len(self.analysis.candidates):
            return self.analysis.candidates[row]
        return None

    def preview_selected(self) -> None:
        if not self.apply_word_editor():
            return
        clip = self.selected_candidate()
        if not clip:
            self.single_export.setEnabled(False)
            self.timeline_trim.setEnabled(False)
            return
        self.preview_end = clip.end
        self.timeline.set_selection(clip.start, clip.end, emit=True)
        # Six-hour VODs need second-level zoom to make individual words clickable.
        if self.timeline.zoom <= 1.01 and self._source_duration > 0:
            self.timeline.set_zoom(
                max(1, self._source_duration / max(10., (clip.end - clip.start) * 1.1)),
                center=(clip.start + clip.end)/2)
            self.timeline_zoom_hint.setText(f"{self.timeline.zoom:.0f}×")
        self.timeline.ensure_visible(clip.start)
        self._sync_timeline_scroll()
        self.player.pause()
        self.player.setPosition(round(clip.start * 1000))
        self.single_export.setEnabled(not bool(self.worker and self.worker.isRunning()))
        self.transcript_from_highlight.setEnabled(bool(self.analysis.transcript))
        self.manual_delete.setEnabled(clip.origin == "manual")
        self.timeline_trim.setEnabled(clip.origin == "manual" and
                                      not bool(self.worker and self.worker.isRunning()))

    def transcript_selection_changed(self) -> None:
        if not self.apply_word_editor():
            return
        if not self.analysis:
            return
        row = self.transcript_table.currentRow()
        if row == self._editor_row or row < 0:
            return
        if not self.apply_transcript_editor():
            # Preserve unfinished corrections when a new row was clicked.
            self.transcript_table.blockSignals(True)
            try:
                if self._editor_row is not None:
                    self.transcript_table.selectRow(self._editor_row)
            finally:
                self.transcript_table.blockSignals(False)
            return
        self._editor_row = row
        self.fill_transcript_editor(row)
        self.jump_to_transcript(row, 0)

    def fill_transcript_editor(self, row: int) -> None:
        if not self.analysis or not 0 <= row < len(self.analysis.transcript):
            return
        cue = self.analysis.transcript[row]
        for widget in (self.transcript_edit_text, self.transcript_edit_start,
                       self.transcript_edit_end):
            widget.blockSignals(True)
        try:
            self.transcript_edit_start.setText(format_timestamp(cue.start))
            self.transcript_edit_end.setText(format_timestamp(cue.end))
            self.transcript_edit_text.setPlainText(cue.text)
        finally:
            for widget in (self.transcript_edit_text, self.transcript_edit_start,
                           self.transcript_edit_end):
                widget.blockSignals(False)
        self.transcript_pending_changed()

    def transcript_pending_changed(self) -> None:
        changed = self.transcript_has_pending()
        if self._editor_row is None:
            self.transcript_editor_hint.setText("Nach der Analyse eine Zeile auswählen.")
        elif changed:
            self.transcript_editor_hint.setText(
                "● Noch nicht übernommen. Auf „Korrektur übernehmen“ klicken, "
                "danach „Projekt speichern“.")
        else:
            self.transcript_editor_hint.setText(
                "✓ Zeile übernommen. Der nächste Export verwendet diesen Text. "
                "Projekt speichern, damit die Korrektur nach Neustart erhalten bleibt.")

    def transcript_has_pending(self) -> bool:
        if not self.analysis or self._editor_row is None:
            return False
        cue = self.analysis.transcript[self._editor_row]
        return (self.transcript_edit_text.toPlainText() != cue.text or
                self.transcript_edit_start.text() != format_timestamp(cue.start) or
                self.transcript_edit_end.text() != format_timestamp(cue.end))

    def apply_transcript_editor(self) -> bool:
        if not self.analysis or self._editor_row is None or not self.transcript_has_pending():
            return True
        row = self._editor_row
        try:
            new_result = apply_segment_changes(
                self.analysis, row, self.transcript_edit_start.text(),
                self.transcript_edit_end.text(), self.transcript_edit_text.toPlainText())
        except ValueError as exc:
            QMessageBox.warning(self, "Untertitel-Korrektur prüfen", str(exc))
            return False
        self.analysis = new_result
        cue = new_result.transcript[row]
        self.transcript_table.blockSignals(True)
        try:
            for col, val in enumerate((format_timestamp(cue.start),
                                       format_timestamp(cue.end), cue.text)):
                self.transcript_table.item(row, col).setText(val)
        finally:
            self.transcript_table.blockSignals(False)
        self.fill_transcript_editor(row)
        self.transcript_dirty = True
        self.timeline.set_annotations(self.analysis.candidates, self.analysis.transcript)
        self._refresh_word_refs()
        self._active_caption = None
        self._update_caption_overlay(self.player.position()/1000)
        self.statusBar().showMessage(
            "Untertitel korrigiert – Projekt speichern (Strg+S). "
            "Export nutzt bereits die neue Fassung.")
        return True

    def reset_transcript_editor(self) -> None:
        if self._editor_row is not None and self.analysis:
            self.fill_transcript_editor(self._editor_row)
        else:
            for widget in (self.transcript_edit_text, self.transcript_edit_start,
                           self.transcript_edit_end):
                widget.blockSignals(True)
                widget.clear()
                widget.blockSignals(False)
            self.transcript_pending_changed()

    def navigate_transcript(self, step: int) -> None:
        if not self.analysis or not self.analysis.transcript:
            return
        current = self.transcript_table.currentRow()
        next_row = max(0, min(len(self.analysis.transcript) - 1, current + step))
        self.transcript_table.selectRow(next_row)
        if self.transcript_table.item(next_row, 0):
            self.transcript_table.scrollToItem(self.transcript_table.item(next_row, 0))

    def nudge_transcript(self, column: int, difference: float) -> None:
        if self._editor_row is None:
            return
        field = self.transcript_edit_start if column == 0 else self.transcript_edit_end
        try:
            value = parse_timestamp(field.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Zeit prüfen", str(exc))
            return
        field.setText(format_timestamp(max(0.0, round(value + difference, 3))))

    def jump_to_highlight_transcript(self) -> None:
        if not self.analysis or not self.analysis.transcript:
            return
        clip = self.selected_candidate()
        if not clip:
            return
        matches = [i for i, cue in enumerate(self.analysis.transcript)
                   if cue.end > clip.start and cue.start < clip.end]
        if not matches:
            QMessageBox.information(self, "Kein Sprachabschnitt",
                "Für dieses Highlight wurde keine Sprache erkannt.")
            return
        row = matches[0]
        self.tabs.setCurrentIndex(1)
        self.transcript_table.selectRow(row)
        self.transcript_table.scrollToItem(self.transcript_table.item(row, 0))

    def play_transcript_segment(self) -> None:
        if not self.analysis or self._editor_row is None:
            return
        if not self.apply_transcript_editor():
            return
        cue = self.analysis.transcript[self._editor_row]
        self.player.pause()
        self.preview_end = cue.end
        self.player.setPosition(round(max(0, cue.start - 0.3) * 1000))
        self.player.play()

    def jump_to_transcript(self, row: int, _column: int) -> None:
        if not self.analysis or row < 0 or row >= len(self.analysis.transcript):
            return
        self.preview_end = None
        self.player.pause()
        self.player.setPosition(round(self.analysis.transcript[row].start * 1000))

    def save_transcript_dialog(self) -> None:
        if not self.analysis or not self.analysis.transcript or not self.apply_transcript_editor():
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
        self.timeline.set_position(pos / 1000)
        if self.timeline.zoom > 1.0 and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            a, b = self.timeline.visible()
            if pos / 1000 > b or pos / 1000 < a:
                self.timeline.set_offset(pos / 1000 - (b-a) * .20)
                self._sync_timeline_scroll()
        self._update_caption_overlay(pos / 1000)
        if self.preview_end is not None and pos >= int(self.preview_end * 1000):
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()

    def _duration_changed(self, duration: int) -> None:
        self.seek.setRange(0, max(1, duration))
        # Waveform worker normally provides ffprobe duration first; the player
        # can supply a fallback while FFmpeg is still preparing the overview.
        if duration > 0 and self._source_duration <= 0:
            self._source_duration = duration / 1000
            self.timeline.set_duration(self._source_duration)

    def seek_to(self, pos: int) -> None:
        self.preview_end = None  # manual scrubbing may leave suggested time span
        self.player.setPosition(pos)

    def start_export(self, all_clips: bool) -> None:
        if not self.analysis or not self.apply_word_editor() or not self.apply_transcript_editor():
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
        if not self.analysis or not self.apply_word_editor() or not self.apply_transcript_editor():
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
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return False
        if not self.transcript_dirty:
            return True
        answer = QMessageBox.question(
            self, "Ungespeicherte Transkriptkorrekturen",
            "Deine Änderungen an Transkript/Highlights sind noch nicht gespeichert. Jetzt Projekt speichern?",
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
        for worker in self._waveform_workers:
            worker.cancel()
        for worker in list(self._waveform_workers):
            if not worker.wait(3000):
                QMessageBox.information(
                    self, "Wellenform wird beendet",
                    "FFmpeg beendet die Wellenform noch. Bitte gleich erneut schließen.")
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
