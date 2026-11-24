"""M13a scene-selection dialog; edits are staged until explicit save."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QListWidget, QLabel, QDoubleSpinBox, QComboBox, QCheckBox,
    QPushButton, QMessageBox,
)
from .scene_selection import load_selection, save_selection


class SceneSelectionDialog(QDialog):
    def __init__(self, video, start, end, parent=None):
        super().__init__(parent)
        self.video = video
        self.plan = load_selection(video, start, end)
        self.setWindowTitle("Szenenauswahl")
        self.resize(660, 440)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Szenen bearbeiten · Reihenfolge entspricht der geplanten Ausgabe.\n"
                                "Noch keine Anwendung im Renderer; Original bleibt unverändert."))
        self.scenes = QListWidget()
        layout.addWidget(self.scenes)
        form = QFormLayout()
        self.start = self._number(start, end, 3)
        self.end = self._number(start, end, 3)
        self.cut = self._number(start, end, 3)
        self.included = QCheckBox("In Ausgabe einschließen")
        self.mode = QComboBox()
        for label, value in (("Manuell", "manual"), ("Automatisch", "automatic"), ("Fester Crop", "fixed")):
            self.mode.addItem(label, value)
        self.region = [self._number(0, 1, 4) for _ in range(4)]
        form.addRow("In (Quellsekunden)", self.start)
        form.addRow("Out (Quellsekunden)", self.end)
        form.addRow("Kameramodus", self.mode)
        form.addRow(self.included)
        for label, field in zip(("Region X", "Region Y", "Region Breite", "Region Höhe"), self.region):
            form.addRow(label + " (0–1)", field)
        form.addRow("Schnittpunkt (Quellsekunden)", self.cut)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        for label, action in (("Änderungen übernehmen", self._apply),
                              ("Teilen", self._split),
                              ("Nach oben", lambda: self._move(-1)),
                              ("Nach unten", lambda: self._move(1))):
            button = QPushButton(label)
            button.clicked.connect(action)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.scenes.currentRowChanged.connect(self._select)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self._refresh(0)

    def _number(self, minimum, maximum, decimals):
        field = QDoubleSpinBox()
        field.setDecimals(decimals)
        field.setRange(minimum, maximum)
        field.setSingleStep(.01 if maximum <= 1 else .1)
        return field

    def _refresh(self, index):
        self.scenes.blockSignals(True)
        try:
            self.scenes.clear()
            for scene in self.plan.scenes:
                self.scenes.addItem(f"{'✓' if scene.included else '–'}  {scene.start:.3f} – {scene.end:.3f} s")
            self.scenes.setCurrentRow(index)
        finally:
            self.scenes.blockSignals(False)
        self._select(index)

    def _select(self, index):
        if not 0 <= index < len(self.plan.scenes):
            return
        scene = self.plan.scenes[index]
        self.start.setValue(scene.start)
        self.end.setValue(scene.end)
        self.cut.setValue((scene.start+scene.end)/2)
        self.included.setChecked(scene.included)
        self.mode.setCurrentIndex(self.mode.findData(scene.mode))
        for field, value in zip(self.region, scene.region):
            field.setValue(value)

    def _change(self, action, index):
        try:
            self.plan = action()
        except ValueError as exc:
            QMessageBox.warning(self, "Szenenänderung nicht möglich", str(exc))
            return False
        self._refresh(index)
        return True

    def _apply(self):
        i = self.scenes.currentRow()
        return self._change(lambda: self.plan.edit(
            i, start=self.start.value(), end=self.end.value(),
            included=self.included.isChecked(), mode=self.mode.currentData(),
            region=tuple(f.value() for f in self.region)), i)

    def _split(self):
        i = self.scenes.currentRow()
        at = self.cut.value()
        if self._apply():
            self._change(lambda: self.plan.split(i, at), i)

    def _move(self, direction):
        i = self.scenes.currentRow()
        if self._apply():
            self._change(lambda: self.plan.move(i, direction), i+direction)

    def _save(self):
        if not self._apply():
            return
        try:
            save_selection(self.video, self.plan)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Szenenplan nicht gespeichert", str(exc))
            return
        self.accept()
