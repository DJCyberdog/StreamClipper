# Codex-Auftrag SC-P0-01 — Unterbrechbarer, atomarer MP4-Export

**Ziel:** Den vorhandenen Export in `media.py` und `gui.py` für längere Twitch-
Aufnahmen robust machen. Keine neuen KI-Detektoren in diesem PR.

## Ist-Stand

- `export_clip()` wartet auf FFmpeg via `communicate()` bis der Clip fertig ist.
- Der GUI-Abbruch wirkt vor dem nächsten Clip, nicht während des Encodings.
- `safe_destination()` vermeidet übliche Dateinamenskollisionen, ist aber
  keine atomare Reservierung (TOCTOU).

## Arbeitspakete

1. FFmpeg-Fortschritt mit `-progress pipe:1` lesen; schätzen auf Basis
   der gewählten Clipdauer, nicht der Gesamtdauer der Quelle.
2. Optionales Cancel-Token in Schleife prüfen, Prozessbaum bei Abbruch
   verlässlich beenden; keine Zombie-Prozesse.
3. Immer in temporäre `.partial.mp4` schreiben, bei Erfolg atomar an freien
   finalen Dateinamen verschieben, bei Abbruch/Fehler bereinigen.
4. Dateien vor Überschreiben schützen, auch bei parallelem Export.
5. Exportfortschritt auf QThread-Signal und GUI-Progressbar abbilden.
6. Unit- und Integrationstests für Erfolg, Cancel, FFmpeg-Fehler,
   vorhandene Zieldatei und Unicode-Quelle ergänzen.
7. README/Roadmap aktualisieren. PR ist Draft, keine automatische Freigabe.

## Akzeptanzkriterien

- Nutzer kann einen laufenden Encode abbrechen, ohne kaputten finalen MP4.
- Kein Original und kein bestehender Export wird verändert.
- Test-Suite grün, inklusive FFmpeg-Integration (sofern installiert).
- Hauptthread blockiert nicht.
- Auf Windows zu prüfende Fälle explizit im PR auflisten.

## Nicht im Scope

Whisper, Gesichtserkennung, TikTok-Upload, Twitch-Download, neue GUI-Frameworks.
