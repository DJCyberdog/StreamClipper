"""Staged translations for the selected highlight; local model runs in QThread."""
from threading import Event
from .m18_language import tr
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QTableWidget,
    QTableWidgetItem,QPushButton,QFileDialog,QMessageBox,QDialogButtonBox)
from .subtitle_translation import cue_key,set_translations,select_language,translate_local,LANGUAGE


class TranslationWorker(QThread):
    ready=Signal(object)
    failure=Signal(str)
    progress=Signal(int,int)
    def __init__(self,texts,folder,parent):
        super().__init__(parent)
        self.texts,self.folder=texts,folder
        self.stop=Event()
    def run(self):
        try:
            self.ready.emit(translate_local(self.texts,self.folder,cancelled=self.stop.is_set,
                                            progress=self.progress.emit))
        except Exception as exc:self.failure.emit(str(exc))


class TranslationDialog(QDialog):
    def __init__(self,result,rows,parent=None):
        super().__init__(parent)
        self.original=self.value=result
        self.rows=tuple(rows)
        self.worker=None
        self.closing=False
        self.setWindowTitle(tr("Untertitel übersetzen · lokal"))
        self.resize(900,520)
        layout=QVBoxLayout(self)
        self.hint=QLabel(tr("Original bleibt unverändert. Sprachcode und passendes gerichtetes Marian-Modell wählen. "
                         "Übersetzungen übernehmen Abschnittszeiten, keine erfundenen Wortzeiten."))
        self.hint.setWordWrap(True);layout.addWidget(self.hint)
        self.language=QLineEdit(result.caption_language or "en")
        layout.addWidget(QLabel(tr("Zielsprache (z. B. de, en)")));layout.addWidget(self.language)
        self.table=QTableWidget(len(rows),3)
        self.table.setHorizontalHeaderLabels([tr("Quellzeit"),"Original",tr("Übersetzung")])
        self.table.horizontalHeader().setStretchLastSection(True)
        for i,row in enumerate(rows):
            cue=result.transcript[row]
            for col,val in ((0,f"{cue.start:.3f}"),(1,cue.text)):
                cell=QTableWidgetItem(val);cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i,col,cell)
        layout.addWidget(self.table)
        row=QHBoxLayout()
        self.load_button=QPushButton(tr("Sprache laden"));self.load_button.clicked.connect(self.load)
        self.generate_button=QPushButton(tr("Fehlende Texte lokal übersetzen …"));self.generate_button.clicked.connect(self.generate)
        self.original_button=QPushButton(tr("Original aktivieren"));self.original_button.clicked.connect(self.use_original)
        for button in (self.load_button,self.generate_button,self.original_button):row.addWidget(button)
        layout.addLayout(row)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.finish);self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.load()

    def load(self):
        if self.worker:return
        language=self.language.text().strip()
        if not LANGUAGE.fullmatch(language):
            QMessageBox.warning(self,tr("Sprache"),tr("Ungültiger Sprachcode"));return
        self.loaded_language=language
        lookup={t.source_sha256:t for t in self.original.translations if t.language==language}
        self.generated={}
        for i,row in enumerate(self.rows):
            item=lookup.get(cue_key(self.original.transcript[row]))
            self.table.setItem(i,2,QTableWidgetItem(item.text if item else ""))
            if item:self.generated[i]=(item.text,item.origin)

    def generate(self):
        if self.worker:return
        if self.language.text().strip()!=self.loaded_language:
            QMessageBox.warning(self,tr("Sprache"),tr("Bitte zuerst Sprache laden."));return
        indices=[i for i in range(len(self.rows)) if not self.table.item(i,2).text().strip()]
        if not indices:return
        folder=QFileDialog.getExistingDirectory(self,tr("Lokalen Marian-Modellordner auswählen"))
        if not folder:return
        self.indices=indices
        self.worker=TranslationWorker([self.original.transcript[self.rows[i]].text for i in indices],folder,self)
        self.worker.ready.connect(self.ready)
        self.worker.failure.connect(self.hint.setText)
        self.worker.progress.connect(lambda a,b:self.hint.setText(f"Übersetzung {a}/{b}"))
        self.worker.finished.connect(self.done)
        self.table.setEnabled(False);self.language.setEnabled(False)
        self.worker.start()

    def ready(self,texts):
        if self.closing:return
        for i,t in zip(self.indices,texts):
            self.table.setItem(i,2,QTableWidgetItem(t));self.generated[i]=(t,"model")

    def done(self):
        worker=self.worker;self.worker=None;worker.deleteLater()
        self.table.setEnabled(True);self.language.setEnabled(True)
        if self.closing:super().reject()

    def use_original(self):
        if self.worker:return
        self.value=select_language(self.original,"")
        self.accept()

    def finish(self):
        if self.worker:return
        if self.language.text().strip()!=self.loaded_language:
            QMessageBox.warning(self,tr("Sprache"),tr("Bitte zuerst Sprache laden."));return
        entries=[]
        for i,row in enumerate(self.rows):
            text=self.table.item(i,2).text().strip()
            old=self.generated.get(i)
            entries.append((row,text,old[1] if old and old[0]==text else "manual"))
        try:self.value=set_translations(self.original,self.loaded_language,entries)
        except ValueError as exc:QMessageBox.warning(self,tr("Übersetzung"),str(exc));return
        self.accept()

    def reject(self):
        if self.worker:
            self.closing=True;self.worker.stop.set();self.hint.setText(tr("Abbruch läuft …"));return
        super().reject()
