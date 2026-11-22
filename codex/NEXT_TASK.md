# NEXT_TASK – M11c / Teil 2: Einheitlicher Undo-Verlauf und Shortcut-Gates

**Stand:** M10.5-Draft #31 → M11a-Draft #34 → M11b-Draft #36 →
M11c-Checkpoint-Entwicklungsbranch `feat/sc-m11c-project-checkpoints`.
Der Checkpoint-Branch ergänzt atomische benannte Projektstände
(Spurplan + optionale Analyse) und bündelt deren Bedienung im Menü
**Datei & Projekt**. CI, Windows-Offscreen und echte Windows-11-Tests
müssen pro genauem Commit geprüft werden; `main` bleibt unverändert.

## Nächster abgegrenzter Arbeitsschritt

1. Getrennte Analyse- und Spur-Undo/Redo-Verläufe zu **einem**
   quellengebundenen, transaktionalen Editierverlauf zusammenführen.
2. Ein einziges Strg+Z / Strg+Umschalt+Z im aktiven Studio;
   bisherige Spur-Undo/Redo-Buttons entweder anbinden oder entfernen.
3. Bestehende History-Tests, neue gemischte Interleavings und Qt-Offscreen-
   Tests für Fokus-/Shortcut-Konflikte ergänzen.
4. Mindestens ein fehlschlagender Test vor der Änderung, anschließend
   `python -m pytest -q`, `python -m compileall -q src`.
5. Real-Windows-Abnahme (1366×768/FullHD) und 6h-VOD nicht behaupten.

## Danach noch offen in M11c

- Analyseclips ohne Dubletten in den Spurplan migrieren.
- Proxy-Videos mit exakt dokumentierter Quellzeitabbildung und Rückfall.
- Checkpoint-/Autosave-Interaktion unter simulierten Crashes und
  großen Transkripten weiter härten.
- Vor M12 weiter **keine** exportgetreue Mehrspur-Komposition behaupten.
