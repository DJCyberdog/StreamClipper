# NEXT_TASK – M12b Video-/Overlay-Compositor, M12c Render-Backends

**Stack (Draft, kein Merge nach main):**
M10.5 #31 → M11a #34 → M11b #36 → M11c #37/#38/#39/#40
→ HF UX #41 → M12a #42 → M12b Audio #43
→ Premium Dock Shell #44 → **M12-UX Teil 2** (neu, auf #44).

## M12-UX Teil 2 (im Draft, noch keine reale Windows-End-to-End-Abnahme)

- **Ein Timeline-Dock:** Wellenform/Highlights/Wortzeiten plus
  Gameplay/Mikrofon/Musik/Overlay-Cliplanes untereinander, gleicher
  sichtbarer Zeitbereich, gleiches 128px-Gutter, Zoom/Scroll/Playhead/IN/OUT.
- Vertikaler QSplitter trennt renderfreie Zeichenlagen; kein zweites
  Track-Canvas mehr im Reiter „Spuren“.
- M12 Magnet: 8px-Snapping an andere Clips, Playhead und IN/OUT;
  jederzeit abschaltbar. Kein Edit des originalen M12b-Basisclips
  durch Dragging; gesperrte Tracks bleiben geschützt.
- **Eigenschaften-Editor:** Quell-IN, Quell-OUT, Timeline-IN,
  Audiogain. Ein Bestätigen -> genau ein `edit_item`-
  History-/atomarer-Save-Schritt. Sperre, Base-Source und Invalid-
  Values fail closed, Reset verwirft ungespeicherte UI-Felder.
- Windows Qt Offscreen: gleiche Pixelabbildung, Scroll/Zoom,
  Magnet, Undo/Redo, Schreibfehler, Originaldatei intakt.
- M11/M12 Rückwärtskompatibilität und bestehende Extras erhalten.

## Jetzt abzuarbeiten

1. Python- und Windows-CI am exakten PR-Head prüfen; inklusive
   Preview/Export, Projekt-Checkpoints, Dock-Presets, Qt-Layout-
   Restore, Audio-Spuren und portablem ZIP.
2. **M12b Teil 2:** Video-/Grafik-Overlay-Compositor über denselben
   versionierten `RenderRequest`, inclusive Source-/Timeline-PTS,
   Bildreihenfolge, Lücken, Opacity und Skalierung; verifizieren
   mit Pixel-/Frame-Golden-Tests vs. Preview. Ungeprüfte Clips
   weiterhin fail-closed statt still ignorieren.
3. **M12c** Encoder-Auswahl und NVENC H.264/HEVC/CPU-Fallback;
   **M12d** vollständige Export-QA;
   **M12e** Renderqueue, Recovery, keine unbestätigten Uploads.
4. Weitere Premium-UX: Clip-Kanten-Ripple/Roll, Track-Lock in der
   Timeline, Audio-Solo, Keyframes und erweitertes M13/M14-
   Inspector-Panel nach echtem Rendergraph (keine Fake-UI).
5. Reale 6h-VOD-/Windows-11-Messung 1366×768, 1920×1080,
   CPU/GPU/VRAM, verschobene Clips/Audio-PTS und
   Projekt-Recovery. Alle Test-Accounts und Online-Freigaben
   bleiben M19.
6. M19 Publishing über offizielle YouTube/TikTok/Instagram/
   Snapchat APIs, pro Ziel explizite Veröffentlichung.

**Grenze:** Neu ist ein synchronisierter zusammengesetzter Timeline-
Viewport und ein echter Property-Editor, kein kompletter NLE-
Multi-Video-Compositor oder fertiger Premiere-Ersatz.
