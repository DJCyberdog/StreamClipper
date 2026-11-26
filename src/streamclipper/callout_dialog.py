"""Editable graphics on the existing timeline; preview uses shared rasterizer."""
from .m18_language import tr
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QComboBox,QPlainTextEdit,
    QLineEdit,QDoubleSpinBox,QCheckBox,QLabel,QPushButton,QDialogButtonBox,QMessageBox)
from .callouts import Callout,rasterize


class CalloutDialog(QDialog):
    def __init__(self,start,end,duration,canvas,item=None,parent=None):
        super().__init__(parent)
        self.canvas=canvas
        self.spec=item.callout if item else Callout(text="Highlight!")
        self.geometry_values={}
        self.setWindowTitle(tr("Text und Callout gestalten"))
        self.resize(560,730)
        layout=QVBoxLayout(self)
        form=QFormLayout()
        self.kind=QComboBox()
        for label,value in (("Text","text"),(tr("Sprechblase"),"bubble"),(tr("Pfeil"),"arrow"),
                            (tr("Rechteck"),"rectangle"),("Ellipse","ellipse")):self.kind.addItem(label,value)
        self.kind.setCurrentIndex(self.kind.findData(self.spec.kind))
        self.text=QPlainTextEdit(self.spec.text);self.text.setMaximumHeight(75)
        self.foreground=QLineEdit(self.spec.foreground)
        self.background=QLineEdit(self.spec.background)
        self.accent=QLineEdit(self.spec.accent)
        self.direction=QComboBox()
        for label,value in ((tr("Rechts"),"right"),(tr("Links"),"left"),(tr("Oben"),"up"),(tr("Unten"),"down")):self.direction.addItem(label,value)
        self.direction.setCurrentIndex(self.direction.findData(self.spec.direction))
        self.filled=QCheckBox(tr("Hintergrund füllen"));self.filled.setChecked(self.spec.filled)
        self.scale=self.number(.5,2,self.spec.font_scale)
        self.start=self.number(0,duration,item.timeline_start if item else start)
        self.end=self.number(0,duration,item.timeline_start+item.source_end-item.source_start if item else end)
        self.x=self.number(0,1,item.x if item else .1)
        self.y=self.number(0,1,item.y if item else .1)
        self.w=self.number(.05,1,item.width if item else .8)
        self.h=self.number(.05,1,item.height if item else .2)
        self.opacity=self.number(0,1,item.opacity if item else 1)
        for label,field in ((tr("Typ"),self.kind),("Text",self.text),(tr("Textfarbe"),self.foreground),
                (tr("Hintergrund"),self.background),(tr("Akzent"),self.accent),(tr("Pfeilrichtung"),self.direction),
                (tr("Füllung"),self.filled),(tr("Schriftgröße"),self.scale),("Start (s)",self.start),
                (tr("Ende (s)"),self.end),(tr("X (relativ)"),self.x),(tr("Y (relativ)"),self.y),
                (tr("Breite"),self.w),(tr("Höhe"),self.h),(tr("Deckkraft"),self.opacity)):
            form.addRow(label,field)
        layout.addLayout(form)
        self.preview=QLabel();self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(120)
        self.preview.setStyleSheet("background:#303038; border:1px solid #666;")
        layout.addWidget(self.preview,1)
        refresh=QPushButton(tr("Grafikvorschau aktualisieren"));refresh.clicked.connect(self.refresh);layout.addWidget(refresh)
        hint=QLabel(tr("Position im Ausgabeformat, nach dem Kamera-Crop. Die Grafikvorschau zeigt das Element, "
                    "die Render-Vorschau anschließend den vollständigen Clip."))
        hint.setWordWrap(True);layout.addWidget(hint)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.finish);box.rejected.connect(self.reject);layout.addWidget(box)
        self.refresh()

    def number(self,a,b,value):
        field=QDoubleSpinBox();field.setDecimals(3);field.setRange(a,b);field.setValue(value);field.setSingleStep(.05)
        return field

    def read(self):
        spec=Callout(self.kind.currentData(),self.text.toPlainText(),self.foreground.text().strip(),
            self.background.text().strip(),self.accent.text().strip(),self.direction.currentData(),
            self.scale.value(),self.filled.isChecked()).validate()
        x,y,w,h=self.x.value(),self.y.value(),self.w.value(),self.h.value()
        if x+w>1.000001 or y+h>1.000001 or self.start.value()>=self.end.value():
            raise ValueError("Ungültiger Zeitbereich oder Grafik außerhalb des Bildes")
        return spec,dict(timeline_start=self.start.value(),source_end=self.end.value()-self.start.value(),
                          x=x,y=y,width=w,height=h,opacity=self.opacity.value())

    def render(self):
        spec,values=self.read()
        w,h=self.canvas
        image=rasterize(spec,max(2,round(w*values["width"]/2)*2),max(2,round(h*values["height"]/2)*2))
        image.putalpha(image.getchannel("A").point(lambda p:round(p*values["opacity"])))
        data=image.tobytes()
        qt=QImage(data,image.width,image.height,image.width*4,QImage.Format.Format_RGBA8888).copy()
        self.preview.setPixmap(QPixmap.fromImage(qt).scaled(500,160,Qt.AspectRatioMode.KeepAspectRatio,
                                                            Qt.TransformationMode.SmoothTransformation))
        return spec,values

    def refresh(self):
        try:self.render()
        except (ValueError,RuntimeError,ImportError) as exc:self.preview.setText(str(exc))

    def finish(self):
        try:self.spec,self.geometry_values=self.render()
        except (ValueError,RuntimeError,ImportError) as exc:
            QMessageBox.warning(self,tr("Callout prüfen"),str(exc));return
        self.accept()
