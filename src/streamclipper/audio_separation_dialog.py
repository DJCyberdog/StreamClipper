"""M15b optional local voice isolation worker; never auto-import estimates."""
from threading import Event
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,QPushButton,
    QComboBox,QFileDialog,QProgressBar,QHBoxLayout,QCheckBox)
from .audio_separation import InworldBackend,separate_stream


class SeparationWorker(QThread):
    ready=Signal(object)
    failed=Signal(str)
    progress=Signal(int)
    def __init__(self,selection,checkpoint,folder,device,parent,*,kind='foreground',reference='',consent=False,use_cache=False,resume_target=False):
        super().__init__(parent)
        self.selection=selection;self.checkpoint=checkpoint;self.folder=folder
        self.device=device;self.stop=Event()
        self.kind=kind;self.reference=reference;self.consent=consent;self.use_cache=use_cache;self.resume_target=resume_target
    def run(self):
        try:
            if self.kind=='target':
                from .target_speaker import VoxLockBackend
                backend=VoxLockBackend(self.checkpoint,self.reference,consent=self.consent,cancelled=self.stop.is_set)
            else:backend=InworldBackend(self.checkpoint,self.device,cancelled=self.stop.is_set)
            result=separate_stream(self.selection,self.folder,backend=backend,
                                    progress=self.progress.emit,cancelled=self.stop.is_set,use_cache=self.use_cache,resume_target=self.resume_target)
            self.ready.emit(result)
        except Exception as exc:self.failed.emit(str(exc))


class SeparationDialog(QDialog):
    def __init__(self,selection,parent=None):
        super().__init__(parent)
        self.selection=selection;self.worker=None;self.closing=False
        self.setWindowTitle("KI-Audiotrennung · Pilot")
        self.resize(690,340)
        layout=QVBoxLayout(self)
        hint=QLabel("Vordergrundsprache oder gezielte Schätzung anhand einer Stimmreferenz. "
                    "NPC-Dialoge können erhalten bleiben. 8–192 kHz Mono/Stereo, Ausgabe 48 kHz, maximal 6 Stunden; lange Aufnahmen benötigen viel freien Speicher. "
                    "Originalaufnahme bleibt unverändert. Lokales Modell, kein automatischer Download.")
        hint.setWordWrap(True);layout.addWidget(hint)
        form=QFormLayout()
        self.kind=QComboBox();self.kind.addItem('Vordergrundsprache · Inworld','foreground');self.kind.addItem('Referenzstimme · VoxLock (CPU)','target')
        form.addRow('Modus',self.kind)
        self.checkpoint=QLineEdit();self.checkpoint.setReadOnly(True)
        choose=QPushButton("Modell auswählen …");choose.clicked.connect(self.choose_model)
        row=QHBoxLayout();row.addWidget(self.checkpoint);row.addWidget(choose)
        form.addRow("Lokales Modell",row)
        self.reference=QLineEdit();self.reference.setReadOnly(True)
        self.reference_button=QPushButton("Stimmreferenz auswählen …");self.reference_button.clicked.connect(self.choose_reference)
        refrow=QHBoxLayout();refrow.addWidget(self.reference);refrow.addWidget(self.reference_button)
        form.addRow("Referenz-WAV (3–30 s)",refrow)
        self.consent=QCheckBox("Meine eigene oder ausdrücklich autorisierte Stimme; nur lokal verwenden")
        form.addRow(self.consent)
        self.cache=QCheckBox('Vordergrund-Cache behalten (lokale PCM-Ausschnitte, Wiederaufnahme bei erneutem Lauf)')
        form.addRow(self.cache)
        self.target_resume=QCheckBox('Zielstimmen-Wiederaufnahme (segmentierter Modus, lokale Audio-Cachedateien und referenzgebundene Dateischlüssel)')
        self.target_resume.setToolTip('Optional: Modellzustand wird je 8-Sekunden-Fenster neu aufgebaut. Kein gespeicherter Voiceprint, aber lokale rekonstruierte Sprachdaten. Qualität kann von kontinuierlicher Inferenz abweichen.')
        form.addRow(self.target_resume)
        self.device=QComboBox()
        for label,value in (("Automatisch","auto"),("NVIDIA CUDA","cuda"),("CPU","cpu")):self.device.addItem(label,value)
        form.addRow("Gerät",self.device);layout.addLayout(form)
        self.progress=QProgressBar();layout.addWidget(self.progress)
        size=round(selection.inventory.duration*48000)*next(s.channels for s in selection.inventory.streams if s.index==selection.index)*4
        disk=QLabel(f'PCM-Speicher: ca. {3*size/1e9:.2f} GB während der Trennung, {2*size/1e9:.2f} GB Ergebnis (zzgl. Reserve).')
        disk.setWordWrap(True);layout.addWidget(disk)
        self.status=QLabel("Lokalen denoiser.safetensors-Checkpoint auswählen.")
        self.status.setWordWrap(True);layout.addWidget(self.status)
        self.start_button=QPushButton("Trennen und WAV speichern …");self.start_button.clicked.connect(self.start_job)
        layout.addWidget(self.start_button)
        close=QPushButton("Schließen / Abbrechen");close.clicked.connect(self.reject);layout.addWidget(close)
        self.kind.currentIndexChanged.connect(self.mode_changed)
        self.consent.toggled.connect(self.controls)
        self.mode_changed()

    def controls(self):
        target=self.kind.currentData()=='target';idle=self.worker is None
        self.kind.setEnabled(idle);self.device.setEnabled(idle and not target)
        self.reference_button.setEnabled(idle and target);self.consent.setEnabled(idle and target)
        self.cache.setEnabled(idle and not target)
        self.target_resume.setEnabled(idle and target and self.consent.isChecked())
        self.start_button.setEnabled(idle and bool(self.checkpoint.text()) and (not target or (bool(self.reference.text()) and self.consent.isChecked())))

    def mode_changed(self):
        self.checkpoint.clear();self.reference.clear();self.consent.setChecked(False);self.cache.setChecked(False);self.target_resume.setChecked(False)
        self.status.setText('Lokalen VoxLock-Ordner mit enroll.onnx und chunk_int8.onnx wählen.' if self.kind.currentData()=='target' else 'Lokalen denoiser.safetensors-Checkpoint auswählen.')
        self.controls()

    def choose_reference(self):
        if self.worker:return
        path,_=QFileDialog.getOpenFileName(self,'Autorisierte Stimmreferenz','','WAV (*.wav)')
        if path:self.reference.setText(path);self.consent.setChecked(False);self.target_resume.setChecked(False);self.controls()

    def choose_model(self):
        if self.worker:return
        if self.kind.currentData()=="target":path=QFileDialog.getExistingDirectory(self,"Lokaler VoxLock-Ordner")
        else:path,_=QFileDialog.getOpenFileName(self,"Lokales Offline-Modell","","Safetensors (*.safetensors)")
        if path:self.checkpoint.setText(path);self.controls()

    def start_job(self):
        if self.worker or not self.start_button.isEnabled():return
        folder=QFileDialog.getExistingDirectory(self,"Ordner für rekonstruierte Audiospuren")
        if not folder:return
        self.progress.setValue(0);self.status.setText("Prüfe Modell und trenne Audio …")
        self.worker=SeparationWorker(self.selection,self.checkpoint.text(),folder,self.device.currentData(),self,kind=self.kind.currentData(),reference=self.reference.text(),consent=self.consent.isChecked(),use_cache=(self.cache.isChecked() if self.kind.currentData()=='foreground' else self.target_resume.isChecked()),resume_target=self.kind.currentData()=='target' and self.target_resume.isChecked())
        self.worker.progress.connect(self.progress.setValue)
        self.worker.ready.connect(lambda p:self.status.setText("Gespeichert: "+str(p)+" · voice_estimate.wav / residual.wav"))
        self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(self.done)
        self.controls();self.worker.start()

    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater()
        self.controls()
        if self.closing:super().reject()

    def reject(self):
        if self.worker:
            self.closing=True;self.worker.stop.set();self.status.setText("Abbruch nach laufendem Modellaufruf …");return
        super().reject()
