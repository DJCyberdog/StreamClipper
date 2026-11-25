"""M15a explicit container audio stream selection and extraction."""
from threading import Event
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QTableWidget,QTableWidgetItem,
    QLabel,QComboBox,QPushButton,QFileDialog,QHBoxLayout)
from .audio_sources import inventory,extract_audio_stream


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
        self.setWindowTitle("Audioquellen · Originalspuren")
        self.resize(940,470)
        layout=QVBoxLayout(self)
        self.hint=QLabel("Liest vorhandene Container-Audiospuren. Rollen sind manuelle Zuordnungen, "
                         "keine KI-Erkennung. Eine einzelne Mixspur enthält nicht automatisch getrennte Stems.")
        self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(["Stream","Codec","Hz","Kanäle","Layout","Sprache","Titel","Start (s)"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table,1)
        form=QFormLayout()
        self.role=QComboBox()
        for label,value in (("Nicht zugeordnet","unspecified"),("Originalmix","mix"),("Mikrofon","microphone"),
             ("Spielton","game"),("Musik","music"),("Sonstiges","other")):self.role.addItem(label,value)
        form.addRow("Rolle (manuell)",self.role);layout.addLayout(form)
        self.status=QLabel("Audiospuren werden geprüft …");self.status.setWordWrap(True);layout.addWidget(self.status)
        buttons=QHBoxLayout()
        self.extract=QPushButton("Ausgewählte Spur als WAV extrahieren …")
        self.extract.clicked.connect(self.start_extract);buttons.addWidget(self.extract)
        close=QPushButton("Schließen / Abbrechen");close.clicked.connect(self.reject);buttons.addWidget(close)
        layout.addLayout(buttons)
        self.table.itemSelectionChanged.connect(self.controls)
        self.launch(AudioSourceWorker(path,self))

    def controls(self):
        busy=self.worker is not None
        self.extract.setEnabled(not busy and self.snapshot is not None and self.table.currentRow()>=0)
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
            self.status.setText(f"{len(value.streams)} Audiospur(en) gefunden. "
                +("Einspuraufnahme: KI-Trennung ist ein separater späterer Schritt." if len(value.streams)==1 else ""))
        else:self.status.setText("Extrahiert: "+str(value)+" · provenance.json im gleichen Ordner.")

    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater();self.controls()
        if self.closing:super().reject()

    def start_extract(self):
        if self.worker or self.snapshot is None:return
        row=self.table.currentRow()
        if not 0<=row<len(self.snapshot.streams):return
        folder=QFileDialog.getExistingDirectory(self,"Ordner für extrahierte Audiospur")
        if not folder:return
        self.status.setText("Extrahiere PCM-Audio mit Originalzeitbasis …")
        self.launch(AudioSourceWorker(self.path,self,snapshot=self.snapshot,index=self.snapshot.streams[row].index,
                                      folder=folder,role=self.role.currentData()))

    def reject(self):
        if self.worker:
            self.closing=True;self.worker.stop.set();self.status.setText("Abbruch läuft …");return
        super().reject()
