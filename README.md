# StreamClipper 0.4 (experimenteller Export)

> **Verbindliche Planung:** [ROADMAP.md](ROADMAP.md) – 60 Features, gebündelte M10.5–M20, 58 umzusetzende S–D-Funktionen vor Release 1.0. Dieser Code bleibt experimentell; CI ersetzt keinen Windows-Praxistest.

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

## Lokale GPU-Beschleunigung für Whisper unter Windows

Faster-Whisper/CTranslate2 benötigt NVIDIA CUDA-12-cuBLAS, cuDNN 9 und
CUDA-Runtime-DLLs. Der NVIDIA-Treiber allein reicht nicht. Statt eines
systemweiten CUDA-Toolkits kann StreamClipper die von NVIDIA veröffentlichten
Windows-Python-Wheels **innerhalb der bestehenden Projekt-.venv** installieren.

1. StreamClipper beenden. Für die erste Prüfung am besten eine kurze Aufnahme
   verwenden; die mehrstündige Analyse ist dafür nicht erforderlich.
2. **`setup_gpu_windows.bat`** im StreamClipper-Ordner ausführen.
3. Das Skript lädt die in `requirements-gpu-windows.txt` dokumentierten Pakete
   und startet `scripts/check_gpu_runtime.py` mit einem echten kurzen
   Whisper-CUDA-Inferenztest. Modellgewichte werden nur lokal gelesen.
4. Bei `ERFOLG` StreamClipper normal mit `run_windows.bat` starten.

Die NVIDIA-Bibliotheken liegen unter
`.venv/Lib/site-packages/nvidia/{cublas,cudnn,cuda_runtime}/bin`.
StreamClipper macht diese Ordner beim Start über die **nur für den laufenden
Prozess gültige** DLL-Suche verfügbar; es ändert keine Registry und keine
permanenten Windows-PATH-Einstellungen. Downloads und Pip-Caches liegen
wie bisher im Projektordner `data/cache`.

**Größe:** Die optionalen Pakete benötigen zusammen deutlich mehr als 1 GB
für Download und Installation. Internet wird nur für die einmalige
Installation benötigt. Python und der NVIDIA-Grafiktreiber bleiben separat
installiert; eine spätere Löschung von `D:\StreamClipper` entfernt die
zusätzlichen Wheel-DLLs mit der `.venv`.

Der GPU-Selbsttest nutzt synthetisches Audio und erzwingt `device="cuda"`.
Die bestehende automatische CPU-Ausweichlösung bleibt unverändert. Ein
funktionierender Test bestätigt nur die CUDA-Whisper-Pipeline; die Performance
bei mehrstündigen Aufnahmen und CLIP/PyTorch-GPU-Beschleunigung sind davon
**nicht** automatisch nachgewiesen.

Offizielle Referenzen:
- https://github.com/SYSTRAN/faster-whisper#gpu
- https://docs.nvidia.com/deeplearning/cudnn/installation/latest/windows.html
- https://pypi.org/project/nvidia-cublas-cu12/
- https://pypi.org/project/nvidia-cudnn-cu12/


## Untertitel sind zu früh oder zu spät?

Im Export-Bereich unter **Untertitelversatz** lässt sich die Einblendung verschieben.
Der GUI-Standardwert beträgt **+0,4 s** (später). Ein negativer Wert blendet
Text früher ein. Die Tonspur und Videospur bleiben unverändert; ein erneutes
Transkribieren mit Whisper ist nicht nötig. Die Einstellung beeinflusst nur
fest eingebrannte Untertitel beim neuen MP4-Export.

Bei CLI-Exports lässt sich dieselbe Korrektur manuell setzen:

```powershell
.\.venv\Scripts\python.exe -m streamclipper.cli export "D:\Videos\gameplay.mp4" `
  --start 120 --end 145 --mode smart16 `
  --transcript-json "D:\Videos\gameplay.highlights.json" `
  --burn-subtitles --subtitle-offset 0.4 `
  --output "D:\Clips\highlight.mp4"
```

Hinweis: Whisper liefert Segment- statt präzise Wort-Zeitstempel. Bei
stark variierendem Sprechtempo kann ein einheitlicher Versatz nicht alle
Wörter korrekt ausrichten. Spätere Versionen können Wort-Alignment ergänzen.

## Benutzerfreundlicher Transkript-Editor (neue Bedienung)

Im Tab **Transkript bearbeiten** wird eine Zeile durch einfaches Anklicken
markiert. Die Vorschau springt zur passenden Stelle, während die Untertitel-
zeile in einem großen Textfeld unterhalb der Liste bearbeitet werden kann.
Mit **Stelle anhören** läuft die Wiedergabe nur bis zum Ende des markierten
Sprachabschnitts. **Vorheriger/Nächster** navigieren zwischen Textabschnitten.
**Zum markierten Highlight** findet passende Sprachabschnitte direkt aus der
Highlight-Liste; eine lange Aufnahme muss nicht manuell durchsucht werden.

**Beginn** und **Ende** können als `HH:MM:SS.mmm` eingegeben oder über
`−0,1`/`+0,1` verschoben werden. **Korrektur übernehmen** (auch `Strg+Enter`)
überträgt Text und Zeiten gemeinsam in die interne Analyse, ohne neu zu
transkribieren. Beim Zeilenwechsel werden gültige offene Korrekturen ebenfalls
übernommen. Ungültige Zeitangaben verhindern das Wegnavigieren, statt
unbemerkt kaputte Untertitel zu erzeugen. **Änderungen verwerfen** stellt
für die gerade geöffnete Zeile den letzten übernommenen Stand wieder her.

**Projekt speichern** (auch `Strg+S`) sichert alle Korrekturen als JSON.
Nach dem nächsten Start dieselbe Aufnahme öffnen und **Analyse laden (JSON)**
wählen; die Erkennung durch Whisper wird dadurch nicht erneut gestartet.
Der anschließende MP4-Export verwendet das korrigierte Transkript unmittelbar.
Originaldateien und die ursprüngliche Audio-/Videospur werden nicht geändert.


## Highlights manuell markieren (ohne KI)

Im Reiter **Highlights** kannst du eine Aufnahme abspielen und jederzeit
**★ Highlight ab hier** auswählen. Der Clip beginnt an der Wiedergabeposition
und nutzt die im Fenster eingestellte Cliplänge (standardmäßig 25 Sekunden).
Alternativ den Clipbeginn mit **Start setzen**, das Ende mit **Ende setzen**
markieren und über **Bereich hinzufügen** speichern. Ein optionaler Name
(z. B. „LKW-Unfall“) wird mitgespeichert.

Manuell markierte Clips sind in der Highlight-Tabelle als **★ Manuell**
kenntlich und erhalten **keinen künstlichen KI-Score**. Sie lassen sich
wie automatische Kandidaten vorhören, einzeln exportieren, mit allen anderen
Clips exportieren oder gezielt entfernen. Für diesen Ablauf werden weder
Whisper noch CLIP benötigt. Ein späterer KI-Analysedurchlauf bewahrt die
vorhandenen manuellen Markierungen.

Mit **Analyse als JSON speichern** werden die Marker zusammen mit den
anderen Projektdaten gesichert. Beim erneuten Laden über **Analyse laden
(JSON)** sind sie wieder verfügbar. Die ursprüngliche Aufnahme wird nie
verändert. Zuverlässigkeit mit sehr langen Aufnahmen muss noch unter
Windows getestet werden.


## Öffentliche Twitch-VODs per Video-URL importieren (optional)

Im Hauptfenster auf **Twitch-VOD importieren** klicken, eine URL wie
`https://www.twitch.tv/videos/1234567890` einfügen und den Speicherordner
wählen. StreamClipper lädt das verfügbare, öffentliche **archivierte VOD**
per `yt-dlp` herunter und lädt die fertige Datei zur Bearbeitung. Der
Import läuft in einem Hintergrundthread mit Fortschrittsanzeige und Abbruch.
Bei Verbindungsabbruch bleiben `.part`-Dateien erhalten; beim erneuten Import
über dieselbe URL in denselben Ordner versucht `yt-dlp` die Fortsetzung.

Die Video-Dateien werden im gewählten Ordner gespeichert, standardmäßig
wird `data/imports/` vorgeschlagen. Für drei bis sechs Stunden VOD können
mehrere Gigabyte freier Speicherplatz erforderlich sein. Import ist ein
**ausdrücklicher Online-Vorgang**; lokale Videoanalyse und Export bleiben
weiterhin offline. Live-Streams, Twitch-Clips, Sub-only/VODs mit
Anmeldung, gelöschte/abgelaufene VODs und automatischer Twitch-Kanal-Import
sind **noch nicht** implementiert. Keine Zugangsbeschränkungen umgehen.

Für eine vorhandene `.venv` genügt ein Doppelklick auf **`setup_twitch_windows.bat`**.
Alternativ einmal das optionale Paket installieren:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[twitch]"
```

Eine frische Ausführung von `setup_windows.bat` installiert `yt-dlp` künftig
mit; der Import selbst lädt sonst keine Python-Abhängigkeiten nach.
Twitch bietet einen offiziellen Download eigener VODs über den Video Producer;
`yt-dlp` ist ein unabhängiges Drittanbieterwerkzeug, dessen Funktion sich
bei Änderungen an Twitch jederzeit ändern kann.

## M6: Zoom-Timeline und Schnitt mit Untertitelvorschau (experimentell)

Im Hauptfenster liegt jetzt eine **Timeline** mit drei Spuren: Audio-Wellenform,
Highlight-Regionen und zeitgestempelte Whisper-Untertitel. Die Wellenform
wird unabhängig von KI in einem abbrechbaren FFmpeg-Hintergrundthread erstellt.
Sie besteht aus maximal 8.192 Amplitudenpunkten, selbst bei sechs Stunden
Aufnahme – es werden keine Roh-Audiosamples im Arbeitsspeicher gesammelt.

**Bedienung:**

- **Klick auf die Timeline** springt zur Stelle im Video; rote Linie = Abspielkopf.
- **Gelbe IN-/OUT-Markierungen ziehen** verändert den Schnittbereich;
  **Umschalt + Ziehen** wählt einen neuen Bereich.
- **Zoom** (Gesamt bis 2880×) und der horizontale
  Scrollregler navigieren in langen Aufnahmen. IN/OUT können zusätzlich in
  Dezimalsekunden auf eine Millisekunde genau eingegeben werden; die Anzeige
  daneben nutzt HH:MM:SS.mmm.
- **▶ Auswahl abspielen** spielt nur die markierte Region.
- **★ Auswahl als Highlight** legt einen neuen manuellen Clip an;
  über **Ausgewählten Clip exportieren** wird er wie bisher gerendert.
- **✂ Markiertes Highlight trimmen** ändert ausschließlich den markierten
  manuellen Clip (KI-Vorschläge werden nicht verdeckt überschrieben).
- **Untertitel auf der unteren Timeline-Spur anklicken** wechselt zum
  vorhandenen Korrektureditor. In der Video-Vorschau erscheinen vereinfachte
  eingeblendete Textgruppen (je maximal acht Wörter) mit dem gewählten
  Untertitelversatz. Korrekturen sind ohne erneute Whisper-Inferenz sichtbar.

**Grenzen:** Die Live-Vorschau zeigt das Originalbild mit einer vereinfachten
Untertitel-Überlagerung; das finale ASS-Fontlayout und die dynamische
16:9-/9:16-Kameraführung werden weiterhin **erst beim Export** gerendert.
Das ist ein erster Schnitt-Workflow, noch kein vollständiger Mehrspur-NLE:
kein Mehrclip-Arrangement, keine Übergänge/Keyframes und kein Undo-Stack.
Die Bedienung auf dem echten Windows-/NVIDIA-Zielrechner und sechs Stunden
reales Videomaterial sind noch separat zu verifizieren.


## M7: Wörter direkt im Highlight auf der Timeline korrigieren

**Neu:** Bei einer Whisper-Analyse werden jetzt mit `word_timestamps=True`
Wortzeitstempel erzeugt. Diese **Whisper-Schätzungen auf Wortebene** sind
präziser als eine gleichmäßige Verteilung ganzer Sätze, können aber ebenfalls
manuelle Korrekturen benötigen.

1. Video öffnen, mit Whisper analysieren oder eine gespeicherte JSON-Analyse
   laden. **Highlights** auswählen – die Timeline zoomt automatisch in den
   Bereich des Clips, auch bei sechs Stunden Laufzeit.
2. Die **untere Wortspur** enthält nur Wörter im ausgewählten Ausschnitt:
   violett = Whisper-Zeitstempel, gelb = aus älteren Transkripten nur
   **geschätzt**, türkis = aktuell ausgewähltes Wort.
3. Wort **anklicken**: Direkt unter der Timeline kannst du Text, Anfang und
   Ende in Sekunden auf drei Nachkommastellen verändern (Schritt 0,05 s).
   Mit **▶ Anhören** wird genau das Wort mit kurzem Vor-/Nachlauf abgespielt.
   **Wortkante ziehen** verschiebt Anfang oder Ende direkt per Maus, sofern
   die Wortbox breit genug ist. Für genaueres Ziehen stärker hineinzoomen.
4. **✓ Wort übernehmen** aktualisiert Untertitelvorschau, JSON-Analyse,
   SRT/VTT/TXT und den nächsten MP4-Export. **Strg+S** speichert die
   Korrekturen. Die ursprüngliche Video- und Audiodatei wird nicht geändert.

Neue automatische Wortzeitmarken erhältst du erst nach einer erneuten
Whisper-Analyse. **Alte Projekte bleiben vollständig ladbar:** Wenn bisher
nur Segment-Zeiten gespeichert wurden, zeigt die Timeline gelb markierte,
linear geschätzte Wortgrenzen an. Sie können manuell korrigiert werden,
ohne die ganze Aufnahme erneut transkribieren zu müssen.

Der MP4-Export zeigt jetzt bei echten Wortmarken **progressiv Wort für Wort**
innerhalb von Gruppen (bis acht Wörter), die Einblendung beginnt nicht vor
jeweiligem Wortbeginn. Ältere, unkorrigierte Segmenttranskripte verwenden
weiterhin die bisherige Näherung. Die Vorschau zeigt denselben Text und
dieselben Zeitmarken, aber noch nicht die exakt gerenderte ASS-Schrift und
Kameraführung des fertigen 9:16/16:9-Videos.

**Nicht Teil von M7:** unabhängige Wort-Sprechererkennung, automatisch
perfekte Wortausrichtung, Mehrspur-Compositing oder vollwertiger Undo-Stack.
Die Windows-/NVIDIA-Praxisabnahme und ein sechsstündiger Realfilm bleiben offen.


## M8 – intelligentere Gameplay-Hinweise (experimentell)

Aktiviere **Gameplay-Dynamik + CLIP (lokal)**. Die Analyse arbeitet jetzt in
zwei Stufen:

1. Ein FFmpeg-Durchlauf prüft den **zeitlichen Szenenverlauf** mit 2 niedrig
   aufgelösten Graustufenbildern pro Sekunde (96 × 54 Pixel). Der Vergleich
   erkennt auffällige Bewegungs-/Bildänderungsspitzen gegenüber der lokalen
   Bewegungsbasis. Dies kann beispielsweise von schnellen Fahrmanövern,
   Schnitten, HUD-Einblendungen oder Kollisionen stammen. **Es ist kein
   verlässlicher Nachweis einer Kollision.** Der Puffer ist konstant klein;
   maximal 360 Zeitfenster pro Aufnahme werden als Kandidaten behalten.
2. Die Bildprüfung mit lokalem **CLIP** verteilt ihre begrenzten Stichproben
   (standardmäßig bis zu 180 Bilder) über die gesamte Aufnahme, gewichtet
   ungewöhnliche Bildveränderungen, Sprachreaktionen und Audio-Peaks und
   prüft oft mehrere Frames nahe eines auffälligen Moments. Eine plausible
   semantische Ähnlichkeit gilt nur als **Indiz**, nie als sicheres Ereignis.

Zeitlich benachbarte Bild-, Sprach- und Audiobeobachtungen werden für einen
begründeten Highlight-Vorschlag kombiniert. Der **Score ist eine Heuristik**,
keine kalibrierte Trefferwahrscheinlichkeit. Gespeicherte manuelle Highlights
und die Wort-Transkripte werden wie bisher erhalten.

**Sechs Stunden:** Die Verarbeitung verbraucht keinen proportional steigenden
Videobild-Puffer. Es wird jedoch das gesamte Video zur Szenenanalyse
dekodiert; die Laufzeit hängt stark vom Codec, PC und gewähltem Modell ab.
Die Begrenzung auf 180 CLIP-Bilder kann kurze Ereignisse weiterhin übersehen.
Es gibt noch **keine** zuverlässige objekt- oder handlungsbasierte
GTA-VI-Klassifikation, kein trainiertes Crash-Modell und keinen vollständigen
Windows-Sechs-Stunden-Langlauftest.

Um wie zuvor nur Audio und Whisper zu analysieren, die Option
**Gameplay-Dynamik + CLIP** deaktivieren. Modelle werden während einer
Analyse weiterhin **nicht** online geladen.

## M9 – Objektspuren und alternative lokale Modelle (experimentell)

StreamClipper bietet nun **drei voneinander unabhängige Modellgruppen**:

| Gruppe | Verfügbare Presets | Bereits vorhandener Standard |
|---|---|---|
| Sprache | Whisper Tiny, Base, Small, Medium, Large-v3 Turbo, Large-v3 | Small |
| Bildhinweise | CLIP ViT-B/32, CLIP ViT-L/14 | ViT-B/32 |
| Objekte | DETR ResNet-50, RT-DETR R18 | Opt-in, zunächst deaktiviert |

Jedes Preset hat einen **eigenen Ordner** unter `data/models`, sodass die
ursprünglichen Whisper-Small- und CLIP-ViT-B/32-Gewichte unangetastet bleiben.
Ein Modell lässt sich über das Dropdown auswählen, ein eigener Modellordner
ist weiterhin möglich. **„Herunterladen“** fragt vor dem Online-Download
nach und führt ihn im GUI-Hintergrund aus. Ein bloßer Modellwechsel löst
weder Download noch Analyse aus. Wer lieber PowerShell verwendet:

```powershell
.\.venv\Scripts\python.exe scripts\setup_local_models.py --list
.\.venv\Scripts\python.exe scripts\setup_local_models.py --model whisper-large-v3-turbo
.\.venv\Scripts\python.exe scripts\setup_local_models.py --model clip-vit-large-patch14
.\.venv\Scripts\python.exe scripts\setup_local_models.py --model detr-resnet-50
```

Für die Analyse müssen die Gewichte vollständig installiert sein; ein
Preflight prüft die Dateien **vor** mehrstündiger Videoverarbeitung. Die
Analyse selbst fordert keine Modelle online nach (`local_files_only=True`).
Bei eigener/anderer Modellwahl bitte Kompatibilität, Lizenz und Leistungsbedarf
prüfen. Large und Turbo können sich bei Rauschen, Dialekt und Gaming-Vokabular
unterschiedlich schlagen; „größer“ ist kein Qualitätsversprechen.

### Was die Objektanalyse tatsächlich macht

Nach dem sequenziellen M8-Szenenscan untersucht das lokale DETR-Modell
standardmäßig **höchstens 90 gezielte Frames** rund um interessante Momente.
Es erkennt allgemeine COCO-Klassen wie *car*, *truck*, *person*, *motorcycle*,
*bus* oder *bicycle*. Ein eigener, deterministischer Tracker verbindet
Bounding-Boxes derselben Klasse in eng benachbarten Bildern. Nur wenn eine
**Objektspur über mehrere Frames** *und* eine nahe Szenenveränderung vorliegen,
erzeugt StreamClipper einen zusätzlichen Hinweis. Diese multimodalen
Begründungen erscheinen bei den Highlight-Vorschlägen und sind über die
Timeline bearbeitbar.

Derzeit ist es **kein** trainierter Crash-, Explosion-, Schuss- oder GTA-VI-
Handlungsdetektor. Der Tracker besitzt keine langfristig beständigen
Fahrzeugidentitäten, keine Geschwindigkeitskalibrierung und kann bei
Kameraschnitten oder Überdeckungen falsch zuordnen. Es handelt sich um
**sparse Objektspuren**, nicht um Tracking sämtlicher Frames einer
sechsstündigen Aufnahme. Die 2-FPS-Szenenprüfung dekodiert weiterhin das
vollständige Video, deshalb bleibt die Gesamtzeit abhängig vom Videocodec.

DETR ResNet-50 (`facebook/detr-resnet-50`) und RT-DETR R18
(`PekingU/rtdetr_r18vd`) sind über Hugging Face mit Apache-2.0-Lizenz
veröffentlicht. Das vermeidet für dieses optionale Modell eine neue
Ultralytics-AGPL-Abhängigkeit. Die jeweiligen Modellkarten und Drittanbieter-
Nutzungsbedingungen müssen vor der kommerziellen Veröffentlichung zusätzlich
geprüft werden.

CLI-Beispiel (alles lokal):

```powershell
.\.venv\Scripts\python.exe -m streamclipper.cli analyze "D:\Videos\GTA VI.mp4" `
 --speech-model ".\data\models\whisper-large-v3-turbo" `
 --vision-model ".\data\models\clip-vit-base-patch32" `
 --detector-model ".\data\models\detr-resnet-50" --max-object-frames 90
```

**Abnahmegrenzen:** Die deterministische Verarbeitung wurde mit künstlichen
Objekterkennungen und synthetischen FFmpeg-Videos getestet. Das tatsächliche
Laden großer DETR-Gewichte, GPU-Betrieb auf Windows 11 und die Fehlerquote
auf echten GTA-VI-Aufnahmen sind noch separat zu prüfen. Der Windows-
PyInstaller-Build enthält die optionalen schweren KI-Pakete weiterhin nicht.


## M10 – gepflegtes Highlight-Sprachlexikon (Deutsch und Englisch)

**Was Whisper macht:** Whisper transkribiert die Aufnahme weiterhin ganz normal.
Erst *danach* prüft die lokale Highlight-Analyse erkannte Sätze gegen ein
regelbasiertes, erklärbares Wörterbuch. Es handelt sich **nicht** um Training,
Selbstlernen oder eine Garantie für einen tatsächlichen Unfall/Spielmoment.

Im Hauptfenster auf **„Highlight-Wörter …“** klicken. Der Dialog zeigt zwei
Bereiche:

- **Standardliste:** Von StreamClipper gepflegte, unveränderliche Vorlagen für
  Überraschung, Reaktion, Lachen sowie Gefahr, Unfall, Kampf, Erfolg und
  Verfolgung. Neue Standardbegriffe kommen mit regulären Updates samt Tests.
- **Eigene Wörter:** Ausdruck eingeben, Kategorie und Priorität wählen, hinzufügen
  oder einen markierten Eintrag ersetzen. Eigene Regeln werden getrennt in
  `data/settings/highlight_words.json` gespeichert und durch Projekt-Updates
  nicht überschrieben. Sie gelten für die *nächste* Analyse, nicht rückwirkend.
  Ein eigener Eintrag mit demselben Wort kann die Priorität der Standardliste
  überschreiben.

**Priorität Hoch** erzeugt einen eigenständigen Sprachhinweis. **Mittel** und
**Niedrig** sind **Kontexthinweise**: Begriffe wie „Polizei“ oder „Crash“
erzeugen alleine kein neues Highlight. Erst zusammen mit einem Audio-Peak,
einer Bildveränderung, CLIP-/Objekthinweisen oder einer starken Sprachreaktion
werden sie bei der Bewertung berücksichtigt (Fenster ±5 Sekunden). Speech und
Speech-Kontext zählen nicht fälschlich als zwei unabhängige Modalitäten.

Nur vollständige Wörter/Wendungen werden erkannt; persönliche Eingaben sind
**keine regulären Ausdrücke** und können daher keine Regex-Befehle einschleusen.
Begrenzung: maximal 150 persönliche Wendungen mit je 2 bis 80 Zeichen. Bei
beschädigter Konfigurationsdatei erscheint ein Fehler, bevor die mehrstündige
Whisper-Analyse beginnt. Sicheres Speichern schützt vorherige Einstellungen.

**Hinweis für lange VODs:** Die Wortliste wird ausschließlich im lokalen
Textnachbearbeitungsschritt verwendet. Sie verursacht keine neuen Modell-Downloads
und erfordert kein erneutes Training; ein bereits gespeichertes Transkript könnte
zukünftig separat neu bewertet werden (noch nicht als UI-Funktion umgesetzt).

**Offene Praxisabnahme:** Windows 11 / PySide6, eigene Streaming-Begriffe und
realistische Fehlalarm-/Trefferquote auf längeren GTA-VI-Aufnahmen testen.

## Fehlerbehebung: fehlendes `timm` bei DETR-Objekterkennung

Wenn bei der Analyse `TimmBackbone requires the timm library` erscheint,
fehlt eine optionale Abhängigkeit des DETR-/Transformers-Backbones. Für eine
bestehende Windows-Quellcodeinstallation in `D:\\StreamClipper`:

```powershell
cd D:\StreamClipper
.\.venv\Scripts\python.exe -m pip install -e ".[vision]"
```

Alternativ genügt als Sofortlösung
`.\.venv\Scripts\python.exe -m pip install timm`. Anschließend StreamClipper
vollständig neu starten. `timm` gehört jetzt zur `vision`-Installationsgruppe;
bei neuen Setups zieht `setup_windows.bat` diese Abhängigkeit automatisch mit.
Für die gepackte Windows-EXE genügt ein `pip install` in einer separaten
`.venv` dagegen nicht; der portable Build muss neu erzeugt werden.

