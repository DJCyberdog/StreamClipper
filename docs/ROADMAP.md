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

- [ ] Optionale lokale Spracherkennung mit Zeitstempeln (faster-whisper)
- [ ] Szenenschnitt-Erkennung aus gesampelten Frames
- [ ] Zusammensetzen mehrerer Evidenzen; Score **kalibrieren oder klar als Heuristik ausweisen**
- [ ] Kontext vor/nach erkannter Aktion erhalten; nicht mitten in Pointe schneiden
- [ ] Aufnahmearten getrennt auswerten (Gaming + Mikrofon, gemischter Stream, VOD)
- [ ] Tests anhand von vom Nutzer freigegebenem Aufnahme-Material

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
