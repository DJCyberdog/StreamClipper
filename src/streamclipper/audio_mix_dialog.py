"""Explicit import/mix workflow; project is committed once after worker success."""
from threading import Event
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLabel,QDoubleSpinBox,QPushButton,QCheckBox,QComboBox,QFileDialog
from .audio_editor import MixOptions,import_pair,create_processed_mix

class MixWorker(QThread):
    ready=Signal(object);failed=Signal(str)
    def __init__(self,project,voice,folder,options,parent):
        super().__init__(parent);self.args=(project,voice);self.folder=folder;self.options=options;self.stop=Event()
    def run(self):
        try:
            if self.folder is None:result=import_pair(*self.args,self.options,cancelled=self.stop.is_set)
            else:result=create_processed_mix(*self.args,self.folder,self.options,cancelled=self.stop.is_set)
            self.ready.emit(result)
        except Exception as exc:self.failed.emit(str(exc))

class AudioMixDialog(QDialog):
    def __init__(self,project,voice,parent=None):
        super().__init__(parent);self.project=project;self.voice=voice;self.value=None;self.worker=None;self.closing=False
        self.setWindowTitle("Audio-Studio · KI-Stems");self.resize(650,430)
        layout=QVBoxLayout(self)
        hint=QLabel("Erzeugt neue Spuren/Dateien und deaktiviert Originalton in der Komposition. "
                    "Andere vorhandene Audiospuren bleiben aktiv; prüfe mögliche Doppelungen. "
                    "Effekte werden in eine neue WAV gerendert; Originale bleiben unverändert.")
        hint.setWordWrap(True);layout.addWidget(hint)
        form=QFormLayout();self.mode=QComboBox()
        self.mode.addItem("Getrennte Spuren mit editierbarem Pegel","pair");self.mode.addItem("Bearbeiteten Mix als neue WAV","mix");form.addRow("Ausgabe",self.mode)
        self.voice_gain=QDoubleSpinBox();self.bg_gain=QDoubleSpinBox()
        for control in (self.voice_gain,self.bg_gain):control.setRange(-60,12);control.setSuffix(" dB")
        form.addRow("KI-Stimme",self.voice_gain);form.addRow("Restton",self.bg_gain)
        self.cleanup=QCheckBox("Sprach-Cleanup (Hochpass/Rauschminderung)")
        self.duck=QCheckBox("Restton bei Sprache absenken (Sidechain)")
        self.normalize=QCheckBox("Loudness-Ziel -16 LUFS / -1,5 dBTP (WAV, nicht MP4-Garantie)")
        for c in (self.cleanup,self.duck,self.normalize):form.addRow(c)
        layout.addLayout(form);self.status=QLabel("Quellzuordnung wird vor der Übernahme geprüft.");self.status.setWordWrap(True);layout.addWidget(self.status)
        self.start=QPushButton("Verarbeiten und übernehmen");self.start.clicked.connect(self.run_job);layout.addWidget(self.start)
        close=QPushButton("Abbrechen / Schließen");close.clicked.connect(self.reject);layout.addWidget(close)
        self.mode.currentIndexChanged.connect(self.controls);self.controls()
    def controls(self):
        idle=self.worker is None;mix=self.mode.currentData()=="mix"
        for c in (self.mode,self.voice_gain,self.bg_gain,self.start):c.setEnabled(idle)
        for c in (self.cleanup,self.duck,self.normalize):c.setEnabled(idle and mix)
    def run_job(self):
        if self.worker:return
        folder=None;mix=self.mode.currentData()=="mix"
        if mix:
            folder=QFileDialog.getExistingDirectory(self,"Ordner für neuen Audiomix")
            if not folder:return
        options=MixOptions(self.voice_gain.value(),self.bg_gain.value(),mix and self.cleanup.isChecked(),mix and self.duck.isChecked(),mix and self.normalize.isChecked())
        self.worker=MixWorker(self.project,self.voice,folder,options,self)
        self.worker.ready.connect(self.ready);self.worker.failed.connect(self.status.setText);self.worker.finished.connect(self.done)
        self.status.setText("Prüfe und verarbeite Audio …");self.controls();self.worker.start()
    def ready(self,value):
        if not self.closing:self.value=value
    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater();self.controls()
        if self.closing:super().reject()
        elif self.value is not None:self.accept()
    def reject(self):
        if self.worker:self.closing=True;self.worker.stop.set();self.status.setText("Abbruch läuft …");return
        super().reject()
