# StreamClipper 0.1

**Lokale Windows-App für Gaming-/Twitch-Highlights mit vertikalem TikTok-Export.**

Das ist ein *funktionsfähiger MVP*, noch kein vollständig KI-gestützter Viral-Clip-Generator.
Der erste Analyzer benutzt RMS-Lautstärkespitzen als messbare Heuristik. Ein hoher Score
bedeutet **nicht**, dass die Szene spannend, lustig oder viral ist. Der Analyzer ist
modular für spätere Sprache-, Szenen- und Gameplay-Event-Detektoren angelegt.

## Funktionen

- Videoimport: MP4, MKV, MOV, WEBM und andere Formate, die FFmpeg unterstützt
- Analyse des ersten Audiostreams in ~1-Sekunden-Fenstern, speicherschonend auch bei langen Aufnahmen
- Automatische, zeitlich überlappungsfreie Highlight-Kandidaten mit Start, Ende, relativem Score und Begründung
- Falls keine Tonspur vorliegt: klar gekennzeichnete Zeitstichproben statt erfundener Highlight-Erkennung
- Videovorschau mit Qt Multimedia und Sprung zum markierten Clip
- 9:16-Export als H.264/AAC MP4 (1080 × 1920, wenn Quelle und Decoder es zulassen)
- Zwei Layouts: `blur` (vollständiges Gameplay vor unscharfem Hintergrund), `crop` (mittiger Ausschnitt)
- Export eines einzelnen oder aller Kandidaten; Dateinamen werden nicht überschrieben
- JSON-Analysebericht zur Nachbearbeitung und späteren Integration weiterer Detektoren
- Kommandozeile für reproduzierbare Tests und Automatisierung

## Windows-Start (Quellcode)

1. Python **3.12 (64-bit)** installieren: https://www.python.org/downloads/windows/
2. FFmpeg + FFprobe installieren: https://ffmpeg.org/download.html
   - Beide `.exe`-Dateien müssen im `PATH` liegen, oder du setzt die Umgebungsvariable
     `STREAMCLIPPER_FFMPEG_DIR` auf den Ordner mit `ffmpeg.exe` und `ffprobe.exe`.
   - Bei der portablen EXE reicht es auch, beide Dateien neben `StreamClipper.exe` zu legen.
3. Das Projekt entpacken und **`run_windows.bat` doppelklicken**.
4. Video öffnen, Cliplänge setzen, **Highlights analysieren**, Vorschlag anklicken,
   Vorschau abspielen, Exportmodus wählen und MP4 exportieren.

`run_windows.bat` legt beim ersten Start eine virtuelle Python-Umgebung `.venv` an
und installiert PySide6. Für den ersten Setup-Lauf wird deshalb Internet benötigt.
Die spätere Videoanalyse läuft lokal, ohne Video-Upload oder API-Schlüssel.

### Manuelle Installation

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[gui,dev]"
.venv\Scripts\python.exe -m streamclipper
```

### Ohne grafische Oberfläche (CLI)

```powershell
.venv\Scripts\python.exe -m streamclipper.cli analyze "D:\Videos\aufnahme.mkv" --clip-seconds 25 --max-clips 8
.venv\Scripts\python.exe -m streamclipper.cli export "D:\Videos\aufnahme.mkv" --start 65 --end 90 --mode blur --output "D:\Clips\clip.mp4"
```

**Anmerkung:** Der CLI-Export überschreibt ebenfalls keine bereits vorhandene Zieldatei;
bei gleichem Namen einen neuen Pfad angeben.

## Windows EXE über GitHub Actions

Nach dem ersten Push in ein neues GitHub-Repository im Reiter **Actions** den Workflow
**Windows portable build** mit `Run workflow` manuell starten. Nach erfolgreichem Build
wird das ZIP-Artefakt `StreamClipper-windows-portable` bereitgestellt. Darin ist die
Windows-App mit PySide6 enthalten, **nicht** FFmpeg/FFprobe. Die beiden Programme
müssen extern verfügbar sein (siehe Anleitung).

Es ist bewusst eine portable App, **kein** MSI-Installer und kein signiertes Release.
Noch nicht auf einer echten Windows-Installation oder mit mehrstündigem OBS-Material getestet.

## Projektstruktur

```text
src/streamclipper/models.py   Datenschnittstellen und JSON-Bericht
src/streamclipper/media.py    FFprobe, Audio-Decoding, Export via FFmpeg
src/streamclipper/analyze.py  deterministischer Audio-Highlight-Detektor
src/streamclipper/gui.py      Windows-GUI, Hintergrundthreads, Video-Vorschau
src/streamclipper/cli.py      testbare Kommandozeile
AGENTS.md                    verbindliche Codex-Projektregeln
codex/NEXT_TASK.md           nächster klar begrenzter Entwicklungsauftrag
.github/workflows/ci.yml    Tests in Pull Requests
.github/workflows/build-windows.yml    manuell baubare portable Windows-App
tests/                       schnelle Unit- und echte FFmpeg-Integrationstests
```

## Architektur und Entwicklung

Siehe [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/ROADMAP.md](docs/ROADMAP.md) und [AGENTS.md](AGENTS.md).

## Grenzen in 0.1

- Keine Spielgeschehnis-Erkennung, kein Sprachverständnis, keine automatisch generierten Untertitel.
- Keine Twitch-Downloadfunktion: lokale Aufnahmen oder selbst heruntergeladene VODs importieren.
- Die Audiopipeline nutzt zunächst **nur die erste** Audiospur. Getrennte OBS-Spuren folgen später.
- Rechenzeit wächst mit der Dauer der Aufnahme. Video-Decoding geschieht erst beim Export;
  die Analyse decodiert nur die Audiospur, ohne großen RAM-Puffer.
- Vorhandene Clips werden nicht automatisch verworfen oder veröffentlicht; du entscheidest.
- Während eines einzelnen laufenden FFmpeg-Exports wird ein Abbruch nach Abschluss des
  aktuellen Clips wirksam; sofortiger Prozessabbruch ist eine Folgeaufgabe.
- Vorschau ist Originalformat, nicht bereits gerendertes vertikales TikTok-Layout.
- TikTok-spezifische Anforderungen können sich ändern. 1080 × 1920 H.264/AAC ist
  eine verbreitete Wahl, aber kein Versprechen einer garantierten Plattformakzeptanz.

## Testen

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

Die Integrationstests erzeugen synthetisches Material und rufen echte FFmpeg-Programme auf.
Keine Drittvideos, Social-Media-Konten oder Cloud-Dienste nötig.

## Lizenz

Quellcode unter Apache License 2.0 (siehe `LICENSE`). FFmpeg, FFprobe, Qt/PySide6 und sonstige Bibliotheken behalten ihre
eigenen Lizenzbedingungen. Bei einer späteren Distribution inklusive FFmpeg deren
Lizenzpflichten gesondert prüfen.
