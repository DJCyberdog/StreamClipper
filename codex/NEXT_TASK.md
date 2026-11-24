# NEXT_TASK – M13a Szenenauswahl vollständig abschließen

Verbindliche Quelle: /ROADMAP.md §5.4. Keine Umdefinition von M13a–e.
Basis: M12d/e #48, CI und Windows-Paket erfolgreich; native GPU-/6h-Abnahme offen.

Vorhanden im Draft #49: Szenen aufteilen, In/Out, Ausgabe-Reihenfolge,
Ein-/Ausschluss, drei Kameramodi, numerische und visuelle normierte Bildregion (asynchron geladenes Quellbild) und atomare
lokale Speicherung pro Highlight; Menü Szenen. Früherer Kamerakeyframe-Kern
ist M13b-Vorarbeit, nicht M13a-Abnahme.

Noch zwingend für M13a:
- Visuelle Bildregion im Quellbildmonitor per Maus implementiert; Qt-/native Bedienprobe und Darstellung bei unterschiedlichen Seitenverhältnissen prüfen.
- Szenenplan in gemeinsamen Projekt-/Undo-/Checkpoint-Vertrag übernehmen;
  Highlight-Grenzenänderung darf gespeicherte manuelle Szenen nicht verlieren.
- Gemeinsame Vorschau-/Export-/Queue-Anbindung: tatsächliche Szenenreihenfolge,
  Ausschluss, In/Out, Crop-Modus, Untertitel und Audio korrekt abbilden.
  Kein stilles Ignorieren eines Szenenplans.
- Qt- und echte FFmpeg-Tests, Windows-CI, native Bedienprobe; M13a erst
  bei belegter Abnahme abschließen, danach M13b gemäß Roadmap.

Aktuelle Begrenzung: Der Dialog speichert nur Metadaten. Rendering unverändert. GUI blockiert für exakt passende gespeicherte Highlight-Szenenpläne Render-Vorschau, Direkt-Export, Neueinreihen und Highlight-Trim bis zur Renderintegration. Bereits eingeplante alte Jobs und CLI sind davon nicht betroffen. Kein Abschluss ohne gemeinsame Renderanbindung.
Keine M13b–e-Arbeit vor Abschluss der M13a-Implementierung.
