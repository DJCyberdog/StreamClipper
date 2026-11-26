"""Explicit ordered montage editing dialog. Original highlights are immutable."""
from dataclasses import replace
from .m18_language import tr
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QComboBox,
    QPushButton,QLabel,QInputDialog,QFileDialog,QMessageBox)
from .montage import Beat,Montage,sampled_ramp,LOOKS

class MontageDialog(QDialog):
    def __init__(self,analysis,parent=None,request_factory=None):
        super().__init__(parent)
        self.analysis=analysis;self.beats=[];self.plan=None
        self.request_factory=request_factory;self.request=None;self.destination_mode="direct"
        self.setWindowTitle(tr("M17 · Montage & Effekte"));self.resize(880,580)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Montage · bestehende Editor-Komposition optional übernehmen")))
        from PySide6.QtWidgets import QCheckBox
        self.compose=QCheckBox(tr("Projektspuren, Untertitel und Szenenpläne nach aktueller Exportkonfiguration übernehmen"))
        self.compose.setChecked(request_factory is not None);self.compose.setEnabled(request_factory is not None)
        layout.addWidget(self.compose)
        self.source=QComboBox()
        for c in analysis.candidates:self.source.addItem(f"{c.start:.2f}–{c.end:.2f}s · {c.reason[:65]}",c)
        layout.addWidget(self.source)
        self.list=QListWidget();layout.addWidget(self.list)
        from .m17_preview import MontageTimeline
        self.timeline=MontageTimeline(self);layout.addWidget(self.timeline)
        self.timeline.selected.connect(self.list.setCurrentRow)
        self.list.currentRowChanged.connect(self.timeline.set_current)
        for group in [
            [(tr("Hinzufügen"),self.add),(tr("Entfernen"),self.remove),("↑",lambda:self.move(-1)),("↓",lambda:self.move(1))],
            [(tr("Zeit & Tempo"),self.timing),(tr("Tempo-Rampe"),self.ramp),(tr("Kontinuierliches Tempo"),self.continuous),(tr("Standbild"),self.freeze)],
            [("Look / LUT",self.look),(tr("Eigener Sound"),self.sound),(tr("Soundbibliothek"),self.library),(tr("Effekte zurücksetzen"),self.reset)],
            [(tr("Plan speichern"),self.save),(tr("Plan öffnen"),self.load),(tr("Abschnitt-Vorschau"),lambda:self.preview(True)),(tr("Montage-Vorschau"),lambda:self.preview(False))]]:
            row=QHBoxLayout();layout.addLayout(row)
            for label,callback in group:
                btn=QPushButton(tr(label));btn.clicked.connect(callback);row.addWidget(btn)
        self.aspect=QComboBox();self.aspect.addItems(["9:16","16:9","1:1"]);layout.addWidget(self.aspect)
        self.encoder=QComboBox()
        for label,key in [("H.264 Auto","auto_h264"),("CPU","cpu_h264"),("NVENC","nvenc_h264")]:self.encoder.addItem(label,key)
        layout.addWidget(self.encoder)
        self.total=QLabel();layout.addWidget(self.total)
        row=QHBoxLayout();layout.addLayout(row)
        for label,fn in [(tr("Abbrechen"),self.reject),(tr("Zur Renderqueue"),self.enqueue),(tr("Montage exportieren"),self.direct)]:
            btn=QPushButton(tr(label));btn.clicked.connect(fn);row.addWidget(btn)
        self.refresh()

    def refresh(self,i=0):
        self.list.clear()
        for b in self.beats:self.list.addItem(f"{b.start:.2f}–{b.end:.2f}s · {b.speed:g}x"+(f" → {b.end_speed:g}x" if b.end_speed is not None else "")+f" · Hold {b.freeze:g}s · {b.look}"+(" · LUT" if b.lut else "")+(" · Sound" if b.sound else ""))
        if self.beats:self.list.setCurrentRow(min(max(0,i),len(self.beats)-1))
        self.timeline.set_parts(self.beats,self.list.currentRow())
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
        z,ok=QInputDialog.getDouble(self,"Out",tr("Ende (s)"),b.end,0,self.analysis.video.duration,3)
        if not ok:return
        s,ok=QInputDialog.getDouble(self,"Tempo",tr("Geschwindigkeit"),b.speed,.25,4,2)
        if ok:self.put(i,replace(b,start=a,end=z,speed=s,end_speed=None))
    def ramp(self):
        i,b=self.selected()
        if b is None:return
        initial,ok=QInputDialog.getDouble(self,tr("Tempo-Rampe"),tr("Starttempo"),.5,.25,4,2)
        if not ok:return
        final,ok=QInputDialog.getDouble(self,tr("Tempo-Rampe"),tr("Endtempo"),2,.25,4,2)
        if not ok:return
        limit=min(32,65-len(self.beats),int((b.end-b.start)/.2))
        if limit<2:QMessageBox.warning(self,tr("Tempo-Rampe"),tr("Abschnitt zu kurz oder zu viele Teile"));return
        steps,ok=QInputDialog.getInt(self,tr("Tempo-Rampe"),tr("Stützstellen (diskrete Annäherung)"),min(8,limit),2,limit)
        if not ok:return
        curve,ok=QInputDialog.getItem(self,tr("Tempo-Rampe"),tr("Kurve:"),["smooth","linear"],0,False)
        if not ok:return
        try:parts=sampled_ramp(b.start,b.end,initial,final,steps,curve)
        except ValueError as e:QMessageBox.warning(self,tr("Rampe"),str(e));return
        if QMessageBox.question(self,tr("Tempo-Rampe"),f"Teil durch {steps} editierbare Tempoabschnitte ersetzen? Effekte dieses Teils werden zurückgesetzt.")!=QMessageBox.StandardButton.Yes:return
        self.beats[i:i+1]=parts;self.refresh(i)
    def continuous(self):
        i,b=self.selected()
        if b is None:return
        a,ok=QInputDialog.getDouble(self,tr("Kontinuierliche Tempoänderung"),tr("Starttempo"),b.speed,.25,4,2)
        if not ok:return
        z,ok=QInputDialog.getDouble(self,tr("Kontinuierliche Tempoänderung"),tr("Endtempo"),b.end_speed if b.end_speed is not None else 2,.25,4,2)
        if not ok:return
        if QMessageBox.question(self,tr("Natürliche Tempoänderung"),tr("Bild und Ton werden kontinuierlich beschleunigt/verlangsamt; die Tonhöhe ändert sich dabei. Für Tonhöhenkorrektur die bisherige diskrete Rampe nutzen. Übernehmen?"))!=QMessageBox.StandardButton.Yes:return
        self.put(i,replace(b,speed=a,end_speed=z))

    def preview(self,selected):
        from .montage_request import MontageRequest
        from .m17_preview import play_preview
        try:
            req=self.current_request()
            if selected:
                i,b=self.selected()
                if b is None:return
                req=MontageRequest.create(req.video,replace(req.plan,beats=(b,)),req.compositions[i:i+1])
            duration=sum((r.duration if req.compositions else b.end-b.start)*2/(b.speed+(b.end_speed if b.end_speed is not None else b.speed))+b.freeze
                         for b,r in zip(req.plan.beats,req.compositions or (None,)*len(req.plan.beats)))
            if duration>45:raise ValueError(tr("Vorschau maximal 45 Sekunden; einzelnen kürzeren Abschnitt wählen."))
            play_preview(req,self)
        except (OSError,ValueError,RuntimeError) as exc:QMessageBox.warning(self,tr("Montage-Vorschau"),str(exc))

    def freeze(self):
        i,b=self.selected()
        if b is None:return
        d,ok=QInputDialog.getDouble(self,tr("Standbild"),tr("Dauer am Ende (s)"),b.freeze,0,5,2)
        if not ok:return
        if not d:self.put(i,replace(b,freeze=0,zoom=1,text=""));return
        zoom,ok=QInputDialog.getDouble(self,tr("Standbild"),"Zoom",b.zoom,1,2,2)
        if not ok:return
        text,ok=QInputDialog.getText(self,tr("Standbild"),tr("Optionaler Text (max. 120 Zeichen):"),text=b.text)
        if ok:self.put(i,replace(b,freeze=d,zoom=zoom,text=text))
    def look(self):
        i,b=self.selected()
        if b is None:return
        name,ok=QInputDialog.getItem(self,"Look",tr("Farblook oder eigene LUT:"),[*LOOKS,"LUT (.cube)"],0,False)
        if not ok:return
        if name=="LUT (.cube)":
            path,_=QFileDialog.getOpenFileName(self,tr("Lokale LUT"),"","Cube (*.cube)")
            if path:self.put(i,replace(b,look="neutral",lut=path))
        else:self.put(i,replace(b,look=name,lut=""))
    def sound(self):
        i,b=self.selected()
        if b is None:return
        path,_=QFileDialog.getOpenFileName(self,tr("Eigener oder lizenzierter Sound"),"","Audio (*.wav *.mp3 *.ogg *.flac *.m4a)")
        if not path:return
        gain,ok=QInputDialog.getDouble(self,"Sound",tr("Pegel (dB)"),b.sound_gain,-60,0,1)
        if ok:self.put(i,replace(b,sound=path,sound_gain=gain))
    def reset(self):
        i,b=self.selected()
        if b is not None:self.put(i,Beat(b.start,b.end))
    def library(self):
        i,b=self.selected()
        if b is None:return
        from .sound_library import entries,import_sound
        items=entries()
        labels=["Neuen eigenen / lizenzierten Sound importieren …"]+[f"{n+1}. {x['name']} ({x['duration']:.1f}s) · {x['rights']}" for n,x in enumerate(items)]
        choice,ok=QInputDialog.getItem(self,tr("Soundbibliothek"),tr("Lokale Bibliothek:"),labels,0,False)
        if not ok:return
        try:
            if choice==labels[0]:
                source,_=QFileDialog.getOpenFileName(self,tr("Sound importieren"),"","Audio (*.wav *.mp3 *.ogg *.flac *.m4a)")
                if not source:return
                label,ok=QInputDialog.getText(self,tr("Soundname"),"Name:")
                if not ok:return
                rights,ok=QInputDialog.getText(self,tr("Nutzungsrechte"),tr("Eigene Aufnahme / Lizenz / Quellenhinweis:"))
                if not ok:return
                item=import_sound(source,label,rights)
            else:item=items[labels.index(choice)-1]
            self.put(i,replace(b,sound=item["path"]))
        except (OSError,ValueError,RuntimeError) as exc:QMessageBox.warning(self,tr("Soundbibliothek"),str(exc))

    def current_plan(self):
        return Montage(tuple(self.beats),self.aspect.currentText(),self.encoder.currentData()).validate(self.analysis.video.duration)

    def current_request(self):
        from .montage_request import MontageRequest
        plan=self.current_plan()
        # A loaded snapshot remains exact until a visible change is made.
        if self.request is not None and plan==self.request.plan and self.compose.isChecked()==bool(self.request.compositions):
            return self.request.validate(verify_media=True)
        if self.request_factory is not None:
            if self.request is not None and QMessageBox.question(self,tr("Montageplan geändert"),
                tr("Geänderter Plan: Editor-Kompositionen aus der aktuellen Sitzung neu erstellen?"))!=QMessageBox.StandardButton.Yes:
                raise ValueError(tr("Neuaufbau abgebrochen"))
            return self.request_factory(plan,self.compose.isChecked())
        return MontageRequest.create(self.analysis.video,plan)

    def save(self):
        from .montage_request import save_plan
        path,_=QFileDialog.getSaveFileName(self,tr("Montageplan speichern"),"Montage.json","JSON (*.json)")
        if not path:return
        try:save_plan(path,self.current_request())
        except (OSError,ValueError,RuntimeError) as exc:QMessageBox.warning(self,tr("Montageplan"),str(exc))

    def load(self):
        from .montage_request import load_plan
        path,_=QFileDialog.getOpenFileName(self,tr("Montageplan öffnen"),"","JSON (*.json)")
        if not path:return
        try:
            req=load_plan(path)
            if req.video!=self.analysis.video:raise ValueError(tr("Montageplan gehört zu anderer Aufnahme"))
        except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:QMessageBox.warning(self,tr("Montageplan"),str(exc));return
        self.request=req;self.beats=list(req.plan.beats)
        self.aspect.setCurrentText(req.plan.aspect)
        self.encoder.setCurrentIndex(self.encoder.findData(req.plan.encoder))
        self.compose.setChecked(bool(req.compositions))
        self.refresh()

    def direct(self):
        self.destination_mode="direct";self.finish()

    def enqueue(self):
        self.destination_mode="queue";self.finish()

    def finish(self):
        try:
            self.request=self.current_request()
            self.plan=self.request.plan
        except (OSError,ValueError,RuntimeError) as e:QMessageBox.warning(self,"Montage",str(e));return
        self.accept()
