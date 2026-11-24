# NEXT_TASK – M12b2 Video-/Grafik-Compositor abnehmen; M12c Encoder

**Stack (Draft, main unverändert):** M10.5 #31 → M11a #34 →
M11b #36 → M11c #37/#38/#39/#40 → HF UX #41 → M12a #42 →
M12b Audio #43 → Premium Dock #44 → Unified Timeline #45 →
**M12b Teil 2 (PiP/Logo)** (neuer gestapelter Draft).

## Jetzt implementiert (Abnahme nur durch CI und echte Tests)

- Projekt-/Checkpointvertrag v3 (v1/v2 beim Lesen migrieren,
  keine Quell-Dateimutation): explizite lokale Video- und
  Einzelbild-Referenz, normalisierte x/y/Breite/Höhe, Deckkraft.
- RenderGraph v2: deterministische Reihenfolge der visuellen
  Layer, Bild-/Clip-Timing über Quell-IN/OUT, Timeline-IN,
  Clip-Zeitfenster einschließlich gekürzter Vorschau, Track-Mute.
  Echte PiP-Video- und statische PNG/JPEG/WebP-Komposition
  bei unverändertem Gameplay-Basisvideo; separate Audio-Layer
  werden weiter gemischt, PiP-Audio nicht automatisch übernommen.
- Gemeinsamer FFmpeg-Pfad aus `RenderRequest` für MP4 und
  20s-Render-Vorschau; keine Video-/Bildpfade in Filtergraphs;
  FFprobe-Preflight und atomic final publication.
- PySide6: explicit „🎬 Video / Logo einfügen“, Grafikbox und
  Deckkraft im bestehenden Inspector, ein Undo-Schritt.
  Audio-Import und Audio-Gain bleiben erhalten.
- Tests: v2→v3-Migration, v2-Checkpoints, VisualLayer-Grenzen,
  Laufzeit/Mute/Stack, echte pixelweise PiP-/Logo-Phasen
  vor/during/nach, decoded preview/export Audio+Bild-Parität
  und Missing-Source ohne Partialdatei.

## Jetzt als nächster Prüfauftrag

1. Linux-Python-Gesamttests und Windows-Qt/FFmpeg-Suite plus
   PyInstaller-ZIP am **exakten PR-HEAD** abschließen. Kein
   PASS ohne tatsächlich abgeschlossenes GitHub-Resultat.
2. Negative Szenarien: beschädigte Bilder, dynamische VFR-PiP
   (PTS), Alpha, stumme Bild-/Audio-Spuren, Windows-Pfade,
   Burned Captions+PiP, Cancellation während FFmpeg,
   Dateisperre/Recovery.
3. **M12c:** NVENC/H.264/HEVC-Probe mit garantierter CPU-Fallback
   und Videoqualität-/Performance-Analyse; Speicherverbrauch
   i5-11400F/RTX 5060 Ti berücksichtigen.
4. **M12d:** Export-QA/Audio-Loudness-/Sync-Metriken;
   **M12e:** Renderqueue/atomare Recovery.
5. **Premium NLE-M13:** Bildbox direkt im Monitor verschieben,
   Keyframes/Opacity-Kurven, echtes Timeline-Trimming/Transitions,
   eigener Caption-Clip-Renderer. Keine automatische
   Interpretation alter Highlight-Metadaten als PiP.
6. Reale 6h-OBS-VOD-/Windows-11-1080p-End-to-End-Akzeptanz,
   1366×768/1920×1080-UX und Audio-PTS.
7. **M19 Publish:** Google/YouTube/TikTok/Instagram/Snapchat
   nur über offizielle freigegebene APIs und expliziten Klick.

**Grenzen:** Noch kein kompletter multi-source NLE-Full-Render,
keine timeline-internen Caption-Objekte, kein animiertes PiP,
kein Quellvideo-Ersatz, keine automatische PiP-Tonmischung.
