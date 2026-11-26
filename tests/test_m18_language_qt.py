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


def test_specialist_dialogs_use_language_without_changing_ids():
    from streamclipper.models import AnalysisResult,VideoInfo,Candidate
    from streamclipper.m17_montage_dialog import MontageDialog
    from streamclipper.caption_style import CaptionStyle
    from streamclipper.caption_style_dialog import CaptionStyleDialog
    app=QApplication.instance() or QApplication([])
    w=QMainWindow()
    candidate=Candidate(0,5,50,"Untertitel",2)
    result=AnalysisResult(VideoInfo("dummy.mp4",30,1920,1080,30,True),[candidate])
    try:
        for english in (True,False):
            apply_language(w,english,persist=False)
            dlg=MontageDialog(result)
            try:
                assert dlg.windowTitle()==("M17 · Montage & effects" if english else "M17 · Montage & Effekte")
                assert dlg.source.currentData()==candidate
                assert dlg.encoder.currentData()=="auto_h264"
                dlg.add()
                assert dlg.total.text()==("1 parts · 5.00s" if english else "1 Teile · 5.00s")
                assert dlg.beats[0].start==0 and dlg.beats[0].end==5
                assert candidate.reason=="Untertitel"
            finally:dlg.close()
            style=CaptionStyle()
            cap=CaptionStyleDialog(style)
            try:
                assert cap.windowTitle()==("Branding · subtitles" if english else "Branding · Untertitel")
                assert cap.mode.currentData()==style.mode
                assert cap.position.currentData()==style.position
            finally:cap.close()
    finally:
        apply_language(w,False,persist=False);w.close();app.processEvents()
