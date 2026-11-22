# NEXT_TASK – M11: Editor, Timeline & Datenhaltung

**Basis:** Stack auf Draft-PR #31 / M10.5. Der Integrationsstand ist
automatisiert getestet, jedoch nicht vollständig auf realem Windows und
sechsstündigen Twitch-VODs abgenommen. Kein Merge nach main ohne Freigabe.

## M11a – dieser Branch (erster nutzbarer Editor-Schritt)

- Compact EditHistory: manuelle Clips hinzufügen/entfernen/trimmen,
  Wort- und Segmentkorrekturen rückgängig/wiederholen, Redo nach neuem
  Edit invalidieren, keine kompletten Transkriptkopien je Schritt.
- Qt-GUI: sichtbare Buttons, Strg+Z und Strg+Umschalt+Z.
- Atomische Sicherung nach kurzer Bearbeitungspause im bestehenden JSON-
  Format unter `data/projects/autosaves`. Kein Cloud-Upload.
- Videoquelle erneut öffnen → Recovery-Dialog; Dauer/Auflösung validieren.
  Explizites Speichern/Verwerfen entfernt zugehörige Sicherung.
- Tests: Core und offscreen-Qt; echte Windows- und 6h-End-to-End-Abnahme
  **noch offen**, großes JSON bei Auto-Sicherung auf UI-Latenz prüfen.

## M11b – nächstes inkrementelles Paket

1. Versioniertes, PySide6-unabhängiges Projektmodell mit Gameplay-, Mikrofon-,
   Musik-, Caption- und Overlay-Spuren.
2. Spur-/Clipoperationen samt History und Migration aus altem Analyse-JSON.
3. Erweiterte, benutzerkontrollierte Projekt-Checkpoints (D-B1) und Proxy-
   Erzeugung/Zuordnung (#05). Projekt nicht auf eine Quelle fest verdrahten.
4. Konfigurierbare Keyboard-Shortcuts (#36); keine voreiligen WYSIWYG-Claims
   vor M12-Render-Vertrag.

Testbefehle: `python -m pytest -q`, `python -m compileall -q src`.
