"""Manual review of flagged ASR cues; optional selected-row reprocessing."""
from threading import Event
from .m18_language import tr
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QLabel,QPushButton,QTableWidget,
    QTableWidgetItem,QComboBox,QLineEdit,QPlainTextEdit)
from .asr_quality import ASROptions,flags,retry_cue,accept_retry
from .semantic import transcribe_video

class RetryWorker(QThread):
    ready=Signal(str);failed=Signal(str)
    def __init__(self,result,row,selection,model,options,parent):
        super().__init__(parent);self.args=(result,row,selection,model);self.options=options;self.stop=Event()
    def run(self):
        try:self.ready.emit(retry_cue(*self.args,transcriber=transcribe_video,options=self.options,cancelled=self.stop.is_set))
        except Exception as exc:self.failed.emit(str(exc))

class ASRReviewDialog(QDialog):
    def __init__(self,result,selection,model,parent=None):
        super().__init__(parent);self.result=result;self.value=result;self.selection=selection;self.model=model
        self.worker=None;self.closing=False;self.target=None
        self.setWindowTitle(tr("ASR-Qualität · auffällige Zeilen"));self.resize(900,600)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel(tr("Heuristische Prüfsignale, keine kalibrierte Fehlerwahrscheinlichkeit. Keine automatische Löschung.")))
        self.rows=[i for i,c in enumerate(result.transcript) if flags(c)]
        self.table=QTableWidget(len(self.rows),3);self.table.setHorizontalHeaderLabels([tr("Zeit (s)"),"Text",tr("Prüfsignal")])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for n,i in enumerate(self.rows):
            c=result.transcript[i]
            for j,t in enumerate((f"{c.start:.2f}–{c.end:.2f}",c.text,", ".join(flags(c)))):self.table.setItem(n,j,QTableWidgetItem(t))
        layout.addWidget(self.table)
        self.language=QComboBox()
        for label,value in ((tr("Automatisch (Sprachwechsel möglich)"),None),(tr("Deutsch"),"de"),(tr("Englisch"),"en")):self.language.addItem(label,value)
        layout.addWidget(self.language);self.glossary=QLineEdit();self.glossary.setMaxLength(1000);self.glossary.setPlaceholderText(tr("Optionale Spielbegriffe / Namen"));layout.addWidget(self.glossary)
        self.retry=QPushButton(tr("Ausgewählte Zeile erneut transkribieren"));self.retry.clicked.connect(self.start);layout.addWidget(self.retry)
        self.proposal=QPlainTextEdit();self.proposal.setPlaceholderText(tr("Zweittranskription prüfen und ggf. korrigieren"));layout.addWidget(self.proposal)
        self.apply=QPushButton(tr("Geprüften Text übernehmen"));self.apply.setEnabled(False);self.apply.clicked.connect(self.commit);layout.addWidget(self.apply)
        self.status=QLabel(f"{len(self.rows)} auffällige Zeilen");self.status.setWordWrap(True);layout.addWidget(self.status)
        close=QPushButton(tr("Schließen / Abbrechen"));close.clicked.connect(self.reject);layout.addWidget(close)
        if self.rows:self.table.selectRow(0)
        self.retry.setEnabled(bool(self.rows))
    def start(self):
        n=self.table.currentRow()
        if self.worker or not 0<=n<len(self.rows):return
        self.target=self.rows[n];self.proposal.clear();self.apply.setEnabled(False)
        self.worker=RetryWorker(self.result,self.target,self.selection,self.model,ASROptions(self.language.currentData(),self.glossary.text()),self)
        self.worker.ready.connect(self.ready);self.worker.failed.connect(self.status.setText);self.worker.finished.connect(self.done)
        self.retry.setEnabled(False);self.table.setEnabled(False);self.status.setText(tr("Lokale Nachprüfung …"));self.worker.start()
    def ready(self,text):
        if not self.closing:self.proposal.setPlainText(text);self.status.setText(tr("Vorschlag prüfen · ursprüngliche Zeitgrenzen bleiben erhalten"))
    def done(self):
        w=self.worker;self.worker=None;w.deleteLater();self.retry.setEnabled(True);self.table.setEnabled(True)
        self.apply.setEnabled(bool(self.proposal.toPlainText().strip()))
        if self.closing:super().reject()
    def commit(self):
        if self.worker or self.target is None:return
        try:self.value=accept_retry(self.result,self.target,self.result.transcript[self.target],self.proposal.toPlainText())
        except ValueError as exc:self.status.setText(str(exc));return
        self.accept()
    def reject(self):
        if self.worker:self.closing=True;self.worker.stop.set();self.status.setText(tr("Abbruch läuft …"));return
        super().reject()
