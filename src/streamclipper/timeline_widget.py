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
from .word_editor import words_in_clip


class TimelineWidget(QWidget):
    playheadMoved = Signal(float)
    selectionChanged = Signal(float, float)
    subtitleSelected = Signal(int)
    wordSelected = Signal(int, int)
    wordBoundaryCommitted = Signal(int, int, str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(174)
        self.setMouseTracking(True)
        self.setToolTip(
            "Klick = springen · Markierungen ziehen = trimmen · "
            "Umschalt + Ziehen = neuen Bereich auswählen · "
            "Wort anklicken = bearbeiten · Wortkante ziehen = Anfang/Ende korrigieren")
        self.duration = 1.0
        self.zoom = 1.0
        self.offset = 0.0
        self.position = 0.0
        self.in_point = 0.0
        self.out_point = 1.0
        self.peaks: list[float] = []
        self.candidates: list[Candidate] = []
        self.cues: list[TranscriptSegment] = []
        self.selected_word: tuple[int, int] | None = None
        self.caption_offset = 0.0
        self.left_gutter = 0  # M12-UX shares 128px time origin with track lanes
        self._drag: str | None = None
        self._anchor = 0.0
        self._word_drag: tuple[int, int, str] | None = None
        self._word_preview: tuple[int, int, float, float] | None = None

    def set_duration(self, duration: float):
        self.duration = max(0.001, duration)
        self.in_point, self.out_point = 0.0, min(self.duration, 25.0)
        self.zoom, self.offset, self.position = 1.0, 0.0, 0.0
        self.peaks.clear()
        self.candidates.clear()
        self.cues.clear()
        self.selected_word = None
        self._word_preview = None
        self._word_drag = None
        self.update()

    def set_zoom(self, zoom: float, center: float | None = None):
        old_start, old_end = self.visible()
        center = (old_start + old_end) / 2 if center is None else center
        self.zoom = max(1.0, min(3000.0, zoom))
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
        self._word_preview = None
        self.update()

    def set_selected_word(self, segment: int | None, word: int | None = None):
        self.selected_word = (segment, word) if segment is not None and word is not None else None
        self.update()

    def ensure_visible(self, t: float):
        a, b = self.visible()
        if not a <= t <= b:
            self.set_offset(t - (b - a) / 2)

    def set_left_gutter(self, width: int) -> None:
        """Align waveform and TrackCanvas rulers without changing source times.

        Default 0 preserves standalone TimelineWidget / M11 compatibility.
        """
        if not isinstance(width, int) or not 0 <= width <= 280:
            raise ValueError("Ungültiger Timeline-Rand")
        self.left_gutter = width
        self.update()

    def _plot_width(self) -> int:
        return max(1, self.width() - self.left_gutter - (8 if self.left_gutter else 0))

    def _x(self, sec: float) -> float:
        return self.left_gutter + x_at_time(
            sec, self._plot_width(), self.duration, self.zoom, self.offset)

    def _t(self, px: float) -> float:
        return time_at_x(
            max(0, px-self.left_gutter), self._plot_width(),
            self.duration, self.zoom, self.offset)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#161c28"))
        if w <= 0 or h <= 0:
            return
        a, b = self.visible()
        gutter, plot_width = self.left_gutter, self._plot_width()
        # Three tracks: ruler, audio, subtitles.
        p.fillRect(QRectF(0, 25, w, 94), QColor("#202b3d"))
        p.fillRect(QRectF(0, 122, w, h - 122), QColor("#1e2330"))
        if gutter:
            p.fillRect(QRectF(0, 0, gutter, h), QColor("#202c3b"))
            p.setPen(QColor("#D6E5F5"))
            p.drawText(9, 71, "WELLENFORM")
            p.drawText(9, 146, "WÖRTER")
        p.setFont(QFont("Arial", 9))
        p.setPen(QColor("#b4c4da"))
        ticks = 10
        for i in range(ticks + 1):
            t = a + (b - a) * i / ticks
            x = round(gutter + plot_width * i / ticks)
            p.drawLine(x, 19, x, 25)
            p.drawText(min(w-92, max(gutter+3, x+2)), 14, format_timestamp(t)[:-4])
        # Highlights under waveform: green for manual / blue for AI suggestions.
        for clip in self.candidates:
            if clip.end <= a or clip.start >= b:
                continue
            left, right = max(gutter, self._x(clip.start)), min(w, self._x(clip.end))
            p.fillRect(QRectF(left, 30, max(1, right-left), 83),
                       QColor(38, 114, 75, 92) if clip.origin == "manual"
                       else QColor(47, 103, 178, 66))
        # Visible-only waveform sampling; never retain rasterized 6h pixmaps.
        amplitudes = waveform_window(
            self.peaks, self.duration, a, b, plot_width)
        p.setPen(QPen(QColor("#67bee5"), 1))
        middle = 70
        for x, amp in enumerate(amplitudes):
            height = max(1, round(41 * amp))
            p.drawLine(gutter+x, middle-height, gutter+x, middle+height)
        # WORD track: only the current in/out (highlight) range, never the
        # entire 6-hour transcript. Purple = native timing; amber = estimated.
        for segment_index, word_index, word in words_in_clip(
                self.cues, self.in_point, self.out_point):
            if self._word_preview is not None and self._word_preview[:2] == (segment_index, word_index):
                cue_start, cue_end = self._word_preview[2:]
            else:
                cue_start, cue_end = word.start, word.end
            cue_start += self.caption_offset
            cue_end += self.caption_offset
            if cue_end <= a or cue_start >= b:
                continue
            left, right = max(gutter, self._x(cue_start)), min(w, self._x(cue_end))
            if right-left < 2:
                continue
            selected = self.selected_word == (segment_index, word_index)
            color = (QColor('#169b8e') if selected else
                     QColor('#b8873f') if word.origin == 'estimated' else
                     QColor('#55418b'))
            p.fillRect(QRectF(left+1, 128, max(1, right-left-2), h-137), color)
            if right-left > 20:
                p.setPen(QColor('#edf2fa'))
                p.drawText(QRectF(left+4, 131, max(0, right-left-8), h-145),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           word.text[:50])
        # Selection overlay and In/Out grab handles.
        left, right = self._x(self.in_point), self._x(self.out_point)
        p.fillRect(QRectF(max(gutter, left), 24,
                          max(0, min(w,right)-max(gutter,left)), h-24),
                   QColor(248, 181, 65, 33))
        p.setPen(QPen(QColor("#ffcf75"), 2))
        for x, label in ((left, "IN"), (right, "OUT")):
            if gutter <= x <= w:
                p.drawLine(int(x), 25, int(x), h)
                p.drawText(int(x)+3 if x < w-35 else int(x)-32, 39, label)
        x = self._x(self.position)
        if gutter <= x <= w:
            p.setPen(QPen(QColor("#ff655f"), 2))
            p.drawLine(int(x), 0, int(x), h)
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = event.position().x(), event.position().y()
        if x < self.left_gutter:
            return
        t = self._t(x)
        # Bottom track chooses individual words in current highlight.
        if y >= 122 and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            for i, j, word in words_in_clip(self.cues, self.in_point, self.out_point):
                if word.start + self.caption_offset <= t <= word.end + self.caption_offset:
                    self.set_selected_word(i, j)
                    self.wordSelected.emit(i, j)
                    left = self._x(word.start + self.caption_offset)
                    right = self._x(word.end + self.caption_offset)
                    # Narrow blocks have no safe drag targets: selecting still works.
                    if right - left >= 18 and abs(x-left) <= 7:
                        self._word_drag = (i, j, 'start')
                    elif right - left >= 18 and abs(x-right) <= 7:
                        self._word_drag = (i, j, 'end')
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
        if self._word_drag:
            i, j, edge = self._word_drag
            for ref_i, ref_j, word in words_in_clip(self.cues, self.in_point, self.out_point):
                if (ref_i, ref_j) != (i, j):
                    continue
                t = max(0.0, min(self.duration,
                    self._t(event.position().x()) - self.caption_offset))
                if edge == 'start':
                    t = min(t, word.end - .05)
                    self._word_preview = (i, j, round(max(0.0,t),3), word.end)
                else:
                    t = max(t, word.start + .05)
                    self._word_preview = (i, j, word.start, round(min(self.duration,t),3))
                self.update()
                return
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
        if self._word_drag:
            self.mouseMoveEvent(event)
            i, j, edge = self._word_drag
            if self._word_preview is not None:
                t = self._word_preview[2 if edge == 'start' else 3]
                self.wordBoundaryCommitted.emit(i, j, edge, t)
            self._word_drag = None
            self._word_preview = None
            self.update()
            return
        if self._drag:
            self.mouseMoveEvent(event)
            self._drag = None
