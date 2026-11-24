"""M13a scene-selection dialog; edits are staged until explicit save."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QListWidget, QLabel, QDoubleSpinBox, QComboBox, QCheckBox,
    QPushButton, QMessageBox,
)
from .scene_selection import load_selection, save_selection
from .scene_region_monitor import RegionMonitor, FrameWorker


class SceneSelectionDialog(QDialog):
    def __init__(self, video, start, end, parent=None):
        super().__init__(parent)
        self.video = video
        self.plan = load_selection(video, start, end)
        self.setWindowTitle("Szenenauswahl")
        self.resize(900, 680)
        self.frame_worker = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Szenen bearbeiten · Reihenfolge entspricht der geplanten Ausgabe.\n"
                                "Noch keine Anwendung im Renderer; Original bleibt unverändert."))
        self.scenes = QListWidget()
        layout.addWidget(self.scenes)
        self.monitor = RegionMonitor()
        layout.addWidget(self.monitor, 1)
        self.frame_button = QPushButton("Quellbild am Schnittpunkt laden")
        self.frame_button.clicked.connect(self._load_frame)
        layout.addWidget(self.frame_button)
        self.frame_status = QLabel("Bildregion mit der Maus aufziehen; Koordinaten bleiben editierbar.")
        layout.addWidget(self.frame_status)
        self.monitor.region_changed.connect(self._region_marked)
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
        for field in self.region:
            field.valueChanged.connect(self._sync_region)
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
        self.monitor.set_frame(b'')
        self.start.setValue(scene.start)
        self.end.setValue(scene.end)
        self.cut.setValue((scene.start+scene.end)/2)
        self.included.setChecked(scene.included)
        self.mode.setCurrentIndex(self.mode.findData(scene.mode))
        for field, value in zip(self.region, scene.region):
            field.setValue(value)
        self._sync_region()

    def _sync_region(self):
        self.monitor.set_region(tuple(field.value() for field in self.region))

    def _region_marked(self, region):
        for field, value in zip(self.region, region):
            field.setValue(value)
        self.mode.setCurrentIndex(self.mode.findData("manual"))

    def _load_frame(self):
        if self.frame_worker is not None:
            return
        at = min(self.cut.value(), self.video.duration-.001)
        if at < 0 or not self.start.value() <= at < self.end.value():
            self.frame_status.setText("Schnittpunkt muss innerhalb der Szene liegen.")
            return
        self.monitor.set_frame(b"")
        self.frame_button.setEnabled(False)
        self.scenes.setEnabled(False)
        self.frame_status.setText("Quellbild wird geladen …")
        worker = FrameWorker(self.video, at, self)
        self.frame_worker = worker
        worker.ready.connect(lambda jpeg: self._frame_ready(worker, jpeg, at))
        worker.failed.connect(self.frame_status.setText)
        worker.finished.connect(lambda: self._frame_finished(worker))
        worker.start()

    def _frame_ready(self, worker, jpeg, at):
        if worker is self.frame_worker and self.monitor.set_frame(jpeg):
            self.frame_status.setText(f"Quellbild bei ca. {at:.3f} s · Region mit Maus aufziehen")
        else:
            self.frame_status.setText("Quellbild konnte nicht angezeigt werden.")

    def _frame_finished(self, worker):
        if self.frame_worker is worker:
            self.frame_worker = None
            self.frame_button.setEnabled(True)
            self.scenes.setEnabled(True)
        worker.deleteLater()

    def reject(self):
        if self.frame_worker is not None:
            self.frame_worker.cancelled.set()
            self.frame_status.setText("Bildabruf wird abgebrochen; danach Dialog schließen.")
            return
        super().reject()

    def _change(self, action, index):
        if self.frame_worker is not None:
            return False
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
        if self.frame_worker is not None or not self._apply():
            return
        try:
            save_selection(self.video, self.plan)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Szenenplan nicht gespeichert", str(exc))
            return
        self.accept()
