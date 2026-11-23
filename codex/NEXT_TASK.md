# NEXT_TASK – M12b: Audio-Compositor abnehmen / Video-Compositor vorbereiten

**Stack:** M10.5 #31 → M11a #34 → M11b #36 →
M11c Checkpoints #37 → M11c Undo #38 → M11c Highlight-Import #39 →
M11c Proxy #40 → HF-UX #41 → M12a Render Preview #42 →
M12b Audio Track Graph Draft #43.
**main unverändert; keine stillen Merges ohne Ownerfreigabe.**

## Im M12b Teil 1 Draft (abzugrenzen und zu prüfen)

- M11-Projekt-Schema v2: optionale lokale Audiodatei und Clip-Gain; v1-
  Projektdateien und Checkpoints werden lesend migriert.
- Deterministischer versionierter RenderGraph: alle Track-Node-Typen
  repräsentiert, Audio-Overlaps/Source-vs-Timeline-Zeiten, Mute, Hidden,
  Locked. Nicht unterstützte Video-/Grafik-Komposition fail-closed.
- FFmpeg mappt explizit ausgewählte Audio-Clipintervalle (Originalton und
  externe lokale Sounddateien) auf die Ausgabetimeline und mischt sie
  gemeinsam mit der ursprünglichen Audioaufnahme.
- Derselbe RenderRequest und graphbasierte FFmpeg-Pfad für MP4 und
  20s-Render-Vorschau. Beta **nur per Checkbox**.
- Qt: lokale Datei wählen, Pegel dB, Quell-/Timeline-Trimming,
  Undo/Redo und Wiederherstellung; keine Änderung an Originaldateien.
- Python-Unit, echte FFmpeg-Audioparität und Windows-Qt-Offscreen prüfen.

## Abnahme vor Freigabe / nächste begrenzte Schritte

1. CI/Windows-Portable-Gates gegen **exakten PR-Head** auswerten und
   fehlgeschlagene Regressionen gezielt korrigieren.
2. Zusätzliche Video-/Grafikclips im M12b-Teil-2-Compositor in
   kontrollierter Reihenfolge mit expliziter Quell-/Ausgabezeit umsetzen,
   mitsamt Offline-/Preview-FFmpeg-Parität und strukturiertem Overlaymodell.
3. FFprobe-Audio-Preflight der UI asynchron machen, Dateisperren/
   Medienersetzung und sichere Reparatur fehlender Pfade prüfen.
4. M12c GPU NVENC/H.264+HEVC und CPU-Fallback, M12d Export-QA,
   M12e Warteschlange/Recovery; keine automatischen Exporte ohne Klick.
5. Reale Windows-11-Aufnahmen inklusive 6h OBS-VOD, CPU/GPU/RAM/VRAM,
   Audio-Synchronität und Audioübersteuerungen messbar abnehmen.

## Nicht behaupten

Kein vollständiges Live-Mehrspur-WYSIWYG, kein Video-/Overlay-Compositor,
keine Loudness-/True-Peak-Garantie, keine echte Windows-/6h-VOD-Abnahme
ohne reproduzierbaren Nachweis. Keine neuen obligatorischen Clouds.
