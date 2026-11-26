"""Thumbnail designer using a frozen RenderRequest and a worker-owned frame."""
from threading import Event
from .m18_language import tr,trf
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QDoubleSpinBox,QComboBox,
    QLineEdit,QLabel,QPushButton,QFileDialog,QMessageBox,QHBoxLayout)
from .thumbnail import ThumbnailDesign,SIZES,capture_composed_frame,compose_thumbnail,save_thumbnail


class CaptureWorker(QThread):
    ready=Signal(object)
    failed=Signal(str)
    progress=Signal(int)
    def __init__(self,request,at,parent):
        super().__init__(parent);self.request=request;self.at=at;self.stop=Event()
    def run(self):
        try:self.ready.emit(capture_composed_frame(self.request,self.at,cancelled=self.stop.is_set,
                                                   progress=self.progress.emit))
        except Exception as exc:self.failed.emit(str(exc))


class ThumbnailDialog(QDialog):
    def __init__(self,request,parent=None):
        super().__init__(parent)
        self.request=request
        self.worker=None;self.frame=None;self.closing=False
        self.setWindowTitle("Thumbnail Designer")
        self.resize(760,680)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.at=self.number(0,max(0,request.duration-.04),min(request.duration/2,max(0,request.duration-.04)))
        self.at.setDecimals(3)
        self.size=QComboBox()
        for w,h in SIZES:self.size.addItem(f"{w} × {h}",(w,h))
        self.fit=QComboBox();self.fit.addItem(tr("Füllen / Crop"),"crop");self.fit.addItem(tr("Einpassen"),"fit")
        self.title=QLineEdit();self.title.setMaxLength(240)
        self.foreground=QLineEdit(request.caption_style.text_color)
        self.background=QLineEdit("#182036")
        self.accent=QLineEdit(request.caption_style.accent_color)
        self.x=self.number(0,1,.05);self.y=self.number(0,1,.65)
        self.w=self.number(.05,1,.90);self.h=self.number(.05,1,.30)
        for label,field in ((tr("Clip-Zeit nach Szenenreihenfolge (s)"),self.at),("Format",self.size),
            ("Bildanpassung",self.fit),(tr("Titel"),self.title),(tr("Textfarbe"),self.foreground),
            (tr("Hintergrund"),self.background),(tr("Akzent"),self.accent),("X",self.x),("Y",self.y),
            (tr("Breite"),self.w),(tr("Höhe"),self.h)):form.addRow(label,field)
        layout.addLayout(form)
        self.preview=QLabel(tr("Zuerst Frame aus dem gerenderten Clip laden."))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setMinimumHeight(180)
        self.preview.setStyleSheet("background:#20232c;")
        layout.addWidget(self.preview,1)
        self.hint=QLabel(tr("Rendert das vollständige gewählte Highlight (max. 60 s). "
                         "Die Bildzeit bezieht sich auf den fertigen Clip, nicht das Original."))
        self.hint.setWordWrap(True);layout.addWidget(self.hint)
        row=QHBoxLayout()
        self.capture=QPushButton(tr("Renderframe laden"));self.capture.clicked.connect(self.start_capture)
        self.refresh_button=QPushButton(tr("Design aktualisieren"));self.refresh_button.clicked.connect(self.refresh)
        self.save_button=QPushButton(tr("PNG / JPEG speichern …"));self.save_button.clicked.connect(self.save)
        close=QPushButton(tr("Schließen / Abbrechen"));close.clicked.connect(self.reject)
        for button in (self.capture,self.refresh_button,self.save_button,close):row.addWidget(button)
        layout.addLayout(row);self.controls()

    def number(self,a,b,v):
        field=QDoubleSpinBox();field.setDecimals(3);field.setRange(a,b);field.setValue(v)
        field.setSingleStep(.05);return field

    def design(self):
        w,h=self.size.currentData()
        return ThumbnailDesign(w,h,self.fit.currentData(),self.title.text(),self.foreground.text(),
            self.background.text(),self.accent.text(),self.x.value(),self.y.value(),
            self.w.value(),self.h.value()).validate()

    def controls(self):
        busy=self.worker is not None
        self.capture.setEnabled(not busy);self.at.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy and self.frame is not None)
        self.save_button.setEnabled(not busy and self.frame is not None)

    def start_capture(self):
        if self.worker:return
        self.frame=None
        self.preview.setText(tr("Clip wird gerendert …"))
        self.worker=CaptureWorker(self.request,self.at.value(),self)
        self.worker.ready.connect(self.ready)
        self.worker.failed.connect(self.hint.setText)
        self.worker.progress.connect(lambda value:self.hint.setText(f"Renderframe · {value}%"))
        self.worker.finished.connect(self.done)
        self.controls();self.worker.start()

    def ready(self,frame):
        if self.closing:return
        self.frame=frame;self.captured_at=self.at.value()
        self.hint.setText(trf("Renderframe bei {at:.3f} s geladen",at=self.captured_at))
        self.refresh()

    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater();self.controls()
        if self.closing:super().reject()

    def refresh(self):
        if self.frame is None:return
        try:
            image=compose_thumbnail(self.frame,self.design())
            qt=QImage(image.tobytes(),image.width,image.height,image.width*3,QImage.Format.Format_RGB888).copy()
            self.preview.setPixmap(QPixmap.fromImage(qt).scaled(680,300,Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
        except (ValueError,RuntimeError) as exc:self.hint.setText(tr(str(exc)))

    def save(self):
        if self.worker or self.frame is None:return
        if self.at.value()!=self.captured_at:
            QMessageBox.warning(self,"Thumbnail",tr("Bildzeit geändert. Bitte neuen Renderframe laden."));return
        destination,_=QFileDialog.getSaveFileName(self,tr("Thumbnail speichern"),"thumbnail.png","PNG (*.png);;JPEG (*.jpg *.jpeg)")
        if not destination:return
        try:target=save_thumbnail(self.frame,self.design(),destination)
        except (OSError,ValueError,RuntimeError) as exc:
            QMessageBox.warning(self,"Thumbnail",tr(str(exc)));return
        self.hint.setText(tr("Gespeichert: ")+str(target));self.refresh()

    def reject(self):
        if self.worker:
            self.closing=True;self.worker.stop.set();self.hint.setText(tr("Abbruch läuft …"));return
        super().reject()
