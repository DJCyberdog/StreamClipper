# Codex-Repository-Anweisungen

## Produktvertrag

Baue **StreamClipper**, eine offline-first Windows-Desktop-App für lokale
Gaming-, OBS- und Twitch-Aufnahmen. Ein Clip wird **niemals automatisch**
veröffentlicht. Die erste Version muss deterministisch testbar sein.

Sprache der UI und der nutzernahen Dokumentation: **Deutsch**.
Codebezeichner, Modulnamen und Tests: Englisch. Python 3.12 primär.

## Architekturregeln

1. Schichten strikt trennen: `models` <- `analyze` / `media` <- `gui` / `cli`.
   Core darf weder PySide6 noch Netzwerkfunktionen importieren.
2. FFmpeg-Aufrufe in `media.py` kapseln. Nie `shell=True`; Eingabepfade gelten
   als untrusted. Rohvideo nicht überschreiben; Zielpfad-Kollisionen abfangen.
3. Alle Detektorergebnisse sind Evidenz, **keine** Halluzination von
   Gameplay-Ereignissen. Audiopeaks nicht als Explosion/Unfall etikettieren.
4. GUI nicht blockieren; langlaufende Jobs auf Worker-Threads. Fehler und
   Abbruchzustände sichtbar machen.
5. Erweiterungen für GPU-Modelle optional und lazy-load; eine Basisversion
   muss ohne CUDA, Cloud-API und Modell-Download arbeiten.
6. Keine API-Keys, personenbezogenen Pfade oder echten privaten VODs committen.
7. Features in kleinen PRs. Keine umfangreichen Framework-Wechsel ohne
   ADR in `docs/`.

## Codex-Arbeitsfolge

1. `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` lesen.
2. Bearbeite **genau eine** Aufgabe pro Branch. Starte bei
   `codex/NEXT_TASK.md`, solange nichts anderes beauftragt ist.
3. Erstelle reproduzierbaren Test, der vor dem Fix/Feature scheitert.
4. Implementiere kleinstmögliche Änderung, inklusive Edge Cases.
5. `python -m pytest -q`, `python -m compileall -q src` ausführen.
6. Dokumentiere Trade-offs und noch nicht verifizierte Windows-Fälle.
7. Draft-PR gegen `main` erstellen; ohne explizite Freigabe nicht mergen.

## Definition of Done

- Akzeptanzkriterien im Issue erfüllt und Tests grün.
- Kein zerstörerischer Dateizugriff.
- Fehlermeldungen bei Codec-/FFmpeg-/Rechteproblemen verständlich.
- Release-Kompatibilität mit Windows-Workflow berücksichtigt.
- `README.md` und Roadmap-Status bei funktionaler Änderung aktualisiert.
- Prüfung an echtem Windows-Zielsystem **nicht** ohne Evidenz als bestanden markieren.

## Build

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m compileall -q src
```

GUI-Entwicklung: `pip install -e '.[gui,dev]'`; dann `python -m streamclipper`.
Windows-Build: `.github/workflows/build-windows.yml`.
