# NEXT_TASK – M13a Abnahme

Verbindlich: /ROADMAP.md §5.4. M13a nicht umdefinieren.
#49 enthält Szenenauswahl, Region-Monitor, Projekt/Undo/Checkpoint,
RenderRequest-/Queue-Snapshot, tatsächliche Szenenreihenfolge, Ausschluss
und Crop-Modi; Vorschau nach Ausgabezeit begrenzt. M13b-Keyframe-Vorarbeit
ist nicht Teil der M13a-Abnahme.

1. Finalen Head der Linux-CI (pytest + compileall) und Windows-Portable-
   CI prüfen. Neue M13a-Tests enthalten reale MP4-Reihenfolge, Crop,
   Audio, Projekt/Checkpoint/Undo und Queue-Roundtrip. Fehler beheben.
2. Native Windows-Bedienprobe: Szenen markieren, reordnen, ausschließen,
   Undo/Redo, Neustart/Checkpoint, Vorschau, Direktexport und Queue.
3. Zusätzliche reale Tests für mehrspuriges Audio und ASS an Szenennaht,
   VFR, mehrere Szenen und Abbruch. Sechs-Stunden-VOD und GPU/CPU-
   Profilwahl dokumentieren. Keine ungeprüfte Qualitätsbehauptung.
4. Erst nach belegter M13a-Abnahme M13b gemäß ROADMAP.md beginnen.

Grenzen: Mehrszenenrender verwendet H264-Zwischenstücke, zusätzlichen
Encode und temporären Speicher. VFR-/Audio-Nahtstellen und exakte
Preview-Parität noch nicht abgenommen; M13e bleibt eigener Meilenstein.
Alte Sidecars werden beim Öffnen/Speichern explizit übernommen, externer
Highlight-Trim bei Plan gesperrt; ältere App nicht zum Downgrade verwenden.
Main unverändert. Keine Roadmap-Änderung.
