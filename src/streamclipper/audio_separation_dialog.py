"""M15b optional local voice isolation worker; never auto-import estimates."""
from threading import Event
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,QPushButton,
    QComboBox,QFileDialog,QProgressBar,QHBoxLayout)
from .audio_separation import InworldBackend,separate_stream


class SeparationWorker(QThread):
    ready=Signal(object)
    failed=Signal(str)
    progress=Signal(int)
    def __init__(self,selection,checkpoint,folder,device,parent):
        super().__init__(parent)
        self.selection=selection;self.checkpoint=checkpoint;self.folder=folder
        self.device=device;self.stop=Event()
    def run(self):
        try:
            backend=InworldBackend(self.checkpoint,self.device,cancelled=self.stop.is_set)
            result=separate_stream(self.selection,self.folder,backend=backend,
                                    progress=self.progress.emit,cancelled=self.stop.is_set)
            self.ready.emit(result)
        except Exception as exc:self.failed.emit(str(exc))


class SeparationDialog(QDialog):
    def __init__(self,selection,parent=None):
        super().__init__(parent)
        self.selection=selection;self.worker=None;self.closing=False
        self.setWindowTitle("KI-Audiotrennung · Pilot")
        self.resize(690,340)
        layout=QVBoxLayout(self)
        hint=QLabel("Schätzt Vordergrundsprache und Restton. Keine gezielte Streamer-Erkennung; "
                    "NPC-Dialoge können erhalten bleiben. Nur 48 kHz Mono/Stereo, maximal 10 Minuten. "
                    "Originalaufnahme bleibt unverändert. Lokales Modell, kein automatischer Download.")
        hint.setWordWrap(True);layout.addWidget(hint)
        form=QFormLayout()
        self.checkpoint=QLineEdit();self.checkpoint.setReadOnly(True)
        choose=QPushButton("Modell auswählen …");choose.clicked.connect(self.choose_model)
        row=QHBoxLayout();row.addWidget(self.checkpoint);row.addWidget(choose)
        form.addRow("Offline-Safetensors",row)
        self.device=QComboBox()
        for label,value in (("Automatisch","auto"),("NVIDIA CUDA","cuda"),("CPU","cpu")):self.device.addItem(label,value)
        form.addRow("Gerät",self.device);layout.addLayout(form)
        self.progress=QProgressBar();layout.addWidget(self.progress)
        self.status=QLabel("Lokalen denoiser.safetensors-Checkpoint auswählen.")
        self.status.setWordWrap(True);layout.addWidget(self.status)
        self.start_button=QPushButton("Trennen und WAV speichern …");self.start_button.clicked.connect(self.start_job)
        layout.addWidget(self.start_button)
        close=QPushButton("Schließen / Abbrechen");close.clicked.connect(self.reject);layout.addWidget(close)
        self.start_button.setEnabled(False)

    def choose_model(self):
        if self.worker:return
        path,_=QFileDialog.getOpenFileName(self,"Lokales Offline-Modell","","Safetensors (*.safetensors)")
        if path:self.checkpoint.setText(path);self.start_button.setEnabled(True)

    def start_job(self):
        if self.worker or not self.checkpoint.text():return
        folder=QFileDialog.getExistingDirectory(self,"Ordner für rekonstruierte Audiospuren")
        if not folder:return
        self.progress.setValue(0);self.status.setText("Prüfe Modell und trenne Audio …")
        self.worker=SeparationWorker(self.selection,self.checkpoint.text(),folder,self.device.currentData(),self)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.ready.connect(lambda p:self.status.setText("Gespeichert: "+str(p)+" · voice_estimate.wav / residual.wav"))
        self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(self.done)
        self.start_button.setEnabled(False);self.device.setEnabled(False);self.worker.start()

    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater()
        self.start_button.setEnabled(True);self.device.setEnabled(True)
        if self.closing:super().reject()

    def reject(self):
        if self.worker:
            self.closing=True;self.worker.stop.set();self.status.setText("Abbruch nach laufendem Modellaufruf …");return
        super().reject()
