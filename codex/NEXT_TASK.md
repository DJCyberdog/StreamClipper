# NEXT_TASK – M11c: Projekt-Checkpoints, Proxy-Editing und Render-Anbindung

**Bisheriger Stack:** M10.5-Draft #31 → M11a-Draft #34 →
M11b-Workspace-/Spurplan-Draft. Es liegt **noch keine vollständige reale
Windows-/6h-Abnahme** vor. `main` bleibt unverändert.

## M11b – umgesetztes Teilpaket (Review offen)

- GUI mit permanent sichtbarer Vorschau und Timeline; Sidebar-Register für
  Highlights, Untertitel, KI & Modelle, Spuren, Export; scrollbare Panels.
- Einklappbarer Worteditor, automatisch beim Wortklick expandiert.
- Versioniertes, reines Python-Spurmodell mit Clip-Zeiten, Sperren, Mute,
  Anordnung, atomischer lokaler Speicherung und eigenem Spur-Undo/Redo.
- Bestands-Analyseprojekte werden nicht überschrieben. Der bisherige
  Video-/Highlight-Export liest die neuen Spuren noch **nicht**.
- Tests Core und Qt-Offscreen. Reale Windows-Ergonomie bei kleinen Fenstern
  und 6h-Quellen noch prüfen.

## M11c – nächste Implementierungswelle

1. **Einheitlicher Bearbeitungsverlauf** für Spur- und Analyseänderungen
   (bislang getrennte Undo-Stapel) plus Shortcut-Konfliktprüfung.
2. Import/Migration der bestehenden AnalysisResult-Clips in den
   Projektspurplan mit bewusst gewählter Zuordnung, ohne Dubletten.
3. Versionierte, benannte Projekt-Checkpoints; Liste, Wiederherstellung,
   Aufbewahrungsgrenzen und überprüfte Crash-Recovery.
4. Proxies für lange Aufnahmen, exakte Quellzeitzuordnung.
5. Vor dem M12-Render-Vertrag keine Zusage, dass Stummschaltung oder
   Spurposition bereits den exportierten Film beeinflussen.

Windows-End-to-End-Proben und 6h-VOD/RAM/VRAM weiterhin ausstehend.
Tests: `python -m pytest -q`, `python -m compileall -q src`.
