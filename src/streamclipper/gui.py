"""Windows desktop UI; analysis and export run off the UI thread."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from .portable import configure_portable_environment

configure_portable_environment()

from PySide6.QtCore import QEvent, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSlider, QSpinBox,
    QInputDialog,
    QDoubleSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget, QScrollArea,
)

from .analyze import analyze
from .media import CancelledError, export_clip, probe_video, safe_destination, tool_path, waveform_peaks
from .model_checks import validate_clip_model
from .model_catalog import (DEFAULTS, download_preset, is_installed, preset,
                            preset_path, presets_for, validate_model_dir)
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
from .highlight_lexicon_dialog import HighlightLexiconDialog
from .editor_project import (EditorProject, ProjectHistory, initial_project,
    add_track, remove_track, rename_track, move_track, toggle_track,
    add_item, edit_item, load_project, save_project)
from .track_canvas import TrackCanvas
from .project_checkpoints import create_checkpoint, list_checkpoints, load_checkpoint

from .edit_history import EditHistory
from .autosave import autosave_path, clear_autosave, load_autosave, save_autosave


def display_time(seconds: float) -> str:
    amount = int(seconds)
    return f"{amount // 3600:02d}:{amount // 60 % 60:02d}:{amount % 60:02d}"


class AnalysisThread(QThread):
    progress_changed = Signal(int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, source: str, length: int, parent=None,
                 speech_model: str | None = None, vision_model: str | None = None,
                 detector_model: str | None = None):
        super().__init__(parent)
        self.source = source
        self.length = length
        self.speech_model = speech_model
        self.vision_model = vision_model
        self.detector_model = detector_model
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            result = analyze(self.source, clip_seconds=self.length,
                             progress=self.progress_changed.emit,
                             cancelled=self._cancelled.is_set,
                             speech_model=self.speech_model,
                             vision_model=self.vision_model,
                             detector_model=self.detector_model)
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


class ModelDownloadThread(QThread):
    """Explicit model provisioning in a background thread; never in inference."""
    done = Signal(str, str)
    failed = Signal(str, str)

    def __init__(self, model_id: str, parent=None):
        super().__init__(parent)
        self.model_id = model_id

    def run(self):
        try:
            destination = download_preset(self.model_id)
            self.done.emit(self.model_id, str(destination))
        except Exception as exc:
            self.failed.emit(self.model_id, str(exc))


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
        self.setWindowTitle("StreamClipper Studio – Editor (experimentell)")
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
        self.model_worker: ModelDownloadThread | None = None
        self._source_duration: float = 0.0
        self._active_caption: str | None = None
        self._word_ref: tuple[int, int] | None = None
        self._word_refs: list[tuple[int, int]] = []
        self._last_timeline_range: tuple[float, float] = (0.0, 25.0)
        self._edit_history = EditHistory()
        self.editor_project: EditorProject | None = None
        self._project_history = ProjectHistory()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(4000)
        self._autosave_timer.timeout.connect(self._write_autosave)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.65)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)

        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setSpacing(7)
        # Permanent preview and timeline, tool panels in the sidebar.
        self.models_page = QScrollArea()
        self.models_page.setWidgetResizable(True)
        models_content = QWidget()
        models_page_layout = QVBoxLayout(models_content)
        self.models_page.setWidget(models_content)
        self.export_page = QScrollArea()
        self.export_page.setWidgetResizable(True)
        export_content = QWidget()
        export_page_layout = QVBoxLayout(export_content)
        self.export_page.setWidget(export_content)

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
        self.highlight_words_button = QPushButton("Highlight-Wörter …")
        self.highlight_words_button.setToolTip("Eigene sprachliche Highlight-Ausdrücke und Gewichtungen verwalten")
        self.highlight_words_button.clicked.connect(self.edit_highlight_words)
        models_page_layout.addWidget(self.highlight_words_button)
        toolbar.addStretch()
        main.addLayout(toolbar)
        # Keep project management out of the increasingly crowded editor tabs.
        project_menu = self.menuBar().addMenu("Datei && Projekt")
        project_menu.addAction("Aufnahme öffnen…", self.open_video)
        project_menu.addAction("Twitch-VOD importieren…", self.import_twitch_video)
        project_menu.addSeparator()
        self.checkpoint_save_action = project_menu.addAction(
            "Benannten Projektstand sichern…", self._save_project_checkpoint)
        self.checkpoint_save_action.setShortcut(QKeySequence("Ctrl+Alt+S"))
        self.checkpoint_restore_action = project_menu.addAction(
            "Projektstand wiederherstellen…", self._restore_project_checkpoint)
        self.checkpoint_restore_action.setShortcut(QKeySequence("Ctrl+Alt+O"))
        self.checkpoint_save_action.setEnabled(False)
        self.checkpoint_restore_action.setEnabled(False)

        # Three independent tasks. Choice never starts a download or analysis.
        # Retain the folder override for existing locally converted models.
        self.model_selectors = {}
        self.model_download_buttons = {}
        model_options = QVBoxLayout()
        model_options.setSpacing(4)
        for kind, label, placeholder in (
            ('speech', 'Sprache / Wort-Timing', 'Whisper-Modellordner'),
            ('vision', 'Gameplay-Dynamik + CLIP', 'CLIP-Modellordner'),
            ('detector', 'Objektspuren (optional)', 'DETR-Modellordner'),
        ):
            line = QHBoxLayout()
            enabled = QCheckBox(label)
            select = QComboBox()
            select.setMinimumWidth(170)
            for item in presets_for(kind):
                select.addItem(item.label, item.id)
                select.setItemData(select.count()-1, item.note, Qt.ItemDataRole.ToolTipRole)
            path = QLineEdit()
            path.setPlaceholderText(placeholder)
            initial = DEFAULTS[kind]
            select.setCurrentIndex(select.findData(initial))
            path.setText(str(preset_path(initial)))
            select.currentIndexChanged.connect(
                lambda _n, k=kind: self.select_model_preset(k))
            enabled.setChecked(kind == 'speech' and is_installed(initial))
            browse = QPushButton('Ordner …')
            browse.clicked.connect(lambda _checked=False, target=path: self.choose_model(target))
            download = QPushButton('Herunterladen')
            download.setToolTip('Nur auf Klick: lädt die gewählte Variante nach data/models/')
            download.clicked.connect(lambda _checked=False, k=kind: self.download_selected_model(k))
            line.addWidget(enabled)
            line.addWidget(select, 1)
            line.addWidget(download)
            model_options.addLayout(line)
            path_row = QHBoxLayout()
            path_row.addWidget(path, 1)
            path_row.addWidget(browse)
            model_options.addLayout(path_row)
            setattr(self, f'{kind}_enabled', enabled)
            setattr(self, f'{kind}_path', path)
            self.model_selectors[kind] = select
            self.model_download_buttons[kind] = download
        self.speech_select = self.model_selectors['speech']
        self.vision_select = self.model_selectors['vision']
        self.detector_select = self.model_selectors['detector']
        models_page_layout.addLayout(model_options)
        models_page_layout.addStretch()

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
        highlights_layout.addWidget(QLabel("Highlight-Vorschläge (Audio / Sprache / Szenendynamik / CLIP)"))
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
        self.tabs.addTab(transcript_tab, "Untertitel")
        self.tabs.addTab(self.models_page, "KI & Modelle")
        # M11b: metadata-based multitrack editor. No audio mix/export yet.
        self.tracks_page = QScrollArea()
        self.tracks_page.setWidgetResizable(True)
        tracks_content = QWidget()
        tracks_layout = QVBoxLayout(tracks_content)
        self.tracks_page.setWidget(tracks_content)
        tracks_intro = QLabel(
            "Spurplan für Schnitt und künftige Mehrspur-Exporte. "
            "Wiedergabe und Export nutzen derzeit noch die Originalaufnahme.")
        tracks_intro.setWordWrap(True)
        tracks_layout.addWidget(tracks_intro)
        self.track_canvas = TrackCanvas()
        self.track_canvas.trackSelected.connect(self._select_project_track)
        self.track_canvas.clipSelected.connect(self._select_project_clip)
        self.track_canvas.clipMoved.connect(self._drag_project_clip)
        tracks_layout.addWidget(self.track_canvas)
        self.tracks_table = QTableWidget(0, 5)
        self.tracks_table.setMinimumHeight(145)
        self.tracks_table.setHorizontalHeaderLabels(
            ["Spur", "Typ", "Stumm", "Gesperrt", "Clips"])
        self.tracks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tracks_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tracks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tracks_table.horizontalHeader().setStretchLastSection(True)
        self.tracks_table.itemSelectionChanged.connect(self._update_track_actions)
        tracks_layout.addWidget(self.tracks_table, 1)
        row1 = QHBoxLayout()
        self.track_add_button = QPushButton("＋ Spur")
        self.track_add_button.clicked.connect(self._add_track_dialog)
        self.track_rename_button = QPushButton("Umbenennen")
        self.track_rename_button.clicked.connect(self._rename_selected_track)
        self.track_remove_button = QPushButton("Entfernen")
        self.track_remove_button.clicked.connect(self._remove_selected_track)
        for control in (self.track_add_button, self.track_rename_button,
                        self.track_remove_button):
            row1.addWidget(control)
        tracks_layout.addLayout(row1)
        row2 = QHBoxLayout()
        self.track_mute_button = QPushButton("Stumm")
        self.track_mute_button.clicked.connect(lambda: self._toggle_selected_track("muted"))
        self.track_lock_button = QPushButton("Sperren")
        self.track_lock_button.clicked.connect(lambda: self._toggle_selected_track("locked"))
        self.track_up_button = QPushButton("↑")
        self.track_up_button.clicked.connect(lambda: self._move_selected_track(-1))
        self.track_down_button = QPushButton("↓")
        self.track_down_button.clicked.connect(lambda: self._move_selected_track(1))
        for control in (self.track_mute_button, self.track_lock_button,
                        self.track_up_button, self.track_down_button):
            row2.addWidget(control)
        tracks_layout.addLayout(row2)
        tracks_layout.addWidget(QLabel("Clips / Zeitpositionen"))
        self.track_clips_table = QTableWidget(0, 5)
        self.track_clips_table.setMinimumHeight(125)
        self.track_clips_table.setHorizontalHeaderLabels(
            ["Clip", "Spur", "Quelle IN", "Quelle OUT", "Timeline IN"])
        self.track_clips_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.track_clips_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.track_clips_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.track_clips_table.horizontalHeader().setStretchLastSection(True)
        self.track_clips_table.itemSelectionChanged.connect(self._track_clip_selection_changed)
        tracks_layout.addWidget(self.track_clips_table, 1)
        row3 = QHBoxLayout()
        self.track_clip_add = QPushButton("Auswahl als Spurclip")
        self.track_clip_add.clicked.connect(self._add_selected_track_clip)
        self.track_clip_move = QPushButton("Clip verschieben")
        self.track_clip_move.clicked.connect(self._move_selected_track_clip)
        self.track_clip_trim = QPushButton("Clip trimmen")
        self.track_clip_trim.clicked.connect(self._trim_selected_track_clip)
        for control in (self.track_clip_add, self.track_clip_move,
                        self.track_clip_trim):
            row3.addWidget(control)
        tracks_layout.addLayout(row3)
        row4 = QHBoxLayout()
        self.track_undo_button = QPushButton("↶ Spuraktion zurück")
        self.track_undo_button.clicked.connect(self._undo_project)
        self.track_redo_button = QPushButton("↷ Spuraktion wiederholen")
        self.track_redo_button.clicked.connect(self._redo_project)
        for control in (self.track_undo_button, self.track_redo_button):
            row4.addWidget(control)
        tracks_layout.addLayout(row4)
        self.track_status = QLabel("Spuren werden mit der Videoquelle geladen.")
        self.track_status.setWordWrap(True)
        tracks_layout.addWidget(self.track_status)
        self.tabs.addTab(self.tracks_page, "Spuren")
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
        self.undo_button = QPushButton("↶ Rückgängig")
        self.undo_button.setToolTip("Letzte Bearbeitung zurücknehmen (Strg+Z)")
        self.undo_button.clicked.connect(self.undo_edit)
        timeline_header.addWidget(self.undo_button)
        self.redo_button = QPushButton("↷ Wiederholen")
        self.redo_button.setToolTip("Rückgenommene Bearbeitung wiederholen (Strg+Umschalt+Z)")
        self.redo_button.clicked.connect(self.redo_edit)
        timeline_header.addWidget(self.redo_button)
        self.autosave_hint = QLabel("Auto-Sicherung bereit")
        timeline_header.addWidget(self.autosave_hint)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo_edit)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.redo_edit)
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
        self.word_editor_toggle = QPushButton("▸ Worteditor einblenden")
        self.word_editor_toggle.setCheckable(True)
        self.word_editor_toggle.toggled.connect(self.toggle_word_editor)
        main.addWidget(self.word_editor_toggle)
        self.word_editor_panel = QWidget()
        word_panel_layout = QVBoxLayout(self.word_editor_panel)
        word_panel_layout.setContentsMargins(0, 0, 0, 0)
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
        word_panel_layout.addLayout(word_top)
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
        word_panel_layout.addLayout(word_controls)
        main.addWidget(self.word_editor_panel)
        self.word_editor_panel.hide()

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

        actions = QVBoxLayout()
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
        export_page_layout.addLayout(actions)

        caption_options = QVBoxLayout()
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
        export_page_layout.addLayout(caption_options)
        export_page_layout.addStretch()
        self.tabs.addTab(self.export_page, "Export")

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
        self.analyze_button.setEnabled(bool(self.source) and not busy
                                      and not bool(self.model_worker and self.model_worker.isRunning()))
        for button in self.model_download_buttons.values():
            button.setEnabled(not busy and not bool(self.model_worker and self.model_worker.isRunning()))
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
        self._update_history_controls(not busy)
        self._update_track_actions()

    def _update_history_controls(self, enabled: bool = True) -> None:
        self.undo_button.setEnabled(enabled and self._edit_history.can_undo)
        self.redo_button.setEnabled(enabled and self._edit_history.can_redo)

    def _register_edit(self, before: AnalysisResult) -> None:
        if self.analysis and self._edit_history.record(before, self.analysis):
            self.transcript_dirty = True
            self.autosave_hint.setText("● Änderungen · Auto-Sicherung folgt")
            self._autosave_timer.start()
            self._update_history_controls()

    def _write_autosave(self) -> None:
        if not self.analysis or not self.source or not self.transcript_dirty:
            return
        if not Path(self.source).is_file():
            self.autosave_hint.setText("Auto-Sicherung: Video fehlt")
            return
        try:
            save_autosave(self.analysis)
        except (OSError, ValueError) as exc:
            self.autosave_hint.setText("⚠ Auto-Sicherung fehlgeschlagen")
            self.statusBar().showMessage(f"Auto-Sicherung: {exc}")
        else:
            self.autosave_hint.setText("✓ Automatisch gesichert")

    def _offer_autosave_recovery(self, video) -> None:
        if not self.source or self.analysis:
            return
        path = autosave_path(self.source)
        if not path.is_file():
            return
        answer = QMessageBox.question(
            self, "Ungespeicherte Sitzung wiederherstellen?",
            "Für dieses Video sind automatisch gesicherte Highlight-/Wortkorrekturen vorhanden. "
            "Wiederherstellen? Die Originalaufnahme wird nicht verändert.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            recovered = load_autosave(
                self.source, duration=video.duration, size=(video.width, video.height))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Auto-Sicherung nicht lesbar", str(exc))
            return
        self.analysis_finished(recovered)
        self.transcript_dirty = True
        self.autosave_hint.setText("✓ Sitzung wiederhergestellt · Projekt speichern")

    def undo_edit(self) -> None:
        if not self.analysis or not self._edit_history.can_undo:
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        restored = self._edit_history.undo(self.analysis)
        self.analysis_finished(restored, preserve_history=True)
        self._autosave_timer.start()
        self.statusBar().showMessage("Korrektur rückgängig – Auto-Sicherung folgt")

    def redo_edit(self) -> None:
        if not self.analysis or not self._edit_history.can_redo:
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        restored = self._edit_history.redo(self.analysis)
        self.analysis_finished(restored, preserve_history=True)
        self._autosave_timer.start()
        self.statusBar().showMessage("Korrektur wiederholt – Auto-Sicherung folgt")

    def _open_editor_project(self, video) -> None:
        """Load metadata for this source; do not modify legacy analysis JSON."""
        try:
            self.editor_project = load_project(video)
            self.track_status.setText("✓ Gespeicherter Spurplan geladen")
        except FileNotFoundError:
            self.editor_project = initial_project(video)
            self.track_status.setText("Neuer Spurplan – Änderungen werden lokal gespeichert")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Spurplan konnte nicht geladen werden", str(exc))
            self.editor_project = initial_project(video)
            self.track_status.setText("Ungültiger Spurplan – Neuer Plan geöffnet")
        self._project_history = ProjectHistory()
        self._refresh_track_tables()
        self._update_checkpoint_actions()

    def _update_checkpoint_actions(self) -> None:
        ready = self.editor_project is not None
        self.checkpoint_save_action.setEnabled(ready)
        self.checkpoint_restore_action.setEnabled(ready)

    def _save_project_checkpoint(self) -> None:
        if not self.editor_project:
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Projektstand", "Bitte laufende Verarbeitung zuerst abschließen.")
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        name, accepted = QInputDialog.getText(
            self, "Projektstand sichern", "Name (z. B. Vor dem Untertitelschnitt):")
        if not accepted:
            return
        try:
            info = create_checkpoint(self.editor_project, name, self.analysis)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Projektstand nicht gesichert", str(exc))
            return
        self.statusBar().showMessage(
            f"✓ Projektstand „{info.name}“ gesichert"
            + (" · Spurplan und Analyse" if info.has_analysis else " · nur Spurplan"))

    def _restore_project_checkpoint(self) -> None:
        if not self.editor_project:
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Projektstand", "Bitte laufende Verarbeitung zuerst abschließen.")
            return
        try:
            entries = list_checkpoints(self.editor_project.source)
        except OSError as exc:
            QMessageBox.warning(self, "Projektstände nicht lesbar", str(exc))
            return
        if not entries:
            QMessageBox.information(self, "Projektstände", "Für diese Aufnahme gibt es noch keine Projektstände.")
            return
        labels = [
            f"{number:02d} · {entry.created_at[:19].replace('T', ' ')} · {entry.name}"
            + (" (mit Analyse)" if entry.has_analysis else " (nur Spuren)")
            for number, entry in enumerate(entries, start=1)
        selected, accepted = QInputDialog.getItem(
            self, "Projektstand wiederherstellen", "Gesicherter Stand:", labels, 0, False)
        if not accepted:
            return
        idx = labels.index(selected)
        answer = QMessageBox.question(
            self, "Projektstand wiederherstellen",
            "Der ausgewählte Projektstand ersetzt den aktuellen Spurplan und "
            "die aktuelle Analyse. Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        # Validate the complete snapshot and persist its track plan BEFORE
        # touching visible editor state. Analysis is recovered by autosave.
        try:
            project, analysis = load_checkpoint(self.editor_project.source, entries[idx].id)
            save_project(project)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "Projektstand nicht wiederhergestellt", str(exc))
            return
        self._autosave_timer.stop()
        self.editor_project = project
        self._project_history = ProjectHistory()
        self._edit_history.clear()
        self._refresh_track_tables()
        self.report_path = None
        if analysis is not None:
            self.analysis_finished(analysis)
            self.transcript_dirty = True
            self._autosave_timer.start()
            self.autosave_hint.setText("● Wiederhergestellt · Auto-Sicherung folgt")
        else:
            self.analysis = None
            self.table.setRowCount(0)
            self.transcript_table.setRowCount(0)
            self.timeline.set_annotations([], [])
            self.transcript_dirty = False
            self._word_ref = None
            self._word_refs = []
            self.word_text.clear()
            self.word_editor_toggle.setChecked(False)
            self.reset_transcript_editor()
            self._update_history_controls()
            if self.source:
                try:
                    clear_autosave(self.source)
                except OSError:
                    pass
            self.autosave_hint.setText("✓ Spurplan aus Projektstand geladen")
        self.track_status.setText("✓ Projektstand geladen · Original unverändert")
        self.statusBar().showMessage(f"Projektstand „{entries[idx].name}“ wiederhergestellt")

    def _selected_track_id(self) -> str | None:
        if not self.editor_project:
            return None
        index = self.tracks_table.currentRow()
        if 0 <= index < len(self.editor_project.tracks):
            return self.editor_project.tracks[index].id
        return None

    def _selected_clip_id(self) -> str | None:
        if not self.editor_project:
            return None
        index = self.track_clips_table.currentRow()
        if 0 <= index < len(self.editor_project.items):
            return self.editor_project.items[index].id
        return None

    def _refresh_track_tables(self) -> None:
        project = self.editor_project
        old_track = self._selected_track_id()
        old_clip = self._selected_clip_id()
        self.tracks_table.blockSignals(True)
        self.track_clips_table.blockSignals(True)
        try:
            self.tracks_table.setRowCount(len(project.tracks) if project else 0)
            self.track_clips_table.setRowCount(len(project.items) if project else 0)
            if project:
                for row, track in enumerate(project.tracks):
                    kind = {"video":"Video", "audio":"Audio",
                            "captions":"Untertitel", "overlay":"Grafik"}[track.kind]
                    values = (track.name, kind, "Ja" if track.muted else "Nein",
                              "Ja" if track.locked else "Nein",
                              str(sum(item.track_id == track.id for item in project.items)))
                    for col, value in enumerate(values):
                        self.tracks_table.setItem(row, col, QTableWidgetItem(value))
                for row, item in enumerate(project.items):
                    names = {track.id: track.name for track in project.tracks}
                    values = (item.label or item.id, names[item.track_id],
                              format_timestamp(item.source_start),
                              format_timestamp(item.source_end),
                              format_timestamp(item.timeline_start))
                    for col, value in enumerate(values):
                        self.track_clips_table.setItem(row, col, QTableWidgetItem(value))
                for row, track in enumerate(project.tracks):
                    if track.id == old_track:
                        self.tracks_table.selectRow(row)
                for row, item in enumerate(project.items):
                    if item.id == old_clip:
                        self.track_clips_table.selectRow(row)
        finally:
            self.tracks_table.blockSignals(False)
            self.track_clips_table.blockSignals(False)
        self.track_canvas.set_project(project)
        if self._source_duration > 0:
            self.track_canvas.set_visible_range(*self.timeline.visible())
        self.track_canvas.set_selected_clip(old_clip)
        self._update_track_actions()

    def _select_project_track(self, track_id: str) -> None:
        if not self.editor_project:
            return
        for row, track in enumerate(self.editor_project.tracks):
            if track.id == track_id:
                self.tracks_table.selectRow(row)
                return

    def _select_project_clip(self, item_id: str) -> None:
        if not self.editor_project:
            return
        for row, item in enumerate(self.editor_project.items):
            if item.id == item_id:
                self.track_clips_table.selectRow(row)
                return

    def _track_clip_selection_changed(self) -> None:
        self.track_canvas.set_selected_clip(self._selected_clip_id())
        self._update_track_actions()

    def _drag_project_clip(self, item_id: str, position: float) -> None:
        self._apply_project_edit(edit_item, item_id, timeline_start=position)

    def _update_track_actions(self) -> None:
        if not hasattr(self, "track_add_button"):
            return
        ready = self.editor_project is not None
        selected = self._selected_track_id()
        clip = self._selected_clip_id()
        for control in (self.track_add_button,):
            control.setEnabled(ready)
        for control in (self.track_rename_button, self.track_remove_button,
                        self.track_mute_button, self.track_lock_button,
                        self.track_up_button, self.track_down_button):
            control.setEnabled(bool(selected))
        self.track_clip_add.setEnabled(bool(selected) and self._source_duration > 0)
        self.track_clip_move.setEnabled(bool(clip))
        self.track_clip_trim.setEnabled(bool(clip))
        self.track_undo_button.setEnabled(ready and self._project_history.can_undo)
        self.track_redo_button.setEnabled(ready and self._project_history.can_redo)

    def _apply_project_edit(self, action, *args, **kwargs) -> bool:
        if not self.editor_project:
            return False
        before = self.editor_project
        try:
            after = action(before, *args, **kwargs)
            if after == before:
                return True
            save_project(after)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Spuränderung nicht gespeichert", str(exc))
            return False
        self._project_history.record(before, after)
        self.editor_project = after
        self._refresh_track_tables()
        self.track_status.setText("✓ Spurplan lokal gespeichert · Original unverändert")
        return True

    def _add_track_dialog(self) -> None:
        types = {"Videospur": "video", "Audiospur": "audio",
                 "Untertitelspur": "captions", "Grafikspur": "overlay"}
        label, accepted = QInputDialog.getItem(
            self, "Spur hinzufügen", "Spurtyp", list(types), 1, False)
        if not accepted:
            return
        name, accepted = QInputDialog.getText(self, "Spur hinzufügen", "Spurname")
        if accepted:
            self._apply_project_edit(add_track, types[label], name)

    def _rename_selected_track(self) -> None:
        track_id = self._selected_track_id()
        if not track_id or not self.editor_project:
            return
        current = next(t for t in self.editor_project.tracks if t.id == track_id)
        name, accepted = QInputDialog.getText(
            self, "Spur umbenennen", "Name", text=current.name)
        if accepted:
            self._apply_project_edit(rename_track, track_id, name)

    def _remove_selected_track(self) -> None:
        track_id = self._selected_track_id()
        if track_id:
            self._apply_project_edit(remove_track, track_id)

    def _toggle_selected_track(self, field: str) -> None:
        track_id = self._selected_track_id()
        if track_id:
            self._apply_project_edit(toggle_track, track_id, field)

    def _move_selected_track(self, direction: int) -> None:
        track_id = self._selected_track_id()
        if track_id:
            self._apply_project_edit(move_track, track_id, direction)

    def _add_selected_track_clip(self) -> None:
        track_id = self._selected_track_id()
        if not track_id:
            return
        a, b = self.timeline.in_point, self.timeline.out_point
        self._apply_project_edit(add_item, track_id, a, b, a,
                                 f"Ausschnitt {format_timestamp(a)}")

    def _move_selected_track_clip(self) -> None:
        item_id = self._selected_clip_id()
        if not item_id or not self.editor_project:
            return
        item = next(i for i in self.editor_project.items if i.id == item_id)
        names = [f"{track.name} ({track.id})" for track in self.editor_project.tracks]
        selected, accepted = QInputDialog.getItem(
            self, "Clip verschieben", "Zielspur", names,
            next((n for n,t in enumerate(self.editor_project.tracks)
                  if t.id == item.track_id), 0), False)
        if not accepted:
            return
        track_id = self.editor_project.tracks[names.index(selected)].id
        position, accepted = QInputDialog.getDouble(
            self, "Clip verschieben", "Position in Timeline (Sekunden)",
            item.timeline_start, 0, 86400, 3)
        if accepted:
            self._apply_project_edit(edit_item, item_id, track_id=track_id,
                                     timeline_start=position)

    def _trim_selected_track_clip(self) -> None:
        item_id = self._selected_clip_id()
        if not item_id or not self.editor_project:
            return
        item = next(i for i in self.editor_project.items if i.id == item_id)
        limit = self.editor_project.source.duration
        start, accepted = QInputDialog.getDouble(
            self, "Clip trimmen", "Quellbeginn (Sekunden)",
            item.source_start, 0, limit, 3)
        if not accepted:
            return
        end, accepted = QInputDialog.getDouble(
            self, "Clip trimmen", "Quellende (Sekunden)",
            item.source_end, 0, limit, 3)
        if accepted:
            self._apply_project_edit(edit_item, item_id,
                                     source_start=start, source_end=end)

    def _undo_project(self) -> None:
        if not self.editor_project or not self._project_history.can_undo:
            return
        before = self._project_history.undo(self.editor_project)
        try:
            save_project(before)
        except (OSError, ValueError) as exc:
            self._project_history.redo(before)
            QMessageBox.warning(self, "Spuraktion nicht gespeichert", str(exc))
            return
        self.editor_project = before
        self._refresh_track_tables()
        self.track_status.setText("↶ Spuraktion rückgängig und gesichert")

    def _redo_project(self) -> None:
        if not self.editor_project or not self._project_history.can_redo:
            return
        after = self._project_history.redo(self.editor_project)
        try:
            save_project(after)
        except (OSError, ValueError) as exc:
            self._project_history.undo(after)
            QMessageBox.warning(self, "Spuraktion nicht gespeichert", str(exc))
            return
        self.editor_project = after
        self._refresh_track_tables()
        self.track_status.setText("↷ Spuraktion wiederholt und gesichert")

    def toggle_word_editor(self, expanded: bool) -> None:
        self.word_editor_panel.setVisible(expanded)
        self.word_editor_toggle.setText(
            "▾ Worteditor ausblenden" if expanded else "▸ Worteditor einblenden")

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
        self._autosave_timer.stop()
        self._edit_history.clear()
        self.editor_project = None
        self._project_history = ProjectHistory()
        self._refresh_track_tables()
        self._update_checkpoint_actions()
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
        self.word_editor_toggle.setChecked(False)
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
        self.autosave_hint.setText("Auto-Sicherung bereit")
        self._update_history_controls()
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
        if not preserve and self.analysis is None:
            self._offer_autosave_recovery(video)
        if self.editor_project is None:
            self._open_editor_project(video)

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
        self.track_canvas.set_visible_range(*self.timeline.visible())

    def timeline_scroll_changed(self, value: int):
        self.timeline.set_offset(float(value))
        self.track_canvas.set_visible_range(*self.timeline.visible())

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
        self.word_editor_toggle.setChecked(True)
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
        previous = self.analysis
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
        self._register_edit(previous)
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
        previous = self.analysis
        try:
            self.analysis = trim_manual_highlight(
                self.analysis, index, self.timeline.in_point, self.timeline.out_point)
        except ValueError as exc:
            QMessageBox.warning(self, "Schnittbereich ungültig", str(exc))
            return
        self._register_edit(previous)
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

    def select_model_preset(self, kind: str) -> None:
        selected = self.model_selectors[kind].currentData()
        getattr(self, f'{kind}_path').setText(str(preset_path(selected)))
        self.statusBar().showMessage(
            f'{preset(selected).label}: '+('installiert' if is_installed(selected)
                                          else 'noch nicht installiert – Herunterladen klicken'))

    def download_selected_model(self, kind: str) -> None:
        if self.model_worker and self.model_worker.isRunning():
            return
        model_id = self.model_selectors[kind].currentData()
        item = preset(model_id)
        choice = QMessageBox.question(
            self, 'Modell herunterladen',
            f'„{item.label}“ von {item.repository} aus dem Internet herunterladen?\n'
            f'Ziel: {preset_path(model_id)}\n\n'
            'Je nach Variante werden mehrere hundert MB bis einige GB benötigt. '
            'Das Modell wird nur nach deiner Zustimmung geladen.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice != QMessageBox.StandardButton.Yes:
            return
        self.model_worker = ModelDownloadThread(model_id, self)
        self.model_worker.done.connect(self.model_download_finished)
        self.model_worker.failed.connect(self.model_download_failed)
        self.model_worker.finished.connect(lambda: self._busy(False))
        for button in self.model_download_buttons.values():
            button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.statusBar().showMessage(f'Lade {item.label} (expliziter Online-Download) …')
        self.model_worker.start()

    def model_download_finished(self, model_id: str, folder: str) -> None:
        item = preset(model_id)
        getattr(self, f'{item.kind}_path').setText(folder)
        self.statusBar().showMessage(f'Bereit und überprüft: {item.label}')
        QMessageBox.information(self, 'Modell bereit', f'{item.label}\n{folder}')

    def model_download_failed(self, model_id: str, error: str) -> None:
        self.statusBar().showMessage('Modelldownload fehlgeschlagen')
        QMessageBox.warning(self, 'Modelldownload fehlgeschlagen',
                            f'{preset(model_id).label}\n{error}')

    def choose_model(self, target: QLineEdit) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Lokales Modellverzeichnis auswählen")
        if directory:
            target.setText(directory)

    def edit_highlight_words(self) -> None:
        try:
            dialog = HighlightLexiconDialog(self)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Wortliste nicht lesbar", str(exc))
            return
        dialog.exec()

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
        detector = self.detector_path.text().strip() if self.detector_enabled.isChecked() else None
        if (self.speech_enabled.isChecked() and not speech) or (self.vision_enabled.isChecked() and not vision) or (self.detector_enabled.isChecked() and not detector):
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
        if detector:
            try:
                validate_model_dir('detector', detector)
            except (FileNotFoundError, ValueError) as exc:
                QMessageBox.warning(self, 'Objektmodell unvollständig', str(exc))
                return
        if speech:
            try:
                validate_model_dir('speech', speech)
            except (FileNotFoundError, ValueError) as exc:
                QMessageBox.warning(self, 'Whisper-Modell unvollständig', str(exc))
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
                                     speech_model=speech, vision_model=vision,
                                     detector_model=detector)
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

    def analysis_finished(self, result: AnalysisResult, *, preserve_history: bool = False) -> None:
        if not preserve_history:
            self._edit_history.clear()
        preserved_manual = bool(self._manual_pending) and not preserve_history
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
        self.transcript_dirty = preserved_manual or preserve_history
        self.timeline.set_annotations(result.candidates, result.transcript)
        self._word_ref = None
        self._refresh_word_refs()
        self._active_caption = None
        self._update_caption_overlay(self.player.position()/1000)
        self._editor_row = None
        self._busy(False)
        self._update_history_controls()
        if preserved_manual:
            self._autosave_timer.start()
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
        previous = self.analysis
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
        self._register_edit(previous)
        self._busy(False)
        self.statusBar().showMessage("Manuelles Highlight hinzugefügt – Projekt speichern")

    def delete_selected_manual_highlight(self) -> None:
        if not self.analysis:
            return
        previous = self.analysis
        try:
            self.analysis = remove_manual_highlight(self.analysis, self.table.currentRow())
        except ValueError as exc:
            QMessageBox.warning(self, "Highlight kann nicht gelöscht werden", str(exc))
            return
        self.refresh_highlight_table()
        self._register_edit(previous)
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
        previous = self.analysis
        self.analysis = new_result
        self._register_edit(previous)
        cue = new_result.transcript[row]
        self.transcript_table.blockSignals(True)
        try:
            for col, val in enumerate((format_timestamp(cue.start),
                                       format_timestamp(cue.end), cue.text)):
                self.transcript_table.item(row, col).setText(val)
        finally:
            self.transcript_table.blockSignals(False)
        self.fill_transcript_editor(row)
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
        self._autosave_timer.stop()
        if self.source:
            try:
                clear_autosave(self.source)
            except OSError:
                pass  # manual report is safe; stale recovery can be removed later
        self.autosave_hint.setText("✓ Projekt gespeichert")
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
        if answer == QMessageBox.StandardButton.Discard:
            self._autosave_timer.stop()
            if self.source:
                try:
                    clear_autosave(self.source)
                except OSError:
                    pass
            return True
        return False

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
        if self.model_worker and self.model_worker.isRunning():
            QMessageBox.information(self, 'Modelldownload läuft',
                                    'Der Modelldownload muss vor dem Schließen abgeschlossen werden.')
            event.ignore()
            return
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
