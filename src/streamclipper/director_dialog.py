"""Per-scene director editor, separate from the original source monitor."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import math
import threading
import time

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout,
    QFormLayout, QListWidget, QLabel, QDoubleSpinBox, QComboBox, QCheckBox, QScrollArea, QWidget,
    QPushButton, QMessageBox, QFileDialog)
from .scene_camera import CameraKeyframe
from .smart_director import Director, OverlayZone, KINDS, director_from_dict, crop_for_scene
from .director_analysis import W,H,follow_patch,edge_candidates
from .media import sampled_jpeg_frames


class AnalysisWorker(QThread):
    result=Signal(object)
    failure=Signal(str)

    def __init__(self,video,scene,at,x,y,mode,parent=None,*,model_directory=None):
        super().__init__(parent)
        self.video,self.scene,self.at,self.x,self.y,self.mode=video,scene,at,x,y,mode
        self.stop=threading.Event()
        self.model_directory=model_directory

    def run(self):
        deadline=time.monotonic()+(180 if self.mode=='clip' else 60)
        def cancelled():
            return self.stop.is_set() or time.monotonic()>deadline
        try:
            if self.mode=="clip":
                from .overlay_recognition import recognize_overlays
                result=recognize_overlays(self.video,self.model_directory,self.scene.start,
                                          self.scene.end,cancelled=cancelled)
                if not cancelled():
                    self.result.emit((self.mode,result))
                return
            start=self.at if self.mode=="track" else self.scene.start
            end=min(self.scene.end,self.video.duration)-.001
            if end<=start:
                raise ValueError("Zu wenig Quellzeit für Analyse")
            if self.mode=='track':
                end=min(end,start+15.5)  # bounded half-second tracking cadence
            count=min(32,max(3,math.ceil((end-start)*2)+1))
            times=sorted(set(round(start+(end-start)*i/(count-1),3) for i in range(count)))
            times=[t for t in times if t<self.video.duration]
            frames=[]
            for at,jpeg in sampled_jpeg_frames(self.video,max_frames=32,timestamps=times,cancelled=cancelled):
                image=QImage.fromData(jpeg).scaled(W,H,Qt.AspectRatioMode.IgnoreAspectRatio).convertToFormat(QImage.Format.Format_Grayscale8)
                if image.isNull():
                    raise ValueError("Bild konnte nicht dekodiert werden")
                stride=image.bytesPerLine()
                buf=bytes(image.constBits())
                frames.append((at,b"".join(buf[i*stride:i*stride+W] for i in range(H))))
            if not frames or cancelled():
                raise ValueError("Analyse abgebrochen")
            value=follow_patch(frames,self.x,self.y) if self.mode=="track" else edge_candidates(frames)
            self.result.emit((self.mode,value))
        except Exception as exc:
            self.failure.emit(str(exc))


class DirectorDialog(QDialog):
    def __init__(self,video,scene,at,region,parent=None):
        super().__init__(parent)
        self.video,self.scene,self.value=video,scene,scene.director
        self.worker=None
        self.setWindowTitle("Smart Director · Szene")
        self.resize(730,680)
        outer=QVBoxLayout(self)
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        body=QWidget();scroll.setWidget(body);outer.addWidget(scroll,1)
        layout=QVBoxLayout(body)
        self.info=QLabel("Manuelle Keyframes haben Vorrang. Tracking ist ein begrenzter Bildmuster-Vorschlag.")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.keys=QListWidget()
        layout.addWidget(self.keys)
        form=QFormLayout()
        self.at=self.num(scene.start,scene.end,at,3)
        self.x=self.num(0,1,region[0]+region[2]/2)
        self.y=self.num(0,1,region[1]+region[3]/2)
        self.zoom=self.num(1,1.6,1.2)
        for name,field in (("Quellzeit",self.at),("Fokus X",self.x),("Fokus Y",self.y),("Zoom",self.zoom)):
            form.addRow(name,field)
        layout.addLayout(form)
        row=QHBoxLayout()
        for name,action in (("Keyframe setzen",self.add_key),("Keyframe löschen",self.del_key),
                            ("Subject Lock ab Punkt",lambda:self.analyze("track")),
                            ("Tracking löschen",self.clear_track)):
            self.button(row,name,action)
        layout.addLayout(row)
        self.zones=QListWidget()
        layout.addWidget(self.zones)
        form=QFormLayout()
        self.kind=QComboBox()
        self.kind.addItems(KINDS)
        self.rect=[self.num(0,1,v) for v in region]
        form.addRow("Overlay-Typ",self.kind)
        for name,field in zip(("X","Y","Breite","Höhe"),self.rect):
            form.addRow(name,field)
        self.dynamic=QCheckBox("Zeitlich begrenzt (z. B. Alert)")
        self.zone_start=self.num(scene.start,scene.end,scene.start,3)
        self.zone_end=self.num(scene.start,scene.end,scene.end,3)
        self.enabled=QCheckBox("Aktiv");self.enabled.setChecked(True)
        self.mask=QCheckBox("Mit Schwarzmaske verdecken")
        self.avoid=QCheckBox("Overlayfreien automatischen Crop verlangen")
        self.avoid.setChecked(self.value.avoid_overlays)
        self.removal=QCheckBox("Maskierung ausdrücklich aktivieren")
        self.removal.setChecked(self.value.removal_enabled)
        self.safe=QComboBox();self.safe.addItems(["bottom","top"]);self.safe.setCurrentText(self.value.caption_safe)
        for label,field in (("Zeitfenster",self.dynamic),("Start",self.zone_start),("Ende",self.zone_end),
                            ("Zone",self.enabled),("Entfernung",self.mask),("Crop",self.avoid),
                            ("Opt-in",self.removal),("Untertitel-Safe-Zone",self.safe)):
            form.addRow(label,field)
        layout.addLayout(form)
        row=QHBoxLayout()
        for name,action in (("Zone hinzufügen",self.add_zone),("Zone ändern",self.edit_zone),
                            ("Zone löschen",self.del_zone),("Randkandidaten",lambda:self.analyze("overlay")),
                            ("CLIP-Overlay-Analyse",lambda:self.analyze("clip"))):
            self.button(row,name,action)
        layout.addLayout(row)
        row=QHBoxLayout()
        self.button(row,"OBS-Profil speichern",self.save_profile)
        self.button(row,"OBS-Profil laden",self.load_profile)
        self.button(row,"Crop-Konflikt prüfen",self.check_crop)
        layout.addLayout(row)
        self.keys.currentRowChanged.connect(self.select_key)
        self.zones.currentRowChanged.connect(self.select_zone)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.finish)
        box.rejected.connect(self.reject)
        outer.addWidget(box)
        self.refresh()

    def num(self,low,high,value,dec=4):
        field=QDoubleSpinBox();field.setDecimals(dec);field.setRange(low,high);field.setValue(value)
        return field

    def button(self,row,label,action):
        b=QPushButton(label);b.clicked.connect(action);row.addWidget(b)

    def refresh(self):
        self.keys.clear()
        for k in self.value.manual:
            self.keys.addItem(f"{k.at:.3f}s · x {k.x:.3f} · y {k.y:.3f} · Zoom {k.zoom:.2f}")
        self.zones.clear()
        for z in self.value.zones:
            self.zones.addItem(f"{z.kind} · {z.region} · {'aktiv' if z.enabled else 'aus'}"
                               + (" · Maske" if z.mask else "") + (" · temporär" if z.start is not None else ""))
        self.info.setText(f"{len(self.value.manual)} manuelle Keyframes · {len(self.value.tracked)} Trackingpunkte. "
                          "Tracking endet bei unsicherer Zuordnung; Overlay-Vorschläge sind unbestätigt und bleiben bis zur Freigabe deaktiviert.")

    def update_value(self,**kw):
        if self.worker is not None:
            return
        try:
            next_value=replace(self.value,**kw)
            next_value.validate()
        except ValueError as exc:
            QMessageBox.warning(self,"Smart Director",str(exc))
            return
        self.value=next_value
        self.refresh()

    def add_key(self):
        key=CameraKeyframe(self.at.value(),self.x.value(),self.y.value(),self.zoom.value())
        self.update_value(manual=tuple(sorted((*[k for k in self.value.manual if abs(k.at-key.at)>=.001],key),key=lambda k:k.at)))

    def select_key(self,i):
        if 0<=i<len(self.value.manual):
            k=self.value.manual[i]
            for field,v in zip((self.at,self.x,self.y,self.zoom),(k.at,k.x,k.y,k.zoom)):field.setValue(v)

    def del_key(self):
        i=self.keys.currentRow()
        if i>=0:self.update_value(manual=tuple(k for j,k in enumerate(self.value.manual) if j!=i))

    def clear_track(self):
        self.update_value(tracked=())

    def zone(self):
        return OverlayZone(self.kind.currentText(),tuple(f.value() for f in self.rect),
            self.zone_start.value() if self.dynamic.isChecked() else None,
            self.zone_end.value() if self.dynamic.isChecked() else None,
            self.enabled.isChecked(),self.mask.isChecked())

    def add_zone(self):
        self.update_value(zones=(*self.value.zones,self.zone()))

    def edit_zone(self):
        i=self.zones.currentRow()
        if i>=0:self.update_value(zones=tuple(self.zone() if j==i else z for j,z in enumerate(self.value.zones)))

    def del_zone(self):
        i=self.zones.currentRow()
        if i>=0:self.update_value(zones=tuple(z for j,z in enumerate(self.value.zones) if j!=i))

    def select_zone(self,i):
        if 0<=i<len(self.value.zones):
            z=self.value.zones[i];self.kind.setCurrentText(z.kind)
            for field,v in zip(self.rect,z.region):field.setValue(v)
            self.dynamic.setChecked(z.start is not None)
            self.zone_start.setValue(z.start if z.start is not None else self.scene.start)
            self.zone_end.setValue(z.end if z.end is not None else self.scene.end)
            self.enabled.setChecked(z.enabled);self.mask.setChecked(z.mask)

    def analyze(self,mode):
        if self.worker is not None:return
        model_directory=None
        if mode=="clip":
            from .portable import local_model_directory
            model_directory=QFileDialog.getExistingDirectory(self,"Installierten CLIP-Modellordner wählen",
                                                             str(local_model_directory()))
            if not model_directory:return
        self.info.setText("Lokale Bildanalyse läuft …")
        self.worker=AnalysisWorker(self.video,self.scene,self.at.value(),self.x.value(),self.y.value(),mode,self,
                                   model_directory=model_directory)
        self.worker.result.connect(self.analysis_ready)
        self.worker.failure.connect(self.info.setText)
        self.worker.finished.connect(self.analysis_done)
        self.worker.start()

    def analysis_ready(self,result):
        mode,value=result
        if mode=="track":
            self.pending=replace(self.value,tracked=value)
        elif mode=="clip":
            self.pending=replace(self.value,zones=(*self.value.zones,*value[:max(0,24-len(self.value.zones))]))
        else:
            # Disabled until explicitly selected and confirmed.
            self.pending=replace(self.value,zones=(*self.value.zones,
                *(OverlayZone("graphic",r,enabled=False) for r in value[:max(0,24-len(self.value.zones))])))

    def analysis_done(self):
        worker=self.worker;self.worker=None
        cancelled=worker.stop.is_set();worker.deleteLater()
        if cancelled:
            super().reject();return
        if hasattr(self,"pending"):
            value=self.pending;del self.pending
            self.update_value(tracked=value.tracked,zones=value.zones)

    def save_profile(self):
        if self.worker:return
        path,_=QFileDialog.getSaveFileName(self,"OBS-Profil speichern","","JSON (*.json)")
        if not path:return
        try:
            # No source or credentials; only static regions.
            with open(path,"x",encoding="utf-8") as handle:
                json.dump({"version":1,"zones":[asdict(z) for z in self.value.zones if z.start is None]},handle,ensure_ascii=False)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,"Profil nicht gespeichert",str(exc))

    def load_profile(self):
        if self.worker:return
        path,_=QFileDialog.getOpenFileName(self,"OBS-Profil laden","","JSON (*.json)")
        if not path:return
        try:
            if Path(path).stat().st_size>65536:raise ValueError("Profil zu groß")
            doc=json.loads(Path(path).read_text(encoding="utf-8"))
            if doc["version"]!=1:raise ValueError("Unbekanntes Profil")
            loaded=director_from_dict({"zones":doc["zones"]})
            if any(z.start is not None for z in loaded.zones):raise ValueError("Profil enthält temporäre Zonen")
            self.update_value(zones=(*self.value.zones,*loaded.zones))
        except (OSError,ValueError,TypeError,KeyError) as exc:QMessageBox.warning(self,"Profil nicht geladen",str(exc))

    def check_crop(self):
        text=[]
        scene=replace(self.scene,director=replace(self.value,avoid_overlays=True))
        for w,h in ((1080,1920),(1920,1080)):
            try:
                result=crop_for_scene(scene,self.video,w,h)
                text.append(f"{w}×{h}: "+("Overlayfreier Crop möglich" if result else "Kein Konflikt im gewählten Pfad"))
            except ValueError as exc:
                text.append(f"{w}×{h}: {exc}")
        if self.value.keys or self.scene.mode!="automatic":text.append("Manuelle Kamera wird nicht überschrieben.")
        QMessageBox.information(self,"Overlay-Crop", "\n".join(text))

    def finish(self):
        if self.worker:return
        self.value=replace(self.value,avoid_overlays=self.avoid.isChecked(),
                           removal_enabled=self.removal.isChecked(),caption_safe=self.safe.currentText())
        try:
            self.value.validate()
        except ValueError as exc:
            QMessageBox.warning(self,'Smart Director',str(exc));return
        self.accept()

    def reject(self):
        if self.worker:
            self.worker.stop.set();self.info.setText("Analyse wird abgebrochen …");return
        super().reject()
