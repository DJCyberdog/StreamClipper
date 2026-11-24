# StreamClipper 0.4 (experimenteller Export)

## M12b Teil 2 – PiP-Videospuren und Grafik-Overlays (Draft)

Im **Spuren**-Reiter eine **zusätzliche Videospur** ("＋ Spur" →
"Video") oder die vorhandene **Grafiken**-Spur auswählen. Mit
**„🎬 Video / Logo einfügen …“** ein lokales Video
(MP4/MKV/MOV/WebM/M4V/AVI) für **Picture-in-Picture/Facecam** oder
ein statisches PNG/JPEG/WebP für ein **Logo/Grafik-Overlay** referenzieren.
Die Dateien werden weder hochgeladen noch verändert.
Über **„Clip entfernen“** lässt sich jeder nicht gesperrte,
nicht zur Basisaufnahme gehörende Spurclip wieder entfernen;
die Mediendatei bleibt erhalten und **Strg+Z** stellt den Clip wieder her.

Die Timeline zeigt die Clips auf derselben Zeitachse wie die Aufnahme.
Im Inspector **Links / Oben / Breite / Höhe** als Anteile des
**exportierten Bildes** von 0 bis 1 und **Deckkraft** einstellen. Geänderte
Werte werden mit „Änderungen übernehmen“ als **ein** atomarer Projekt-
und Undo/Redo-Schritt gespeichert. Gesperrte Spuren und der
ursprüngliche Gameplay-Basisclip sind vor Änderungen geschützt.

Im Reiter **Export** die ausdrücklich optionale Checkbox
**„Projektspuren rendern · Audio / PiP / Grafiken (M12b Beta)“**
aktivieren. Die max. 20-s-Render-Vorschau und der MP4-Export nutzen
denselben versionierten FFmpeg-Compositor. Jede Bildquelle bekommt
Quell-IN/OUT und eine unabhängige Timeline-Position; überlagerte
Medien werden in stabiler Spur-/Clip-Reihenfolge gestapelt, auch bei
Lücken und überlappenden Bereichen. PiP-Videos bringen **keinen
automatischen Ton** mit; separate Audio-Clipspuren können parallel
gemischt werden. Externe Medien werden vor FFmpeg via FFprobe geprüft.

**Kompatibilität:** Projektformat **v3** kann v1/v2-Dateien und
Checkpoints unverändert einlesen. Eigene Visual-Parameter werden
erst bei bewusster Speicherung in v3 persistiert; alte Daten werden
nicht automatisch überschrieben.

**Noch nicht verfügbar:** Kein Austausch-/Ripple-Schnitt des
Gameplay-Basisvideos, keine freie Vollbild-Mehrquellen-Sequenz,
keine animierten Text-/Grafik-Keyframes, keine echten Timeline-
Caption-Clips. Diese nicht implementierten Cliptypen werden beim
opt-in Projekt-Rendering **abgewiesen**, niemals stillschweigend
als fertig behandelt. Echte Echtzeit-Mehrspur-WYSIWYG-Wiedergabe
im Programmmonitor, GPU-Rendering und Export-QA folgen separat.
Die vollständige Windows-11-/6h-VOD-Abnahme bleibt offen.


## M12-UX Teil 2 – Eine gemeinsame Timeline + editierbarer Inspector (Draft)

Die Wellenform (Highlights, Untertitel/Wortzeiten) und die Grafik für
Gameplay/Mikrofon/Musik/Grafik-Spuren sind nun **im selben Timeline-Dock**
direkt untereinander angeordnet. Beide verwenden **denselben sichtbaren
Quell-/Timeline-Zeitbereich und denselben 128px-Timeline-Rand**: Zoom,
Scrollposition, Playhead und IN/OUT werden synchron angezeigt. Der
vertikale Splitter zwischen Wellenform und Spurlanes kann skaliert
werden; im Projektbereich gibt es keine zweite Track-Canvas-Duplikation
mehr. `TimelineWidget` behält seinen eigenständigen Null-Rand-Modus,
um alte Tests und externe Nutzer nicht zu brechen.

**Magnet** im Timeline-Kopf schaltet 8-Pixel-Snapping ein/aus.
Beim Verschieben eines Spurclips können seine linke oder rechte
Clipkante an anderen Clipkanten, Playhead oder Markierungen einrasten;
das vorhandene Undo/Redo und die gesperrten Spuren gelten weiter.
Der erste originale Basisclip kann nicht über das grafische Drag
verschoben werden, weil der M12b-Renderer die veränderte Basisspur noch
nicht komposen kann.

Im Arbeitsbereich Schnitt/Audio zeigt das Eigenschaften-Panel
**direkt editierbare** Quell-IN/OUT, Timeline-IN und Audioclip-Pegel.
Die Aktion **Änderungen übernehmen** committet alle vier Felder
atomar als **genau einen** Projekt-/Undo-Schritt. Gesperrte Spuren und
Basisclip sind dort schreibgeschützt; fehlerhafte Werte werden vom
Projektvertrag abgewiesen. **Werte zurücksetzen** verwirft unbestätigte
Änderungen, ohne Projekt- oder Videodateien zu verändern.

**Noch nicht vollständig:** Das ist ein integrierter Timeline-
Viewport mit getrennt implementierten Wellenform-/Track-Zeichen-
schichten, keine vollständige Premiere-Sequenz mit Ripple-/Roll-
Edits, automatischem Mehrspur-Video-Compositor oder Effektrenderer.
M12b Zusatzvideo-/Overlay-Komposition, NVENC und Export-QA bleiben
eigene Meilensteine. UI-Tests für echtes 6h-VOD unter Windows
und unterschiedliche Bildschirmauflösungen bleiben offen.

## M12-UX – Premium-Workspace und andockbare Panels (Draft)

StreamClipper Studio bekommt eine **Premiere-inspirierte, aber eigenständige**
Editoroberfläche. Sie besteht aus einem zentralen **Programmmonitor**,
einem andockbaren **Projekt-/Werkzeugdock** mit allen bisherigen
Registerkarten, einer separaten **Timeline** und einem kontextbezogenen
**Eigenschaften-Inspektor**. Dies ist die erste funktionierende
Docking-Shell, noch keine abgeschlossene Profi-NLE.

Oben rechts in der Anwendung zwischen den Arbeitsbereichen
**Highlights / Schnitt / Audio / Untertitel / Export** wechseln.
Wiedergabe, Quellzeit, Projektinhalt und Undo-Historie bleiben erhalten.
Unter **Ansicht & Arbeitsbereiche** kannst du einzelne Panels
ein-/ausblenden, per Titelleiste umsetzen/abdocken, das aktuelle Layout
speichern oder **Layout zurücksetzen**. Das Layout wird auch beim
normalen Beenden lokal gespeichert und beim Neustart wiederhergestellt.
Die UI-Konfiguration liegt separat im portablen Verzeichnis unter
`data/ui/workspace-layout-v1.json` (versioniert, atomar, keine Tokens
und keine Projekt-/Video-Inhalte). Window-Positionen werden absichtlich
nicht automatisch wiederhergestellt, damit eine Änderung der
Monitoranordnung die App nicht außerhalb des Bildschirms platziert.

Die bestehende Original-/Proxy- und Render-Vorschau, alle M11-Clip-/
Wort-Edits, M12-Audiospuren sowie Export-/Download-Worker bleiben
dieselben Objekte und Signale. Zusätzliche Untermenüs und die grafische
Anordnung sind noch **experimentell**; die vereinheitlichte
mehrspurige Timeline, Drag&Drop, Keyframe-Panels und weitere
Polishing-Schritte werden in M12-UX Teil 2/M13 bearbeitet.

**Wichtig:** Premium-Ziel bedeutet nicht, dass unfertige Renderfähigkeiten
vorgetäuscht werden. M12-UX verbessert die Bedienoberfläche; es ersetzt
keine noch offenen M12-Video-Overlays, NVENC-/Export-QA- oder M19-Upload-Funktionen.


## M12b – Eigene Audiodateien auf der Timeline mischen (Draft)

Die M11-Spuren unterstützen jetzt eine **opt-in Audio-Komposition**:
Im Reiter **Spuren** eine Audio-/Mikrofon-/Musikspur wählen, dann
**🎵 Audiodatei einfügen …** anklicken (lokale WAV/MP3/FLAC/M4A/OGG-Datei).
Der Clip wird referenziert, nicht kopiert; seine ursprüngliche Datei
bleibt unverändert. Quelle IN/OUT und Timeline-Start lassen sich editieren;
**Pegel …** regelt den Clip in dB (−60 bis +12). Spur-Stumm schaltet
sämtliche Clips dieser Audiospur aus; Sperre unterbindet Bearbeitung,
nicht Wiedergabe; „ausgeblendet“ ist nur eine GUI-Eigenschaft.

Im **Export**-Reiter opt-in **„Audiospuren mitmischen (M12b, experimentell)“**
setzen. Dann verwenden normaler MP4-Export **und** die maximal 20 Sekunden
lange Render-Vorschau denselben versionierten Graphen und die gleiche
FFmpeg-Audiomischung. Die Original-Tonspur bleibt Basis; weitere Audios
werden anhand von Quell-IN/OUT und Position auf der Ausgabe-Timeline
mittels FFmpeg gemischt; Pausen und Überlappungen sind unterstützt.
Achtung: Mehrere laute Audiosignale können übersteuern. Den Clip-Pegel
ggf. absenken; Loudness-/True-Peak-Normalisierung folgt später.

**Rückwärtskompatibel:** Bestehende Projektdateien/Checkpoints im
Schema v1 werden lesend nach v2 migriert. Neue Versionen werden atomar
als v2 gespeichert. Fehlende/unpassende lokale Audiodateien werden
vor dem Rendern abgewiesen und niemals stillschweigend übersprungen.

**Bewusste M12b-Grenzen:** Nur **ein** unverändertes Hauptvideo mit
darübergelegten Audiospuren wird komponiert. Extra-Videoclips, Grafik-/
Overlay-Layer und eigenständige Timeline-Caption-Clips sind noch
**nicht** gerendert; bei opt-in Graph-Auswahl gibt es eine verständliche
Ablehnung statt eines scheinbar vollständigen Ergebnisses. Die
bisherigen ASS-Untertitel über das Transkript bleiben unterstützt.
Audio-Datei-Metadaten werden beim Einfügen per FFprobe geprüft; später
wird dieser Preflight in einen eigenen Hintergrundjob ausgelagert.
Keine VST-/Audio-Trennung, kein NVENC, keine Renderqueue oder
automatische True-Peak-Prüfung. Nicht nach 1.0 verschoben.


## M12a – Exportgetreue Render-Vorschau für einen Quellclip (Draft)

Im **Export**-Reiter gibt es den neuen Button
**🎞 Exportgetreue Vorschau (bis 20 s)**. Er rendert die ersten
maximal 20 Sekunden des ausgewählten Highlights; ohne Highlightauswahl
den Bereich aus der Haupt-Timeline. Der Fortschritt steht in der
unteren App-Leiste, Abbruch erfolgt über **Abbrechen**.

Im Gegensatz zur bisherigen Original-/480p-Proxy-Vorschau zeigt diese
Render-Vorschau eine **echte temporäre MP4** mit denselben FFmpeg-
Exportfiltern: eingestellter 16:9-/9:16-Modus, der für den Clip
berechnete dynamische Bildausschnitt und optional im Video eingebrannte,
korrigierte Untertitel samt Zeitversatz. Ein einziger unveränderlicher
`RenderRequest` mit Quellvideo und Originalzeitfenster ist das
gemeinsame Parametermodell. Sowohl regulärer MP4-Export als auch die
Vorschau rufen den identischen `export_clip`-Encoder auf.

Die kurze Datei wird nur auf Klick und auf einem QThread erzeugt.
Die Vorschau öffnet in einem eigenen Player. Originalplayer,
Proxy-Umschaltung und Timeline-Zeitbasis werden nicht verändert.
Temporäre MP4s werden nach Schließen des Vorschaufensters entfernt,
sofern Windows die Video-Dateisperre schon freigegeben hat.

**Bewusste Grenzen von M12a:** noch kein zusammengesetzter Mehrspur-
Rendergraph: zusätzliche Video-/Audiotracks, Overlays, Facecam, spätere
Smart-Director-Keyframes und M13/M14-Effekte erscheinen hier **noch
nicht**. Für den bereits existierenden Single-Source-FFmpeg-Pfad
sind die Ausgabeparameter identisch; das ist noch nicht die vollständige
Live-WYSIWYG-Vorschau aller geplanten Features. Es gibt weiterhin
keine NVENC-/HEVC-Engine, Render-Queue und umfassende automatische
Export-QA (M12b ff.).

**Abnahme:** automatisierte Parität von exportiertem und gerendertem
Clip bei identischem Quellfenster inklusive ASS-Untertiteln; Windows-
Qt-Offscreen-Regressionsprüfung und portables Paket. Echte Windows-11-
End-to-End- und 6h-VOD-Messungen bleiben offene Freigabeschritte.


## M10.5-Ergänzung – Modellspeicher und HF-Token (Draft)

Im Reiter **KI & Modelle** lässt sich ein optionaler Hugging-Face-Read-Token
maskiert einfügen (**Übernehmen**), über **Verbindung prüfen** ausdrücklich
online gegen die Hugging-Face-API prüfen oder über **Entfernen** aus
StreamClipper löschen. Ohne Token bleiben öffentliche Modelle verwendbar.
Bereits vorhandene HF_TOKEN-/HF-Login-Konfigurationen werden erkannt, aber
weder angezeigt noch verändert. Read-Token erzeugen:
https://huggingface.co/settings/tokens

**Standard: Sitzungstoken im Arbeitsspeicher.** Die dauerhafte Speicherung
erfolgt nur bei bewusst gesetzter Checkbox über den **Windows Credential
Manager**; weder Dateien unter data/ noch Logs/CLI/Umgebungsvariablen
enthalten diesen Token. Auf anderen Systemen ist nur der Sitzungsmodus
verfügbar. „Entfernen“ beeinflusst keine außerhalb StreamClipper gesetzte
HF-Umgebungsvariable.

Beim Download zeigt der **untere Fortschrittsbalken** die tatsächlich
gemeldeten Transfer-Bytes an. Nur bei vollständig bekannten Remote-
Dateigrößen werden Prozentwerte (höchstens 99 vor Modellvalidierung)
gezeigt. Bei nicht bekannten Größen, Metadaten- oder Rekonstruktionsarbeit
ist die Leiste absichtlich unbestimmt. Der Download kann abgebrochen
werden, ohne vorhandene Modelldateien zu löschen. Authentifizierung gilt
für reguläre und alternative Gewichtsdownloads.

Diese UX-Ergänzung ist **kein Entwicklungsblocker für M11/M12**.
Reale Windows-Tests mit großem Modell und echtem Token stehen als
optionale Abnahmebelege noch aus; niemals echte Tokens ins Repo legen.


## M11c / Teil 4 – Optionale Proxy-Vorschau (Draft)

**Vorschau → Proxy erstellen** erzeugt auf ausdrücklichen Klick eine
niedriger aufgelöste, CPU-basierte H.264/AAC-Vorschau (maximal 854×480).
Während der Verarbeitung zeigt die Vorschau einen Fortschrittsbalken
und bietet **Abbrechen** an. Der Prozess läuft im Hintergrund, nutzt
FFmpeg als Streaming-Encoder (keine vollständige VOD-Dekodierung im
Python-Speicher) und schreibt erst nach Prüfung eine MP4-Datei.

Unter **Original / Proxy (480p)** wird die Anzeige umgeschaltet. Alle
Zeitleistenpositionen, Highlight-Grenzen, Untertitel und Exporte beziehen
sich weiterhin auf das **Originalvideo**. Der Proxy verwendet die
Frame-Zeitabstände der Quelle, statt VFR-Material auf eine angenommene
konstante Bildrate zu zwingen. Anfängliche Video-/Audio-Abweichungen über
150 ms oder eine Gesamtdauer-Abweichung über 300 ms werden abgewiesen.
*Grenze:* Eine FFmpeg-kodierte Vorschau kann keine pixel- bzw. framegenaue
Identität zum Original garantieren; insbesondere beim Scrubbing können
unterschiedliche Keyframes eine abweichende Anzeigeframe-Wahl bewirken.
Schnitt und Export arbeiten daher **niemals mit Proxy-Zeitstempeln als
neuer Projektquelle**.

Der lokale Cache liegt ausschließlich unter `data/proxies/` und wird
durch Pfad, Dateigröße, Änderungszeit, Video-Metadaten und Encoderpreset
adressiert; ein vollständiger Hash des sechsstündigen Originals wäre
unnötige I/O-Last. Beschädigte oder veraltete Cacheeinträge werden
ignoriert. Ein fehlgeschlagener bzw. abgebrochener FFmpeg-Lauf bietet
keine unfertige Vorschau an. Ist ein Proxy beim Abspielen defekt,
fällt das Programm auf das Original zurück. Der Cache wird **nicht**
ungefragt gelöscht und keine Quelldatei wird überschrieben.

**Abnahme offen:** echter Windows-11-Vorschautest bei 1366×768 und
FullHD, echte 6h-VOD-Messungen (Speicher, CPU/GPU, Abbruch, VFR/Sync),
breitere Codec- und Dateisystemtests. Das ist **kein** gemeinsamer
M12-Mehrspur-Rendergraph: Änderungen an Audio-/Grafikspuren beeinflussen
die Proxyvorschau noch nicht.


## M11c / Teil 3 – Analyse-Highlights in den Spurplan übernehmen (Draft)

Im **Spuren**-Arbeitsbereich gibt es nun **★ Highlights übernehmen …**.
Erst nach einem bewussten Klick und der Auswahl einer Zielvideospur
werden vorhandene Highlights als *Metadaten-Clips* aufgenommen. Standardziel:
eine eigene Spur **Highlights (Import)**; vorhandene Videospuren können
alternativ ausgewählt werden. Eine gesperrte Zielspur wird nicht verändert.

Die Übernahme ist **idempotent**: Bereits importierte Zeitbereiche werden
mit stabilen, quellenbezogenen Clip-Kennungen erkannt. Auch nach manuellem
Verschieben/Trimmen eines importierten Spurclips wird er bei unveränderter
Analyse nicht erneut importiert. Identische vorhandene Clips auf der
gewählten Spur werden ausgelassen; andere manuelle Spurelemente bleiben
unverändert. Ein später geändertes Highlight-Zeitfenster kann als neuer Clip
übernommen werden; das Verfahren synchronisiert keine Bearbeitungen zurück
ins AnalysisResult. Der gesamte Import ist eine gemeinsame Undo-Aktion
und wird atomisch in der bestehenden Projektdatei gespeichert.
Bei fehlerhaften Zeitgrenzen, falscher Aufnahme, gesperrten Spuren oder
Schreibfehlern wird der Import abgewiesen.

**Kein Renderer:** importierte Highlights verändern weiterhin weder
Wiedergabe noch Videoexport. Auch die Quelldatei bleibt unberührt.
Echte Windows-11-Ergonomie und 6h-End-to-End bleiben Abnahmepunkte.


## M11c / Teil 2 – Gemeinsamer Undo-/Redo-Verlauf (Draft)

Highlights, Untertitelkorrekturen und Spurplan-Aktionen benutzen nun einen
**gemeinsamen chronologischen Bearbeitungsverlauf**. **Strg+Z** und
**Strg+Umschalt+Z** gelten für die letzte Studio-Aktion, unabhängig davon,
welches Werkzeugregister offen ist. Während eine Texteingabe fokussiert ist,
haben deren native Text-Undo-/Redo-Aktionen Vorrang. Die bisher doppelten
Rückgängig-/Wiederholen-Buttons im Spurenregister entfallen. Es bleiben nur
die einheitlichen Buttons oberhalb der Timeline.

Der Verlauf verwendet für große Transkripte weiterhin platzsparende
Änderungs-Deltas. Spuraktionen werden vor der sichtbaren Undo-/Redo-Änderung
atomisch auf Datenträger gespeichert; scheitert das Speichern, bleibt
der sichtbare Stand einschließlich History-Cursor unverändert.
Der Sitzungsverlauf wird nach Quellenwechsel, Neu-Analyse, externem
Berichtimport und Checkpoint-Restore bewusst zurückgesetzt. Benannte
Projektstände (Teil 1) bleiben separat nutzbar.

**Noch offen:** Analyseclip-Import in Spurplan, Proxy-Schnitt, M12-Rendervertrag,
echter Windows-11-Ergonomietest (1366×768 / FullHD) und reale 6h-VOD-Prüfung.


## M11c / Teil 1 – Benannte Projektstände (Draft)

Über das neue Menü **Datei & Projekt** lassen sich Projektstände benennen,
sichern (**Strg+Alt+S**) und wiederherstellen (**Strg+Alt+O**).
Ein Stand umfasst den versionierten Spurplan und, falls eine Analyse geladen
ist, die Highlight- und Transkriptkorrekturen. Beim Wiederherstellen wird die
Aufnahmezuordnung (Pfad, Dauer, Auflösung) geprüft. Ein beschädigter Stand
wird nicht zur Wiederherstellung angeboten; Quellvideo und bestehende
Analyseberichte werden nie überschrieben. Standardmäßig bleiben die 20
neuesten gültigen Projektstände pro Aufnahme erhalten.

**Grenzen:** Projektstände sind lokale JSON-Metadatensicherungen, keine
Kopien der Videodatei. Spuren verändern weiterhin nicht das Renderergebnis;
es gibt weiterhin getrennte Undo-Verläufe für Spuren und Analyse. M11c ist
noch **nicht vollständig abgenommen**: gemeinsame Undo-/Shortcut-Führung,
Clipmigration, Proxy-Editing und lange Windows-End-to-End-Proben fehlen.
Das Menü verhindert einen weiteren überfüllten Editor-Reiter.


## M11b – Übersichtlichere Oberfläche und Spurplan (experimentell)

Die Bearbeitungsoberfläche zeigt die **Videovorschau und Timeline dauerhaft**.
Die rechte Seitenleiste ist jetzt in **Highlights, Untertitel, KI & Modelle,
Spuren und Export** gegliedert. Modell-Downloads und Exportoptionen belegen
nicht mehr ständig den Hauptbereich. Der Worteditor unter der Timeline lässt
sich ein-/ausklappen und öffnet sich beim Anklicken eines Wortes automatisch.
Längere Seitenleisten sind scrollbar.

Zusätzlich zeigt eine **grafische Spurübersicht** die Clips als Zeitblöcke.
Der sichtbare Zeitbereich wird mit dem Zoom/Scroll der Haupt-Timeline
synchronisiert; Clips können angeklickt oder per Maus in der Timeline
verschoben werden. Gesperrte Spuren verhindern Drag-Bearbeitungen.
Die zugehörige Clip-/Spurtabelle bleibt für präzise Werte erhalten.

Ein eigenständiges **versioniertes Mehrspur-Projektmodell** verwaltet
Gameplay-, Mikrofon-, Musik-, Untertitel- und Grafikspuren. Im Register
**Spuren** können Spuren hinzugefügt, umbenannt, sortiert, gesperrt und
stummgeschaltet werden. Timeline-Auswahlen lassen sich als Clip-Metadaten
hinzufügen, in Quelle/Timeline verschieben und trimmen. Spuraktionen lassen
sich über eigene Zurück-/Wiederholen-Buttons umkehren.

Das Spurprojekt wird atomar unter `data/projects/editor/` gespeichert.
Es verändert **weder** Originalvideo **noch** bisherige
`.highlights.json`-Berichte; der vorhandene Analyse-/Exportworkflow bleibt
kompatibel. **Grenze:** Dies ist ein **Spurplan/Metadaten-Editor**, noch
**keine echte Mehrspur-Audio-/Video-Komposition oder exportgetreue
Spuren-Wiedergabe**. Diese Integration benötigt den Folgeausbau von M11/M12.
Die vollständige M11-Abnahme umfasst noch Projektsnapshots/Checkpoints,
Proxy-Editing, gemeinsame Undo/Redo-Historie/Shortcuts und echte Windows-6h-Tests.

## M11a – Editor-Historie und Auto-Sicherung (Entwicklungsstand)

Der erste, **noch nicht vollständig abgenommene** M11-Schritt unterstützt
`Strg+Z` und `Strg+Umschalt+Z` sowie sichtbare Buttons für Rückgängig/
Wiederholen von **manuellen Highlights, Trimmen und übernommenen Wort-/
Transkriptkorrekturen**. Die Befehle speichern nur geänderte Einträge statt
jedes Mal das gesamte sechsstündige Transkript zu kopieren.

Ungespeicherte Änderungen werden nach kurzer Bearbeitungspause zusätzlich im
bestehenden Analyse-JSON-Format **atomar** unter
`data/projects/autosaves/` gesichert (lokal, ohne Cloud). Wenn dieselbe
Videoquelle erneut geöffnet wird, erscheint bei vorhandener Sicherung eine
Wiederherstellungsfrage. **Originalvideo und ausdrücklich gespeicherter
Analysebericht werden nicht überschrieben.** Nach ausdrücklichem
Speichern oder Verwerfen werden alte Auto-Sicherungen entfernt.

**Noch offen für M11:** echte Mehrspur-Timeline, fortgeschrittene Projekt-/
Checkpointverwaltung, Proxy-Editing, frei konfigurierbare Shortcuts,
6h-Windows-Praxistest und die Gesamtabnahme. Der JSON-Autosave selbst
arbeitet derzeit während des Idle-Timers; Zeit-/UI-Auswirkungen auf sehr
große Berichte müssen auf Windows noch gemessen werden.


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

