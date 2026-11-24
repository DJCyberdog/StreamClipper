# NEXT_TASK – M14 Untertitel, Branding & visuelle Gestaltung

Owner-Freigabe 2026-11-24: „M13 wurde lokal abgenommen. Weiter geht's“.
Lokale Abnahme als Owner-Aussage dokumentiert; keine unabhängigen Modell-,
GPU- oder Messprotokolle vorliegend. Basis PR #50, 39511c48.
Linux CI 45452643105 PASS. Windows 45452643337: pytest 174 passed,
1 skipped, danach Exit 1; Build übersprungen. Ursache noch nicht belegt.
M13 bleibt als Owner-abgenommen dokumentiert, CI-Fehler nicht verschweigen.
Kein Merge ohne gesonderte Freigabe.

Verbindlich ROADMAP.md §5.5: S-B2, A-B2, #19, #23, #28, #30.
M14 begonnen; kein neuer Roadmap-Untermeilenstein.

Implementiert: CaptionStyle mit Vorlagen, Schrift, Farben, Größe, Position,
Wortgruppen, aktiver Worthervorhebung und Pop-Animation. Untertitelgestaltung
im Branding-Menü. Projektpersistenz, Undo/Redo, Checkpoint, unveränderliche
RenderRequest-/Queue-Snapshots. Gemeinsamer ASS-Renderpfad für Vorschau,
Direktexport und Queue. Eindeutige Einzelwort-Textkorrektur erhält Wortzeiten;
bei geänderten Grenzen oder nicht eindeutiger Zuordnung keine erfundenen Zeiten.
Ältere Daten ohne Stil erhalten Standardwerte.

Neu: #23 separate, quellgebundene Übersetzungen, lokaler Marian-Adapter,
Worker-Dialog mit manueller Korrektur und Sprachwahl; Undo/Redo, Analyse-JSON,
Autosave, Checkpoint, Render-Vorschau/Direkt/Queue und CLI. Geänderte Originale
invalidieren die betroffene Übersetzung; fehlende Übersetzungen verhindern
Sprachmischung. Abschnittszeiten, keine künstlichen Zielwortzeiten.
Echter Marian-Modelllauf offen. Übersetzungs-Head e27dbfa5: Linux 382 passed,
19 skipped, compileall PASS; Windows beim Abruf noch laufend.

Neu #28: editierbare Callouts auf Grafikspuren (Text, Sprechblase, Pfeil,
Rechteck, Ellipse), zeitliche Platzierung, Farben, Größe, Position und
Deckkraft. Procedural RGBA aus Metadaten im privaten Renderordner, kein
externes Asset nötig. GUI-Elementvorschau, gemeinsamer Renderpfad,
Undo/Redo, Checkpoint und Queue. Tests für echte MP4-Zeitgrenzen und
Preview-Parität geschrieben, neue CI offen. Font zunächst Pillow-Standard.

Nächste konkrete Schritte:
- CI dieses Heads und Windows-Prozessende diagnostizieren; neue Tests laufen lassen.
- Wort-/Timingkorrektur und Übersetzung mit tatsächlichem lokalem Modell abnehmen.
- Branding-Vorlagen/Logos mit bestehender Grafikspur verknüpfen.
- #28 CI/GUI-Abnahme; #30 Thumbnail-Designer aus dem tatsächlichen Renderframe
  und gemeinsamen exportgetreuen Workflow fertigstellen.
- Abnahme inkl. kombinierter M13/M14-Renderfälle und nativer Bedienprobe.
  Version 0.8 erst nach vollständigem M14, kein voreiliger Release.

Python-Quellcode-Update analog M9; .venv und data erhalten. PyInstaller separat.
