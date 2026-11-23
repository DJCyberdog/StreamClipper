"""StreamClipper Studio visual system.

Muted graphite surfaces, restrained sapphire accent, readable contrast and
predictable 4/8/12px spacing. No new custom graphics or native controls lost.
"""
EDITOR_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #141922;
    color: #E6EBF4;
    font-family: "Segoe UI", "Arial";
    font-size: 12px;
}
QMenuBar, QMenu, QStatusBar {
    background: #171E29;
    color: #E5ECF5;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #314A69;
    border-radius: 4px;
}
QDockWidget {
    border: 1px solid #2D394A;
    color: #D5E0EF;
    font-weight: 600;
    titlebar-close-icon: none;
}
QDockWidget::title {
    text-align: left;
    padding: 9px 12px;
    background: #1C2532;
    border-bottom: 1px solid #304054;
}
QTabWidget::pane {
    border: 1px solid #303C50;
    background: #18212C;
    border-radius: 5px;
}
QTabBar::tab {
    color: #A4B3C7;
    background: #1B2633;
    border: 1px solid #304052;
    padding: 8px 12px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #F1F6FD;
    background: #304B68;
    border-bottom: 2px solid #61ABDB;
}
QTabBar::tab:hover:!selected { background: #26394E; }
QPushButton {
    background: #25354A;
    color: #E5EFFB;
    border: 1px solid #39516B;
    border-radius: 6px;
    padding: 7px 10px;
    min-height: 20px;
}
QPushButton:hover { background: #34516F; border-color: #6197C5; }
QPushButton:pressed { background: #233C55; }
QPushButton:disabled {
    background: #1C2631;
    color: #718195;
    border-color: #2C3542;
}
QPushButton[role="primary"] {
    background: #245B8C;
    border: 1px solid #4385B6;
    font-weight: 600;
}
QPushButton[role="primary"]:hover { background: #2C73AA; }
QLineEdit, QPlainTextEdit, QTableWidget, QComboBox,
QSpinBox, QDoubleSpinBox {
    background: #1B2633;
    color: #E6EBF4;
    border: 1px solid #3A4A5D;
    border-radius: 5px;
    selection-background-color: #3574A6;
    padding: 4px;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #5CA9DC;
}
QTableWidget { gridline-color: #2A3646; }
QTableWidget::item:selected { background: #2D608B; }
QHeaderView::section {
    background: #26364A;
    color: #D9E5F3;
    border: 0;
    border-right: 1px solid #344457;
    padding: 7px;
}
QScrollArea { border: none; }
QScrollBar:vertical, QScrollBar:horizontal { background: #1C2632; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #425872;
    border-radius: 4px;
    min-height: 18px;
    min-width: 18px;
}
QSplitter::handle { background: #303E51; }
QProgressBar {
    background: #222D3B;
    border: 1px solid #304357;
    border-radius: 5px;
    height: 13px;
    text-align: center;
}
QProgressBar::chunk { background: #3985B9; border-radius: 4px; }
QToolTip {
    color: #EDF3FB;
    background: #2B3B51;
    border: 1px solid #527397;
    padding: 5px;
}
"""
