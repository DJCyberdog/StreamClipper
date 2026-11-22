# M10.5 – Konsolidierung und Abnahmeprotokoll

**Stand:** 22.11.2026 · **Status: IN REVIEW, NICHT ABGENOMMEN** · Integrationsbranch: `integration/m10-5-consolidated-baseline`

## Code-Herkunft

- Vollständiger M10-Dateibaum aus `48b74abf46e9efd341936e03b9e1041dc67958a9` (PR #30) als zweite Git-Elternlinie.
- Die gestapelte Entwicklung: **#3, #6, #7, #9, #11, #12, #14, #16, #17, #18, #19, #23, #24, #25, #26, #27, #28, #29, #30**.
- **Maßgebliche `/ROADMAP.md` und `AGENTS.md` stammen aus aktuellem `main`**; die funktionsreichere README und ältere technische Roadmap aus M10 werden mit deutlichem Verweis erhalten.
- `codex/NEXT_TASK.md` referenziert jetzt M10.5 statt des überholten P0-Export-Tickets.
- Neuer statischer Importvertragstest prüft direkte lokale Modul-Exports und schützt vor unvollständigen GUI-Patchpaketen (bekannter Fehler: `apply_segment_changes` fehlte).

## Bislang belegte Ergebnisse

- M10-Quellcodepaket in Linux-Umgebung: **183 passed, 2 skipped**.
- Mit neuem Importvertragstest: **184 passed, 2 skipped**; `python -m compileall -q src` erfolgreich.
- Stichproben-Git-Blob-SHA von `gui.py`, `analyze.py`, `semantic.py` und `highlight_lexicon.py` stimmen mit PR #30 überein.
- Für den finalen PR-#30-Commit standen GitHub **CI** und **Windows portable build** beide auf **success**. Das beweist noch nicht, dass der neue Integrationscommit besteht oder die GUI auf dem Zielrechner lauffähig ist.

## Neuer Nutzerbefund / M10.5-P1-01

- **Beobachtet:** Beim Download eines großen CLIP-Modells läuft Hugging Face
  sichtbar im Konsolenfenster; die **untere GUI-Leiste bleibt bei 0 %**.
  Grund: `ModelDownloadThread` hat kein Download-Progress-Signal.
- **Zusatzanforderung:** Die Nutzeroberfläche soll **optional** einen
  Hugging-Face-Token annehmen, prüfen und für `snapshot_download(..., token=...)`
  benutzen. Hintergrund: HF-Hub-Hinweis zu höheren Ratenlimits bei
  authentifizierten Requests.
- **Verbindlich:** Token maskiert, standardmäßig nur im Sitzungsspeicher;
  nur nach ausdrücklicher Zustimmung verschlüsselt/OS-geschützt speichern.
  Keine Tokens in Git, lokalen Klartext-Configs, Logs, URLs oder Exceptions.
  Ohne Token bleibt der öffentliche Download nutzbar.
- **Tests:** Nachvollziehbare Fortschritts-/Authentifizierungs-/401-/403-/
  Retry-/Redaktions-Tests (Fake-Tokens) sowie echter Windows-Download.
- **Tracking:** [Issue #32](https://github.com/DJCyberdog/StreamClipper/issues/32),
  `/ROADMAP.md` Abschnitt **M10.5-P1-01**. **Nicht implementiert,
  nicht abgenommen**; M10.5 bleibt offen.

## Noch offene Gates

- [ ] **Neue CI + neuer Windows-Build** müssen auf dem Integration-Commit bestehen.
- [ ] Echte Windows-11-Praxissitzung: Start, PySide6, FFmpeg, alle GUI-Tabs und Modell-Downloads.
- [ ] **P1 #32:** Live-Modelldownload-Fortschritt sowie optionale HF-Token-Eingabe, sichere Speicherung und Fehlerbehandlung getestet.
- [ ] Whisper/CLIP/DETR mit echten lokalen Gewichten auf GPU/CPU validieren.
- [ ] Highlight erstellen → Timeline/Wort-Timing ändern → persönliches Wörterbuch ergänzen → JSON speichern/neuladen → MP4 exportieren, ohne Datenverlust.
- [ ] Öffentlichen Twitch-VOD-URL-Import mit Abbruch und Wiederaufnahme testen.
- [ ] Sechs-Stunden-VOD-End-to-End-Test; RAM/VRAM, Laufzeit, KI-Treffer/Fehlalarme dokumentieren.
- [ ] Auf Grundlage der Evidenz PR reviewen und erst nach Freigabe in `main` übernehmen.

**Noch kein Stable-Release.** Eine grüne CI- oder Windows-Packaging-Pipeline ersetzt keine echte Praxiserprobung.
