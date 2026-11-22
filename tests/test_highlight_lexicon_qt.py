"""Optional Qt smoke test for own highlight phrase settings dialog."""
import os

import pytest


@pytest.mark.skipif(os.environ.get("CI") == "" and os.environ.get("DISPLAY") is None and os.name != "nt",
                    reason="Headless display unavailable")
def test_custom_highlight_word_dialog(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from streamclipper import highlight_lexicon as lexicon
    from streamclipper.highlight_lexicon_dialog import HighlightLexiconDialog
    app = QApplication.instance() or QApplication([])
    file = tmp_path / "highlight_words.json"
    monkeypatch.setattr(lexicon, "settings_path", lambda: file)
    dialog = HighlightLexiconDialog()
    dialog.phrase.setText("Da war ein Monstertruck")
    dialog.upsert()
    assert dialog.table.rowCount() == 1
    dialog.save()
    assert lexicon.load_custom_rules(file)[0].phrase == "Da war ein Monstertruck"
    dialog.deleteLater()
    app.processEvents()
