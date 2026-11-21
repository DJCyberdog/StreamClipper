# Roadmap / Definition of Done

## M0 — Audio-MVP (implementiert, Einschränkungen dokumentiert)

- [x] FFprobe Video-Metadaten lesen
- [x] lokal analysierbare RMS-Audiopeaks über FFmpeg
- [x] Kandidaten ohne Überlappung, kein fingiertes Gameplay-Verständnis
- [x] GUI mit Clip-Vorschau, Analyse/Export in Hintergrundthread
- [x] Crop/Blur-Export als 9:16 H.264/AAC
- [x] CLI, JSON, Unit- und FFmpeg-Integrationstests
- [x] Windows-GitHub-Actions-Packaging vorbereitet
- [ ] Manuelle Abnahme auf echter Windows-11-Installation
- [ ] Native Windows-EXE über GitHub Actions erfolgreich gebaut und gestartet

## M1 — Robuster Aufnahme-/Export-Workflow (Codex-P0)

- [ ] Problemfälle: Videos ohne Ton, mehrere OBS-Tonspuren, variable Framerate, beschädigte Eingabe
- [x] Fortschritt/Abbruch während FFmpeg-Export, atomare Dateinamen, Teil-Dateien bereinigen (SC-P0-01; Windows-Praxistest offen)
- [ ] Vorschau im tatsächlichen 9:16-Layout, Crop-Position anpassbar
- [ ] Clipgrenzen vor Export manuell veränderbar
- [ ] Windows GUI-Smoke-Test / Build-Artefakt verifizieren
- [ ] Tests für sehr lange Videos (Unicode und Überschreibschutz durch SC-P0-01 abgedeckt)

## M2 — Gaming-Detektoren / Erklärbare Highlight-Fusion

- [x] Optionale lokale Spracherkennung mit Zeitstempeln (faster-whisper); reale Modellabnahme offen
- [x] Gesampelte Frames + optionale lokale CLIP-Bildähnlichkeit; echte Ereignisvalidierung offen
- [x] Zusammensetzen mehrerer Evidenzen; Score ausdrücklich als **unkalibrierte Heuristik** ausgewiesen
- [ ] Kontext vor/nach erkannter Aktion präziser validieren; derzeit feste Preroll-Fenster
- [ ] Aufnahmearten getrennt auswerten (Gaming + Mikrofon, gemischter Stream, VOD)
- [ ] Reale Windows-/Modell-Abnahme anhand von vom Nutzer freigegebenem Aufnahme-Material

## M3 — Shorts-Qualität

- [ ] Untertitel mit Korrekturfenster und Styles
- [ ] Sprach-/Gesicht-/HUD-aware 9:16-Kadrierung, Gaming-Fokus
- [ ] 30/60 Sekunden Presets, TikTok-Safe-Zones
- [ ] Clip-Duplikate und überlappende Szenen erkennen
- [ ] Batch-Import und Ordnerüberwachung

## Abnahmeprinzip

Jedes Issue/PR benötigt reproduzierbare Tests, klare Einschränkungen und
Demo-Evidenz. Niemand darf die Software als KI-Verständnis oder erfolgssichere
TikTok-Optimierung verkaufen, bevor entsprechende Methoden implementiert,
validiert und messbar verglichen wurden.

## M2a — Nacharbeiten aus dem experimentellen Multimodal-Modus

- [ ] CLI/GUI mit echten lokal geladenen Whisper-/CLIP-Gewichten unter Windows 11 testen
- [ ] AI-fähiges Windows-Packaging ohne übergroßes Standard-EXE-Artefakt
- [ ] Manuell annotiertes Gaming-Evaluationsset und Fehlerratenmessung
- [ ] Zeitliche Szenen-/Ereigniserkennung statt Einzelbild-Ähnlichkeit
- [ ] Transkript- und Gameplay-Hinweise für Sprache/Mischspur und Kontext verbessern

## M4 – eingebrannte Untertitel / dynamische Bildführung (experimentell)

- [x] Whisper-Transkript einmal pro Analyse behalten und für Clip-Captions wiederverwenden
- [x] Fest eingebrannte Untertitel beim MP4-Export (ASS/FFmpeg, deutsche/englische Texte)
- [x] Automatischer 16:9-Zoom/Pan und 9:16-Reframe anhand lokaler Bildbewegungen
- [x] Pro Clip getrennte Motion-Sampling-Pipeline, temporäre Assets gelöscht
- [x] Synthetische Untertitel-/Motion-/FFmpeg-Tests ohne externe KI-Gewichte
- [ ] Windows-11-Praxistest mit echten OBS-Streams und Whisper-Modell
- [ ] Objektbasierte Erkennung statt einfacher Bewegungsheuristik
- [ ] Echtzeit-Vorschau des endgültigen Untertitel-/Kameralayouts
- [ ] Qualitätstest für ganze drei- bis vierstündige Aufnahmen

## M5 – manuelle Highlights / URL-Import

- [x] Markieren ohne KI, benennen, JSON speichern und MP4 exportieren (Windows-Praxistest offen)
- [x] Öffentliche Twitch-VODs per URL mit optionalem yt-dlp herunterladen und lokal laden (Windows-Praxistest offen)
- [ ] Sechs-Stunden-Langlauftest, Checkpoints, Wiederaufnahme KI-Analyse
- [ ] Authentifizierte VODs, Twitch-Clips, Bildvorschaubilder für Imports und Diskspace-Abfrage
