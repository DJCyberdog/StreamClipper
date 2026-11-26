"""Explicit ordered montage editing dialog. Original highlights are immutable."""
from dataclasses import replace
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QComboBox,
    QPushButton,QLabel,QInputDialog,QFileDialog,QMessageBox)
from .montage import Beat,Montage,speed_ramp,LOOKS

class MontageDialog(QDialog):
    def __init__(self,analysis,parent=None):
        super().__init__(parent)
        self.analysis=analysis;self.beats=[];self.plan=None
        self.setWindowTitle("M17 · Montage & Effekte");self.resize(700,450)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Originalaufnahme · eigenständige Komposition ohne bestehende Projektspuren"))
        self.source=QComboBox()
        for c in analysis.candidates:self.source.addItem(f"{c.start:.2f}–{c.end:.2f}s · {c.reason[:65]}",c)
        layout.addWidget(self.source)
        self.list=QListWidget();layout.addWidget(self.list)
        for group in [
            [("Hinzufügen",self.add),("Entfernen",self.remove),("↑",lambda:self.move(-1)),("↓",lambda:self.move(1))],
            [("Zeit & Tempo",self.timing),("Tempo-Rampe",self.ramp),("Standbild",self.freeze)],
            [("Look / LUT",self.look),("Eigener Sound",self.sound),("Effekte zurücksetzen",self.reset)]]:
            row=QHBoxLayout();layout.addLayout(row)
            for label,callback in group:
                btn=QPushButton(label);btn.clicked.connect(callback);row.addWidget(btn)
        self.aspect=QComboBox();self.aspect.addItems(["9:16","16:9","1:1"]);layout.addWidget(self.aspect)
        self.encoder=QComboBox()
        for label,key in [("H.264 Auto","auto_h264"),("CPU","cpu_h264"),("NVENC","nvenc_h264")]:self.encoder.addItem(label,key)
        layout.addWidget(self.encoder)
        self.total=QLabel();layout.addWidget(self.total)
        row=QHBoxLayout();layout.addLayout(row)
        for label,fn in [("Abbrechen",self.reject),("Montage exportieren",self.finish)]:
            btn=QPushButton(label);btn.clicked.connect(fn);row.addWidget(btn)
        self.refresh()

    def refresh(self,i=0):
        self.list.clear()
        for b in self.beats:self.list.addItem(f"{b.start:.2f}–{b.end:.2f}s · {b.speed:g}x · Hold {b.freeze:g}s · {b.look}"+(" · LUT" if b.lut else "")+(" · Sound" if b.sound else ""))
        if self.beats:self.list.setCurrentRow(min(max(0,i),len(self.beats)-1))
        self.total.setText(f"{len(self.beats)} Teile · {sum(b.duration for b in self.beats):.2f}s")
    def selected(self):
        i=self.list.currentRow()
        return (i,self.beats[i]) if 0<=i<len(self.beats) else (-1,None)
    def put(self,i,b):
        try:b.validate(self.analysis.video.duration)
        except ValueError as e:QMessageBox.warning(self,"Montage",str(e));return
        self.beats[i]=b;self.refresh(i)
    def add(self):
        c=self.source.currentData()
        if c is not None and len(self.beats)<64:
            self.beats.append(Beat(c.start,c.end));self.refresh(len(self.beats)-1)
    def remove(self):
        i,b=self.selected()
        if b is not None:del self.beats[i];self.refresh(i)
    def move(self,d):
        i,b=self.selected();j=i+d
        if b is not None and 0<=j<len(self.beats):
            self.beats[i],self.beats[j]=self.beats[j],self.beats[i];self.refresh(j)
    def timing(self):
        i,b=self.selected()
        if b is None:return
        a,ok=QInputDialog.getDouble(self,"In","Start (s)",b.start,0,self.analysis.video.duration,3)
        if not ok:return
        z,ok=QInputDialog.getDouble(self,"Out","Ende (s)",b.end,0,self.analysis.video.duration,3)
        if not ok:return
        s,ok=QInputDialog.getDouble(self,"Tempo","Geschwindigkeit",b.speed,.25,4,2)
        if ok:self.put(i,replace(b,start=a,end=z,speed=s))
    def ramp(self):
        i,b=self.selected()
        if b is None:return
        try:
            parts=speed_ramp(b.start,b.end)
            if len(self.beats)+len(parts)-1>64:raise ValueError("Maximal 64 Teile")
        except ValueError as e:QMessageBox.warning(self,"Rampe",str(e));return
        if QMessageBox.question(self,"Tempo-Rampe","Teil durch drei Tempoabschnitte (0,5× / 1× / 2×) ersetzen? Effekte dieses Teils werden zurückgesetzt.")!=QMessageBox.StandardButton.Yes:return
        self.beats[i:i+1]=parts;self.refresh(i)
    def freeze(self):
        i,b=self.selected()
        if b is None:return
        d,ok=QInputDialog.getDouble(self,"Standbild","Dauer am Ende (s)",b.freeze,0,5,2)
        if not ok:return
        if not d:self.put(i,replace(b,freeze=0,zoom=1,text=""));return
        zoom,ok=QInputDialog.getDouble(self,"Standbild","Zoom",b.zoom,1,2,2)
        if not ok:return
        text,ok=QInputDialog.getText(self,"Standbild","Optionaler Text (max. 120 Zeichen):",text=b.text)
        if ok:self.put(i,replace(b,freeze=d,zoom=zoom,text=text))
    def look(self):
        i,b=self.selected()
        if b is None:return
        name,ok=QInputDialog.getItem(self,"Look","Farblook oder eigene LUT:",[*LOOKS,"LUT (.cube)"],0,False)
        if not ok:return
        if name=="LUT (.cube)":
            path,_=QFileDialog.getOpenFileName(self,"Lokale LUT","","Cube (*.cube)")
            if path:self.put(i,replace(b,look="neutral",lut=path))
        else:self.put(i,replace(b,look=name,lut=""))
    def sound(self):
        i,b=self.selected()
        if b is None:return
        path,_=QFileDialog.getOpenFileName(self,"Eigener oder lizenzierter Sound","","Audio (*.wav *.mp3 *.ogg *.flac *.m4a)")
        if not path:return
        gain,ok=QInputDialog.getDouble(self,"Sound","Pegel (dB)",b.sound_gain,-60,0,1)
        if ok:self.put(i,replace(b,sound=path,sound_gain=gain))
    def reset(self):
        i,b=self.selected()
        if b is not None:self.put(i,Beat(b.start,b.end))
    def finish(self):
        try:self.plan=Montage(tuple(self.beats),self.aspect.currentText(),self.encoder.currentData()).validate(self.analysis.video.duration)
        except ValueError as e:QMessageBox.warning(self,"Montage",str(e));return
        self.accept()
