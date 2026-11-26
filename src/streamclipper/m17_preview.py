"""Montage output-time overview and exact-render preview, separate from source playback."""
from PySide6.QtCore import Qt,Signal,QUrl,QThread
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QSlider,QProgressBar,QMessageBox)
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from pathlib import Path
import tempfile,threading

class MontageTimeline(QWidget):
    selected=Signal(int)
    def __init__(self,parent=None):
        super().__init__(parent);self.parts=();self.current=-1
        self.setMinimumHeight(78)
        self.setToolTip("Ausgabezeit vor optionalem Szenenplan-Trim; Klick wählt Montageabschnitt")
    def set_parts(self,beats,current=-1):
        self.parts=tuple(b.duration for b in beats);self.current=current;self.update()
    def set_current(self,index):
        self.current=index;self.update()
    def index_at(self,x):
        total=sum(self.parts);width=max(1,self.width()-16)
        if not total or not 8<=x<8+width:return -1
        point=(x-8)/width*total;elapsed=0.
        for i,d in enumerate(self.parts):
            elapsed+=d
            if point<elapsed:return i
        return -1
    def mousePressEvent(self,event):
        i=self.index_at(event.position().x())
        if i>=0:self.selected.emit(i)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total=sum(self.parts);w=max(1,self.width()-16)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.drawText(8,15,"Montage-Zeitachse (vor Szenenplan-Trim)")
        if total<=0:
            p.drawText(8,45,"Highlights hinzufügen");return
        elapsed=0.
        for i,d in enumerate(self.parts):
            x=8+round(w*elapsed/total);elapsed+=d
            end=8+round(w*elapsed/total)
            p.setPen(QPen(QColor("#e1c8ff") if i==self.current else QColor("#606078"),2 if i==self.current else 1))
            p.setBrush(QColor("#7847b8") if i==self.current else QColor("#3d5678"))
            p.drawRoundedRect(x,23,max(1,end-x-2),31,3,3)
            if end-x>=24:
                p.setPen(QColor("#ffffff"));p.drawText(x+4,43,str(i+1))
        p.setPen(self.palette().color(self.foregroundRole()))
        p.drawText(8,72,"0:00")
        label=f"{total:.1f} s";p.drawText(max(8,self.width()-p.fontMetrics().horizontalAdvance(label)-8),72,label)

class PreviewWorker(QThread):
    progress=Signal(int)
    outcome=Signal(object)
    def __init__(self,request,path,parent=None):
        super().__init__(parent);self.request=request;self.path=path;self.stop=threading.Event()
    def run(self):
        try:
            path=self.request.render(self.path,cancelled=self.stop.is_set,progress=self.progress.emit)
            self.outcome.emit((path,None))
        except Exception as exc:self.outcome.emit((None,str(exc)))

class PreviewProgress(QDialog):
    def __init__(self,worker,parent=None):
        super().__init__(parent);self.worker=worker;self.result=None
        self.setWindowTitle("Montage-Vorschau rendern");layout=QVBoxLayout(self)
        self.status=QLabel("Exportgetreue Vorschau wird erstellt …");layout.addWidget(self.status)
        bar=QProgressBar();layout.addWidget(bar);worker.progress.connect(bar.setValue)
        self.cancel=QPushButton("Abbrechen");layout.addWidget(self.cancel);self.cancel.clicked.connect(self.reject)
        worker.outcome.connect(self.receive);worker.finished.connect(self.accept)
    def receive(self,result):self.result=result
    def reject(self):
        self.worker.stop.set();self.cancel.setEnabled(False);self.status.setText("Abbruch läuft …")
    def closeEvent(self,event):
        if self.worker.isRunning():self.reject();event.ignore()
        else:super().closeEvent(event)

def play_preview(request,parent):
    # Exactly the same immutable request and renderer as export; selected
    # beat or complete short montage. No source-player mutation.
    temp=tempfile.TemporaryDirectory(prefix="sc-montage-preview-")
    try:
        worker=PreviewWorker(request,Path(temp.name)/"preview.mp4",parent)
        progress=PreviewProgress(worker,parent)
        worker.start();progress.exec();worker.wait()
        result=progress.result;cancelled=worker.stop.is_set()
        progress.deleteLater();worker.deleteLater()
        if cancelled or result is None or result[1]:
            if result and not cancelled:QMessageBox.warning(parent,"Vorschau",result[1])
            return
        dialog=QDialog(parent);dialog.setWindowTitle("Montage · exportgetreue Vorschau");dialog.resize(800,600)
        layout=QVBoxLayout(dialog)
        player=QMediaPlayer(dialog);audio=QAudioOutput(dialog);audio.setVolume(.6);player.setAudioOutput(audio)
        view=QVideoWidget(dialog);player.setVideoOutput(view);layout.addWidget(view,1)
        row=QHBoxLayout();layout.addLayout(row)
        toggle=QPushButton("Wiedergabe / Pause");row.addWidget(toggle)
        toggle.clicked.connect(lambda:player.pause() if player.playbackState()==QMediaPlayer.PlaybackState.PlayingState else player.play())
        seek=QSlider(Qt.Orientation.Horizontal);row.addWidget(seek,1)
        player.durationChanged.connect(lambda d:seek.setRange(0,max(1,d)))
        player.positionChanged.connect(lambda p:seek.setValue(p) if not seek.isSliderDown() else None)
        seek.sliderMoved.connect(player.setPosition)
        close=QPushButton("Schließen");layout.addWidget(close);close.clicked.connect(dialog.accept)
        player.setSource(QUrl.fromLocalFile(str(result[0])));player.play()
        try:dialog.exec()
        finally:
            player.stop();player.setSource(QUrl());player.setVideoOutput(None);player.setAudioOutput(None)
            dialog.deleteLater()
    finally:
        try:temp.cleanup()
        except OSError:pass # Windows decoder may temporarily retain a file handle
