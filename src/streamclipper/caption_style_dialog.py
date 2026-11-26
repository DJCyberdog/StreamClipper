"""Project caption style inspector."""
from .m18_language import tr
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QFormLayout,QComboBox,
    QLineEdit,QDoubleSpinBox,QSpinBox,QMessageBox,QLabel,QVBoxLayout)
from .caption_style import CaptionStyle,PRESETS


class CaptionStyleDialog(QDialog):
    def __init__(self,style,parent=None):
        super().__init__(parent)
        self.value=style
        self.setWindowTitle(tr("Branding · Untertitel"))
        layout=QVBoxLayout(self)
        hint=QLabel(tr("Gestaltung gilt für dieses Projekt. Die Render-Vorschau zeigt den tatsächlichen Export. "
                    "Animierte Wörter nutzen vorhandene Wortzeiten; keine neue Whisper-Analyse."))
        hint.setWordWrap(True);layout.addWidget(hint)
        form=QFormLayout()
        self.preset=QComboBox();self.preset.addItems(["Benutzerdefiniert",*PRESETS])
        self.mode=QComboBox()
        for label,value in ((tr("Klassisch"),"legacy"),(tr("Wort hervorheben"),"highlight"),(tr("Pop-Animation"),"pop")):
            self.mode.addItem(label,value)
        self.font=QLineEdit()
        self.scale=QDoubleSpinBox();self.scale.setRange(.5,2);self.scale.setSingleStep(.1)
        self.text_color=QLineEdit();self.accent_color=QLineEdit();self.outline_color=QLineEdit()
        self.position=QComboBox()
        for label,value in ((tr("Szenen-Safe-Zone (Standard)"),"scene"),(tr("Oben"),"top"),(tr("Unten"),"bottom")):
            self.position.addItem(label,value)
        self.words=QSpinBox();self.words.setRange(1,8)
        for label,widget in ((tr("Vorlage"),self.preset),("Animation",self.mode),(tr("Schrift"),self.font),
            (tr("Größe"),self.scale),(tr("Textfarbe #RRGGBB"),self.text_color),
            (tr("Akzentfarbe #RRGGBB"),self.accent_color),(tr("Kontur #RRGGBB"),self.outline_color),
            ("Position",self.position),(tr("Wörter pro Gruppe"),self.words)):
            form.addRow(label,widget)
        layout.addLayout(form)
        self.load(style)
        self.preset.currentTextChanged.connect(lambda name:self.load(PRESETS[name]) if name in PRESETS else None)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.finish);buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load(self,style):
        self.mode.setCurrentIndex(self.mode.findData(style.mode))
        self.font.setText(style.font);self.scale.setValue(style.scale)
        self.text_color.setText(style.text_color);self.accent_color.setText(style.accent_color)
        self.outline_color.setText(style.outline_color)
        self.position.setCurrentIndex(self.position.findData(style.position))
        self.words.setValue(style.group_words)

    def finish(self):
        try:
            self.value=CaptionStyle(self.mode.currentData(),self.font.text().strip(),self.scale.value(),
                self.text_color.text().strip(),self.accent_color.text().strip(),
                self.outline_color.text().strip(),self.position.currentData(),self.words.value()).validate()
        except ValueError as exc:
            QMessageBox.warning(self,"Branding",str(exc));return
        self.accept()
