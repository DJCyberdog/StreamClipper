# NEXT_TASK – M11c / Teil 3: Analyseclips in Spurplan migrieren

**Stack:** M10.5 #31 → M11a #34 → M11b #36 → M11c Checkpoints #37
→ Draft-Branch `feat/sc-m11c-unified-undo`.
`main` bleibt unverändert; jeder gestapelte PR benötigt eigene Tests/CI.

## Fertig zur Prüfung in Teil 2

- Ein globaler, quellengebundener und zeitlich sortierter Undo-/Redo-Verlauf
  für Clip-/Wort-/Transkript- und Spuränderungen.
- Kompakte Transkript-Deltas statt 6h-Vollkopien.
- Strg+Z und Strg+Umschalt+Z: zuerst natives Undo fokussierter
  editierbarer Textfelder, sonst Studio-Verlauf.
- Doppelte Undo-/Redo-Buttons aus Spurregister entfernt.
- Bei gescheiterter Spurpersistenz bleibt History und UI unverändert.
- Core-Tests, Qt-Offscreen und Windows-Build als Gate.

## Nächster abgeschlossener Arbeitsschritt: M11c Teil 3

1. Legacy-AnalysisResult-Clips auf explizite Nutzeraktion in den
   Spurplan übernehmen; Quelle und Zeitbereiche validieren.
2. Idempotenz/Deduplizierung über stabilen Metadatenbezug,
   ohne manuelle Spurelemente zu überschreiben.
3. Gesperrte Spuren und bestehende Projektstände unverändert respektieren.
4. Bei unerwarteten Daten und Schreibfehlern Fail-Closed / atomische
   Speicherung, Core- und Qt-Tests vor der Umsetzung.
5. Danach M11c Teil 4: Proxies für 6h-VOD, Rückabbildung exakter Quellzeiten.

## Nicht behaupten

Keine Mehrspur-Abmischung, kein exportgetreuer Renderer vor M12.
Keine reale Windows-11-Abnahme oder 6h-Messung ohne Messbeleg.
