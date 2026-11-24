"""Source-frame monitor with letterbox-correct normalized region selection."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QThread
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget
import threading
import time

from .media import sampled_jpeg_frames


def normalized_region(rect, a, b):
    if rect.width() <= 0 or rect.height() <= 0:
        raise ValueError("Bildfläche fehlt")
    def clamp(point):
        return (max(0., min(1., (point.x()-rect.x())/rect.width())),
                max(0., min(1., (point.y()-rect.y())/rect.height())))
    ax, ay = clamp(a)
    bx, by = clamp(b)
    x, y = min(ax,bx), min(ay,by)
    # Quantize edges rather than width independently.
    x, y, right, bottom = (round(v, 4) for v in (x,y,max(ax,bx),max(ay,by)))
    if right-x < .01 or bottom-y < .01:
        raise ValueError("Bildregion zu klein")
    return x, y, round(right-x, 4), round(bottom-y, 4)


class FrameWorker(QThread):
    ready = Signal(bytes)
    failed = Signal(str)

    def __init__(self, video, at, parent=None):
        super().__init__(parent)
        self.video, self.at = video, at
        self.cancelled = threading.Event()

    def run(self):
        deadline = time.monotonic()+20
        try:
            at, jpeg = next(sampled_jpeg_frames(
                self.video, max_frames=1, timestamps=[self.at],
                cancelled=lambda: self.cancelled.is_set() or time.monotonic() >= deadline))
            if not self.cancelled.is_set():
                self.ready.emit(jpeg)
        except Exception as exc:
            if not self.cancelled.is_set():
                self.failed.emit(str(exc))


class RegionMonitor(QWidget):
    region_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.image = QImage()
        self.region = (0.,0.,1.,1.)
        self.anchor = None
        self.cursor = None

    def set_frame(self, jpeg):
        self.image = QImage.fromData(jpeg)
        self.anchor = self.cursor = None
        self.update()
        return not self.image.isNull()

    def set_region(self, region):
        self.region = tuple(region)
        self.update()

    def image_rect(self):
        if self.image.isNull():
            return QRectF()
        scale = min(self.width()/self.image.width(), self.height()/self.image.height())
        w, h = self.image.width()*scale, self.image.height()*scale
        return QRectF((self.width()-w)/2, (self.height()-h)/2, w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#16191e"))
        rect = self.image_rect()
        if self.image.isNull():
            painter.setPen(QColor("#dddddd"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Quellbild laden")
            return
        painter.drawImage(rect, self.image)
        region = self.region
        if self.anchor is not None and self.cursor is not None:
            try:
                region = normalized_region(rect, self.anchor, self.cursor)
            except ValueError:
                pass
        x,y,w,h = region
        painter.setPen(QPen(QColor("#50e3c2"), 2))
        painter.drawRect(QRectF(rect.x()+x*rect.width(), rect.y()+y*rect.height(),
                                w*rect.width(), h*rect.height()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(event.position()):
            self.anchor = QPointF(event.position())
            self.cursor = self.anchor
            self.update()

    def mouseMoveEvent(self, event):
        if self.anchor is not None:
            self.cursor = QPointF(event.position())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.anchor is None:
            return
        try:
            region = normalized_region(self.image_rect(), self.anchor, event.position())
        except ValueError:
            pass
        else:
            self.set_region(region)
            self.region_changed.emit(region)
        finally:
            self.anchor = self.cursor = None
            self.update()
