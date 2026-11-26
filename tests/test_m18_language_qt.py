import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QPushButton,QLabel,QTabWidget,QComboBox
from streamclipper.m18_language import apply_language

def test_roundtrip_ui_labels_without_mutating_user_content():
    app=QApplication.instance() or QApplication([])
    w=QMainWindow();panel=QWidget();w.setCentralWidget(panel);layout=QVBoxLayout(panel)
    w.setWindowTitle("StreamClipper Studio | Schnitt & Highlights")
    button=QPushButton("Aufnahme öffnen…");layout.addWidget(button)
    w.source_label=QLabel("Untertitel");layout.addWidget(w.source_label)
    w.caption_overlay=QLabel("Ende");layout.addWidget(w.caption_overlay)
    tabs=QTabWidget();layout.addWidget(tabs);track=QWidget();tabs.addTab(track,"Spuren")
    w.mode=QComboBox();w.mode.addItem("9:16 – fester Mittel-Ausschnitt","crop");layout.addWidget(w.mode)
    action=w.menuBar().addMenu("Datei && Projekt").addAction("Aufnahme öffnen…")
    events=[];w.mode.currentIndexChanged.connect(events.append)
    try:
        apply_language(w,True,persist=False)
        assert button.text()=="Open recording…" and action.text()=="Open recording…"
        assert tabs.tabText(0)=="Tracks" and tabs.widget(0) is track
        assert w.mode.currentData()=="crop" and not events
        assert w.source_label.text()=="Untertitel" and w.caption_overlay.text()=="Ende"
        apply_language(w,False,persist=False)
        assert button.text()=="Aufnahme öffnen…" and tabs.tabText(0)=="Spuren"
        assert w.mode.currentData()=="crop" and not events
    finally:w.close();app.processEvents()
