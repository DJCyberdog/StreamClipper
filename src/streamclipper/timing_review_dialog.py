"""Review only source-matched speech evidence. No automatic transcript change."""
from threading import Event
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QLabel,QPushButton,QTableWidget,
    QTableWidgetItem,QDoubleSpinBox,QHBoxLayout)
from .speech_activity import detect_speech
from .speech_timing import propose_timings,apply_proposals

class TimingWorker(QThread):
    ready=Signal(object)
    failed=Signal(str)
    def __init__(self,selection,parent):
        super().__init__(parent);self.selection=selection;self.stop=Event()
    def run(self):
        try:self.ready.emit(detect_speech(self.selection,cancelled=self.stop.is_set))
        except Exception as exc:self.failed.emit(str(exc))

class TimingReviewDialog(QDialog):
    def __init__(self,result,selection,parent=None):
        super().__init__(parent)
        self.result=result;self.value=result;self.selection=selection;self.spans=None
        self.proposals=();self.worker=None;self.closing=False
        self.setWindowTitle("Untertitel · Sprachzeiten prüfen");self.resize(960,560)
        layout=QVBoxLayout(self)
        self.hint=QLabel("VAD-Korrekturvorschläge. Alte/unbekannte und manuell bearbeitete Zeilen bleiben geschützt. "
            "Wortzeiten bleiben unverändert; unsichere oder fehlende Sprachsignale werden nicht erzwungen korrigiert.")
        self.hint.setWordWrap(True);layout.addWidget(self.hint)
        row=QHBoxLayout();row.addWidget(QLabel("Lesbarkeits-Nachlauf (s)"))
        self.padding=QDoubleSpinBox();self.padding.setRange(0,.5);self.padding.setDecimals(2);self.padding.setSingleStep(.05);self.padding.setValue(.12)
        row.addWidget(self.padding);row.addStretch();layout.addLayout(row)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(["Übernehmen","Text","Bisher (s)","Vorschlag (s)","Kürzung (s)"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.table)
        self.status=QLabel("Lokale Sprachaktivität wird ermittelt …");self.status.setWordWrap(True);layout.addWidget(self.status)
        self.apply=QPushButton("Markierte Vorschläge übernehmen");self.apply.clicked.connect(self.commit);self.apply.setEnabled(False);layout.addWidget(self.apply)
        close=QPushButton("Abbrechen / Schließen");close.clicked.connect(self.reject);layout.addWidget(close)
        self.padding.valueChanged.connect(self.refresh)
        self.worker=TimingWorker(selection,self);self.worker.ready.connect(self.ready);self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(self.done);self.worker.start()
    def ready(self,spans):
        if self.closing:return
        self.spans=spans;self.refresh()
    def refresh(self):
        if self.spans is None:return
        protected=[i for i,c in enumerate(self.result.transcript) if c.review_origin not in ("asr","vad")]
        self.proposals=propose_timings(self.result.transcript,self.spans,duration=self.result.video.duration,
                                       protected_rows=protected,padding=self.padding.value())
        self.table.setRowCount(len(self.proposals))
        for i,p in enumerate(self.proposals):
            check=QTableWidgetItem();check.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Unchecked);self.table.setItem(i,0,check)
            for col,value in enumerate((p.before.text,f"{p.before.start:.3f} – {p.before.end:.3f}",
                f"{p.after.start:.3f} – {p.after.end:.3f}",f"{p.before.end-p.before.start-p.after.end+p.after.start:.3f}"),1):
                self.table.setItem(i,col,QTableWidgetItem(value))
        self.status.setText(f"{len(self.proposals)} Vorschläge · {len(protected)} geschützte Zeilen. Bitte einzeln prüfen und markieren.")
        self.apply.setEnabled(self.worker is None and bool(self.proposals))
    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater()
        self.apply.setEnabled(bool(self.proposals))
        if self.closing:super().reject()
    def commit(self):
        selected=[p for i,p in enumerate(self.proposals) if self.table.item(i,0).checkState()==Qt.CheckState.Checked]
        if not selected:return
        try:self.value=apply_proposals(self.result,selected)
        except ValueError as exc:self.status.setText(str(exc));return
        self.accept()
    def reject(self):
        if self.worker:
            self.closing=True;self.worker.stop.set();self.status.setText("Abbruch läuft …");return
        super().reject()
