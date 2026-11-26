"""M15a explicit container audio stream selection and extraction."""
from threading import Event
from .m18_language import tr,trf
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QTableWidget,QTableWidgetItem,
    QLabel,QComboBox,QPushButton,QFileDialog,QHBoxLayout)
from .audio_sources import inventory,extract_audio_stream,SpeechSource


class AudioSourceWorker(QThread):
    ready=Signal(object)
    failed=Signal(str)
    def __init__(self,path,parent,*,snapshot=None,index=None,folder=None,role="unspecified"):
        super().__init__(parent)
        self.path=path;self.snapshot=snapshot;self.index=index
        self.folder=folder;self.role=role;self.stop=Event()
    def run(self):
        try:
            result=(inventory(self.path) if self.snapshot is None else
                    extract_audio_stream(self.snapshot,self.index,self.folder,role=self.role,
                                         cancelled=self.stop.is_set))
            self.ready.emit(result)
        except Exception as exc:self.failed.emit(str(exc))


class AudioSourcesDialog(QDialog):
    def __init__(self,path,parent=None):
        super().__init__(parent)
        self.path=path;self.worker=None;self.snapshot=None;self.closing=False
        self.selection=None;self.extracted=None;self.action=None
        self.setWindowTitle(tr("Audioquellen · Originalspuren"))
        self.resize(940,470)
        layout=QVBoxLayout(self)
        self.hint=QLabel(tr("Liest vorhandene Container-Audiospuren. Rollen sind manuelle Zuordnungen, "
                         "keine KI-Erkennung. Eine einzelne Mixspur enthält nicht automatisch getrennte Stems."))
        self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(["Stream","Codec","Hz",tr("Kanäle"),"Layout",tr("Sprache"),tr("Titel"),"Start (s)"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table,1)
        form=QFormLayout()
        self.role=QComboBox()
        for label,value in ((tr("Nicht zugeordnet"),"unspecified"),(tr("Originalmix"),"mix"),(tr("Mikrofon"),"microphone"),
             (tr("Spielton"),"game"),(tr("Musik"),"music"),(tr("Sonstiges"),"other")):self.role.addItem(label,value)
        form.addRow(tr("Rolle (manuell)"),self.role);layout.addLayout(form)
        self.status=QLabel(tr("Audiospuren werden geprüft …"));self.status.setWordWrap(True);layout.addWidget(self.status)
        buttons=QHBoxLayout()
        self.extract=QPushButton(tr("Ausgewählte Spur als WAV extrahieren …"))
        self.extract.clicked.connect(self.start_extract);buttons.addWidget(self.extract)
        self.separate=QPushButton(tr("KI-Audiotrennung …"));self.separate.clicked.connect(self.start_separation);buttons.addWidget(self.separate)
        self.use=QPushButton(tr("Für Whisper wählen"));self.use.clicked.connect(self.choose_speech);buttons.addWidget(self.use)
        self.use_estimate=QPushButton(tr('KI-Sprachspur für Whisper wählen …'));self.use_estimate.clicked.connect(self.choose_estimate);layout.addWidget(self.use_estimate)
        self.reset=QPushButton(tr("Whisper: Standardspur"));self.reset.clicked.connect(self.reset_speech);buttons.addWidget(self.reset)
        self.add=QPushButton(tr("Extrahierte WAV auf Timeline"));self.add.clicked.connect(self.choose_extracted);buttons.addWidget(self.add)
        close=QPushButton(tr("Schließen / Abbrechen"));close.clicked.connect(self.reject);buttons.addWidget(close)
        layout.addLayout(buttons)
        self.table.itemSelectionChanged.connect(self.controls)
        self.launch(AudioSourceWorker(path,self))

    def controls(self):
        busy=self.worker is not None
        self.extract.setEnabled(not busy and self.snapshot is not None and self.table.currentRow()>=0)
        self.separate.setEnabled(not busy and self.snapshot is not None and self.table.currentRow()>=0)
        self.use.setEnabled(not busy and self.snapshot is not None and self.table.currentRow()>=0)
        self.reset.setEnabled(not busy)
        self.use_estimate.setEnabled(not busy and self.snapshot is not None)
        self.add.setEnabled(not busy and self.extracted is not None)
        self.role.setEnabled(not busy)
        self.table.setEnabled(not busy)

    def launch(self,worker):
        self.worker=worker
        worker.ready.connect(self.ready)
        worker.failed.connect(self.status.setText)
        worker.finished.connect(self.done)
        self.controls();worker.start()

    def ready(self,value):
        if self.closing:return
        if self.snapshot is None:
            self.snapshot=value
            self.table.setRowCount(len(value.streams))
            for row,s in enumerate(value.streams):
                for col,field in enumerate((s.index,s.codec,s.sample_rate,s.channels,s.layout,s.language,
                                            s.title,"—" if s.start_time is None else f"{s.start_time:.3f}")):
                    self.table.setItem(row,col,QTableWidgetItem(str(field)))
            if value.streams:self.table.selectRow(0)
            self.status.setText(trf("{count} Audiospur(en) gefunden. ",count=len(value.streams))
                +(tr("Einspuraufnahme: KI-Trennung ist als Pilot verfügbar.") if len(value.streams)==1 else ""))
        else:
            self.extracted=value
            self.status.setText(tr("Extrahiert: ")+str(value)+tr(" · provenance.json im gleichen Ordner."))

    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater();self.controls()
        if self.closing:super().reject()

    def start_separation(self):
        if self.worker or self.snapshot is None:return
        row=self.table.currentRow()
        if not 0<=row<len(self.snapshot.streams):return
        from .audio_separation_dialog import SeparationDialog
        selection=SpeechSource(self.snapshot,self.snapshot.streams[row].index,self.role.currentData()).validate()
        SeparationDialog(selection,self).exec()

    def choose_speech(self):
        if self.worker or self.snapshot is None:return
        row=self.table.currentRow()
        if not 0<=row<len(self.snapshot.streams):return
        self.selection=SpeechSource(self.snapshot,self.snapshot.streams[row].index,self.role.currentData()).validate()
        self.action="speech";self.accept()

    def choose_estimate(self):
        if self.worker or self.snapshot is None:return
        path,_=QFileDialog.getOpenFileName(self,tr("Rekonstruierte Sprachspur"),"","WAV (*.wav)")
        if not path:return
        from .reconstructed_speech import select_reconstructed
        try:self.selection=select_reconstructed(self.snapshot,path)
        except Exception as exc:self.status.setText(tr(str(exc)));return
        self.action="speech";self.accept()

    def reset_speech(self):
        if self.worker:return
        self.selection=None;self.action="speech";self.accept()

    def choose_extracted(self):
        if self.worker or self.extracted is None:return
        self.action="timeline";self.accept()

    def start_extract(self):
        if self.worker or self.snapshot is None:return
        row=self.table.currentRow()
        if not 0<=row<len(self.snapshot.streams):return
        folder=QFileDialog.getExistingDirectory(self,tr("Ordner für extrahierte Audiospur"))
        if not folder:return
        self.status.setText(tr("Extrahiere PCM-Audio mit Originalzeitbasis …"))
        self.launch(AudioSourceWorker(self.path,self,snapshot=self.snapshot,index=self.snapshot.streams[row].index,
                                      folder=folder,role=self.role.currentData()))

    def reject(self):
        if self.worker:
            self.closing=True;self.worker.stop.set();self.status.setText(tr("Abbruch läuft …"));return
        super().reject()
