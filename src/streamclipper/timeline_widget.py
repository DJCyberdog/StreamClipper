"""Zoomable, bounded-memory waveform / caption timeline for PySide6.

Drawing and interaction never decode media. One external worker supplies a
bounded set of waveform peaks. Time mapping is tested in the pure core.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .models import Candidate, TranscriptSegment
from .timeline import (time_at_x, visible_range, waveform_window, x_at_time)
from .transcript_editor import format_timestamp


class TimelineWidget(QWidget):
    playheadMoved = Signal(float)
    selectionChanged = Signal(float, float)
    subtitleSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(174)
        self.setMouseTracking(True)
        self.setToolTip(
            "Klick = springen · Markierungen ziehen = trimmen · "
            "Umschalt + Ziehen = neuen Bereich auswählen · "
            "Untertitel anklicken = Text bearbeiten")
        self.duration = 1.0
        self.zoom = 1.0
        self.offset = 0.0
        self.position = 0.0
        self.in_point = 0.0
        self.out_point = 1.0
        self.peaks: list[float] = []
        self.candidates: list[Candidate] = []
        self.cues: list[TranscriptSegment] = []
        self.caption_offset = 0.0
        self._drag: str | None = None
        self._anchor = 0.0

    def set_duration(self, duration: float):
        self.duration = max(0.001, duration)
        self.in_point, self.out_point = 0.0, min(self.duration, 25.0)
        self.zoom, self.offset, self.position = 1.0, 0.0, 0.0
        self.peaks.clear()
        self.candidates.clear()
        self.cues.clear()
        self.update()

    def set_zoom(self, zoom: float, center: float | None = None):
        old_start, old_end = self.visible()
        center = (old_start + old_end) / 2 if center is None else center
        self.zoom = max(1.0, min(200.0, zoom))
        self.set_offset(center - self.duration / self.zoom / 2)

    def set_offset(self, offset: float):
        start, _ = visible_range(self.duration, self.zoom, offset)
        self.offset = start
        self.update()

    def visible(self) -> tuple[float, float]:
        return visible_range(self.duration, self.zoom, self.offset)

    def set_position(self, value: float):
        self.position = max(0.0, min(self.duration, value))
        self.update()

    def set_selection(self, start: float, end: float, *, emit: bool = False):
        start = max(0.0, min(self.duration, start))
        end = max(start + 0.05, min(self.duration, end))
        if end > self.duration:
            end = self.duration
            start = max(0.0, end - 0.05)
        self.in_point, self.out_point = start, end
        self.update()
        if emit:
            self.selectionChanged.emit(start, end)

    def set_peaks(self, peaks: list[float]):
        self.peaks = peaks[:65536]
        self.update()

    def set_caption_offset(self, value: float):
        self.caption_offset = value
        self.update()

    def set_annotations(self, candidates: list[Candidate], cues: list[TranscriptSegment]):
        self.candidates = candidates
        self.cues = cues
        self.update()

    def ensure_visible(self, t: float):
        a, b = self.visible()
        if not a <= t <= b:
            self.set_offset(t - (b - a) / 2)

    def _x(self, sec: float) -> float:
        return x_at_time(sec, max(1, self.width()), self.duration,
                         self.zoom, self.offset)

    def _t(self, px: float) -> float:
        return time_at_x(px, max(1, self.width()), self.duration,
                         self.zoom, self.offset)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#161c28"))
        if w <= 0 or h <= 0:
            return
        a, b = self.visible()
        # Three tracks: ruler, audio, subtitles.
        p.fillRect(QRectF(0, 25, w, 94), QColor("#202b3d"))
        p.fillRect(QRectF(0, 122, w, h - 122), QColor("#1e2330"))
        p.setFont(QFont("Arial", 9))
        p.setPen(QColor("#b4c4da"))
        ticks = 10
        for i in range(ticks + 1):
            t = a + (b - a) * i / ticks
            x = round(w * i / ticks)
            p.drawLine(x, 19, x, 25)
            p.drawText(min(w-92, max(3, x + 2)), 14, format_timestamp(t)[:-4])
        # Highlights under waveform: green for manual / blue for AI suggestions.
        for clip in self.candidates:
            if clip.end <= a or clip.start >= b:
                continue
            left, right = max(0, self._x(clip.start)), min(w, self._x(clip.end))
            p.fillRect(QRectF(left, 30, max(1, right-left), 83),
                       QColor(38, 114, 75, 92) if clip.origin == "manual"
                       else QColor(47, 103, 178, 66))
        # Visible-only waveform sampling; never retain rasterized 6h pixmaps.
        amplitudes = waveform_window(self.peaks, self.duration, a, b, w)
        p.setPen(QPen(QColor("#67bee5"), 1))
        middle = 70
        for x, amp in enumerate(amplitudes):
            height = max(1, round(41 * amp))
            p.drawLine(x, middle-height, x, middle+height)
        # Caption track, clickable blocks. Long captions collapse visually.
        p.setPen(QColor("#edf2fa"))
        for index, cue in enumerate(self.cues):
            cue_start, cue_end = cue.start + self.caption_offset, cue.end + self.caption_offset
            if cue_end <= a or cue_start >= b:
                continue
            left, right = max(0, self._x(cue_start)), min(w, self._x(cue_end))
            if right-left < 2:
                continue
            p.fillRect(QRectF(left+1, 128, max(1, right-left-2), h-137),
                       QColor("#55418b"))
            if right-left > 55:
                p.drawText(QRectF(left+5, 131, right-left-10, h-145),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           cue.text[:60])
        # Selection overlay and In/Out grab handles.
        left, right = self._x(self.in_point), self._x(self.out_point)
        p.fillRect(QRectF(max(0, left), 24, max(0, min(w,right)-max(0,left)), h-24),
                   QColor(248, 181, 65, 33))
        p.setPen(QPen(QColor("#ffcf75"), 2))
        for x, label in ((left, "IN"), (right, "OUT")):
            if 0 <= x <= w:
                p.drawLine(int(x), 25, int(x), h)
                p.drawText(int(x)+3 if x < w-35 else int(x)-32, 39, label)
        x = self._x(self.position)
        if 0 <= x <= w:
            p.setPen(QPen(QColor("#ff655f"), 2))
            p.drawLine(int(x), 0, int(x), h)
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = event.position().x(), event.position().y()
        t = self._t(x)
        # Bottom track lets the user jump directly to subtitle editing.
        if y >= 122 and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            for i, cue in enumerate(self.cues):
                if cue.start + self.caption_offset <= t <= cue.end + self.caption_offset:
                    self.subtitleSelected.emit(i)
                    return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._drag = "new"
            self._anchor = t
            self.set_selection(t, min(self.duration, t+0.1), emit=True)
        elif abs(x - self._x(self.in_point)) <= 11:
            self._drag = "in"
        elif abs(x - self._x(self.out_point)) <= 11:
            self._drag = "out"
        else:
            self._drag = "playhead"
            self.playheadMoved.emit(t)

    def mouseMoveEvent(self, event):
        if not self._drag:
            return
        t = self._t(event.position().x())
        if self._drag == "in":
            self.set_selection(min(t, self.out_point - .05), self.out_point, emit=True)
        elif self._drag == "out":
            self.set_selection(self.in_point, max(t, self.in_point + .05), emit=True)
        elif self._drag == "new":
            a, b = sorted((self._anchor, t))
            self.set_selection(a, max(a + .05, b), emit=True)
        elif self._drag == "playhead":
            self.playheadMoved.emit(t)

    def mouseReleaseEvent(self, event):
        if self._drag:
            self.mouseMoveEvent(event)
            self._drag = None
