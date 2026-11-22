"""Small, user-owned customization dialog for speech-highlight cue words."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QTabWidget, QWidget,
)
from PySide6.QtCore import Qt

from .highlight_lexicon import (
    CATEGORIES, DEFAULT_RULES, PhraseRule, load_custom_rules, save_custom_rules,
    validate_custom_rules,
)

PRIORITY_LABELS = {
    "high": "Hoch – eigener Hinweis", "context": "Mittel – nur mit weiteren Signalen",
    "low": "Niedrig – nur mit weiteren Signalen",
}


class HighlightLexiconDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Eigene Highlight-Wörter")
        self.resize(700, 485)
        self._rules = load_custom_rules()
        layout = QVBoxLayout(self)
        label = QLabel("Standardwörter pflegt StreamClipper. Hier kannst du eigene Ausdrücke "
                       "hinzufügen oder deren Priorität überschreiben. Keine Regex nötig.")
        label.setWordWrap(True)
        layout.addWidget(label)
        tabs = QTabWidget()
        personal_page = QWidget()
        personal_layout = QVBoxLayout(personal_page)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Ausdruck", "Kategorie", "Priorität"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.pick_row)
        personal_layout.addWidget(self.table)
        standard_page = QWidget()
        standard_layout = QVBoxLayout(standard_page)
        standard_layout.addWidget(QLabel(
            "Diese Liste ist fest in der aktuellen StreamClipper-Version enthalten. "
            "Eigene Begriffe können ihre Priorität überschreiben."))
        defaults = QTableWidget(len(DEFAULT_RULES), 3)
        defaults.setHorizontalHeaderLabels(["Ausdruck", "Kategorie", "Priorität"])
        defaults.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        defaults.horizontalHeader().setStretchLastSection(True)
        for index, rule in enumerate(DEFAULT_RULES):
            for col, label in enumerate((rule.phrase, CATEGORIES[rule.category],
                                         PRIORITY_LABELS[rule.priority])):
                defaults.setItem(index, col, QTableWidgetItem(label))
        standard_layout.addWidget(defaults)
        tabs.addTab(personal_page, "Eigene Wörter")
        tabs.addTab(standard_page, "Standardliste")
        layout.addWidget(tabs)
        form = QFormLayout()
        self.phrase = QLineEdit()
        self.phrase.setPlaceholderText("z. B. Nicht dein Ernst!")
        form.addRow("Wort oder Satz", self.phrase)
        self.category = QComboBox()
        for key, value in CATEGORIES.items():
            self.category.addItem(value, key)
        form.addRow("Kategorie", self.category)
        self.priority = QComboBox()
        for key, value in PRIORITY_LABELS.items():
            self.priority.addItem(value, key)
        form.addRow("Priorität", self.priority)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.add_button = QPushButton("Hinzufügen / Auswahl ersetzen")
        self.add_button.clicked.connect(self.upsert)
        row.addWidget(self.add_button)
        self.new_button = QPushButton("Neue Eingabe")
        self.new_button.clicked.connect(self.clear_selection)
        row.addWidget(self.new_button)
        self.delete_button = QPushButton("Ausgewählten Eintrag löschen")
        self.delete_button.clicked.connect(self.delete_selected)
        row.addWidget(self.delete_button)
        layout.addLayout(row)
        layout.addWidget(QLabel("Die Liste wird nur für zukünftige Analysen verwendet. "
                                "Vorhandene Highlights bleiben unverändert."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self):
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self._rules))
            for i, rule in enumerate(self._rules):
                for col, value in enumerate((rule.phrase, CATEGORIES[rule.category],
                                             PRIORITY_LABELS[rule.priority])):
                    self.table.setItem(i, col, QTableWidgetItem(value))
        finally:
            self.table.blockSignals(False)

    def pick_row(self):
        index = self.table.currentRow()
        if not (0 <= index < len(self._rules)):
            return
        rule = self._rules[index]
        self.phrase.setText(rule.phrase)
        self.category.setCurrentIndex(self.category.findData(rule.category))
        self.priority.setCurrentIndex(self.priority.findData(rule.priority))

    def clear_selection(self):
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.phrase.clear()
        self.phrase.setFocus()

    def upsert(self):
        candidate = PhraseRule(self.phrase.text(), self.category.currentData(),
                               self.priority.currentData(), "user")
        index = self.table.currentRow() if self.table.selectedItems() else -1
        proposed = list(self._rules)
        if index >= 0:
            proposed[index] = candidate
        else:
            proposed.append(candidate)
        try:
            self._rules = validate_custom_rules(proposed)
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültiger Ausdruck", str(exc))
            return
        self.refresh()
        self.clear_selection()

    def delete_selected(self):
        index = self.table.currentRow() if self.table.selectedItems() else -1
        if 0 <= index < len(self._rules):
            del self._rules[index]
            self.refresh()
            self.clear_selection()

    def save(self):
        try:
            save_custom_rules(self._rules)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Konnte Wortliste nicht speichern", str(exc))
            return
        self.accept()
