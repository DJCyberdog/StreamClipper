# NEXT_TASK – M10.5: Konsolidierungsabnahme

Die verbindliche Planung steht in **/ROADMAP.md**. Aktuelles Arbeitsziel ist
**M10.5 – Integration & Baseline**, nicht das alte SC-P0-01-Ticket.

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
