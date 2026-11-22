# NEXT_TASK – M10.5: Konsolidierungsabnahme

Die verbindliche Planung steht in **/ROADMAP.md**. Aktuelles Arbeitsziel ist
**M10.5 – Integration & Baseline**, nicht das alte SC-P0-01-Ticket.

## Sofortiger P1-Fix – [Issue #32](https://github.com/DJCyberdog/StreamClipper/issues/32)

**Vor M10.5-Abnahme** die Modelldownload-UX vollständig verbinden:

- Fortschritt von `huggingface_hub.snapshot_download` im unteren Qt-Fortschrittsbalken
  anzeigen (echte Bytewerte bei bekannten Größen, Busy-Modus bei unbekannten Größen).
- Optionalen HF-Token **direkt in der App** maskiert einfügen, testen,
  für alle Downloadphasen nutzen, bei Bedarf entfernen.
- Bestehendes `HF_TOKEN`/HF-Login erkennen, aber niemals anzeigen oder überschreiben.
- Standard: **nur Sitzungsspeicher**; optionale Persistenz ausschließlich nach
  Zustimmung im Windows Credential Manager / entsprechend geschütztem OS-Store.
  Keine Klartextspeicherung in `data/`, Config, Git, Logs oder Fehlermeldungen.
- Authentifizierte/anonyme Downloads; verständliche 401/403-Meldungen,
  Retry ohne Datenverlust; Unit-/Qt-Tests mit Fake-Tokens.
- **Exakte P1-Abnahmekriterien:** `/ROADMAP.md`, Abschnitt **M10.5-P1-01**.
  Das ist Teil des bestehenden Modellmanagements, kein 61. Hauptfeature.

1. Den Draft-Integrations-PR `integration/m10-5-consolidated-baseline` prüfen und CI/Windows
   auf dem exakten Integrationscommit auswerten.
2. Windows 11: `run_windows.bat`, portable EXE, GUI/Timeline/Wort-Editor,
   Modellwahl, Sprachlexikon, FFmpeg starten und bedienen.
3. Echte Whisper-/CLIP-/DETR-Modellgewichte laden, GPU und CPU-Fallback testen.
4. Testvideo: Highlight → Wortkorrektur → Wörterbuch → JSON-Persistenz → MP4.
5. Öffentlicher Twitch-VOD-Import und ein vollständiges 6h-Gaming-VOD; RAM/
   VRAM/Performance sowie Erkennungsfehler protokollieren.
6. Offene Befunde in `docs/M10_5_INTEGRATION.md` ergänzen; Integration
   erst nach Review/Freigabe mergen.
7. Danach **M11 – Editor, Timeline & Datenhaltung**, einschließlich der vom
   Owner vor 1.0 eingeplanten D-B1-Projektfunktionen.

Prüfbefehle: `python -m pytest -q`, `python -m compileall -q src`.
Keine stillen Uploads, kein Cloud-Zwang, kein ungefragtes Publishing.
