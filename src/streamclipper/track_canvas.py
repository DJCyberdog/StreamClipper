"""Lightweight, non-rendering multitrack overview for the M11 editor.

The ruler shows *timeline positions*; clip blocks use source-relative lengths.
No frame decoding and no assertion that this is an export-faithful preview.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .editor_project import EditorProject
from .transcript_editor import format_timestamp


class TrackCanvas(QWidget):
    clipSelected = Signal(str)
    trackSelected = Signal(str)
    clipMoved = Signal(str, float)

    _LEFT = 128
    _TOP = 34
    _ROW = 36
    _COLORS = {
        "video": "#3684b7",
        "audio": "#409e7d",
        "captions": "#9977c7",
        "overlay": "#ce9155",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project: EditorProject | None = None
        self.view_start = 0.0
        self.view_end = 60.0
        self._selected = ""
        self._drag: tuple[str, float, float] | None = None
        self._preview_position: float | None = None
        self._playhead: float = 0.0
        self._selection: tuple[float, float] = (0.0, 0.0)
        self._snap_enabled = True
        self.setMinimumHeight(220)
        self.setMouseTracking(True)
        self.setToolTip("Clip anklicken = auswählen · Clip ziehen = Timeline-Position ändern. "
                        "Das ist ein Spurplan, noch keine gerenderte Mehrspur-Vorschau.")

    def set_project(self, project: EditorProject | None) -> None:
        self.project = project
        self.setMinimumHeight(max(200, self._TOP + self._ROW * len(project.tracks) + 8)
                              if project else 200)
        if project and not any(item.id == self._selected for item in project.items):
            self._selected = ""
        self.update()

    def set_playhead(self, second: float) -> None:
        """Source/timeline readout without moving the media decoder."""
        self._playhead = max(0.0, float(second))
        self.update()

    def set_selection(self, start: float, end: float) -> None:
        self._selection = (float(start), float(end))
        self.update()

    def set_snap_enabled(self, enabled: bool) -> None:
        self._snap_enabled = bool(enabled)
        self.update()

    def _snap_time(self, value: float, moving_id: str, clip_duration: float) -> float:
        """Magnet: 8px tolerance, nearest non-self clip edge/playhead/IN/OUT.

        Both edges of the moved clip can align to the same target, while
        snapping never changes source time, media bytes or track ownership.
        """
        if not self._snap_enabled or not self.project:
            return value
        threshold = 8 * (self.view_end - self.view_start) / max(
            1, self.width() - self._LEFT - 8)
        boundaries = [self._playhead, *self._selection]
        for item in self.project.items:
            if item.id != moving_id:
                boundaries.extend((item.timeline_start,
                                   item.timeline_start + item.source_end - item.source_start))
        best_distance, best = threshold, value
        for point in boundaries:
            for candidate in (point, point - clip_duration):
                distance = abs(candidate-value)
                if distance < best_distance:
                    best_distance, best = distance, candidate
        return max(0.0, round(best, 3))

    def set_visible_range(self, start: float, end: float) -> None:
        if not 0 <= start < end:
            return
        self.view_start, self.view_end = float(start), float(end)
        self.update()

    def _x(self, timestamp: float) -> float:
        usable = max(1, self.width() - self._LEFT - 8)
        return self._LEFT + usable * (timestamp - self.view_start) / (
            self.view_end - self.view_start)

    def _time(self, x: float) -> float:
        usable = max(1, self.width() - self._LEFT - 8)
        return self.view_start + (x - self._LEFT) * (
            self.view_end - self.view_start) / usable

    def set_selected_clip(self, clip_id: str | None) -> None:
        self._selected = clip_id or ""
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#17202d"))
        width = self.width()
        p.setPen(QColor("#afc1d7"))
        p.drawText(9, 22, "SPUREN")
        if self._snap_enabled:
            p.setPen(QColor("#78B9DB"))
            p.drawText(max(self._LEFT+12, width-64), 22, "SNAP")
        p.drawText(self._LEFT + 3, 22, format_timestamp(self.view_start)[:-4])
        p.drawText(max(self._LEFT + 10, width - 85), 22,
                   format_timestamp(self.view_end)[:-4])
        for i in range(1, 5):
            x = round(self._x(self.view_start + i * (self.view_end - self.view_start) / 5))
            p.setPen(QPen(QColor("#354155"), 1))
            p.drawLine(x, self._TOP - 3, x, self.height())
        if not self.project:
            p.setPen(QColor("#91a6bf"))
            p.drawText(10, 80, "Eine Aufnahme öffnen, um Spuren zu sehen.")
            p.end()
            return
        # A single timebase governs the waveform above and the track lanes.
        left_sel = max(self._LEFT, self._x(self._selection[0]))
        right_sel = min(width, self._x(self._selection[1]))
        if right_sel > left_sel:
            p.fillRect(QRectF(left_sel, self._TOP, right_sel-left_sel,
                              max(0, self.height()-self._TOP)),
                       QColor(248, 181, 65, 18))
        for row, track in enumerate(self.project.tracks):
            y = self._TOP + row * self._ROW
            p.fillRect(QRectF(0, y, width, self._ROW - 1),
                       QColor("#202d3e" if row % 2 == 0 else "#1b2635"))
            p.setPen(QColor("#e0e6f0"))
            p.drawText(8, y + 21, track.name[:18])
            if track.locked:
                p.setPen(QColor("#deb876"))
                p.drawText(self._LEFT - 24, y + 21, "L")
            if track.muted:
                p.setPen(QColor("#bd7781"))
                p.drawText(self._LEFT - 42, y + 21, "M")
            for item in self.project.items:
                if item.track_id != track.id:
                    continue
                pos = (self._preview_position
                       if self._drag and self._drag[0] == item.id
                       else item.timeline_start)
                end = pos + item.source_end - item.source_start
                if end < self.view_start or pos > self.view_end:
                    continue
                a, b = max(self._LEFT + 1, self._x(pos)), min(width - 2, self._x(end))
                if b <= a:
                    continue
                p.setBrush(QColor(self._COLORS[track.kind]))
                p.setPen(QPen(QColor("#f2d38a" if self._selected == item.id
                                    else "#405b73"), 2 if self._selected == item.id else 1))
                box = QRectF(a, y + 4, max(1, b - a), self._ROW - 9)
                p.drawRoundedRect(box, 4, 4)
                p.save()
                p.setClipRect(box)
                p.setPen(QColor("#ffffff"))
                p.drawText(QRectF(a + 4, y + 6, max(0, b - a - 6),
                                  self._ROW - 13),
                           Qt.AlignmentFlag.AlignVCenter, (item.label or item.id)[:60])
                p.restore()
        x = self._x(self._playhead)
        if self._LEFT <= x <= width:
            p.setPen(QPen(QColor("#FF655F"), 2))
            p.drawLine(round(x), 0, round(x), self.height())
        p.end()

    def mousePressEvent(self, event):
        if not self.project or event.button() != Qt.MouseButton.LeftButton:
            return
        row = int((event.position().y() - self._TOP) // self._ROW)
        if not 0 <= row < len(self.project.tracks):
            return
        track = self.project.tracks[row]
        self.trackSelected.emit(track.id)
        at = self._time(event.position().x())
        if event.position().x() < self._LEFT:
            return
        for item in reversed(self.project.items):
            if (item.track_id == track.id
                    and item.timeline_start <= at <=
                    item.timeline_start + item.source_end - item.source_start):
                self.set_selected_clip(item.id)
                self.clipSelected.emit(item.id)
                if not track.locked and item.id != "source":
                    self._drag = (item.id, item.timeline_start, event.position().x())
                    self._preview_position = item.timeline_start
                return

    def mouseMoveEvent(self, event):
        if not self._drag:
            return
        _, old_position, down_x = self._drag
        delta = (event.position().x() - down_x) * (
            self.view_end - self.view_start) / max(1, self.width() - self._LEFT - 8)
        candidate = max(0.0, round(old_position + delta, 3))
        if self.project:
            item = next(i for i in self.project.items if i.id == self._drag[0])
            duration = item.source_end - item.source_start
            candidate = self._snap_time(candidate, item.id, duration)
            candidate = min(candidate, max(0.0, 86400-duration))
        self._preview_position = candidate
        self.update()

    def mouseReleaseEvent(self, event):
        if not self._drag:
            return
        self.mouseMoveEvent(event)
        item_id, original, _ = self._drag
        position = self._preview_position
        self._drag = None
        self._preview_position = None
        self.update()
        if position is not None and abs(position - original) >= 0.05:
            self.clipMoved.emit(item_id, position)
