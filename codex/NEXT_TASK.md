# NEXT_TASK – M12-UX: Premium Dock-Shell / M12b Video-Compositor

**Branch-Stack:** M10.5 #31 → M11a #34 → M11b #36 →
M11c #37/#38/#39/#40 → HF UX #41 → M12a #42 →
M12b Audio Graph #43 → M12-UX Premium Dock Shell Draft #44.
`main` unverändert; kein Merge ohne explizite Ownerfreigabe.

## Im aktuellen M12-UX-Teil-1-Draft

- Existing GUI in **Qt QMainWindow/DockWidgets**: Projekt-/Highlight-Tools
  links, zentraler Programmmonitor, **bewegliche Timeline unten**,
  kontextbezogener Inspector rechts. Spuren-/Underteitel-/Export-Widgets
  werden wiederverwendet, keine geklonten Signal- oder Editzustände.
- Arbeitsbereich-Umschalter: Highlights / Schnitt / Audio / Untertitel
  / Export. Nur UI-Sichtbarkeit/Tabfokus wird geändert, niemals
  Quelle, Playhead, Clipauswahl oder Edit-Historie neu angelegt.
- Einheitliches Premium-QSS (Graphit/Saphir, lesbare Zustände).
- Layout im lokalen `data/ui/workspace-layout-v1.json` ohne Medien-
  daten oder Credentials, versioniert, atomar und mit Reset. Keine
  Fensterposition über Monitorwechsel hinweg wiederherstellen.
- Windows-Qt-Offscreen-Regression: Docks/Areas, Presets, Wiedergabe-
  Identität, Layout-Neustart, Inspector und 1366x768. Pure Storage-
  Tests für Validierung, korruptes JSON, unbekannte Schemas.

## Nächste begrenzte Schritte

1. Linux-Python-Tests und Windows-Qt-/Portable-Build auf **exaktem**
   PR-Head abnehmen; gefundenes Fail gezielt beheben.
2. **M12-UX Teil 2:** tatsächliche zusammengeführte mehrspurige
   Timeline (ein TrackCanvas, eine Wellenform, eine Zeitbasis),
   Splitter-Resizing/Drag-Drop, Mini-/Full-Track-Ansichten,
   Inspector-Eigenschaftseditor und Shortcuts; Änderungen bleiben
   nichtdestruktiv und undoable.
3. **M12b Teil 2:** zusätzliche Video- und Grafikquellen korrekt
   compositen, zeitbasierte Overlaps/Layering und eindeutige
   Preview-vs-MP4-Goldentest; derzeit fail-closed.
4. **M12c** NVENC/H264/HEVC/CPU-Fallback; **M12d**
   Exportqualitätskontrolle; **M12e** Renderqueue mit Recovery.
5. Reale Windows-11-Tests auf 1366x768/1920x1080, 6h-OBS-Aufnahmen,
   GPU/RAM/VRAM, Audio-PTS, Export-Abbruch und Portabilität.
6. M13–M19 fachliche Inspector/Workspace-Integration und
   ausschließlich bestätigtes Online-Publishing über offizielle APIs.

**Nicht behaupten:** Das Docking-Grundlayout ist noch kein vollständiger
Premiere-Ersatz, keine komplette Live-WYSIWYG-Mehrspur-Vorschau und
kein abgeschlossener M12-Freeze. Keine Autoposts/Cloud-Pflicht.
