# StreamClipper 0.4 (experimenteller Export)

**Lokale Windows-App für Gaming-/Twitch-Highlights mit optionalen eingebrannten Untertiteln und dynamischem 16:9-/9:16-Export.**

Das ist ein *funktionsfähiger MVP*, noch kein vollständig KI-gestützter Viral-Clip-Generator.
Der Baseline-Analyzer benutzt RMS-Lautstärkespitzen als messbare Heuristik. Der optionale
0.2-Modus ergänzt lokale Sprache und Bildähnlichkeit. Ein hoher Score
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

**Anmerkung:** Der CLI-Export überschreibt niemals vorhandene Dateien; bei
Namenskonflikten wird automatisch ein nummerierter freier Name verwendet.

## Windows EXE über GitHub Actions

Der Workflow **Windows portable build** läuft bei Pull Requests automatisch und
kann unter **Actions** mit `Run workflow` zusätzlich manuell gestartet werden. Nach erfolgreichem Build
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
.github/workflows/build-windows.yml    Windows-Build auf PRs und manuell
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
- Ein laufender FFmpeg-Export ist nun auch während des Encodings abbrechbar; die
  GUI zeigt den Clipfortschritt an. Die Ausgabe wird zuerst als `.partial.mp4`
  in einem temporären Unterordner erzeugt, geprüft und erst danach unter einem
  freien Namen atomar veröffentlicht. Beim Abbruch wird die temporäre Datei
  entfernt. Auf Dateisystemen ohne atomare Hardlink-Unterstützung kann unter
  Linux/macOS der Export mit einer verständlichen Fehlermeldung scheitern.
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

## Experimenteller Gaming-/Sprachmodus (0.2, lokal)

Die Standardanalyse funktioniert weiterhin **ohne KI-Modelle**. Für zusätzliches
Sprachverständnis und Bildhinweise ist die Windows-**Python**-Installation mit
optionalen Bibliotheken erforderlich. Der automatisch erzeugte portable
Windows-Build enthält diese großen KI-Bibliotheken und Modellgewichte **noch
nicht**. Dafür ist ein separates Packaging-Arbeitspaket vorgesehen.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[gui,dev,speech,vision,models]"
# Einmalig, mit Internetverbindung, bewusst vom Nutzer auszulösen:
python scripts/setup_local_models.py --which both
# Danach auch ohne Internetverbindung:
python -m streamclipper
```

Die zwei neuen Checkboxen der GUI aktivieren optional **Sprache (Whisper)**
und **Spielbilder (CLIP)**. Die vorgegebenen Modellpfade werden nach dem Setup
automatisch gefunden. Alternativ einzelne lokale Modellverzeichnisse wählen.
Große KI-Modelle benötigen mehr Arbeitsspeicher und Zeit als der reine Audio-MVP;
GPU-Ausführung wird nach Verfügbarkeit ausgewählt, aber nicht garantiert.

Auch über die CLI nutzbar:

```powershell
streamclipper-cli analyze "C:\Videos\Gaming.mkv" --speech-model "$PWD\data\models\whisper-small" --vision-model "$PWD\data\models\clip-vit-base-patch32" --max-visual-frames 180
```

**Was die Scores bedeuten:** Das Ergebnis ist eine **nicht kalibrierte,
erklärbare Priorisierung** von Hinweisen, ausdrücklich **keine** verlässliche
Unfallerkennung, Emotionserkennung, Viralitätswahrscheinlichkeit oder
TikTok-Empfehlung. Whisper kann Worte falsch erkennen; die Reaktionssuche nutzt
zunächst deutsche/englische Formulierungen. CLIP vergleicht einzelne
Screenshot-Ähnlichkeiten mit neutralen und aktionsbezogenen Beschreibungen.
Eine visuelle Ähnlichkeit ist **kein Beweis**, dass wirklich ein Unfall oder
eine Verfolgungsjagd stattfand. Standardmäßig werden bis zu 180
über die gesamte Aufnahmedauer verteilte Bildstichproben per FFmpeg-Seeking
klassifiziert; kurze Ereignisse können deshalb verpasst werden.

Das Analyseprogramm öffnet **keine Netzwerkverbindung** und lädt **keine
Modellgewichte automatisch**. Nur das ausdrücklich gestartete Setup-Skript
benötigt Internet und lädt Modelle von Hugging Face. Gewichte sind **nicht
Teil des Apache-2.0-Repositories** und unterliegen ihren jeweiligen
Lizenzbedingungen. Die Textauszüge aus dem Transkript landen im lokalen
JSON-Bericht; solche Berichte nicht unbedacht öffentlich teilen.

**Abnahmegrenze:** Unit-/synthetische Integrationstests verwenden keine
gekauften oder privaten Gameplay-Dateien und keine echten Modellgewichte.
Ein Funktions- und Qualitätsvergleich mit realen Windows-11-Gaming-Aufnahmen
sowie das Packaging der KI-Modelle sind noch offen.

## Alle StreamClipper-Daten im eigenen Ordner (ab 0.2.1)

**Empfohlen für Windows:** Das Projekt z. B. nach `D:\StreamClipper` entpacken
und einmalig **`setup_windows.bat`** doppelklicken. Das Skript erstellt `.venv`,
installiert GUI und beide optionalen KI-Bibliotheken und lädt **nach ausdrücklichem
Start des Setups** die beiden Modelle. Danach startet **`run_windows.bat`** die App.
Python 3.12 und FFmpeg/FFprobe müssen weiterhin separat installiert sein.

Alle vom Setup und StreamClipper verwalteten Dateien befinden sich im Projekt:

```text
D:\StreamClipper\
  .venv\                      Python-Pakete
  data\models\               Whisper- und CLIP-Modellgewichte
  data\cache\                Hugging Face, PyTorch, Pip, CUDA-Cache usw.
  data\tmp\                  temporäre Setup-/Analyse-Dateien
  setup_windows.bat           einmaliges Setup inklusive KI-Modellen
  run_windows.bat             App starten
```

Die Pfade werden automatisch aus dem Verzeichnis ermittelt, in dem das Projekt
liegt; bei Umzug des Ordners werden sie beim nächsten Start neu gesetzt. Die
Umgebungsvariablen werden **nur innerhalb des jeweiligen Prozesses** geändert,
nicht dauerhaft in den Windows-Einstellungen. Dies gilt auch, wenn du die
GUI direkt per `.venv\Scripts\python.exe -m streamclipper` startest oder die
Modellinstallation direkt ausführst.

**Nicht enthalten:** separat installiertes Python/FFmpeg, Windows-Protokolle,
bereits existierende externe Caches früherer Installationen oder Videoexporte,
die du bewusst außerhalb von `D:\StreamClipper` speicherst. Ein früherer
Hugging-Face-Cache unter `%USERPROFILE%\.cache\huggingface` oder
`%LOCALAPPDATA%` wird **nicht** automatisch gelöscht. Einmal bereits anderswo
installierte Python-Pakete werden ebenfalls nicht entfernt.

Wenn die KI-Bibliotheken bereits in `.venv` installiert sind, reicht:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_models.py --which both
.\.venv\Scripts\python.exe -m streamclipper
```

Die Modelle landen standardmäßig in `data\models` innerhalb des entpackten
Projektordners; eine manuelle `--directory`-Angabe ist nicht mehr nötig.

## Vollständige automatische Transkription (ab 0.3.0)

Beim **Highlights analysieren** die Checkbox **„Sprache + Transkript (lokales Whisper)“**
aktivieren und den vorbereiteten Whisper-Modellordner auswählen (bei portablem Setup
gewöhnlich `data/models/whisper-small`). StreamClipper erkennt die komplette
Tonspur, zeigt im Reiter **Transkript** alle erkannten Sätze mit Start-/Endzeit
an und springt per Doppelklick an die entsprechende Videostelle. Die Sprache
wird für Highlight-Hinweise zugleich genutzt; **Whisper läuft dafür nur einmal**.
Über **Transkript speichern (SRT/TXT/VTT)** kann der Text exportiert werden.

Eine reine Transkription **ohne zusätzliche Highlight- oder CLIP-Analyse** ist
über die Kommandozeile möglich:

```powershell
.\.venv\Scripts\python.exe -m streamclipper.cli transcribe "D:\Videos\Gaming.mkv"
# Erstellt Gaming.transkript.srt und Gaming.transkript.txt neben dem Video.
# Individuelles Ziel (nur ein Format):
.\.venv\Scripts\python.exe -m streamclipper.cli transcribe "D:\Videos\Gaming.mkv" --output "D:\StreamClipper\data\transcripts\Gaming.vtt"
```

**Hinweise:** Dateien werden nicht überschrieben; bei vorhandenem Dateinamen
ein anderes Ziel wählen. SRT/VTT sind **separate Untertiteldateien**, noch
nicht ins exportierte MP4 eingebrannt. Die Zeitstempel beziehen sich auf das
Originalvideo. Sprecherzuordnung und wortgenaue Synchronisierung sind nicht
enthalten. Streaming-/OBS-Aufnahmen mit mehreren Audiospuren werden für Whisper
noch nicht separat gemischt; dabei entscheidet die von faster-whisper verwendete
Audioauswahl. Whisper kann insbesondere bei Spielemusik und überlagerten
Dialogen falsch transkribieren. Originalvideos bleiben unverändert.

Der Transkripttext wird bei einer gespeicherten Highlight-JSON-Analyse auch
im JSON hinterlegt; dieses JSON gegebenenfalls vertraulich behandeln.

## 0.4 – Untertitel im Bild und dynamischer Kameraausschnitt (experimentell)

Whisper wird während der Analyse **einmal** ausgeführt und erzeugt zeitgestempelte
Textabschnitte im Analyseergebnis. Wähle in der GUI **„Sprache + Transkript
(lokales Whisper)“**, starte die Analyse und anschließend bei Export
**„Untertitel direkt ins Video“**. Die fertige MP4 enthält die Untertitel
fest eingebrannt – TikTok braucht keine separate SRT/TXT-Datei.

Neue Exportmodi (GUI und CLI):

- **smart16**: 16:9 (standardmäßig 1920×1080), sanfter digitaler Zoom (ca. 18 %)
  mit gleitendem Ausschnitt anhand lokaler Bildbewegungen.
- **smart9**: 9:16 (standardmäßig 1080×1920), beweglicher Hochformat-Ausschnitt.
- **blur/crop**: unveränderte bestehende feste Hochformat-Layouts.

Der Tracking-Algorithmus dekodiert **nur den ausgewählten Clip**, mit
kleinen Graustufenbildern und maximal 120 Samples (standardmäßig 2 fps).
Er folgt einem geglätteten Schwerpunkt lokaler Bewegungsunterschiede. Dies
ist **keine** Objekt-/Gesichts-/Spielerkennung: bei Kamerawechseln, HUD,
Explosionen oder sehr schnellen Bewegungen kann der Ausschnitt falsch liegen.
Insbesondere wird kein Motiv garantiert über die ganze Szene verfolgt.

Die Untertitel sind lesbar mit weißer Schrift, schwarzer Kontur und
sicherer Behandlung von Sonderzeichen. Der Zwischenschritt ist eine temporäre
ASS-Datei, die nach dem Rendern entfernt wird. Bei Abbruch oder Fehler wird
keine teilweise gerenderte finale MP4 veröffentlicht. Externe FFmpeg-Builds
müssen den **ass/libass-Filter** enthalten. Die von Gyan gebaute Windows
Full-Version enthält ihn üblicherweise; mit `ffmpeg -filters` prüfen.

**CLI-Beispiel mit vorhandener Analyse-JSON** (nicht noch einmal transkribieren):

```powershell
.\.venv\Scripts\python.exe -m streamclipper.cli export "D:\Videos\gameplay.mkv" `
  --start 120 --end 145 --mode smart16 `
  --transcript-json "D:\Videos\gameplay.highlights.json" --burn-subtitles `
  --output "D:\Clips\highlight.mp4"
```

Die SRT/TXT/VTT-Exportmöglichkeit bleibt freiwillig, ist für den fertigen
Clip aber **nicht** erforderlich. Der Vorschaubereich spielt weiterhin die
Originalaufnahme; eine Vorschau **mit** eingebrannten Untertiteln und
Auto-Reframing kann derzeit erst nach dem Export betrachtet werden.

**Tests:** synthetische FFmpeg-Integration für 16:9 und 9:16, Untertitel,
Unicode-Namen, Datensicherheit; echte Whisper-Inferenz, echte 3+-Stunden-
OBS-Aufnahmen und die Windows-GUI sind noch separat abzunehmen.

## Fehlerbehebung: Whisper / PyAV `metadata_errors`

Bei der Fehlermeldung `open() got an unexpected keyword argument 'metadata_errors'`
sind `faster-whisper` und die installierte Version von PyAV nicht kompatibel.
StreamClipper schließt ab sofort PyAV 18+ über das optionale `speech`-Extra aus.
Auf bereits eingerichteten Windows-Installationen lässt sich das ohne Löschen
von Modellen, Videos oder `.venv` reparieren:

```powershell
.\.venv\Scripts\python.exe -m pip install "av==17.1.0"
.\.venv\Scripts\python.exe -m pip show av
```

Das installierte FFmpeg-Programm wird dadurch nicht verändert: PyAV ist eine
separate Python-Abhängigkeit von Whisper innerhalb der lokalen `.venv`.
