"""Windows desktop UI; analysis and export run off the UI thread."""
from __future__ import annotations

import sys
import threading
import subprocess
import os
from pathlib import Path

from .portable import configure_portable_environment

configure_portable_environment()

from PySide6.QtCore import QByteArray, QEvent, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDockWidget, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSlider, QSpinBox,
    QInputDialog,
    QDoubleSpinBox, QFormLayout, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget, QScrollArea,
)

from .analyze import analyze
from .media import (CancelledError, probe_video, probe_audio_duration,
                    probe_still_image, safe_destination, tool_path,
                    waveform_peaks)
from .render_contract import RenderRequest, render_request
from .render_queue import RenderQueue, QueueJob
from .export_qa import read_report
from .rendered_preview import RenderedPreview, render_clip_preview
from .model_checks import validate_clip_model
from .model_catalog import (DEFAULTS, download_preset, is_installed, preset,
                            preset_path, presets_for, validate_model_dir, safe_hf_error)
from .model_download_progress import format_bytes
from .hf_credentials import (supported as hf_store_supported,
    read_token as read_hf_credential, save_token as save_hf_credential,
    remove_token as remove_hf_credential)
from .models import AnalysisResult, Candidate, VideoInfo
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
from .caption_style import CaptionStyle
from .subtitle_translation import export_transcript
from .highlight_lexicon_dialog import HighlightLexiconDialog
from .editor_project import (EditorProject, initial_project,
    add_track, remove_track, rename_track, move_track, toggle_track,
    add_item, edit_item, remove_item, load_project, save_project, Track,
    set_scene_plan, scene_plan_for, set_caption_style, update_callout)
from .track_canvas import TrackCanvas
from .editor_theme import EDITOR_STYLESHEET
from .workspace_layout import (WORKSPACE_NAMES, WorkspaceLayout,
                               save_workspace, load_workspace, delete_workspace)
from .proxy import (
    ProxyState, cached_proxy, ensure_proxy, original_to_proxy_ms,
    proxy_to_original_ms)
from .highlight_import import import_analysis_candidates
from .project_checkpoints import create_checkpoint, list_checkpoints, load_checkpoint

from .edit_history import WorkspaceHistory
from .autosave import autosave_path, clear_autosave, load_autosave, save_autosave


def render_transcript(analysis,start,end,scene_plan,burn,offset):
    if not burn:
        return tuple(analysis.transcript)
    intervals=[(s.start,s.end) for s in scene_plan.output_scenes] if scene_plan else [(start,end)]
    return export_transcript(analysis,intervals,offset=offset)


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
    encoder_notice = Signal(str)

    def __init__(self, analysis: AnalysisResult, items: list[Candidate], directory: str,
                 mode: str, parent=None, burn_subtitles: bool = False,
                 subtitle_offset: float = 0.0,
                 project: EditorProject | None = None,
                 encoder: str = "cpu_h264", scene_plans=(), caption_style=CaptionStyle()):
        super().__init__(parent)
        self.scene_plans = tuple(scene_plans)
        self.caption_style = caption_style
        self.analysis = analysis
        self.items = items
        self.directory = directory
        self.mode = mode
        self.burn_subtitles = burn_subtitles
        self.subtitle_offset = subtitle_offset
        self.project = project
        self.encoder = encoder
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
                scene_plan=next((p for p in self.scene_plans if
                        (p.start,p.end)==(clip.start,clip.end)),None)
                transcript=render_transcript(self.analysis,clip.start,clip.end,scene_plan,
                                              self.burn_subtitles,self.subtitle_offset)
                request = RenderRequest(
                    video=self.analysis.video,
                    start=clip.start, end=clip.end, mode=self.mode,
                    burn_subtitles=self.burn_subtitles and bool(transcript),
                    subtitle_offset=self.subtitle_offset,
                    transcript=transcript,
                    project=self.project, encoder=self.encoder,
                    caption_style=self.caption_style,
                    scene_plan=scene_plan)
                actual = render_request(
                    request, target, cancelled=self._cancelled.is_set,
                    progress=lambda value, i=i: self.progress_changed.emit(
                        round(((i - 1) + value / 100) / len(self.items) * 100)
                    ),
                    encoder_notice=self.encoder_notice.emit,
                )
                outputs.append(str(actual))
            self.done.emit(outputs)
        except Exception as exc:
            self.failed.emit(str(exc))


class QueueRunThread(QThread):
    """Exactly one persistent queue worker; never touch QWidget from run()."""
    changed = Signal(object)
    info = Signal(str)
    finished_jobs = Signal(object)
    failed = Signal(str)

    def __init__(self, queue: RenderQueue, parent=None):
        super().__init__(parent)
        self.queue = queue
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()
        self.queue.cancel()

    def run(self) -> None:
        try:
            while not self._stop.is_set():
                item = self.queue.run_next(
                    progress=self.changed.emit, notice=self.info.emit)
                if item is None:
                    break
                self.changed.emit(item)
            self.finished_jobs.emit(self.queue.jobs())
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
    """HF model download; byte updates and cancellation stay off the GUI."""
    done = Signal(str, str)
    failed = Signal(str, str)
    was_cancelled = Signal(str)
    progress_changed = Signal(object)

    def __init__(self, model_id: str, parent=None, *, token: str | None = None):
        super().__init__(parent)
        self.model_id = model_id
        self.token = token
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            def report(percent, transferred, total, stage):
                self.progress_changed.emit(
                    (self.model_id, percent, transferred, total, stage))
            destination = download_preset(
                self.model_id, token=self.token, progress=report,
                cancelled=self._cancelled.is_set)
            self.done.emit(self.model_id, str(destination))
        except CancelledError:
            self.was_cancelled.emit(self.model_id)
        except Exception as exc:
            self.failed.emit(self.model_id, safe_hf_error(exc))
        finally:
            # No credentials in persistent settings, logs or GUI progress.
            self.token = None


class HfTokenCheckThread(QThread):
    """A token check is a user-initiated network request, never UI-blocking."""
    checked = Signal(str)
    failed = Signal(str)

    def __init__(self, token: str | None, parent=None):
        super().__init__(parent)
        self.token = token

    def run(self) -> None:
        try:
            from huggingface_hub import HfApi
            details = HfApi().whoami(token=self.token)
            # Do not surface arbitrary response data or exception messages.
            self.checked.emit("Verbindung bestätigt" if isinstance(details, dict)
                              else "Verbindung bestätigt")
        except Exception as exc:
            self.failed.emit(safe_hf_error(exc))
        finally:
            self.token = None


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


class ProxyThread(QThread):
    """Small preview transcode stays off the Qt UI thread."""
    progress_changed = Signal(int)
    done = Signal(str, object)
    failed = Signal(str, str)
    was_cancelled = Signal(str)

    def __init__(self, video: VideoInfo, parent=None) -> None:
        super().__init__(parent)
        self.video = video
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            result = ensure_proxy(
                self.video, cancelled=self._cancelled.is_set,
                progress=self.progress_changed.emit)
            if self._cancelled.is_set():
                self.was_cancelled.emit(self.video.path)
            else:
                self.done.emit(self.video.path, result)
        except CancelledError:
            self.was_cancelled.emit(self.video.path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.failed.emit(self.video.path, str(exc))


class RenderPreviewThread(QThread):
    """Prepare an export-identical short clip away from the UI thread."""
    progress_changed = Signal(int)
    done = Signal(object)
    failed = Signal(str)
    was_cancelled = Signal()
    encoder_notice = Signal(str)

    def __init__(self, request: RenderRequest, parent=None):
        super().__init__(parent)
        self.request = request
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            outcome = render_clip_preview(
                self.request, progress=self.progress_changed.emit,
                cancelled=self._cancelled.is_set,
                encoder_notice=self.encoder_notice.emit)
            self.done.emit(outcome)
        except CancelledError:
            self.was_cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class RenderedClipDialog(QDialog):
    """Separate playback keeps source/proxy timeline positions untouched.

    The temporary file exists only while this viewer owns it.
    """
    def __init__(self, result: RenderedPreview, temporary, parent=None):
        super().__init__(parent)
        self.setWindowTitle("StreamClipper – exportgetreue Clipvorschau")
        self.resize(800, 610)
        self._temporary = temporary
        self._released = False
        main = QVBoxLayout(self)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(.65)
        self.player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumHeight(320)
        self.player.setVideoOutput(self.video_widget)
        main.addWidget(self.video_widget, 1)
        controls = QHBoxLayout()
        self.play_button = QPushButton("▶ Wiedergabe / Pause")
        self.play_button.clicked.connect(self._toggle_play)
        controls.addWidget(self.play_button)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        controls.addWidget(self.seek, 1)
        self.time_label = QLabel("00:00:00")
        controls.addWidget(self.time_label)
        main.addLayout(controls)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(
            lambda value: self.seek.setRange(0, max(1, value)))
        scope = ("erste 20 Sekunden des Bereichs" if result.excerpt_of_longer_clip
                 else "gesamter ausgewählter Bereich")
        self.scope_label = QLabel(
            f"Render-Vorschau: {scope} · Originalzeit "
            f"{display_time(result.request.start)}–{display_time(result.request.end)}")
        if result.request.scene_plan is not None:
            self.scope_label.setText(f"Render-Vorschau: {result.request.duration:.2f} s · "
                                     f"{len(result.request.scene_plan.output_scenes)} Szenen in Ausgabereihenfolge")
        self.scope_label.setWordWrap(True)
        main.addWidget(self.scope_label)
        disclaimer = QLabel(
            "Derselbe FFmpeg-Renderpfad wie beim MP4-Export: Crop, dynamische "
            "Kamera und optional eingebrannte Untertitel. "
            + ("Mit aktivierten Projektspuren: Mikrofon/Musik, "
               "PiP-Video und Grafik-Overlays. "
               if result.request.project is not None else
               "Ohne Projektspuren; nur die Originalaufnahme. ")
            + "Timeline-Caption-Clips und Keyframes noch nicht unterstützt.")
        disclaimer.setWordWrap(True)
        main.addWidget(disclaimer)
        close = QPushButton("Vorschau schließen und temporäre Datei entfernen")
        close.clicked.connect(self.close)
        main.addWidget(close)
        self.player.setSource(QUrl.fromLocalFile(str(result.path)))

    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _position_changed(self, pos: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        self.time_label.setText(display_time(pos / 1000))

    def closeEvent(self, event) -> None:
        self.player.stop()
        self.player.setSource(QUrl())
        if not self._released:
            self._released = True
            try:
                self._temporary.cleanup()
            except OSError:
                # Windows backends can temporarily hold a decoder handle.
                # Do not block app shutdown; the temporary directory stays
                # clearly marked under data/tmp for later manual cleanup.
                pass
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StreamClipper Studio | Schnitt & Highlights")
        self.resize(1440, 920)
        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AnimatedDocks)
        self._workspace_name = "Highlights"
        self._default_dock_state: QByteArray | None = None
        self.render_queue: RenderQueue | None = None
        self.queue_worker: QueueRunThread | None = None
        self.source: str | None = None
        self.analysis: AnalysisResult | None = None
        self.worker: AnalysisThread | ExportThread | TwitchImportThread | RenderPreviewThread | None = None
        self._render_preview_dialog: RenderedClipDialog | None = None
        self.preview_end: float | None = None
        self.transcript_dirty = False
        self.report_path: str | None = None
        self._editor_row: int | None = None
        self._manual_from: float | None = None
        self._manual_to: float | None = None
        self._manual_pending: list[Candidate] = []
        self._waveform_workers: list[WaveformThread] = []
        self.model_worker: ModelDownloadThread | None = None
        self.hf_check_worker: HfTokenCheckThread | None = None
        self._hf_session_token: str | None = None
        self._source_duration: float = 0.0
        self._video_info: VideoInfo | None = None
        self._proxy_state: ProxyState | None = None
        self._proxy_active = False
        self._preview_switching = False
        self._proxy_pending_original_ms = 0
        self._proxy_resume_playing = False
        self.proxy_worker: ProxyThread | None = None
        self._active_caption: str | None = None
        self._word_ref: tuple[int, int] | None = None
        self._word_refs: list[tuple[int, int]] = []
        self._last_timeline_range: tuple[float, float] = (0.0, 25.0)
        self._history = WorkspaceHistory()
        self._history_blocked = False
        self.editor_project: EditorProject | None = None
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
        self.player.mediaStatusChanged.connect(self._proxy_media_status_changed)

        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(10, 8, 10, 8)
        main.setSpacing(8)
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
        studio_label = QLabel("STREAMCLIPPER  /  STUDIO")
        studio_label.setStyleSheet(
            "color: #91BBDD; font-weight: 700; letter-spacing: 1px;")
        toolbar.addWidget(studio_label)
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
        toolbar.addWidget(QLabel("Arbeitsbereich"))
        self.workspace_picker = QComboBox()
        self.workspace_picker.setObjectName("streamclipper.workspacePicker")
        for workspace in WORKSPACE_NAMES:
            self.workspace_picker.addItem(workspace)
        self.workspace_picker.currentTextChanged.connect(self._activate_workspace)
        toolbar.addWidget(self.workspace_picker)
        self.highlight_words_button = QPushButton("Highlight-Wörter …")
        self.highlight_words_button.setToolTip("Eigene sprachliche Highlight-Ausdrücke und Gewichtungen verwalten")
        self.highlight_words_button.clicked.connect(self.edit_highlight_words)
        models_page_layout.addWidget(self.highlight_words_button)
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

        hf_row = QHBoxLayout()
        hf_row.addWidget(QLabel("Hugging Face Token (optional)"))
        self.hf_token_input = QLineEdit()
        self.hf_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_token_input.setPlaceholderText("hf_… (wird nicht angezeigt oder protokolliert)")
        self.hf_token_input.setToolTip("Token nur für die Sitzung; öffentlicher Download ohne Token möglich.")
        hf_row.addWidget(self.hf_token_input, 1)
        self.hf_use_token = QPushButton("Übernehmen")
        self.hf_use_token.clicked.connect(self._apply_hf_token)
        hf_row.addWidget(self.hf_use_token)
        models_page_layout.addLayout(hf_row)

        hf_buttons = QHBoxLayout()
        self.hf_persist_token = QCheckBox("In Windows-Anmeldeinformationen sichern (optional)")
        self.hf_persist_token.setEnabled(hf_store_supported())
        self.hf_persist_token.setToolTip(
            "Nur mit ausdrücklicher Auswahl. Sonst bleibt dein Token in dieser Sitzung.")
        hf_buttons.addWidget(self.hf_persist_token)
        self.hf_check_button = QPushButton("Verbindung prüfen")
        self.hf_check_button.clicked.connect(self._check_hf_token)
        hf_buttons.addWidget(self.hf_check_button)
        self.hf_remove_button = QPushButton("Entfernen")
        self.hf_remove_button.clicked.connect(self._remove_hf_token)
        hf_buttons.addWidget(self.hf_remove_button)
        models_page_layout.addLayout(hf_buttons)
        self.hf_status = QLabel("Kein Sitzungstoken · öffentliche Modelle ohne Anmeldung möglich")
        self.hf_status.setWordWrap(True)
        models_page_layout.addWidget(self.hf_status)
        self._refresh_hf_status()
        models_page_layout.addStretch()

        self.source_label = QLabel("Noch kein Video geladen. Videos bleiben lokal auf deinem Rechner.")
        self.source_label.setWordWrap(True)
        main.addWidget(self.source_label)

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
        proxy_row = QHBoxLayout()
        proxy_row.addWidget(QLabel("Vorschau"))
        self.proxy_mode = QComboBox()
        self.proxy_mode.addItem("Original", "original")
        self.proxy_mode.addItem("Proxy (480p)", "proxy")
        self.proxy_mode.currentIndexChanged.connect(self._select_preview_source)
        proxy_row.addWidget(self.proxy_mode)
        self.proxy_create = QPushButton("Proxy erstellen")
        self.proxy_create.setToolTip(
            "Kleine lokale Vorschau erzeugen, unabhängig vom Original-Export")
        self.proxy_create.clicked.connect(self._create_proxy)
        proxy_row.addWidget(self.proxy_create)
        self.proxy_cancel = QPushButton("Abbrechen")
        self.proxy_cancel.clicked.connect(self._cancel_proxy)
        proxy_row.addWidget(self.proxy_cancel)
        preview_layout.addLayout(proxy_row)
        self.proxy_progress = QProgressBar()
        self.proxy_progress.setRange(0, 100)
        self.proxy_progress.setValue(0)
        self.proxy_progress.setMaximumHeight(12)
        preview_layout.addWidget(self.proxy_progress)
        self.proxy_status = QLabel(
            "Proxy optional · Schnittmarken und Export nutzen immer das Original.")
        self.proxy_status.setWordWrap(True)
        preview_layout.addWidget(self.proxy_status)
        preview_layout.addWidget(QLabel(
            "Vorschau: Originalbild + Untertitel. 16:9/9:16-Reframing erst im Export."
        ))
        preview_container.setObjectName("streamclipper.programMonitor")
        main.addWidget(preview_container, 1)

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
        # M12b opt-in sound layers; video/overlay clips remain metadata.
        self.tracks_page = QScrollArea()
        self.tracks_page.setWidgetResizable(True)
        tracks_content = QWidget()
        tracks_layout = QVBoxLayout(tracks_content)
        self.tracks_page.setWidget(tracks_content)
        tracks_intro = QLabel(
            "Gameplay bleibt das Basisvideo. Externe Facecam-Videos auf einer "
            "zusätzlichen Videospur und PNG/JPEG/WebP-Logos auf einer Grafikspur "
            "werden als zeitlich begrenzte PiP-/Overlay-Ebenen gerendert. "
            "Originalton und lokale Audio-Spurclips sind separat mischbar. "
            "Projektspuren im Export ausdrücklich aktivieren.")
        tracks_intro.setWordWrap(True)
        tracks_layout.addWidget(tracks_intro)
        import_row = QHBoxLayout()
        self.track_import_button = QPushButton("★ Highlights übernehmen …")
        self.track_import_button.setToolTip(
            "Vorhandene Analyse-Highlights auf Wunsch als Spurclips importieren; "
            "Original und Export bleiben unverändert.")
        self.track_import_button.clicked.connect(self._import_analysis_highlights)
        import_row.addWidget(self.track_import_button)
        import_row.addWidget(QLabel(
            "Audio + PiP/Grafiken per gemeinsamer Rendergraph · opt-in"), 1)
        tracks_layout.addLayout(import_row)
        self.track_canvas = TrackCanvas()
        self.track_canvas.trackSelected.connect(self._select_project_track)
        self.track_canvas.clipSelected.connect(self._select_project_clip)
        self.track_canvas.clipMoved.connect(self._drag_project_clip)
        tracks_layout.addWidget(QLabel(
            "Grafische Spuren: unten in der gemeinsamen Timeline · "
            "die Tabellen hier bleiben für präzise Verwaltung verfügbar."))
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
        self.track_clips_table = QTableWidget(0, 6)
        self.track_clips_table.setMinimumHeight(125)
        self.track_clips_table.setHorizontalHeaderLabels(
            ["Clip", "Spur", "Quelle IN", "Quelle OUT", "Timeline IN", "Medium / Pegel"])
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
        self.track_clip_delete = QPushButton("Clip entfernen")
        self.track_clip_delete.setToolTip(
            "Entfernt nur den gewählten Timeline-Clip, niemals dessen Mediendatei. "
            "Mit Strg+Z rückgängig machen.")
        self.track_clip_delete.clicked.connect(self._remove_selected_track_clip)
        self.track_audio_import = QPushButton("🎵 Audiodatei einfügen …")
        self.track_audio_import.setToolTip(
            "Lokale WAV/MP3/FLAC-Datei auf der gewählten Audiospur einfügen.")
        self.track_audio_import.clicked.connect(self._add_audio_file_to_track)
        self.track_visual_import = QPushButton("🎬 Video / Logo einfügen …")
        self.track_visual_import.setToolTip(
            "Externe Videodatei auf zusätzliche Videospur oder "
            "PNG/JPEG/WebP auf Grafikspur legen. Position/Größe im Inspector.")
        self.track_visual_import.clicked.connect(self._add_visual_file_to_track)
        self.track_gain_button = QPushButton("Pegel …")
        self.track_gain_button.clicked.connect(self._edit_selected_clip_gain)
        for control in (self.track_clip_add, self.track_clip_move,
                        self.track_clip_trim, self.track_clip_delete):
            row3.addWidget(control)
        tracks_layout.addLayout(row3)
        row4 = QHBoxLayout()
        for control in (self.track_audio_import, self.track_visual_import,
                        self.track_gain_button):
            row4.addWidget(control)
        tracks_layout.addLayout(row4)
        history_hint = QLabel(
            "Rückgängig / Wiederholen: Strg+Z / Strg+Umschalt+Z für alle Bearbeitungen.")
        history_hint.setWordWrap(True)
        tracks_layout.addWidget(history_hint)
        self.track_status = QLabel("Spuren werden mit der Videoquelle geladen.")
        self.track_status.setWordWrap(True)
        tracks_layout.addWidget(self.track_status)
        self.tabs.addTab(self.tracks_page, "Spuren")
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply_transcript_editor)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_report)
        # M12-UX: the same existing tool tabs are docked rather than
        # recreated, preserving all analysis/editor signal connections.
        self.project_dock = QDockWidget("PROJEKT / HIGHLIGHTS / WERKZEUGE", self)
        self.project_dock.setObjectName("streamclipper.projectDock")
        self.project_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea)
        self.project_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.project_dock.setWidget(results_container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)

        # Timeline lives in a separate movable/resizable bottom dock.
        # Scroll area prevents controls clipping on 1366x768 screens.
        timeline_scroll_host = QScrollArea()
        timeline_scroll_host.setObjectName("streamclipper.timelineScroller")
        timeline_scroll_host.setWidgetResizable(True)
        timeline_content = QWidget()
        timeline_layout = QVBoxLayout(timeline_content)
        timeline_layout.setContentsMargins(10, 8, 10, 8)
        timeline_layout.setSpacing(6)
        timeline_scroll_host.setWidget(timeline_content)
        self.timeline_dock = QDockWidget("SEQUENZ / TIMELINE", self)
        self.timeline_dock.setObjectName("streamclipper.timelineDock")
        self.timeline_dock.setAllowedAreas(
            Qt.DockWidgetArea.TopDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea)
        self.timeline_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.timeline_dock.setWidget(timeline_scroll_host)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_dock)
        # M6: zoomable waveform editing; existing player/timing stay unchanged.
        timeline_header = QHBoxLayout()
        timeline_header.addWidget(QLabel("TIMELINE · Wellenform / Clips / Untertitel"))
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
        self.timeline_snap = QCheckBox("Magnet")
        self.timeline_snap.setChecked(True)
        self.timeline_snap.setToolTip(
            "Spurclips an Playhead, IN/OUT und anderen Clipkanten einrasten "
            "(8 Pixel Toleranz).")
        self.timeline_snap.toggled.connect(self.track_canvas.set_snap_enabled)
        timeline_header.addWidget(self.timeline_snap)
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
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self._shortcut_undo)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.redo_shortcut.activated.connect(self._shortcut_redo)
        timeline_layout.addLayout(timeline_header)

        self.timeline = TimelineWidget()
        self.timeline.playheadMoved.connect(self.timeline_seek)
        self.timeline.selectionChanged.connect(self.timeline_range_changed)
        self.timeline.subtitleSelected.connect(self.timeline_select_subtitle)
        self.timeline.wordSelected.connect(self.select_timeline_word)
        self.timeline.wordBoundaryCommitted.connect(self.commit_timeline_word_edge)
        self.timeline.set_left_gutter(self.track_canvas._LEFT)
        self.unified_timeline = QSplitter(Qt.Orientation.Vertical)
        self.unified_timeline.setObjectName("streamclipper.unifiedTimeline")
        self.unified_timeline.addWidget(self.timeline)
        self.unified_timeline.addWidget(self.track_canvas)
        self.unified_timeline.setChildrenCollapsible(False)
        self.unified_timeline.setSizes([210, 280])
        timeline_layout.addWidget(self.unified_timeline, 1)
        self.track_canvas.set_playhead(0)
        self.timeline_scroll = QSlider(Qt.Orientation.Horizontal)
        self.timeline_scroll.setMinimum(0)
        self.timeline_scroll.setMaximum(0)
        self.timeline_scroll.valueChanged.connect(self.timeline_scroll_changed)
        timeline_layout.addWidget(self.timeline_scroll)

        # Integrated word editor: active highlight only, directly below the
        # waveform and word track. No separate transcription tab required.
        self.word_editor_toggle = QPushButton("▸ Worteditor einblenden")
        self.word_editor_toggle.setCheckable(True)
        self.word_editor_toggle.toggled.connect(self.toggle_word_editor)
        timeline_layout.addWidget(self.word_editor_toggle)
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
        timeline_layout.addWidget(self.word_editor_panel)
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
        timeline_layout.addLayout(clip_tools)

        actions = QVBoxLayout()
        actions.addWidget(QLabel("Exportformat"))
        self.mode = QComboBox()
        self.mode.addItem("16:9 – dynamische Kamera (sanfter Zoom)", "smart16")
        self.mode.addItem("9:16 – dynamischer Ausschnitt für TikTok", "smart9")
        self.mode.addItem("9:16 – ganzes Bild / unscharfer Hintergrund", "blur")
        self.mode.addItem("9:16 – fester Mittel-Ausschnitt", "crop")
        actions.addWidget(self.mode)
        actions.addWidget(QLabel("Video-Encoder · H.264 / HEVC"))
        self.encoder_mode = QComboBox()
        self.encoder_mode.setObjectName("streamclipper.encoderMode")
        self.encoder_mode.addItem(
            "Automatisch · H.264 NVENC → CPU-Fallback", "auto_h264")
        self.encoder_mode.addItem(
            "H.264 · nur CPU (kompatibel)", "cpu_h264")
        self.encoder_mode.addItem(
            "H.264 · nur NVIDIA NVENC", "nvenc_h264")
        self.encoder_mode.addItem(
            "Automatisch · HEVC NVENC → CPU-Fallback", "auto_hevc")
        self.encoder_mode.addItem(
            "HEVC · nur CPU", "cpu_hevc")
        self.encoder_mode.addItem(
            "HEVC · nur NVIDIA NVENC", "nvenc_hevc")
        self.encoder_mode.setToolTip(
            "NVENC nutzt die GPU als Encoder, nicht als Echtzeit-FX-Engine. "
            "Auto prüft den Encoder vor dem Start und versucht höchstens "
            "einmal CPU, falls NVENC während des Exports ausfällt. "
            "HEVC benötigt einen kompatiblen Player bzw. Plattform-Support.")
        actions.addWidget(self.encoder_mode)
        self.encoder_status = QLabel(
            "H.264 Auto · NVENC-Prüfung erst beim Rendern")
        self.encoder_status.setWordWrap(True)
        actions.addWidget(self.encoder_status)
        self.burn_subtitles = QCheckBox("Untertitel direkt ins Video")
        self.burn_subtitles.setChecked(True)
        self.burn_subtitles.setToolTip("Benötigt eine durch Whisper transkribierte Aufnahme.")
        actions.addWidget(self.burn_subtitles)
        self.include_track_audio = QCheckBox(
            "Projektspuren rendern · Audio / PiP / Grafiken (M12b Beta)")
        self.include_track_audio.setToolTip(
            "Originalaufnahme + ausdrücklich verknüpfte Ton-, Facecam- und "
            "Logo-Spurclips über denselben FFmpeg-Graphen für Vorschau/MP4. "
            "Reine Highlight-Metadaten und Timeline-Caption-Clips "
            "werden beim Rendern abgewiesen.")
        actions.addWidget(self.include_track_audio)
        self.render_preview_button = QPushButton("🎞 Exportgetreue Vorschau (bis 20 s)")
        self.render_preview_button.setToolTip(
            "Ausgewählten Bereich mit dem exakt gleichen FFmpeg-Rendergraphen "
            "wie beim MP4-Export bis maximal 20 Sekunden rendern.")
        self.render_preview_button.clicked.connect(self.start_render_preview)
        self.render_preview_button.setEnabled(False)
        actions.addWidget(self.render_preview_button)
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
        queue_title = QLabel("RENDERQUEUE  /  MP4-QUALITÄTSPRÜFUNG")
        queue_title.setStyleSheet(
            "color: #91BBDD; font-weight: 700; letter-spacing: 1px;")
        export_page_layout.addWidget(queue_title)
        queue_hint = QLabel(
            "Jobs werden lokal gespeichert; das Rendering beginnt erst mit "
            "„Queue starten“. Nach einem Absturz nicht automatisch neu rendern. "
            "Jede fertige MP4 bekommt einen geprüften .qa.json-Bericht.")
        queue_hint.setWordWrap(True)
        export_page_layout.addWidget(queue_hint)
        self.queue_table = QTableWidget(0, 4)
        self.queue_table.setObjectName("streamclipper.renderQueue")
        self.queue_table.setHorizontalHeaderLabels(
            ["Job", "Status", "Fortschritt", "Ergebnis / Hinweise"])
        self.queue_table.setMinimumHeight(180)
        self.queue_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.queue_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        self.queue_table.itemSelectionChanged.connect(self._refresh_queue)
        export_page_layout.addWidget(self.queue_table)
        queue_controls = QHBoxLayout()
        self.queue_selected_button = QPushButton("Auswahl einreihen")
        self.queue_selected_button.clicked.connect(
            lambda: self._queue_enqueue(False))
        self.queue_all_button = QPushButton("Alle Highlights einreihen")
        self.queue_all_button.clicked.connect(
            lambda: self._queue_enqueue(True))
        self.queue_open_button = QPushButton("Queue laden")
        self.queue_open_button.setToolTip(
            "Lokale Queue öffnen und unterbrochene Jobs nach Neustart anzeigen, "
            "ohne Rendering zu starten.")
        self.queue_open_button.clicked.connect(self._ensure_render_queue)
        self.queue_start_button = QPushButton("▶ Queue starten")
        self.queue_start_button.clicked.connect(self._queue_start)
        self.queue_cancel_button = QPushButton("■ Queue anhalten")
        self.queue_cancel_button.clicked.connect(self._queue_cancel)
        self.queue_retry_button = QPushButton("Auswahl fortsetzen")
        self.queue_retry_button.clicked.connect(self._queue_resume)
        self.queue_remove_button = QPushButton("Job verwerfen")
        self.queue_remove_button.clicked.connect(self._queue_discard)
        for control in (self.queue_selected_button, self.queue_all_button,
                        self.queue_open_button, self.queue_start_button,
                        self.queue_cancel_button,
                        self.queue_retry_button, self.queue_remove_button):
            queue_controls.addWidget(control)
        export_page_layout.addLayout(queue_controls)
        export_page_layout.addStretch()
        self.tabs.addTab(self.export_page, "Export")

        # Contextual inspector: read-only snapshot of the current selection.
        # Real trim, gain and transcript edits continue to use their original
        # controls; inspector never silently changes project data.
        self.inspector_dock = QDockWidget("EIGENSCHAFTEN / AUSWAHL", self)
        self.inspector_dock.setObjectName("streamclipper.inspectorDock")
        self.inspector_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea)
        self.inspector_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable)
        inspector_scroll = QScrollArea()
        inspector_scroll.setWidgetResizable(True)
        inspector_contents = QWidget()
        inspector_layout = QVBoxLayout(inspector_contents)
        inspector_layout.setContentsMargins(12, 12, 12, 12)
        inspector_layout.setSpacing(10)
        self.inspector_heading = QLabel("Keine Auswahl")
        self.inspector_heading.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #D9EBFC;")
        self.inspector_heading.setWordWrap(True)
        inspector_layout.addWidget(self.inspector_heading)
        self.inspector_details = QLabel(
            "Wähle einen Highlight- oder Timeline-Clip. "
            "Hier siehst du den aktuellen Zustand des Projekts.")
        self.inspector_details.setWordWrap(True)
        inspector_layout.addWidget(self.inspector_details)
        # Direct clip properties edit one immutable EditorProject delta through
        # the same atomic save + undo path used by the original Spuren tab.
        self._inspector_item_id: str | None = None
        self.inspector_edit_area = QWidget()
        property_form = QFormLayout(self.inspector_edit_area)
        property_form.setContentsMargins(0, 6, 0, 6)
        property_form.setSpacing(8)
        self.inspector_source_start = QDoubleSpinBox()
        self.inspector_source_end = QDoubleSpinBox()
        self.inspector_timeline_start = QDoubleSpinBox()
        self.inspector_gain = QDoubleSpinBox()
        for label, control in (
                ("Quell-IN", self.inspector_source_start),
                ("Quell-OUT", self.inspector_source_end),
                ("Timeline-IN", self.inspector_timeline_start),
                ("Clip-Pegel", self.inspector_gain)):
            control.setDecimals(3 if control is not self.inspector_gain else 1)
            control.setSingleStep(.1 if control is not self.inspector_gain else .5)
            control.setSuffix(" s" if control is not self.inspector_gain else " dB")
            property_form.addRow(label, control)
        self.inspector_gain.setRange(-60, 12)
        self.inspector_gain.setToolTip(
            "Pegel pro Audio-Clip; Stummschalten erfolgt weiterhin pro Spur.")
        self.inspector_visual_area = QWidget()
        visual_form = QFormLayout(self.inspector_visual_area)
        visual_form.setContentsMargins(0, 8, 0, 8)
        self.inspector_x = QDoubleSpinBox()
        self.inspector_y = QDoubleSpinBox()
        self.inspector_width = QDoubleSpinBox()
        self.inspector_height = QDoubleSpinBox()
        self.inspector_opacity = QDoubleSpinBox()
        for label, field in (
                ("Links (0–1)", self.inspector_x),
                ("Oben (0–1)", self.inspector_y),
                ("Breite (0–1)", self.inspector_width),
                ("Höhe (0–1)", self.inspector_height),
                ("Deckkraft", self.inspector_opacity)):
            field.setDecimals(3)
            field.setRange(0, 1)
            field.setSingleStep(.02)
            field.setToolTip("Anteil des exportierten Bildes, nicht Originalpixel.")
            visual_form.addRow(label, field)
        self.inspector_width.setMinimum(.05)
        self.inspector_height.setMinimum(.05)
        self.inspector_visual_area.setVisible(False)
        property_form.addRow(self.inspector_visual_area)
        self.inspector_apply_button = QPushButton("Änderungen übernehmen")
        self.inspector_apply_button.setProperty("role", "primary")
        self.inspector_apply_button.clicked.connect(self._apply_inspector_clip)
        property_form.addRow(self.inspector_apply_button)
        self.inspector_cancel_button = QPushButton("Werte zurücksetzen")
        self.inspector_cancel_button.clicked.connect(self._update_inspector)
        property_form.addRow(self.inspector_cancel_button)
        self.inspector_edit_area.setVisible(False)
        inspector_layout.addWidget(self.inspector_edit_area)
        self.inspector_edit_button = QPushButton("Auswahl bearbeiten")
        self.inspector_edit_button.setEnabled(False)
        self.inspector_edit_button.clicked.connect(self._inspect_edit_selection)
        inspector_layout.addWidget(self.inspector_edit_button)
        inspector_layout.addStretch()
        inspector_scroll.setWidget(inspector_contents)
        self.inspector_dock.setWidget(inspector_scroll)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        self.table.itemSelectionChanged.connect(self._update_inspector)
        self.tracks_table.itemSelectionChanged.connect(self._update_inspector)
        self.track_clips_table.itemSelectionChanged.connect(self._update_inspector)
        self._install_workspace_controls()
        self._default_dock_state = QByteArray(self.saveState(1))
        self._update_inspector()

        self.progress = QProgressBar()
        self.progress.setValue(0)
        main.addWidget(self.progress)
        self.statusBar().showMessage("Bereit")
        self._timeline_buttons = (self.timeline_in, self.timeline_out,
                                  self.timeline_play, self.timeline_add,
                                  self.timeline_trim, self.timeline_zoom,
                                  self.timeline_scroll, self.timeline_snap)
        self._busy(False)
        self.setStyleSheet(EDITOR_STYLESHEET)
        self._load_workspace_on_start()

    _WORKSPACE_TABS = {
        "Highlights": 0, "Schnitt": 3, "Audio": 3,
        "Untertitel": 1, "Export": 4,
    }

    def _edit_scene_selection(self) -> None:
        from .scene_selection_dialog import SceneSelectionDialog
        clip = self.selected_candidate()
        if self._history_blocked or not self.editor_project:
            return
        if not clip or not self._video_info:
            QMessageBox.information(self, "Szenenauswahl", "Bitte zuerst ein Highlight auswählen.")
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        try:
            dialog = SceneSelectionDialog(self._video_info, clip.start, clip.end, self,
                plan=scene_plan_for(self.editor_project, clip.start, clip.end),
                commit=lambda plan: self._apply_project_edit(set_scene_plan, plan))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Szenenplan nicht geladen", str(exc))
            return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("Szenenplan im Projekt gespeichert · Undo/Redo verfügbar")

    def _install_workspace_controls(self) -> None:
        scene_menu = self.menuBar().addMenu("Szenen")
        scene_menu.addAction("Highlight in Szenen bearbeiten …", self._edit_scene_selection)
        audio_menu = self.menuBar().addMenu("Audio")
        audio_menu.addAction("Audioquellen / Originalspuren …", self._inspect_audio_sources)
        branding = self.menuBar().addMenu("Branding")
        branding.addAction("Untertitel gestalten …", self._edit_caption_style)
        branding.addAction("Untertitel übersetzen …", self._edit_translations)
        branding.addAction("Text / Callout hinzufügen …", self._add_callout)
        branding.addAction("Ausgewählten Callout bearbeiten …", self._edit_callout)
        branding.addAction("Thumbnail Designer …", self._edit_thumbnail)
        branding.addSeparator()
        branding.addAction("Branding-Profil speichern …", self._save_branding_profile)
        branding.addAction("Branding-Profil anwenden …", self._apply_branding_profile)
        menu = self.menuBar().addMenu("Ansicht && Arbeitsbereiche")
        for name in WORKSPACE_NAMES:
            action = menu.addAction(name)
            action.triggered.connect(
                lambda _checked=False, preset=name: self._activate_workspace(preset))
        menu.addSeparator()
        self.save_workspace_action = menu.addAction(
            "Aktuelles Layout speichern", self._save_workspace_layout)
        self.reset_workspace_action = menu.addAction(
            "Layout zurücksetzen", self._reset_workspace_layout)
        menu.addSeparator()
        for dock in (self.project_dock, self.timeline_dock, self.inspector_dock):
            menu.addAction(dock.toggleViewAction())
        self.tabs.currentChanged.connect(lambda _index: self._update_inspector())

    def _inspect_audio_sources(self):
        if not self.source or self._history_blocked or (self.worker and self.worker.isRunning()) or (self.queue_worker and self.queue_worker.isRunning()):
            return
        from .audio_sources_dialog import AudioSourcesDialog
        AudioSourcesDialog(self.source,self).exec()

    def _edit_translations(self):
        if not self.analysis or not self.analysis.transcript or self._history_blocked:
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        clip=self.selected_candidate()
        a,b=(clip.start,clip.end) if clip else (self.timeline.in_point,self.timeline.out_point)
        rows=[i for i,cue in enumerate(self.analysis.transcript) if cue.end>a and cue.start<b]
        if not rows:
            QMessageBox.information(self,"Übersetzung","Keine Untertitel im gewählten Highlight.");return
        if len(rows)>500:
            QMessageBox.warning(self,"Übersetzung","Bitte kürzeren Ausschnitt wählen (maximal 500 Abschnitte).");return
        from .translation_dialog import TranslationDialog
        dialog=TranslationDialog(self.analysis,rows,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            before=self.analysis
            self.analysis=dialog.value
            self._register_edit(before)
            self.statusBar().showMessage("Export-Sprache: "+(self.analysis.caption_language or "Original")+
                                         " · Quellplayer zeigt Original · Projekt speichern")

    def _callout_dialog(self,item=None):
        if not self.editor_project or self._history_blocked:
            return
        from .callout_dialog import CalloutDialog
        from .media import video_dimensions
        track=next((t for t in self.editor_project.tracks
                    if t.id==(item.track_id if item else self._selected_track_id())
                    and t.kind=="overlay" and not t.locked),None)
        if track is None and item is None:
            track=next((t for t in self.editor_project.tracks if t.kind=="overlay" and not t.locked),None)
        if track is None:
            QMessageBox.warning(self,"Callout","Eine entsperrte Grafikspur wird benötigt.");return
        clip=self.selected_candidate() if self.analysis else None
        a,b=(clip.start,clip.end) if clip else (self.timeline.in_point,self.timeline.out_point)
        dialog=CalloutDialog(a,b,self.editor_project.source.duration,
                             video_dimensions(str(self.mode.currentData()),1080,1920),item,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        values=dict(dialog.geometry_values)
        if item:
            ok=self._apply_project_edit(update_callout,item.id,dialog.spec,**values)
        else:
            duration=values.pop("source_end")
            at=values.pop("timeline_start")
            ok=self._apply_project_edit(add_item,track.id,0.,duration,at,
                 (dialog.spec.text or dialog.spec.kind)[:120],callout=dialog.spec,**values)
        if ok:
            self.include_track_audio.setChecked(True)
            self.statusBar().showMessage("Callout gespeichert · Render-Vorschau zeigt die vollständige Komposition.")

    def _add_callout(self):
        self._callout_dialog()

    def _edit_callout(self):
        if not self.editor_project:return
        item=next((i for i in self.editor_project.items if i.id==self._selected_clip_id() and i.callout),None)
        if item is None:
            QMessageBox.information(self,"Callout","Bitte einen Callout auf der Grafikspur auswählen.");return
        self._callout_dialog(item)

    def _edit_thumbnail(self):
        if not self._video_info or self._history_blocked or (self.worker and self.worker.isRunning()) or (self.queue_worker and self.queue_worker.isRunning()):
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():return
        clip=self.selected_candidate() if self.analysis else None
        start,end=(clip.start,clip.end) if clip else (self.timeline.in_point,self.timeline.out_point)
        if not self._scene_render_allowed(self._video_info,[(start,end)]):return
        plan=scene_plan_for(self.editor_project,start,end)
        try:
            transcript=render_transcript(self.analysis,start,end,plan,self.burn_subtitles.isChecked(),
                       self.caption_offset.value()) if self.analysis and self.analysis.video.path==self.source else ()
            request=RenderRequest(self._video_info,start,end,str(self.mode.currentData()),
                burn_subtitles=self.burn_subtitles.isChecked() and bool(transcript),transcript=transcript,
                subtitle_offset=self.caption_offset.value(),
                project=self.editor_project if self.include_track_audio.isChecked() else None,
                encoder=str(self.encoder_mode.currentData()),scene_plan=plan,
                caption_style=self._current_caption_style()).validate()
            if request.duration>60:raise ValueError("Thumbnail Designer: Highlight auf maximal 60 Sekunden begrenzen.")
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self,"Thumbnail",str(exc));return
        from .thumbnail_dialog import ThumbnailDialog
        ThumbnailDialog(request,self).exec()

    def _save_branding_profile(self):
        if not self.editor_project or self._history_blocked:return
        from .branding_profile import BrandProfile,save_profile
        name,ok=QInputDialog.getText(self,"Branding-Profil","Name des Profils:")
        if not ok:return
        item=next((i for i in self.editor_project.items if i.id==self._selected_clip_id()
                    and i.media_path and any(t.id==i.track_id and t.kind=="overlay" for t in self.editor_project.tracks)),None)
        if item and QMessageBox.question(self,"Branding","Ausgewählte Grafik als wiederverwendbares Logo übernehmen?")!=QMessageBox.StandardButton.Yes:
            item=None
        profile=BrandProfile(name,self._current_caption_style(),item.media_path,item.x,item.y,item.width,item.height,item.opacity) if item else BrandProfile(name,self._current_caption_style())
        path,_=QFileDialog.getSaveFileName(self,"Branding-Profil speichern",name+".json","Branding (*.json)")
        if not path:return
        try:target=save_profile(profile,path)
        except (ValueError,OSError) as exc:QMessageBox.warning(self,"Branding",str(exc));return
        self.statusBar().showMessage("Branding-Profil gespeichert: "+str(target))

    def _apply_branding_profile(self):
        if not self.editor_project or self._history_blocked:return
        from .branding_profile import load_profile,apply_profile
        path,_=QFileDialog.getOpenFileName(self,"Branding-Profil laden","","Branding (*.json)")
        if not path:return
        try:profile=load_profile(path)
        except (ValueError,OSError) as exc:QMessageBox.warning(self,"Branding",str(exc));return
        clip=self.selected_candidate() if self.analysis else None
        a,b=(clip.start,clip.end) if clip else (self.timeline.in_point,self.timeline.out_point)
        track=next((t for t in self.editor_project.tracks if t.id==self._selected_track_id()
                    and t.kind=="overlay" and not t.locked and not t.muted),None)
        if track is None:track=next((t for t in self.editor_project.tracks if t.kind=="overlay" and not t.locked and not t.muted),None)
        if QMessageBox.question(self,"Branding",f"Profil {profile.name} anwenden? Untertitelstil im Projekt ersetzen"
                + (f" und Logo im gewählten Zeitbereich auf {track.name if track else 'fehlender Grafikspur'} hinzufügen?" if profile.logo else "?"))!=QMessageBox.StandardButton.Yes:return
        if self._apply_project_edit(apply_profile,profile,a,b,track.id if track else None):
            if profile.logo:self.include_track_audio.setChecked(True)
            self.statusBar().showMessage("Branding angewendet · Render-Vorschau zum Prüfen öffnen.")

    def _current_caption_style(self):
        return self.editor_project.caption_style if self.editor_project else CaptionStyle()

    def _edit_caption_style(self):
        if not self.editor_project or self._history_blocked:
            self.statusBar().showMessage("Bitte zuerst eine Aufnahme öffnen.")
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        from .caption_style_dialog import CaptionStyleDialog
        dialog=CaptionStyleDialog(self._current_caption_style(),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            if self._apply_project_edit(set_caption_style,dialog.value):
                self.statusBar().showMessage("Untertitelgestaltung gespeichert · Render-Vorschau zum Prüfen öffnen.")

    def _activate_workspace(self, name: str) -> None:
        """Switch what is visible, without resetting playback or user dock sizes."""
        if name not in self._WORKSPACE_TABS or not hasattr(self, "project_dock"):
            return
        self._workspace_name = name
        self.project_dock.show()
        self.timeline_dock.show()
        self.inspector_dock.setVisible(
            name in {"Schnitt", "Audio", "Untertitel"})
        self.tabs.setCurrentIndex(self._WORKSPACE_TABS[name])
        if self.workspace_picker.currentText() != name:
            self.workspace_picker.blockSignals(True)
            try:
                self.workspace_picker.setCurrentText(name)
            finally:
                self.workspace_picker.blockSignals(False)
        self._update_inspector()
        self.statusBar().showMessage(
            f"Arbeitsbereich „{name}“ aktiv · Panelpositionen bleiben erhalten", 3500)

    def _load_workspace_on_start(self) -> None:
        """Restore valid Qt dock state, otherwise a safe default for any display."""
        layout = load_workspace()
        if layout is not None and self.restoreState(QByteArray(layout.state), 1):
            self._workspace_name = layout.active
            self.workspace_picker.blockSignals(True)
            try:
                self.workspace_picker.setCurrentText(layout.active)
            finally:
                self.workspace_picker.blockSignals(False)
            self.tabs.setCurrentIndex(self._WORKSPACE_TABS[layout.active])
            self._update_inspector()
            return
        self._activate_workspace("Highlights")

    def _save_workspace_layout(self, quiet: bool = False) -> None:
        try:
            save_workspace(WorkspaceLayout(
                self._workspace_name, bytes(self.saveState(1))))
        except (OSError, ValueError) as exc:
            if not quiet:
                QMessageBox.warning(
                    self, "Layout nicht gesichert",
                    f"Der UI-Arbeitsbereich wurde nicht gespeichert: {exc}")
        else:
            if not quiet:
                self.statusBar().showMessage(
                    "Arbeitsbereich lokal gespeichert · Clip- und Projektdaten unverändert")

    def _reset_workspace_layout(self) -> None:
        """Recover a clean dock arrangement after accidental offscreen docking."""
        try:
            delete_workspace()
        except OSError:
            # In-memory reset is still safe if the portable folder is readonly.
            pass
        if self._default_dock_state is not None:
            self.restoreState(self._default_dock_state, 1)
        self._activate_workspace("Highlights")
        self.statusBar().showMessage(
            "Standardlayout wiederhergestellt · Quellvideo und Projekt unverändert")

    def _update_inspector(self) -> None:
        if not hasattr(self, "inspector_heading"):
            return
        project = self.editor_project
        clip_id = self._selected_clip_id() if project else None
        track_id = self._selected_track_id() if project else None
        is_tracks = self.tabs.tabText(self.tabs.currentIndex()) == "Spuren"
        clip = next((item for item in project.items if item.id == clip_id),
                    None) if project else None
        track = next((item for item in project.tracks if item.id == track_id),
                     None) if project else None
        candidate = self.selected_candidate() if self.analysis else None
        editable = False
        if is_tracks and clip is not None:
            owner = next(t for t in project.tracks if t.id == clip.track_id)
            self.inspector_heading.setText(clip.label or "Timeline-Clip")
            self.inspector_details.setText(
                f"Spur: {owner.name} ({owner.kind})\\n"
                f"Quelle: {format_timestamp(clip.source_start)} bis "
                f"{format_timestamp(clip.source_end)}\\n"
                f"Timeline: {format_timestamp(clip.timeline_start)}\\n"
                f"Pegel: {clip.gain_db:+.1f} dB\\n"
                f"Stumm: {'Ja' if owner.muted else 'Nein'} · "
                f"Gesperrt: {'Ja' if owner.locked else 'Nein'}")
            editable = True
        elif is_tracks and track is not None:
            self.inspector_heading.setText(track.name)
            self.inspector_details.setText(
                f"Spurtyp: {track.kind}\\n"
                f"Stumm: {'Ja' if track.muted else 'Nein'}\\n"
                f"Gesperrt: {'Ja' if track.locked else 'Nein'}\\n"
                f"Spurclips: {sum(i.track_id == track.id for i in project.items)}")
            editable = True
        elif candidate is not None:
            self.inspector_heading.setText("Highlight-Auswahl")
            self.inspector_details.setText(
                f"Start: {format_timestamp(candidate.start)}\\n"
                f"Ende: {format_timestamp(candidate.end)}\\n"
                f"Dauer: {candidate.end-candidate.start:.2f} s\\n"
                f"Erkennung: {candidate.reason}")
            editable = True
        else:
            self.inspector_heading.setText("Projekt-Übersicht")
            name = Path(self.source).name if self.source else "Keine Datei geöffnet"
            count = len(self.analysis.candidates) if self.analysis else 0
            self.inspector_details.setText(
                f"Aufnahme: {name}\\n"
                f"Highlights: {count}\\n"
                "Wähle einen Clip oder eine Spur, um Details zu sehen.")
        self._inspector_item_id = clip.id if is_tracks and clip is not None else None
        if self._inspector_item_id is not None:
            owner = next(t for t in project.tracks if t.id == clip.track_id)
            limit = 86400.0 if clip.media_path is not None else project.source.duration
            self.inspector_source_start.setRange(0, limit)
            self.inspector_source_end.setRange(0, limit)
            self.inspector_timeline_start.setRange(0, 86400)
            self.inspector_source_start.setValue(clip.source_start)
            self.inspector_source_end.setValue(clip.source_end)
            self.inspector_timeline_start.setValue(clip.timeline_start)
            self.inspector_gain.setValue(clip.gain_db)
            self.inspector_gain.setEnabled(owner.kind == "audio")
            visual = owner.kind in {"video", "overlay"} and bool(clip.media_path)
            self.inspector_visual_area.setVisible(visual)
            if visual:
                for field, value in (
                        (self.inspector_x, clip.x),
                        (self.inspector_y, clip.y),
                        (self.inspector_width, clip.width),
                        (self.inspector_height, clip.height),
                        (self.inspector_opacity, clip.opacity)):
                    field.setValue(value)
            can_edit = not owner.locked and not self._history_blocked and clip.id != "source"
            if visual:
                for field in (self.inspector_x, self.inspector_y,
                              self.inspector_width, self.inspector_height,
                              self.inspector_opacity):
                    field.setEnabled(can_edit)
            self.inspector_edit_area.setVisible(True)
            for field in (self.inspector_source_start, self.inspector_source_end,
                          self.inspector_timeline_start):
                field.setEnabled(can_edit)
            self.inspector_gain.setEnabled(can_edit and owner.kind == "audio")
            self.inspector_apply_button.setEnabled(can_edit)
            self.inspector_cancel_button.setEnabled(can_edit)
            self.inspector_apply_button.setToolTip(
                "" if can_edit else
                "Basisspur oder gesperrte Spur: Eigenschaften sind schreibgeschützt.")
        else:
            self.inspector_visual_area.setVisible(False)
            self.inspector_edit_area.setVisible(False)
        self.inspector_edit_button.setEnabled(editable and not self._history_blocked)

    def _apply_inspector_clip(self) -> None:
        """Commit all visible clip-property edits as ONE undoable project edit."""
        if (self._history_blocked or self.editor_project is None
                or not self._inspector_item_id
                or self._selected_clip_id() != self._inspector_item_id):
            return
        item = next(
            (x for x in self.editor_project.items if x.id == self._inspector_item_id),
            None)
        if item is None or item.id == "source":
            return
        track = next(x for x in self.editor_project.tracks if x.id == item.track_id)
        if track.locked:
            return
        payload = {
            "source_start": self.inspector_source_start.value(),
            "source_end": self.inspector_source_end.value(),
            "timeline_start": self.inspector_timeline_start.value(),
        }
        if track.kind == "audio":
            payload["gain_db"] = self.inspector_gain.value()
        elif track.kind in {"video", "overlay"} and item.media_path:
            payload.update(
                x=self.inspector_x.value(), y=self.inspector_y.value(),
                width=self.inspector_width.value(),
                height=self.inspector_height.value(),
                opacity=self.inspector_opacity.value())
        if self._apply_project_edit(edit_item, item.id, **payload):
            self._update_inspector()

    def _inspect_edit_selection(self) -> None:
        """Open the *existing* editor rather than maintaining duplicate state."""
        if self._history_blocked:
            return
        if (self.tabs.tabText(self.tabs.currentIndex()) == "Spuren"
                and self.editor_project is not None):
            if self._selected_clip_id() is not None and self.inspector_apply_button.isEnabled():
                self.inspector_source_start.setFocus()
                self.inspector_source_start.selectAll()
            elif self._selected_clip_id() is not None:
                self.track_clips_table.setFocus()
            elif self._selected_track_id() is not None:
                self.tracks_table.setFocus()
        elif self.analysis is not None and self.selected_candidate() is not None:
            self.tabs.setCurrentIndex(0)
            self.preview_selected()
            self.table.setFocus()

    def _source_position_ms(self) -> int:
        if self._preview_switching:
            return self._proxy_pending_original_ms
        position = self.player.position()
        if self._proxy_active and self._proxy_state:
            return proxy_to_original_ms(position, self._proxy_state.timing)
        return position

    def _source_position_seconds(self) -> float:
        return max(0, self._source_position_ms()) / 1000.0

    def _media_position_ms(self, original_ms: int) -> int:
        if self._proxy_active and self._proxy_state:
            return original_to_proxy_ms(original_ms, self._proxy_state.timing)
        return max(0, original_ms)

    def _set_preview_position(self, original_ms: int) -> None:
        if self._preview_switching:
            self._proxy_pending_original_ms = original_ms
        else:
            self.player.setPosition(self._media_position_ms(original_ms))

    def _update_proxy_controls(self) -> None:
        # A QThread can be scheduled but not yet report isRunning().
        # Keep the button locked until its finished signal cleans up.
        running = self.proxy_worker is not None
        ready = bool(self._video_info) and not self._history_blocked
        self.proxy_create.setEnabled(ready and not running and self._proxy_state is None)
        self.proxy_cancel.setEnabled(running)
        self.proxy_mode.setEnabled(ready and not running and self._proxy_state is not None)

    def _create_proxy(self) -> None:
        if not self._video_info or self._history_blocked or self.proxy_worker:
            return
        self.proxy_progress.setValue(0)
        self.proxy_status.setText("Proxy wird im Hintergrund erstellt …")
        worker = ProxyThread(self._video_info, self)
        self.proxy_worker = worker
        worker.progress_changed.connect(
            lambda value, w=worker: self._proxy_worker_progress(w, value))
        worker.done.connect(self._proxy_ready)
        worker.failed.connect(self._proxy_failed)
        worker.was_cancelled.connect(self._proxy_cancelled)
        worker.finished.connect(lambda w=worker: self._proxy_worker_finished(w))
        worker.start()
        self._update_proxy_controls()

    def _proxy_worker_progress(self, worker: ProxyThread, value: int) -> None:
        # Ignore delayed queued signals from a previous source/worker.
        if self.proxy_worker is worker and self.source == worker.video.path:
            self.proxy_progress.setValue(value)

    def _cancel_proxy(self) -> None:
        if self.proxy_worker is not None:
            self.proxy_worker.cancel()
            self.proxy_status.setText("Proxy-Abbruch angefordert …")

    def _proxy_worker_finished(self, worker: ProxyThread) -> None:
        if self.proxy_worker is worker:
            self.proxy_worker = None
        worker.deleteLater()
        self._update_proxy_controls()

    def _proxy_ready(self, source: str, state: ProxyState) -> None:
        if self.source != source or not self._video_info:
            return
        verified = cached_proxy(self._video_info)
        if verified is None or verified != state:
            self.proxy_status.setText("Proxy-Cache nicht mehr gültig · Original aktiv")
            self.proxy_progress.setValue(0)
            return
        self._proxy_state = state
        self.proxy_progress.setValue(100)
        self.proxy_status.setText(
            "✓ Proxy (480p) bereit · Export und Analyse nutzen weiterhin das Original")
        self._update_proxy_controls()

    def _proxy_failed(self, source: str, reason: str) -> None:
        if source == self.source:
            self.proxy_status.setText("⚠ Proxy fehlgeschlagen · Original weiterhin nutzbar")
            self.proxy_progress.setValue(0)
            QMessageBox.warning(self, "Proxy konnte nicht erstellt werden", reason)

    def _proxy_cancelled(self, source: str) -> None:
        if source == self.source:
            self.proxy_status.setText("Proxy abgebrochen · Original unverändert")
            self.proxy_progress.setValue(0)

    def _select_preview_source(self, _index: int) -> None:
        requested = self.proxy_mode.currentData() == "proxy"
        if not self.source or (requested and not self._proxy_state):
            self.proxy_mode.blockSignals(True)
            self.proxy_mode.setCurrentIndex(0)
            self.proxy_mode.blockSignals(False)
            return
        if requested != self._proxy_active:
            self._switch_preview_media(requested)

    def _switch_preview_media(self, use_proxy: bool, *,
                              original_ms: int | None = None) -> None:
        if not self.source:
            return
        source_ms = self._source_position_ms() if original_ms is None else original_ms
        resume = (self.player.playbackState()
                  == QMediaPlayer.PlaybackState.PlayingState)
        self.player.pause()
        self._proxy_active = use_proxy and self._proxy_state is not None
        self._proxy_pending_original_ms = source_ms
        self._proxy_resume_playing = resume
        self._preview_switching = True
        filename = (str(self._proxy_state.media_path)
                    if self._proxy_active and self._proxy_state else self.source)
        self.player.setSource(QUrl.fromLocalFile(filename))
        self.proxy_status.setText(
            "Proxy-Vorschau · Export bleibt original" if self._proxy_active
            else "Original-Vorschau · Originalzeitbasis")

    def _proxy_media_status_changed(self, status) -> None:
        if (status == QMediaPlayer.MediaStatus.InvalidMedia
                and self._proxy_active and self.source):
            source_ms = self._source_position_ms()
            self._proxy_state = None
            self.proxy_mode.blockSignals(True)
            self.proxy_mode.setCurrentIndex(0)
            self.proxy_mode.blockSignals(False)
            self._switch_preview_media(False, original_ms=source_ms)
            self.proxy_status.setText("⚠ Proxy nicht abspielbar · Original aktiviert")
            self._update_proxy_controls()
            return
        if (status == QMediaPlayer.MediaStatus.InvalidMedia and
                self._preview_switching and not self._proxy_active):
            # An invalid original must not permanently suppress timeline updates.
            self._preview_switching = False
            self._proxy_resume_playing = False
            self.proxy_status.setText("⚠ Originalvideo kann nicht abgespielt werden")
            return
        if (self._preview_switching and status in (
                QMediaPlayer.MediaStatus.LoadedMedia,
                QMediaPlayer.MediaStatus.BufferedMedia)):
            source_ms = self._proxy_pending_original_ms
            self._preview_switching = False
            self._set_preview_position(source_ms)
            if self._proxy_resume_playing:
                self.player.play()
            self._proxy_resume_playing = False

    def _busy(self, busy: bool) -> None:
        busy = busy or bool(self.queue_worker is not None
                            and self.queue_worker.isRunning())
        self._history_blocked = busy
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
        self.render_preview_button.setEnabled(
            bool(self._video_info) and not busy)
        self.encoder_mode.setEnabled(not busy)
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
        self._update_checkpoint_actions()
        self._update_proxy_controls()
        self._update_inspector()
        self._refresh_queue()

    def _update_history_controls(self, enabled: bool = True) -> None:
        active = enabled and not self._history_blocked
        self.undo_button.setEnabled(active and self._history.can_undo)
        self.redo_button.setEnabled(active and self._history.can_redo)

    def _register_edit(self, before: AnalysisResult) -> None:
        if self.analysis and self._history.record_analysis(before, self.analysis):
            self.transcript_dirty = True
            self.autosave_hint.setText("● Änderungen · Auto-Sicherung folgt")
            self._autosave_timer.start()
            self._update_history_controls()

    def _shortcut_history(self, *, redo: bool) -> None:
        # Native undo for active text fields takes precedence over the timeline.
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QPlainTextEdit)) and not focused.isReadOnly():
            focused.redo() if redo else focused.undo()
            return
        if isinstance(focused, (QSpinBox, QDoubleSpinBox)) and not focused.isReadOnly():
            line = focused.lineEdit()
            if line is not None:
                line.redo() if redo else line.undo()
                return
        self.redo_edit() if redo else self.undo_edit()

    def _shortcut_undo(self) -> None:
        self._shortcut_history(redo=False)

    def _shortcut_redo(self) -> None:
        self._shortcut_history(redo=True)

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

    def _step_history(self, *, redo: bool) -> None:
        if self._history_blocked:
            return
        if not (self._history.can_redo if redo else self._history.can_undo):
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        # Pending editor updates may invalidate the redo branch.
        if not (self._history.can_redo if redo else self._history.can_undo):
            self._update_history_controls()
            return
        previous_analysis, previous_project = self.analysis, self.editor_project
        try:
            next_analysis, next_project = (
                self._history.redo(previous_analysis, previous_project)
                if redo else self._history.undo(previous_analysis, previous_project))
        except ValueError as exc:
            QMessageBox.warning(self, "Bearbeitungsverlauf inkonsistent", str(exc))
            return
        if next_project is not previous_project and next_project is not None:
            try:
                save_project(next_project)
            except (OSError, ValueError) as exc:
                # The disk failed; the history cursor and UI stay unchanged.
                if redo:
                    self._history.undo(next_analysis, next_project)
                else:
                    self._history.redo(next_analysis, next_project)
                QMessageBox.warning(self, "Spuraktion nicht gespeichert", str(exc))
                self._update_history_controls()
                return
        if next_project is not previous_project:
            self.editor_project = next_project
            self._refresh_track_tables()
            self.track_status.setText(
                "✓ Spuränderung " + ("wiederholt" if redo else "zurückgenommen")
                + " und gespeichert")
        if next_analysis is not previous_analysis and next_analysis is not None:
            self.analysis_finished(next_analysis, preserve_history=True)
            self._autosave_timer.start()
        self._update_history_controls()
        self._update_track_actions()
        self.statusBar().showMessage(
            ("↷ Wiederholt" if redo else "↶ Rückgängig")
            + " · gemeinsamer Bearbeitungsverlauf")

    def undo_edit(self) -> None:
        self._step_history(redo=False)

    def redo_edit(self) -> None:
        self._step_history(redo=True)

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
        self._history.clear()
        self._refresh_track_tables()
        self._update_checkpoint_actions()
        self._update_history_controls()

    def _update_checkpoint_actions(self) -> None:
        ready = self.editor_project is not None and not self._history_blocked
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
            for number, entry in enumerate(entries, start=1)]
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
        self._history.clear()
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
                    kind = next(t.kind for t in project.tracks
                                if t.id == item.track_id)
                    if kind == "audio":
                        extra = ((Path(item.media_path).name if item.media_path
                                  else "Aufnahme") + f" · {item.gain_db:+.1f} dB")
                    elif item.callout is not None:
                        extra = "Callout · " + item.callout.kind
                    elif kind in {"video", "overlay"} and item.media_path:
                        extra = Path(item.media_path).name
                    else:
                        extra = "—"
                    values = (item.label or item.id, names[item.track_id],
                              format_timestamp(item.source_start),
                              format_timestamp(item.source_end),
                              format_timestamp(item.timeline_start), extra)
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
        self._update_inspector()

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
        self._update_inspector()

    def _drag_project_clip(self, item_id: str, position: float) -> None:
        if item_id == "source":
            self.statusBar().showMessage(
                "Die M12b-Basisaufnahme bleibt am Timeline-Ursprung.", 4000)
            return
        self._apply_project_edit(edit_item, item_id, timeline_start=position)

    def _update_track_actions(self) -> None:
        if not hasattr(self, "track_add_button"):
            return
        ready = self.editor_project is not None and not self._history_blocked
        selected = self._selected_track_id() if ready else None
        clip = self._selected_clip_id() if ready else None
        for control in (self.track_add_button,):
            control.setEnabled(ready)
        for control in (self.track_rename_button, self.track_remove_button,
                        self.track_mute_button, self.track_lock_button,
                        self.track_up_button, self.track_down_button):
            control.setEnabled(bool(selected))
        track = next((t for t in self.editor_project.tracks if t.id == selected),
                     None) if ready else None
        clip_obj = next((i for i in self.editor_project.items if i.id == clip),
                        None) if ready else None
        clip_track = next((t for t in self.editor_project.tracks
                           if clip_obj and t.id == clip_obj.track_id),
                          None) if ready else None
        self.track_clip_add.setEnabled(bool(selected) and self._source_duration > 0)
        self.track_clip_move.setEnabled(bool(clip))
        self.track_clip_trim.setEnabled(bool(clip))
        self.track_clip_delete.setEnabled(
            bool(clip_obj and clip_obj.id != "source" and clip_track
                 and not clip_track.locked))
        self.track_audio_import.setEnabled(
            bool(track and track.kind == "audio" and not track.locked))
        self.track_visual_import.setEnabled(
            bool(track and (track.kind == "overlay" or
                            (track.kind == "video" and track.id != "gameplay"))
                 and not track.locked))
        self.track_gain_button.setEnabled(
            bool(clip_obj and clip_track and clip_track.kind == "audio"
                 and not clip_track.locked))
        if hasattr(self, "include_track_audio"):
            has_layers = bool(self.editor_project and any(
                i.id != "source" for i in self.editor_project.items))
            # Busy disables changes but must NOT clear the opt-in choice.
            # Unsupported legacy metadata-only clips remain fail-closed if
            # the user deliberately enables project rendering.
            self.include_track_audio.setEnabled(has_layers and ready)
            if not has_layers:
                self.include_track_audio.setChecked(False)
        self.track_import_button.setEnabled(
            ready and self.analysis is not None and bool(self.analysis.candidates))
        self._update_history_controls()

    def _apply_project_edit(self, action, *args, **kwargs) -> bool:
        if not self.editor_project or self._history_blocked:
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
        self._history.record_project(before, after)
        self.editor_project = after
        self._refresh_track_tables()
        self._update_history_controls()
        self.track_status.setText("✓ Spurplan lokal gespeichert · Original unverändert")
        return True

    def _import_analysis_highlights(self) -> None:
        """Explicit, source-checked snapshot import; no automatic re-analysis."""
        if not self.editor_project or not self.analysis or self._history_blocked:
            return
        if not self.analysis.candidates:
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        tracks = [t for t in self.editor_project.tracks if t.kind == "video"]
        labels = ["Highlights (Import) · eigene Videospur"] + [
            f"{t.name} ({t.id})" for t in tracks]
        choice, accepted = QInputDialog.getItem(
            self, "Highlights übernehmen", "Ziel für die Spurclips:",
            labels, 0, False)
        if not accepted:
            return
        selected = labels.index(choice)
        target = None if selected == 0 else tracks[selected - 1].id
        before = len(self.editor_project.items)
        if not self._apply_project_edit(
                import_analysis_candidates, self.analysis, track_id=target):
            return
        imported = len(self.editor_project.items) - before
        skipped = len(self.analysis.candidates) - imported
        self.track_status.setText(
            f"✓ {imported} neue Highlights übernommen · "
            f"{skipped} bereits vorhanden · Original unverändert")
        self.statusBar().showMessage(
            f"Highlight-Import: {imported} neue, {skipped} unverändert")

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

    def _remove_selected_track_clip(self) -> None:
        """Non-destructive timeline deletion through shared undo/history."""
        item_id = self._selected_clip_id()
        if item_id and item_id != "source":
            self._apply_project_edit(remove_item, item_id)

    def _add_audio_file_to_track(self) -> None:
        """Explicitly reference a local audio file; never upload or modify it."""
        track_id = self._selected_track_id()
        if not self.editor_project or self._history_blocked or not track_id:
            return
        track = next((t for t in self.editor_project.tracks if t.id == track_id), None)
        if not track or track.kind != "audio" or track.locked:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Lokale Audiodatei für die Spur auswählen", "",
            "Audio (*.wav *.mp3 *.flac *.m4a *.aac *.ogg *.opus);;Alle Dateien (*)")
        if not path:
            return
        try:
            audio_source = Path(path).resolve(strict=True)
            duration = probe_audio_duration(audio_source)
            if duration > 86400:
                raise ValueError("Audiodateien über 24 Stunden werden nicht unterstützt")
            at = self.timeline.in_point
            end = min(duration, 86400-at)
            if end < .01:
                raise ValueError("Kein Platz mehr auf der Timeline")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            QMessageBox.warning(self, "Audiodatei nicht verwendbar", str(exc))
            return
        gain, accepted = QInputDialog.getDouble(
            self, "Audiopegel", "Pegel in dB (maximal +12)", 0, -60, 12, 1)
        if accepted:
            self._apply_project_edit(
                add_item, track_id, 0.0, end, at,
                audio_source.stem[:120], media_path=str(audio_source),
                gain_db=gain)

    def _add_visual_file_to_track(self) -> None:
        """Add a genuine, local PiP video or image, never copy/modify media."""
        track_id = self._selected_track_id()
        if self.editor_project is None or self._history_blocked or not track_id:
            return
        track = next((t for t in self.editor_project.tracks if t.id == track_id),
                     None)
        if (not track or track.locked
                or track.kind not in {"video", "overlay"}
                or track.id == "gameplay"):
            return
        picker = ("Video (*.mp4 *.mkv *.mov *.webm *.m4v *.avi)"
                  if track.kind == "video" else
                  "Grafiken (*.png *.jpg *.jpeg *.webp)")
        path, _ = QFileDialog.getOpenFileName(
            self, "Lokale Video-/Grafikdatei auswählen", "",
            picker + ";;Alle Dateien (*)")
        if not path:
            return
        try:
            media = Path(path).resolve(strict=True)
            if track.kind == "video":
                duration = probe_video(media).duration
            else:
                probe_still_image(media)
                duration = self.timeline.out_point - self.timeline.in_point
            if not 0 < duration <= 86400:
                raise ValueError("Datei besitzt keine gültige Dauer")
            at = self.timeline.in_point
            length = min(duration, self.timeline.out_point-at, 86400-at)
            if length < .05:
                raise ValueError("Zu kurzer Platz auf der Timeline")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            QMessageBox.warning(self, "Videomedium nicht verwendbar", str(exc))
            return
        self._apply_project_edit(
            add_item, track.id, 0.0, length, at,
            media.stem[:120], media_path=str(media))
        self.statusBar().showMessage(
            "Video-/Grafik-Layer lokal referenziert. "
            "Bildposition und Größe im Inspector bearbeiten.", 6500)

    def _edit_selected_clip_gain(self) -> None:
        if not self.editor_project or self._history_blocked:
            return
        item_id = self._selected_clip_id()
        item = next((i for i in self.editor_project.items if i.id == item_id), None)
        track = next((t for t in self.editor_project.tracks
                      if item and t.id == item.track_id), None)
        if not item or not track or track.kind != "audio" or track.locked:
            return
        value, ok = QInputDialog.getDouble(
            self, "Clip-Pegel", "Pegel in dB (-60 bis +12)",
            item.gain_db, -60, 12, 1)
        if ok:
            self._apply_project_edit(edit_item, item.id, gain_db=value)

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
        if item.media_path is not None:
            try:
                kind = next(t.kind for t in self.editor_project.tracks
                            if t.id == item.track_id)
                if kind == "audio":
                    limit = probe_audio_duration(item.media_path)
                elif kind == "video":
                    limit = probe_video(item.media_path).duration
                elif kind == "overlay":
                    limit = 86400
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                QMessageBox.warning(self, "Medienquelle fehlt", str(exc))
                return
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

    # Compatibility hooks: now use the same last action regardless of active tab.
    def _undo_project(self) -> None:
        self.undo_edit()

    def _redo_project(self) -> None:
        self.redo_edit()

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
        if self._render_preview_dialog is not None:
            self._render_preview_dialog.close()
            self._render_preview_dialog = None
        self.render_preview_button.setEnabled(False)
        for old in self._waveform_workers:
            old.cancel()
        if self.proxy_worker is not None:
            self.proxy_worker.cancel()
        self._video_info = None
        self._proxy_state = None
        self._proxy_active = False
        self._preview_switching = False
        self._proxy_resume_playing = False
        self.proxy_mode.blockSignals(True)
        self.proxy_mode.setCurrentIndex(0)
        self.proxy_mode.blockSignals(False)
        self.proxy_progress.setValue(0)
        self.proxy_status.setText(
            "Proxy optional · Schnittmarken und Export nutzen das Original.")
        self._update_proxy_controls()
        self._autosave_timer.stop()
        self._history.clear()
        self.editor_project = None
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
        self._video_info = video
        self.render_preview_button.setEnabled(not self._history_blocked)
        self._proxy_state = cached_proxy(video)
        if self._proxy_state:
            self.proxy_progress.setValue(100)
            self.proxy_status.setText(
                "✓ Gespeicherter Proxy gefunden · Vorschau kann umgeschaltet werden")
        self._update_proxy_controls()
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
        self.timeline.set_zoom(zoom, center=self._source_position_seconds())
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
        self._set_preview_position(round(second * 1000))
        self.timeline.set_position(second)
        self.track_canvas.set_playhead(second)

    def timeline_range_changed(self, start: float, end: float):
        if not self.apply_word_editor():
            # A malformed edit must not get lost when changing highlights.
            self.timeline.set_selection(*self._last_timeline_range)
            return
        self._last_timeline_range = (start, end)
        self.track_canvas.set_selection(start, end)
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
        self._set_preview_position(round(max(0, cue.start - .15) * 1000))
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
        self._update_caption_overlay(self._source_position_seconds())
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
        self._set_preview_position(round(max(0, cue.start - .2) * 1000))
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
        if 0 <= index < len(previous.candidates):
            clip = previous.candidates[index]
            from .scene_selection import saved_selection_exists
            if (scene_plan_for(self.editor_project, clip.start, clip.end) is not None
                    or saved_selection_exists(previous.video, clip.start, clip.end)):
                QMessageBox.warning(self, "Szenenplan erhalten",
                    "Bitte In/Out innerhalb des Szeneneditors ändern; der Highlight-Rahmen bleibt erhalten.")
                return
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
        self._set_preview_position(round(self.timeline.in_point * 1000))
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
        self._update_caption_overlay(self._source_position_seconds())

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

    def _refresh_hf_status(self) -> None:
        if self._hf_session_token:
            label = "Token für diese Sitzung hinterlegt"
        else:
            saved = False
            if hf_store_supported():
                try:
                    saved = bool(read_hf_credential())
                except OSError:
                    pass
            if saved:
                label = "Token in Windows-Anmeldeinformationen hinterlegt"
            elif os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN"):
                label = "Hugging Face bereits über Umgebung konfiguriert"
            else:
                # No network, and no token string copied into a UI widget.
                try:
                    from huggingface_hub import get_token
                    label = ("Hugging Face bereits über HF-Login konfiguriert"
                             if get_token() else "Anonym · öffentliche Modelle verfügbar")
                except ImportError:
                    label = "Anonym · öffentliche Modelle verfügbar"
        self.hf_status.setText(label)

    def _apply_hf_token(self) -> bool:
        token = self.hf_token_input.text().strip()
        if not token.startswith("hf_") or len(token) > 4096 or len(token) < 6:
            QMessageBox.warning(
                self, "Hugging Face Token",
                "Bitte ein gültiges Read-Token im Format hf_… einfügen.")
            return False
        if self.hf_persist_token.isChecked():
            try:
                save_hf_credential(token)
            except (OSError, RuntimeError, ValueError):
                QMessageBox.warning(
                    self, "Token speichern",
                    "Sicherer Windows-Speicher nicht verfügbar. Token wurde "
                    "nicht dauerhaft gespeichert.")
                return False
        self._hf_session_token = token
        self.hf_token_input.clear()  # no plain text left in the visible field
        self._refresh_hf_status()
        self.statusBar().showMessage("Hugging Face Token übernommen")
        return True

    def _active_hf_token(self) -> str | None:
        if self.hf_token_input.text().strip():
            if not self._apply_hf_token():
                raise ValueError("Hugging Face Tokenformat ungültig")
        if self._hf_session_token:
            return self._hf_session_token
        if hf_store_supported():
            try:
                return read_hf_credential()
            except OSError:
                self.hf_status.setText(
                    "Windows-Anmeldeinformationen nicht verfügbar · Sitzungstoken möglich")
        # None is HF's documented implicit environment/HF-login lookup.
        return None

    def _remove_hf_token(self) -> None:
        if self.model_worker is not None or self.hf_check_worker is not None:
            return
        self.hf_token_input.clear()
        self._hf_session_token = None
        self.hf_persist_token.setChecked(False)
        if hf_store_supported():
            try:
                remove_hf_credential()
            except OSError:
                QMessageBox.warning(
                    self, "Token entfernen",
                    "Windows-Anmeldeinformationen konnten nicht gelöscht werden.")
                return
        self._refresh_hf_status()
        self.statusBar().showMessage(
            "StreamClipper-Token entfernt · externe HF-Anmeldungen bleiben unberührt")

    def _check_hf_token(self) -> None:
        if self.hf_check_worker is not None or self.model_worker is not None:
            return
        try:
            token = self._active_hf_token()
        except ValueError:
            return
        worker = HfTokenCheckThread(token, self)
        self.hf_check_worker = worker
        self.hf_check_button.setEnabled(False)
        self.hf_status.setText("Hugging Face: Verbindung wird geprüft …")
        worker.checked.connect(self._hf_check_succeeded)
        worker.failed.connect(self._hf_check_failed)
        worker.finished.connect(lambda w=worker: self._hf_check_finished(w))
        worker.start()

    def _hf_check_succeeded(self, message: str) -> None:
        self.hf_status.setText(message)
        self.statusBar().showMessage("Hugging Face: authentifizierte Verbindung bestätigt")

    def _hf_check_failed(self, message: str) -> None:
        self.hf_status.setText(message)

    def _hf_check_finished(self, worker: HfTokenCheckThread) -> None:
        if self.hf_check_worker is worker:
            self.hf_check_worker = None
        worker.deleteLater()
        self.hf_check_button.setEnabled(self.model_worker is None)

    def _model_download_progress(self, worker: ModelDownloadThread, event: object) -> None:
        if self.model_worker is not worker:
            return
        model_id, percent, transferred, total, stage = event
        if model_id != worker.model_id:
            return
        label = preset(model_id).label
        if stage == "complete":
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.progress.setFormat(f"Modell: {label} · 100 % · geprüft")
            return
        if percent is None:
            self.progress.setRange(0, 0)  # busy, never a fictional percentage
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
        details = {
            "metadata": "Dateien/Größen werden ermittelt",
            "fallback": "Alternative Gewichtsdatei wird geladen",
            "validation": "Modell wird validiert",
            "download": "Modell wird geladen",
        }.get(stage, "Modell wird geladen")
        amount = format_bytes(transferred)
        suffix = f" / {format_bytes(total)}" if total else ""
        self.progress.setFormat(f"{label}: {details} · {amount}{suffix}")
        self.statusBar().showMessage(f"{label}: {details} · {amount}{suffix}")

    def _model_download_cancelled(self, model_id: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Bereit")
        self.statusBar().showMessage(
            f"Modelldownload abgebrochen: {preset(model_id).label} · vorhandene Dateien behalten")

    def _model_worker_finished(self, worker: ModelDownloadThread) -> None:
        if self.model_worker is worker:
            self.model_worker = None
        worker.deleteLater()
        self._busy(False)
        self.hf_check_button.setEnabled(self.hf_check_worker is None)
        self.hf_use_token.setEnabled(True)
        self.hf_remove_button.setEnabled(True)

    def download_selected_model(self, kind: str) -> None:
        if (self.model_worker is not None or self.hf_check_worker is not None
                or self._history_blocked):
            return
        model_id = self.model_selectors[kind].currentData()
        item = preset(model_id)
        choice = QMessageBox.question(
            self, 'Modell herunterladen',
            f'„{item.label}“ von {item.repository} aus dem Internet herunterladen?\\n'
            f'Ziel: {preset_path(model_id)}\\n\\n'
            'Je nach Variante werden mehrere hundert MB bis einige GB benötigt. '
            'Das Modell wird nur nach deiner Zustimmung geladen.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            token = self._active_hf_token()
        except ValueError:
            return
        worker = ModelDownloadThread(model_id, self, token=token)
        self.model_worker = worker
        worker.progress_changed.connect(
            lambda event, w=worker: self._model_download_progress(w, event))
        worker.done.connect(self.model_download_finished)
        worker.failed.connect(self.model_download_failed)
        worker.was_cancelled.connect(self._model_download_cancelled)
        worker.finished.connect(lambda w=worker: self._model_worker_finished(w))
        self.progress.setRange(0, 0)
        self.progress.setFormat(f"Modell: {item.label} · Metadaten werden geladen")
        self._busy(True)
        self.hf_check_button.setEnabled(False)
        self.hf_use_token.setEnabled(False)
        self.hf_remove_button.setEnabled(False)
        self.statusBar().showMessage(f'Lade {item.label} (expliziter Online-Download) …')
        worker.start()

    def model_download_finished(self, model_id: str, folder: str) -> None:
        item = preset(model_id)
        getattr(self, f'{item.kind}_path').setText(folder)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat(f"Modell: {item.label} · 100 % · validiert")
        self.statusBar().showMessage(f'Bereit und überprüft: {item.label}')
        QMessageBox.information(self, 'Modell bereit', f'{item.label}\\n{folder}')

    def model_download_failed(self, model_id: str, error: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Modelldownload fehlgeschlagen")
        self.statusBar().showMessage('Modelldownload fehlgeschlagen')
        QMessageBox.warning(self, 'Modelldownload fehlgeschlagen',
                            f'{preset(model_id).label}\\n{error}')

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
            self._history.clear()
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
        self._update_caption_overlay(self._source_position_seconds())
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
        return max(0.0, self._source_position_seconds())

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
        self._set_preview_position(round(clip.start * 1000))
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
        self._update_caption_overlay(self._source_position_seconds())
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
        self._set_preview_position(round(max(0, cue.start - 0.3) * 1000))
        self.player.play()

    def jump_to_transcript(self, row: int, _column: int) -> None:
        if not self.analysis or row < 0 or row >= len(self.analysis.transcript):
            return
        self.preview_end = None
        self.player.pause()
        self._set_preview_position(round(self.analysis.transcript[row].start * 1000))

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
            target = save_transcript(export_transcript(self.analysis), destination)
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
        if self._preview_switching:
            return
        original_ms = (proxy_to_original_ms(pos, self._proxy_state.timing)
                       if self._proxy_active and self._proxy_state else pos)
        if not self.seek.isSliderDown():
            self.seek.setValue(original_ms)
        self.time_label.setText(display_time(original_ms / 1000))
        self.timeline.set_position(original_ms / 1000)
        self.track_canvas.set_playhead(original_ms / 1000)
        if (self.timeline.zoom > 1.0 and
                self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState):
            a, b = self.timeline.visible()
            if original_ms / 1000 > b or original_ms / 1000 < a:
                self.timeline.set_offset(original_ms / 1000 - (b-a) * .20)
                self._sync_timeline_scroll()
        self._update_caption_overlay(original_ms / 1000)
        if self.preview_end is not None and original_ms >= int(self.preview_end * 1000):
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()

    def _duration_changed(self, duration: int) -> None:
        if self._preview_switching:
            return
        # The source timeline must never adopt the proxy's shorter/longer
        # mux duration. Only the original source owns clip timing.
        if duration > 0 and self._source_duration <= 0 and not self._proxy_active:
            self._source_duration = duration / 1000
            self.timeline.set_duration(self._source_duration)
        self.seek.setRange(0, max(1, round(self._source_duration * 1000)
                                  if self._source_duration > 0 else duration))

    def seek_to(self, pos: int) -> None:
        self.preview_end = None  # manual scrubbing may leave suggested time span
        self._set_preview_position(pos)

    def _scene_render_allowed(self, video, intervals) -> bool:
        from .scene_selection import require_unplanned_highlight
        try:
            for start, end in intervals:
                if scene_plan_for(self.editor_project, start, end) is None:
                    require_unplanned_highlight(video, start, end)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Szenenplan – bitte im Projekt übernehmen", str(exc))
            return False
        return True

    def start_render_preview(self) -> None:
        """Render a bounded export-identical MP4 without touching source playback."""
        if self.queue_worker is not None and self.queue_worker.isRunning():
            self.statusBar().showMessage(
                "Renderqueue läuft; Render-Vorschau ist vorübergehend gesperrt", 6000)
            return
        if (self.worker is not None and self.worker.isRunning()) or (
                self.model_worker is not None or self._history_blocked):
            return
        if not self._video_info or not self.source:
            self.statusBar().showMessage("Videodaten werden noch geladen")
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        clip = self.selected_candidate() if self.analysis else None
        if clip is None:
            start, end = self.timeline.in_point, self.timeline.out_point
        else:
            start, end = clip.start, clip.end
        transcript = (tuple(self.analysis.transcript)
                      if self.analysis and self.analysis.video.path == self.source
                      else ())
        if not self._scene_render_allowed(self._video_info, [(start, end)]):
            return
        try:
            if self.analysis and self.analysis.video.path==self.source:
                transcript=render_transcript(self.analysis,start,end,scene_plan_for(self.editor_project,start,end),
                                             self.burn_subtitles.isChecked(),self.caption_offset.value())
            request = RenderRequest(
                video=self._video_info, start=start, end=end,
                mode=str(self.mode.currentData()),
                burn_subtitles=(self.burn_subtitles.isChecked() and bool(transcript)),
                subtitle_offset=self.caption_offset.value(),
                transcript=transcript,
                project=(self.editor_project if self.include_track_audio.isChecked()
                         else None),
                encoder=str(self.encoder_mode.currentData()),
                scene_plan=scene_plan_for(self.editor_project, start, end),
                caption_style=self._current_caption_style(),
            ).validate()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Render-Vorschau nicht möglich", str(exc))
            return
        if self._render_preview_dialog is not None:
            self._render_preview_dialog.close()
            self._render_preview_dialog = None
        worker = RenderPreviewThread(request, self)
        self.worker = worker
        worker.encoder_notice.connect(self._encoder_notice)
        worker.progress_changed.connect(
            lambda value, w=worker: self._render_preview_progress(w, value))
        worker.done.connect(
            lambda value, w=worker: self._render_preview_done(w, value))
        worker.failed.connect(
            lambda reason, w=worker: self._render_preview_failed(w, reason))
        worker.was_cancelled.connect(
            lambda w=worker: self._render_preview_cancelled(w))
        worker.finished.connect(lambda w=worker: self._render_preview_finished(w))
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Render-Vorschau · %p %")
        self.encoder_status.setText("Encoder wird im Hintergrund geprüft …")
        self._busy(True)
        self.statusBar().showMessage(
            "Render-Vorschau wird mit den MP4-Exportfiltern erstellt …")
        worker.start()

    def _encoder_notice(self, message: str) -> None:
        """Never hide a GPU fallback behind an apparently successful export."""
        self.encoder_status.setText(message)
        self.statusBar().showMessage(message, 8000)

    def _render_preview_progress(self, worker: RenderPreviewThread, value: int) -> None:
        if self.worker is worker:
            self.progress.setValue(value)

    def _render_preview_done(self, worker: RenderPreviewThread, outcome: object) -> None:
        result, temporary = outcome
        if (self.worker is not worker or not self.source or
                result.request.video.path != self.source):
            temporary.cleanup()
            return
        dialog = RenderedClipDialog(result, temporary, self)
        self._render_preview_dialog = dialog
        dialog.finished.connect(
            lambda _status, d=dialog: self._render_preview_dialog_finished(d))
        dialog.show()
        dialog.player.play()
        self.progress.setValue(100)
        self.statusBar().showMessage(
            "Exportgetreuer Ausschnitt bereit · eigene Wiedergabe, Original unverändert")

    def _render_preview_dialog_finished(self, dialog: RenderedClipDialog) -> None:
        if self._render_preview_dialog is dialog:
            self._render_preview_dialog = None

    def _render_preview_failed(self, worker: RenderPreviewThread, reason: str) -> None:
        if self.worker is worker:
            self.progress.setValue(0)
            self.statusBar().showMessage("Render-Vorschau fehlgeschlagen")
            QMessageBox.warning(self, "Render-Vorschau fehlgeschlagen", reason)

    def _render_preview_cancelled(self, worker: RenderPreviewThread) -> None:
        if self.worker is worker:
            self.progress.setValue(0)
            self.statusBar().showMessage(
                "Render-Vorschau abgebrochen · Original und Projekt unverändert")

    def _render_preview_finished(self, worker: RenderPreviewThread) -> None:
        if self.worker is worker:
            self.worker = None
        worker.deleteLater()
        self._busy(False)

    def start_export(self, all_clips: bool) -> None:
        if self.queue_worker is not None and self.queue_worker.isRunning():
            self.statusBar().showMessage(
                "Renderqueue läuft; Direkt-Export ist vorübergehend gesperrt", 6000)
            return
        if not self.analysis or not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        items = self.analysis.candidates if all_clips else [self.selected_candidate()]
        items = [item for item in items if item is not None]
        if not items:
            return
        if not self._scene_render_allowed(self.analysis.video, [(item.start, item.end) for item in items]):
            return
        directory = QFileDialog.getExistingDirectory(self, "Exportordner wählen")
        if not directory:
            return
        self.progress.setValue(0)
        self.worker = ExportThread(self.analysis, items, directory,
                                   str(self.mode.currentData()), self,
                                   burn_subtitles=self.burn_subtitles.isChecked()
                                   and bool(self.analysis.transcript),
                                   subtitle_offset=self.caption_offset.value(),
                                   project=(self.editor_project
                                            if self.include_track_audio.isChecked()
                                            else None),
                                   encoder=str(self.encoder_mode.currentData()),
                                   scene_plans=self.editor_project.scene_plans if self.editor_project else (),
                                   caption_style=self._current_caption_style())
        self.worker.encoder_notice.connect(self._encoder_notice)
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.done.connect(self.export_finished)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(lambda: self._busy(False))
        self._busy(True)
        self.encoder_status.setText("Encoder wird im Hintergrund geprüft …")
        self.statusBar().showMessage(f"Exportiere {len(items)} Clip(s) …")
        self.worker.start()

    def export_finished(self, outputs: list[str]) -> None:
        self._busy(False)
        self.statusBar().showMessage(f"{len(outputs)} MP4-Clip(s) erfolgreich exportiert")
        QMessageBox.information(self, "Export abgeschlossen",
            "Exportiert:\n" + "\n".join(outputs[:10]))

    def _ensure_render_queue(self) -> bool:
        """Open the protected local queue only on first actual queue action."""
        if self.render_queue is not None:
            return True
        try:
            self.render_queue = RenderQueue()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Renderqueue nicht verfügbar", str(exc))
            return False
        self._refresh_queue()
        return True

    def _refresh_queue(self) -> None:
        if not hasattr(self, "queue_table"):
            return
        queue = self.render_queue
        items = queue.jobs() if queue is not None else ()
        selected = self._selected_queue_id()
        self.queue_table.blockSignals(True)
        try:
            self.queue_table.setRowCount(len(items))
            for i, job in enumerate(items):
                columns = (job.label, job.status, str(job.progress) + " %",
                           job.result or job.detail or job.destination)
                for column, value in enumerate(columns):
                    cell = QTableWidgetItem(value)
                    cell.setToolTip(job.destination + "\\n" + job.detail)
                    cell.setData(Qt.ItemDataRole.UserRole, job.id)
                    self.queue_table.setItem(i, column, cell)
                if job.id == selected:
                    self.queue_table.selectRow(i)
        finally:
            self.queue_table.blockSignals(False)
        active = self.queue_worker is not None and self.queue_worker.isRunning()
        self.queue_start_button.setEnabled(not active and any(
            j.status == "QUEUED" for j in items))
        self.queue_cancel_button.setEnabled(active or bool(
            selected and any(j.id == selected and j.status == "QUEUED"
                             for j in items)))
        self.queue_retry_button.setEnabled(not active and bool(
            selected and any(j.id == selected and j.status in {
                "INTERRUPTED", "FAILED", "CANCELLED"} for j in items)))
        self.queue_remove_button.setEnabled(not active and bool(
            selected and any(j.id == selected and j.status != "RUNNING"
                             for j in items)))
        self.queue_selected_button.setEnabled(
            not active and bool(self._video_info))
        self.queue_all_button.setEnabled(
            not active and bool(self.analysis and self.analysis.candidates))

    def _selected_queue_id(self) -> str | None:
        if not hasattr(self, "queue_table"):
            return None
        item = self.queue_table.item(self.queue_table.currentRow(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _queue_enqueue(self, all_clips: bool) -> None:
        if not self._video_info or not self._ensure_render_queue():
            return
        if self.queue_worker is not None and self.queue_worker.isRunning():
            return
        if not self.apply_word_editor() or not self.apply_transcript_editor():
            return
        directory = QFileDialog.getExistingDirectory(
            self, "Zielordner für Renderqueue")
        if not directory:
            return
        clips = list(self.analysis.candidates) if (
            all_clips and self.analysis) else []
        if not clips:
            selected = self.selected_candidate() if self.analysis else None
            if selected is not None:
                clips = [selected]
            elif not all_clips:
                a, b = self.timeline.in_point, self.timeline.out_point
                clips = [Candidate(a, b, 0, "Timeline-Auswahl", a)]
        if not clips:
            return
        transcript = (tuple(self.analysis.transcript)
                      if self.analysis and self.analysis.video.path == self.source
                      else ())
        if not self._scene_render_allowed(self._video_info, [(item.start, item.end) for item in clips]):
            return
        added = 0
        for item in clips:
            try:
                if self.analysis and self.analysis.video.path==self.source:
                    transcript=render_transcript(self.analysis,item.start,item.end,
                        scene_plan_for(self.editor_project,item.start,item.end),
                        self.burn_subtitles.isChecked(),self.caption_offset.value())
                request = RenderRequest(
                    video=self._video_info, start=item.start, end=item.end,
                    mode=str(self.mode.currentData()),
                    burn_subtitles=(self.burn_subtitles.isChecked()
                                    and bool(transcript)),
                    subtitle_offset=self.caption_offset.value(),
                    transcript=transcript,
                    project=(self.editor_project
                             if self.include_track_audio.isChecked() else None),
                    encoder=str(self.encoder_mode.currentData()),
                    scene_plan=scene_plan_for(self.editor_project, item.start, item.end),
                    caption_style=self._current_caption_style()).validate()
                self.render_queue.enqueue(
                    request, directory,
                    label=f"{display_time(item.start)} – {display_time(item.end)}")
                added += 1
            except (OSError, ValueError, RuntimeError) as exc:
                QMessageBox.warning(
                    self, "Renderjob abgelehnt", str(exc))
                break
        self._refresh_queue()
        self.statusBar().showMessage(
            f"{added} Renderjob(s) in die lokale Queue aufgenommen · noch nicht gestartet")

    def _queue_start(self) -> None:
        if (self.worker is not None and self.worker.isRunning()
                or self.model_worker is not None
                or self.proxy_worker is not None
                and self.proxy_worker.isRunning()):
            self.statusBar().showMessage(
                "Ein anderer Job läuft; Renderqueue erst danach starten", 6000)
            return
        if not self._ensure_render_queue():
            return
        if self.queue_worker is not None and self.queue_worker.isRunning():
            return
        if not any(j.status == "QUEUED" for j in self.render_queue.jobs()):
            return
        worker = QueueRunThread(self.render_queue, self)
        self.queue_worker = worker
        worker.changed.connect(lambda _job: self._refresh_queue())
        worker.info.connect(self._encoder_notice)
        worker.finished_jobs.connect(self._queue_finished)
        worker.failed.connect(self._queue_failed)
        worker.finished.connect(
            lambda w=worker: self._queue_worker_finished(w))
        self._busy(True)
        worker.start()
        self._refresh_queue()

    def _queue_cancel(self) -> None:
        if self.queue_worker is not None and self.queue_worker.isRunning():
            self.queue_worker.cancel()
            self.statusBar().showMessage("Renderqueue-Abbruch angefordert …")
            return
        if self.render_queue is None:
            return
        job_id = self._selected_queue_id()
        if job_id:
            self.render_queue.cancel(job_id)
            self._refresh_queue()

    def _queue_resume(self) -> None:
        if not self._ensure_render_queue():
            return
        job_id = self._selected_queue_id()
        if job_id:
            try:
                self.render_queue.resume(job_id)
            except ValueError as exc:
                QMessageBox.warning(self, "Fortsetzen nicht möglich", str(exc))
            self._refresh_queue()

    def _queue_discard(self) -> None:
        if not self._ensure_render_queue():
            return
        job_id = self._selected_queue_id()
        if job_id:
            try:
                self.render_queue.discard(job_id)
            except ValueError as exc:
                QMessageBox.warning(self, "Job kann nicht entfernt werden", str(exc))
            self._refresh_queue()

    def _queue_finished(self, _jobs) -> None:
        self._refresh_queue()
        counts = {status: sum(j.status == status for j in self.render_queue.jobs())
                  for status in ("COMPLETE", "FAILED", "BLOCKED", "CANCELLED")}
        self.statusBar().showMessage(
            "Queue abgeschlossen · " + " / ".join(
                f"{key}: {value}" for key, value in counts.items()), 12000)

    def _queue_failed(self, message: str) -> None:
        self.statusBar().showMessage("Queue-Systemfehler", 10000)
        QMessageBox.warning(self, "Renderqueue fehlgeschlagen", message)

    def _queue_worker_finished(self, worker: QueueRunThread) -> None:
        if self.queue_worker is worker:
            self.queue_worker = None
        worker.deleteLater()
        self._busy(False)
        self._refresh_queue()

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
        if self.model_worker is not None:
            self.model_worker.cancel()
            self.statusBar().showMessage("Modelldownload-Abbruch angefordert …")
        elif self.worker is not None:
            # Also catch QThreads queued for start but not yet isRunning().
            self.worker.cancel()
            self.statusBar().showMessage("Abbruch angefordert …")

    def closeEvent(self, event) -> None:
        if self.queue_worker is not None and self.queue_worker.isRunning():
            QMessageBox.information(
                self, "Renderqueue läuft",
                "Bitte die Renderqueue zuerst anhalten und den laufenden Job abschließen.")
            event.ignore()
            return
        if self.hf_check_worker is not None:
            QMessageBox.information(self, "Verbindungsprüfung läuft",
                                    "Bitte die laufende Verbindungskontrolle abschließen lassen.")
            event.ignore()
            return
        if self.model_worker is not None:
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
        if self._render_preview_dialog is not None:
            self._render_preview_dialog.close()
            self._render_preview_dialog = None
        if self.proxy_worker is not None:
            self.proxy_worker.cancel()
            if not self.proxy_worker.wait(3000):
                QMessageBox.information(
                    self, "Proxy wird beendet",
                    "FFmpeg verarbeitet den Abbruch noch. Bitte erneut schließen.")
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
        if self.render_queue is not None:
            try:
                self.render_queue.close()
            except RuntimeError as exc:
                QMessageBox.warning(self, "Renderqueue nicht beendet", str(exc))
                event.ignore()
                return
            self.render_queue = None
        self._save_workspace_layout(quiet=True)
        event.accept()


def main() -> None:
    application = QApplication(sys.argv)
    application.setApplicationName("StreamClipper")
    window = MainWindow()
    window.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
