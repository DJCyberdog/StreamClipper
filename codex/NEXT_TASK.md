# NEXT_TASK – M11c / Teil 4: Proxy Editing für lange Aufnahmen

**Stack:** M10.5 #31 → M11a #34 → M11b #36 →
M11c Checkpoints #37 → M11c Undo #38 →
M11c Highlight-Import (Draft) #39.
`main` bleibt unverändert; kein unfreigegebener Merge.

## Teil 3 – Implementierung zur Prüfung

- Expliziter Import vorhandener Analyse-Highlights in die eigene Spur
  `highlights_import` oder vom User gewählte vorhandene Videospur.
- Vorherige Prüfung von Quelle, Zeiten, Typ, Sperren und Projektgrenzen;
  kein Import auf Hintergrundjob.
- Stabile importierte Clip-IDs aus Quellpfad und Millisekundenfenster,
  idempotent beim Reimport, kein Überschreiben manuell bearbeiteter Clips.
- Eine atomische Spurplan-Persistenz und gemeinsamer Undo-Schritt.
- GUI-Status zeigt hinzugefügte und ausgelassene Highlights.
- Kein Einfluss auf Videoexport oder tatsächliche Audio-Komposition.

## Nächste abgegrenzte Aufgabe: M11c Teil 4

1. Proxy-Konzept und reproduzierbare, quellzeitgetreue Metadatenabbildung
   entwickeln: VFR, Drift und Cut-In/Out unter Test.
2. Lange 6h-Aufnahmen mit Streaming-/bounded-memory-Prozess statt
   Komplettdecodierung; Hardwarepfade nur optional.
3. Proxy-Dateien separat unter `data/proxies/` mit Source-Fingerprint,
   Cache-Invalidierung und atomischer Erstellung; niemals Original ändern.
4. GUI-Auswahl Proxy / Original sowie Status im Vorschau-Bereich,
   ohne zusätzliche Hauptregisterkarte. Keine Jobs auf UI-Thread.
5. Pytest / compileall / Windows-Qt-Smokes; reale Windows 1366×768,
   FullHD, 6h-VOD/RAM/VRAM gesondert abnehmen.

## Nicht behaupten

Kein M12 exportgetreuer Mehrspur-Renderer und keine fertige gemischte
Mehrspurvorschau. `main` bleibt bis expliziter Owner-Freigabe unberührt.
