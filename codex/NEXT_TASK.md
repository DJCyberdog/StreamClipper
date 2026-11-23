# NEXT_TASK – M12b: Gemeinsamer Mehrspur-Rendervertrag

**Stack:** M10.5 #31 → M11a #34 → M11b #36 →
M11c Checkpoints #37 → M11c Undo #38 →
M11c Highlight Import #39 → M11c Proxy #40 →
HF-UX #41 → M12a single-source Render Preview Draft #42.
Keine unfreigegebenen Merges nach `main`.

## M12a (im Draft, Review-/Abnahmezustand separat dokumentieren)

- `RenderRequest` ist das eine unveränderliche Quellclip-/Modus-/
  Untertitel- und Zeitfensterobjekt für tatsächlichen MP4-Export
  **und** 20-Sekunden-Render-Vorschau.
- Beide nutzen denselben `export_clip`-FFmpeg-Boundary; keine
  approximative UI-Filtervorschau als „exportgetreu“ ausgeben.
- QThread, untere Fortschrittsleiste, Abbruch, separates Player-Fenster
  und temporäre MP4, die nach Ansicht gelöscht wird.
- Keine Modelltranskription, Proxy-Konvertierung oder Spuränderungen
  für diesen Vorschauklick; Original bleibt unangetastet.
- Decoded-Frame-Parität inkl. eingebrannter ASS-Untertitel,
  Qt-Offscreen, Linux-Pytest/compileall und Windows-Build prüfen.

## M12b: Nächste abgegrenzte Entwicklung

1. Versioniertes `RenderGraph`-Schema für **wirkliche** Timeline-
   Spuren aus M11: Gameplay-Video, Clipzeiten, unabhängige Mik-/Musik-
   Audiospuren, Mute, Captions, Grafiken; Quell- und Zielzeit explizit.
2. Deterministische Reihenfolge, Track-Lock-/Mute-Semantik,
   Timeline-Lücken, Überlappung, A/V-PTS, Audiopegel, Clip-Speed
   und valide/ungültige Quellreferenzen fail-closed modellieren.
3. Erst dann denselben Graph sowohl im echten Mehrspur-Preview als auch
   im Export realisieren, mit Golden-Frame- und Audiovergleich;
   keinen stillen Unterschied zwischen „Preview“ und „Export“.
4. Danach M12c NVENC/H.264+HEVC/CPU-Fallback, M12d Export-QA,
   M12e Renderqueue/Recovery, reales Windows-11-End-to-End.
5. Reale 6h-VOD-Messungen, Windows 1366×768/1080p UX und
   20s-Renderpreview-GPU/RAM-/Audio- und Cancel-Tests abnehmen.

## Nicht behaupten

M12 nicht abgeschlossen. Kein Mehrspur-WYSIWYG, keine externe
Cloud-Abhängigkeit, keine automatische Veröffentlichung, kein
Projekt-Merge ohne explizite Owner-Freigabe.
