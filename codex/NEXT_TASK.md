# NEXT_TASK – M11c Preview-Abnahme / M12 Render-Vertrag

**Stack:** M10.5 #31 → M11a #34 → M11b #36 →
M11c Checkpoints #37 → M11c Undo #38 → M11c Highlight Import #39 →
M11c Proxy Preview Draft #40.
`main` bleibt unverändert. Echte Abnahmen vor dem Merge dokumentieren.

## M11c Teil 4 (zur Prüfung)

- CPU-basiertes, optionales 854×480-H.264/AAC-Proxy-Transcoding mit
  FFmpeg im QThread, Abbrechen/Fortschritt und originaltreuem Schnittmodell.
- VFR-frame PTS-Abstände erhalten (`-fps_mode passthrough`), Video-PTS
  auf Proxy-Beginn normalisieren; getrennte Original↔Proxy-Zeitzuordnung.
- Start-/Audioversatz über 150 ms sowie Gesamtdrift über 300 ms
  ausdrücklich ablehnen statt scheinbarer Synchronität.
- Quelle/Video-Metadaten, Größe/mtime_ns und Encoder-Preset binden Cache
  unter `data/proxies/`; temporäre Dateien und Manifest atomisch
  publizieren, alte/kaputte Caches nicht für Vorschau anbieten.
- GUI-Umschaltung Original/Proxy mit identischen Originalzeiten,
  automatischer Fallback bei InvalidMedia.
- Pytest-, VFR-FFmpeg-, Qt-Offscreen- und Windows-Portabel-Build-Gates.

## Nächste begrenzte Schritte

1. Auf echtem Windows 11 ergonomische Vorschau bei 1366×768 und
   1920×1080 prüfen; Audioausgabe, Wechsel im Playback, Worttiming.
2. Reale sechsstündige OBS-/Twitch-VODs mit VFR und Audio-Offsets
   messen: Peak-RAM/VRAM, Encode-Dauer, Scrubbing/Drift und Cancel/Crash.
3. Cachepublikation nach Strom-/Festplattenfehler sowie concurrent
   Worker konkurrierender Quellen härten; Fallback-Tests erweitern.
4. Separat M12-Datenvertrag für WYSIWYG-Vorschau/MP4-Rendergraph
   der Video-, Audio-, Untertitel- und Overlay-Spuren definieren.
5. `main` weiterhin nicht ohne Ownerfreigabe verändern.

## Nicht behaupten

Keine exportgetreue Mehrspur-Vorschau, keine frameidentische Proxyansicht
und keine echte Windows-/6h-Abnahme ohne reproduzierbare Messungen.
