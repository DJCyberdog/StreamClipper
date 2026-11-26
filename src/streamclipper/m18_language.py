"""Local DE/EN preference and exact UI-string catalog (not user media text)."""
from pathlib import Path
import json
from .portable import installation_directory
from .gaming_intelligence import atomic_json

CATALOG_TEXT="""📂 Aufnahme öffnen	📂 Open recording
🌐 Video-URL importieren	🌐 Import video URL
Highlights analysieren	Analyze highlights
Abbrechen	Cancel
🎞 Exportgetreue Vorschau (bis 20 s)	🎞 Render preview (up to 20 s)
Ausgewählten Clip exportieren	Export selected clip
Alle Clips exportieren	Export all clips
Datei && Projekt	File && Project
Szenen	Scenes
Ansicht && Arbeitsbereiche	View && Workspaces
Integrationen (M18)	Integrations (M18)
Story & Montage (M17)	Story & Montage (M17)
Gaming Intelligence (M16)	Gaming Intelligence (M16)
StreamClipper Studio | Schnitt & Highlights	StreamClipper Studio | Editing & Highlights
Cliplänge	Clip length
Arbeitsbereich	Workspace
Highlight-Wörter …	Highlight words …
Aufnahme öffnen…	Open recording…
Video-URL importieren…	Import video URL…
Ordner …	Folder …
Herunterladen	Download
Übernehmen	Apply
In Windows-Anmeldeinformationen sichern (optional)	Store in Windows Credential Manager (optional)
Verbindung prüfen	Check connection
Entfernen	Remove
Kein Sitzungstoken · öffentliche Modelle ohne Anmeldung möglich	No session token · public models available without login
Noch kein Video geladen. Videos bleiben lokal auf deinem Rechner.	No video loaded. Videos stay on your computer.
▶ Wiedergabe / Pause	▶ Play / pause
Vorschau	Preview
Proxy erstellen	Create proxy
Highlight-Vorschläge (Audio / Sprache / Szenendynamik / CLIP)	Highlight suggestions (audio / speech / scene activity / CLIP)
Ende	End
Erkennungsgrund	Evidence
★ Highlight ab hier	★ Highlight from here
[ Start setzen	[ Set in point
Ende setzen ]	Set out point ]
Bereich hinzufügen	Add range
Optionaler Name, z. B. 'LKW-Unfall'	Optional name, e.g. 'Truck crash'
Start/Ende noch nicht gesetzt	In/out not set
Manuelles Highlight entfernen	Remove manual highlight
Score = nicht kalibrierte Evidenz-Heuristik, keine Viralitätsprognose.	Score = uncalibrated evidence heuristic, not a prediction of virality.
Beginn	Start
Whisper-Text	Whisper text
◀ Vorheriger	◀ Previous
Nächster ▶	Next ▶
▶ Stelle anhören	▶ Listen to segment
Zum markierten Highlight	Go to selected highlight
Gesprochenen Text korrigieren	Correct spoken text
Untertitelzeile auswählen …	Select a caption …
✓ Korrektur übernehmen	✓ Apply correction
Änderungen verwerfen	Discard changes
💾 Projekt speichern	💾 Save project
Nach der Analyse hier eine Zeile auswählen.	Select a row here after analysis.
Untertitel	Subtitles
KI & Modelle	AI & models
★ Highlights übernehmen …	★ Import highlights …
＋ Spur	＋ Track
Umbenennen	Rename
Stumm	Mute
Sperren	Lock
Clips / Zeitpositionen	Clips / time positions
Auswahl als Spurclip	Add selection as track clip
Clip verschieben	Move clip
Clip trimmen	Trim clip
Clip entfernen	Remove clip
🎵 Audiodatei einfügen …	🎵 Insert audio file …
🎬 Video / Logo einfügen …	🎬 Insert video / logo …
Pegel …	Gain …
Spuren werden mit der Videoquelle geladen.	Tracks are loaded with the video source.
Spuren	Tracks
TIMELINE · Wellenform / Clips / Untertitel	TIMELINE · Waveform / Clips / Subtitles
Magnet	Snap
Keine Aufnahme geladen	No recording loaded
↶ Rückgängig	↶ Undo
↷ Wiederholen	↷ Redo
Auto-Sicherung bereit	Autosave ready
▸ Worteditor einblenden	▸ Show word editor
WORTGENAUE UNTERTITEL · aktives Highlight	WORD-LEVEL CAPTIONS · active highlight
Highlight wählen; Wörter erscheinen in der violetten Spur	Select a highlight; words appear on the purple track
◀ Wort	◀ Word
Wort ▶	Word ▶
Wort in der Timeline anklicken und hier korrigieren	Select a word on the timeline and correct it here
Wortbeginn	Word start
Wortende	Word end
▶ Anhören	▶ Listen
✓ Wort übernehmen	✓ Apply word
▶ Auswahl abspielen	▶ Play selection
★ Auswahl als Highlight	★ Selection as highlight
✂ Markiertes Highlight trimmen	✂ Trim selected highlight
Exportformat	Export format
16:9 – dynamische Kamera (sanfter Zoom)	16:9 – dynamic camera (gentle zoom)
9:16 – dynamischer Ausschnitt für TikTok	9:16 – dynamic crop for TikTok
9:16 – ganzes Bild / unscharfer Hintergrund	9:16 – full image / blurred background
9:16 – fester Mittel-Ausschnitt	9:16 – fixed center crop
Video-Encoder · H.264 / HEVC	Video encoder · H.264 / HEVC
Untertitel direkt ins Video	Burn subtitles into video
Analyse als JSON speichern	Save analysis as JSON
Analyse laden (JSON)	Load analysis (JSON)
Transkript speichern (SRT/TXT/VTT)	Save transcript (SRT/TXT/VTT)
Untertitelversatz	Subtitle offset
+ = später, − = früher · ohne erneute Transkription	+ = later, − = earlier · no retranscription
RENDERQUEUE  /  MP4-QUALITÄTSPRÜFUNG	RENDER QUEUE  /  MP4 QUALITY CHECK
Auswahl einreihen	Queue selection
Alle Highlights einreihen	Queue all highlights
Queue laden	Load queue
▶ Queue starten	▶ Start queue
■ Queue anhalten	■ Stop queue
Auswahl fortsetzen	Resume selection
Job verwerfen	Discard job
Keine Auswahl	No selection
Änderungen übernehmen	Apply changes
Werte zurücksetzen	Reset values
Auswahl bearbeiten	Edit selection
Auto · NVDEC Szenenscan / NVENC Proxy	Auto · NVDEC scene scan / NVENC proxy
GPU bevorzugen · auch Einzelbilder	Prefer GPU · also individual frames
Nur CPU · Analyse / Proxy	CPU only · analysis / proxy
Bereit	Ready
Inferenzgerät: noch kein Modell aktiv	Inference device: no active model
Analysezeit: –	Analysis time: –
Highlight in Szenen bearbeiten …	Edit highlight as scenes …
Audioquellen / Originalspuren …	Audio sources / original tracks …
Originalton in Komposition ein-/ausschalten	Toggle original audio in composition
Untertitel-Zeitstempel prüfen …	Review subtitle timing …
ASR-Qualität prüfen …	Review ASR quality …
ASR-Zwischenstände lokal behalten (explizite Sprachspur)	Keep local ASR checkpoints (explicit speech track)
KI-Stems / Audio-Mix …	AI stems / audio mix …
Voice-over-Datei auf ausgewählte Audiospur …	Add voice-over file to selected audio track …
Dynamische Clipgrenzen bei M16-Analyse	Dynamic clip boundaries during M16 analysis
Story-Längenbudget einstellen …	Set story length budget …
Storygrenzen aus aktuellem Transkript vorschlagen …	Suggest story boundaries from current transcript …
15/30/60s-Varianten & Hooks …	15/30/60s variants & hooks …
Kapitelübersicht …	Chapter overview …
Montage & Effekte …	Montage & effects …
Experimentelle M16-Analyse	Experimental M16 analysis
Schnelle Vision (CUDA FP16 / Batch, experimentell)	Fast vision (CUDA FP16 / batch, experimental)
Akustisches Reaktionsmodell auswählen / deaktivieren …	Select / disable acoustic reaction model …
Lokale Analyse-Zwischenstände behalten	Keep local analysis checkpoints
Persönliche Ranking-Präferenzen verwenden	Use personal ranking preferences
Spielprofil auswählen …	Select game profile …
Vorschlag bewerten …	Rate suggestion …
Ranking-Präferenzen zurücksetzen …	Reset ranking preferences …
Transkript nach Momenten durchsuchen …	Search transcript for moments …
Semantische Sprachsuche (lokales Modell) …	Semantic speech search (local model) …
Semantische Bildsuche (CLIP) …	Semantic image search (CLIP) …
Highlight-Kontaktbogen speichern …	Save highlight contact sheet …
Lokalen Chat beim nächsten M16-Lauf auswählen	Select local chat for next M16 run
Twitch-Chat beim nächsten M16-Lauf laden (lokaler Helfer)	Download Twitch chat on next M16 run (local helper)
Untertitel gestalten …	Style subtitles …
Untertitel übersetzen …	Translate subtitles …
Text / Callout hinzufügen …	Add text / callout …
Ausgewählten Callout bearbeiten …	Edit selected callout …
Branding-Profil speichern …	Save branding profile …
Branding-Profil anwenden …	Apply branding profile …
OBS verbinden / Sitzung benennen …	Connect OBS / name session …
Zeitmarke setzen (OBS oder Editor)	Set marker (OBS or editor)
Zeitmarken in manuelle Highlights übernehmen …	Import markers as manual highlights …
Watch Folder auswählen / pausieren …	Select / pause watch folder …
Erkannte Aufnahmen öffnen …	Open detected recordings …
Kanalaufnahme verwalten …	Manage channel ingestion …
Kanalaufnahme für diese Sitzung starten / pausieren	Start / pause channel ingestion for this session
Schnittliste EDL / FCPXML …	Export EDL / FCPXML cut list …
GIF / WebM exportieren …	Export GIF / WebM …
Vorhandene SRT/VTT-Untertitel übernehmen …	Import existing SRT/VTT subtitles …
YouTube-Konto vorbereiten (OAuth-Pilot) …	Prepare YouTube account (OAuth pilot) …
Lokale Stream-Deck-Befehle annehmen (Sitzung)	Accept local Stream Deck commands (session)
Beste verfügbare	Best available
Ton automatisch / Original	Automatic / original audio
Original / Zusammenführung ohne Neukodierung	Original / merge without re-encoding
MP4 (Remux, nur kompatible Codecs)	MP4 (remux, compatible codecs only)
Vorhandene Untertitel als separate Dateien übernehmen	Include existing subtitles as separate files
Nach erfolgreichem Download im Editor öffnen	Open in editor after successful download
Download vorbereiten	Prepare download
Hinzufügen	Add
Entfernen	Remove
Zeit & Tempo	Time & speed
Tempo-Rampe	Speed ramp
Kontinuierliches Tempo	Continuous speed
Standbild	Freeze frame
Eigener Sound	Custom sound
Soundbibliothek	Sound library
Effekte zurücksetzen	Reset effects
Plan speichern	Save plan
Plan öffnen	Open plan
Abschnitt-Vorschau	Section preview
Montage-Vorschau	Montage preview
Zur Renderqueue	Add to render queue
Montage exportieren	Export montage
M17 · Montage & Effekte	M17 · Montage & effects
Wiedergabe / Pause	Play / pause
Schließen	Close
M18-Integration läuft …	M18 integration running …
Videoimport abgeschlossen	Video import complete
Video-Metadaten	Video metadata
Videoimport wird vorbereitet	Preparing video import
Videoimport	Video import
Netzwerkzugriff und Rechte	Network access and rights
Import speichern	Save import
Zeitbasis:	Time base:
OBS-Aufnahme	OBS recording
OBS-Stream	OBS stream
Editor-Modus (OBS trennen)	Editor mode (disconnect OBS)
Eindeutiger Sitzungsname (später der Aufnahme zuordnen):	Unique session name (associate with recording later):
Lokaler WebSocket-Port	Local WebSocket port
WebSocket-Passwort (nur Sitzung)	WebSocket password (session only)
Keine passenden Marker	No matching markers
Aktuellen Ordner pausieren?	Pause current folder?
Aufnahmen überwachen (nur diese Sitzung)	Watch recordings (this session only)
Keine neuen stabilen Aufnahmen	No new stable recordings
Aufnahme auswählen:	Select recording:
Kanalaufnahme	Channel ingestion
Kanal	Channel
Neuen autorisierten Kanal hinzufügen	Add authorized channel
Eigener / ausdrücklich autorisierter Kanal:	Own / explicitly authorized channel:
Bereits registriert	Already registered
Nutzungsrechte	Usage rights
Kanal-Zielordner	Channel destination folder
Abrufintervall	Poll interval
Minuten	Minutes
Mengenlimit	Item limit
Speicherlimit	Storage limit
Kein aktiver Kanal	No active channel
Schnittliste (nur Schnitte, keine Effekte)	Cut list (cuts only, no effects)
Alternative Ausgabe	Alternative export
Vorhandene Untertitel	Existing subtitles
Nur Kontovorbereitung, kein Upload:	Account preparation only, no upload:
Registrierte Desktop-App verbinden	Connect registered desktop app
Gespeicherten Token laden	Load saved token
Lokalen Token entfernen	Remove local token
Registrierte OAuth-Client-ID:	Registered OAuth client ID:
Client-Secret (nur Sitzung):	Client secret (session only):
Tokenspeicher	Token storage
Kein Token gespeichert	No token stored
"""
CATALOG=dict(line.split("\t",1) for line in CATALOG_TEXT.splitlines() if "\t" in line)
CATALOG.update({"OBS-Zeitbasis gewählt – Verbindung beim nächsten Marker":"OBS time base selected – connect on next marker","OBS-Zeitmarke gespeichert":"OBS marker saved","Editor-Zeitmarke gespeichert":"Editor marker saved","Zeitmarke":"Marker","Zeitbasis auswählen:":"Select time base:","OBS-Sitzungsname:":"OBS session name:","Zeitversatz zur geöffneten Originalaufnahme (s):":"Offset to the open original recording (s):","Konfiguration (kein Abruf ohne Sitzungsfreigabe):":"Configuration (no polling without session consent):","Automatische Downloads dieses Kanals sind ausdrücklich autorisiert? Plattformbedingungen gelten.":"Are automatic downloads of this channel explicitly authorized? Platform terms apply.","Maximal neue Videos je Prüfung":"Maximum new videos per check","Maximal GiB pro Video":"Maximum GiB per video","Aktion:":"Action:","Aktivieren/Pausieren":"Enable / pause","Registrierung löschen (keine Medien löschen)":"Remove registration (keep media)","Kanalaufnahme pausiert – laufenden Import bei Bedarf abbrechen":"Channel ingestion paused – cancel current import if needed","Autorisierte Kanäle während dieser App-Sitzung prüfen und neue Videos automatisch innerhalb der Limits importieren? Erster Abruf speichert nur den Ausgangsbestand.":"Check authorized channels during this app session and import new videos within the limits? First check records the existing inventory only.","Watch Folder nicht erreichbar – pausiert":"Watch folder unavailable – paused","Kanalprüfung abgeschlossen":"Channel check completed","Kanalprüfung fehlgeschlagen – nächster regulärer Abruf":"Channel check failed – next scheduled poll","Windows-Tokenspeicher nicht verfügbar":"Windows credential storage unavailable","Token lokal geladen; API-Zugriff noch nicht validiert":"Token loaded locally; API access not validated","Offiziellen Google-Systembrowser-Login mit Upload-Scope öffnen? Es werden keine Medien übertragen.":"Open official Google sign-in in the system browser with upload scope? No media will be transferred.","Token in Windows Credential Manager speichern? Nein = nur Sitzung.":"Store token in Windows Credential Manager? No = session only.","OAuth-Autorisierung erhalten – kein Upload, keine API-Abnahme":"OAuth authorization received – no upload, API not yet validated"})
CATALOG.update({"Videoimport":"Video import","HTTPS-Einzelvideo (Twitch, YouTube, Kick, weitere unterstützte Quellen):":"HTTPS single video (Twitch, YouTube, Kick, other supported sources):","Video-URL":"Video URL","Nur eigene oder ausdrücklich autorisierte Inhalte importieren. Plattformbedingungen beachten. Öffentliche Abrufbarkeit allein genügt nicht. Metadaten jetzt abrufen?":"Import only your own or explicitly authorized content. Platform terms apply. Public availability alone is not sufficient. Fetch metadata now?","Netzwerkzugriff und Rechte":"Network access and rights","Video-Metadaten":"Video metadata","Beste verfügbare":"Best available","Ton automatisch / Original":"Automatic / original audio","Original / Zusammenführung ohne Neukodierung":"Original / merge without re-encoding","MP4 (Remux, nur kompatible Codecs)":"MP4 (remux, compatible codecs only)","Vorhandene Untertitel als separate Dateien übernehmen":"Include existing subtitles as separate files","Nach erfolgreichem Download im Editor öffnen":"Open in editor after successful download","Download vorbereiten":"Prepare download","Import speichern":"Save import","Videoimport wird vorbereitet":"Preparing video import","Videoimport abgeschlossen":"Video import complete","Titel unbekannt":"Unknown title","Kanal unbekannt":"Unknown channel","Sprache unbekannt":"Unknown language","unbekannt":"unknown","Dauer: ":"Duration: ","Video importiert: ":"Video imported: ","Größe unbekannt":"Size unknown","Ton vorhanden":"Audio available","Keine Tonspur verfügbar":"No audio track available","Videoimport · ":"Video import · ","FFmpeg-Merge":"FFmpeg merge","Videoimport · %p %":"Video import · %p %","Bis":"Up to","Maximal":"Maximum","geschätzt %.2f GiB":"estimated %.2f GiB"})
CATALOG['Importdatei prüfen']='Verify imported file'
CATALOG.update({"Audioquellen · Originalspuren":"Audio sources · original tracks","Liest vorhandene Container-Audiospuren. Rollen sind manuelle Zuordnungen, keine KI-Erkennung. Eine einzelne Mixspur enthält nicht automatisch getrennte Stems.":"Reads existing container audio tracks. Roles are assigned manually, not by AI. A single mixed track does not automatically contain separate stems.","Kanäle":"Channels","Sprache":"Language","Titel":"Title","Start (s)":"Start (s)","Rolle (manuell)":"Role (manual)","Nicht zugeordnet":"Unassigned","Originalmix":"Original mix","Mikrofon":"Microphone","Spielton":"Game audio","Musik":"Music","Sonstiges":"Other","Audiospuren werden geprüft …":"Checking audio tracks …","Ausgewählte Spur als WAV extrahieren …":"Extract selected track as WAV …","KI-Audiotrennung …":"AI audio separation …","Für Whisper wählen":"Select for Whisper","KI-Sprachspur für Whisper wählen …":"Select AI speech track for Whisper …","Whisper: Standardspur":"Whisper: default track","Extrahierte WAV auf Timeline":"Add extracted WAV to timeline","Schließen / Abbrechen":"Close / cancel","Abbrechen / Schließen":"Cancel / close","Rekonstruierte Sprachspur":"Reconstructed speech track","Ordner für extrahierte Audiospur":"Folder for extracted audio track","Extrahiere PCM-Audio mit Originalzeitbasis …":"Extracting PCM audio on the original time base …","Abbruch läuft …":"Cancelling …","Audio-Studio · KI-Stems":"Audio studio · AI stems","Erzeugt neue Spuren/Dateien und deaktiviert Originalton in der Komposition. Andere vorhandene Audiospuren bleiben aktiv; prüfe mögliche Doppelungen. Effekte werden in eine neue WAV gerendert; Originale bleiben unverändert.":"Creates new tracks/files and disables original audio in the composition. Other audio tracks remain active; check for duplicates. Effects are rendered to a new WAV; originals remain unchanged.","Getrennte Spuren mit editierbarem Pegel":"Separate tracks with editable gain","Bearbeiteten Mix als neue WAV":"Processed mix as new WAV","Ausgabe":"Output","KI-Stimme":"AI voice","Restton":"Residual audio","Sprach-Cleanup (Hochpass/Rauschminderung)":"Speech cleanup (high-pass/noise reduction)","Restton bei Sprache absenken (Sidechain)":"Duck residual audio during speech (sidechain)","Loudness-Ziel -16 LUFS / -1,5 dBTP (WAV, nicht MP4-Garantie)":"Loudness target -16 LUFS / -1.5 dBTP (WAV, not an MP4 guarantee)","Quellzuordnung wird vor der Übernahme geprüft.":"Source mapping is checked before applying.","Verarbeiten und übernehmen":"Process and apply","Ordner für neuen Audiomix":"Folder for new audio mix","Prüfe und verarbeite Audio …":"Checking and processing audio …","ASR-Qualität · auffällige Zeilen":"ASR quality · flagged lines","Heuristische Prüfsignale, keine kalibrierte Fehlerwahrscheinlichkeit. Keine automatische Löschung.":"Heuristic review signals, not calibrated error probabilities. No automatic deletion.","Zeit (s)":"Time (s)","Prüfsignal":"Review signal","Automatisch (Sprachwechsel möglich)":"Automatic (language switching possible)","Deutsch":"German","Englisch":"English","Optionale Spielbegriffe / Namen":"Optional game terms / names","Ausgewählte Zeile erneut transkribieren":"Transcribe selected line again","Zweittranskription prüfen und ggf. korrigieren":"Review and correct second transcription","Geprüften Text übernehmen":"Apply reviewed text","Lokale Nachprüfung …":"Local recheck …","Vorschlag prüfen · ursprüngliche Zeitgrenzen bleiben erhalten":"Review proposal · original time boundaries remain unchanged","Untertitel · Sprachzeiten prüfen":"Subtitles · review speech timing","VAD-Korrekturvorschläge. Alte/unbekannte und manuell bearbeitete Zeilen bleiben geschützt. Wortzeiten bleiben standardmäßig unverändert; unsichere oder fehlende Sprachsignale werden nicht erzwungen korrigiert.":"VAD correction suggestions. Old/unknown and manually edited lines remain protected. Word timings remain unchanged by default; uncertain or missing speech signals are not forcibly corrected.","Lesbarkeits-Nachlauf (s)":"Reading-time padding (s)","Überlange Randwörter als VAD-Schätzung vorschlagen (kein Forced Alignment)":"Suggest overlong edge-word adjustments using VAD (not forced alignment)","Statt Randkorrekturen: Teilung an bestätigten Sprechpausen (Wortzeiten bleiben erhalten)":"Instead of edge corrections: split at confirmed pauses (word timings preserved)","Bisher (s)":"Previous (s)","Vorschlag (s)":"Proposed (s)","Kürzung (s)":"Reduction (s)","Begründung":"Reason","Lokale Sprachaktivität wird ermittelt …":"Detecting local speech activity …","Markierte Vorschläge übernehmen":"Apply selected suggestions","Branding · Untertitel":"Branding · subtitles","Gestaltung gilt für dieses Projekt. Die Render-Vorschau zeigt den tatsächlichen Export. Animierte Wörter nutzen vorhandene Wortzeiten; keine neue Whisper-Analyse.":"Style applies to this project. The render preview shows the actual export. Animated words use existing word timings; no new Whisper analysis.","Benutzerdefiniert":"Custom","Klassisch":"Classic","Wort hervorheben":"Highlight word","Pop-Animation":"Pop animation","Szenen-Safe-Zone (Standard)":"Scene safe zone (default)","Oben":"Top","Unten":"Bottom","Vorlage":"Preset","Schrift":"Font","Größe":"Size","Textfarbe #RRGGBB":"Text color #RRGGBB","Akzentfarbe #RRGGBB":"Accent color #RRGGBB","Kontur #RRGGBB":"Outline #RRGGBB","Wörter pro Gruppe":"Words per group","Untertitel übersetzen · lokal":"Translate subtitles · local","Original bleibt unverändert. Sprachcode und passendes gerichtetes Marian-Modell wählen. Übersetzungen übernehmen Abschnittszeiten, keine erfundenen Wortzeiten.":"The original stays unchanged. Select a language code and matching directional Marian model. Translations use segment timings, not invented word timings.","Zielsprache (z. B. de, en)":"Target language (e.g. de, en)","Quellzeit":"Source time","Übersetzung":"Translation","Sprache laden":"Load language","Fehlende Texte lokal übersetzen …":"Translate missing texts locally …","Original aktivieren":"Activate original","Ungültiger Sprachcode":"Invalid language code","Bitte zuerst Sprache laden.":"Load a language first.","Lokalen Marian-Modellordner auswählen":"Select local Marian model folder","Text und Callout gestalten":"Design text and callout","Sprechblase":"Speech bubble","Pfeil":"Arrow","Rechteck":"Rectangle","Rechts":"Right","Links":"Left","Hintergrund füllen":"Fill background","Typ":"Type","Textfarbe":"Text color","Hintergrund":"Background","Akzent":"Accent","Pfeilrichtung":"Arrow direction","Füllung":"Fill","Schriftgröße":"Font size","Ende (s)":"End (s)","X (relativ)":"X (relative)","Y (relativ)":"Y (relative)","Breite":"Width","Höhe":"Height","Deckkraft":"Opacity","Grafikvorschau aktualisieren":"Refresh graphic preview","Position im Ausgabeformat, nach dem Kamera-Crop. Die Grafikvorschau zeigt das Element, die Render-Vorschau anschließend den vollständigen Clip.":"Position in the output format after camera crop. The graphic preview shows the element; the render preview shows the complete clip.","Callout prüfen":"Check callout","Szenenauswahl":"Scene selection","Szenen bearbeiten · Reihenfolge entspricht der geplanten Ausgabe.\nOriginal bleibt unverändert; Manuell erhält die markierte Region, Fester Crop füllt das Zielformat.":"Edit scenes · order matches the planned output.\nThe original stays unchanged; manual retains the selected region, fixed crop fills the output format.","Quellbild am Schnittpunkt laden":"Load source frame at cut point","Bildregion mit der Maus aufziehen; Koordinaten bleiben editierbar.":"Drag a region with the mouse; coordinates remain editable.","In Ausgabe einschließen":"Include in output","Manuell":"Manual","Automatisch":"Automatic","Fester Crop":"Fixed crop","In (Quellsekunden)":"In (source seconds)","Out (Quellsekunden)":"Out (source seconds)","Kameramodus":"Camera mode","Region Breite":"Region width","Region Höhe":"Region height","Schnittpunkt (Quellsekunden)":"Cut point (source seconds)","Teilen":"Split","Nach oben":"Move up","Nach unten":"Move down","Subject-Punkt gewählt · Smart Director öffnen und Subject Lock starten":"Subject point selected · open Smart Director and start subject lock","Schnittpunkt muss innerhalb der Szene liegen.":"Cut point must be inside the scene.","Quellbild wird geladen …":"Loading source frame …","Quellbild konnte nicht angezeigt werden.":"Source frame could not be displayed.","Bildabruf wird abgebrochen; danach Dialog schließen.":"Cancelling frame retrieval; close dialog afterwards.","Szenenänderung nicht möglich":"Scene change not possible","Szenenplan nicht gespeichert":"Scene plan not saved","Füllen / Crop":"Fill / crop","Einpassen":"Fit","Clip-Zeit nach Szenenreihenfolge (s)":"Clip time after scene ordering (s)","Zuerst Frame aus dem gerenderten Clip laden.":"Load a frame from the rendered clip first.","Rendert das vollständige gewählte Highlight (max. 60 s). Die Bildzeit bezieht sich auf den fertigen Clip, nicht das Original.":"Renders the entire selected highlight (max. 60 s). Frame time refers to the finished clip, not the original.","Renderframe laden":"Load rendered frame","Design aktualisieren":"Refresh design","PNG / JPEG speichern …":"Save PNG / JPEG …","Clip wird gerendert …":"Rendering clip …","Bildzeit geändert. Bitte neuen Renderframe laden.":"Frame time changed. Load a new rendered frame.","Thumbnail speichern":"Save thumbnail","Gespeichert: ":"Saved: ","Eigene Highlight-Wörter":"Custom highlight words","Standardwörter pflegt StreamClipper. Hier kannst du eigene Ausdrücke hinzufügen oder deren Priorität überschreiben. Keine Regex nötig.":"StreamClipper maintains default words. Add custom expressions or override their priority here. No regex required.","Ausdruck":"Expression","Kategorie":"Category","Priorität":"Priority","Diese Liste ist fest in der aktuellen StreamClipper-Version enthalten. Eigene Begriffe können ihre Priorität überschreiben.":"This list is built into the current StreamClipper version. Custom terms can override their priority.","Eigene Wörter":"Custom words","Standardliste":"Default list","z. B. Nicht dein Ernst!":"e.g. Are you serious!","Wort oder Satz":"Word or phrase","Hinzufügen / Auswahl ersetzen":"Add / replace selection","Neue Eingabe":"New entry","Ausgewählten Eintrag löschen":"Delete selected entry","Die Liste wird nur für zukünftige Analysen verwendet. Vorhandene Highlights bleiben unverändert.":"This list is used only for future analyses. Existing highlights remain unchanged.","Ungültiger Ausdruck":"Invalid expression","Konnte Wortliste nicht speichern":"Could not save word list","Montage · bestehende Editor-Komposition optional übernehmen":"Montage · optionally use existing editor composition","Projektspuren, Untertitel und Szenenpläne nach aktueller Exportkonfiguration übernehmen":"Include project tracks, subtitles and scene plans using current export settings","Geschwindigkeit":"Speed","Starttempo":"Start speed","Endtempo":"End speed","Abschnitt zu kurz oder zu viele Teile":"Section too short or too many parts","Stützstellen (diskrete Annäherung)":"Samples (discrete approximation)","Kurve:":"Curve:","Rampe":"Ramp","Kontinuierliche Tempoänderung":"Continuous speed change","Natürliche Tempoänderung":"Natural speed change","Bild und Ton werden kontinuierlich beschleunigt/verlangsamt; die Tonhöhe ändert sich dabei. Für Tonhöhenkorrektur die bisherige diskrete Rampe nutzen. Übernehmen?":"Video and audio speed change continuously; pitch changes too. Use the stepped ramp for pitch correction. Apply?","Montage-Vorschau":"Montage preview","Dauer am Ende (s)":"Hold duration (s)","Optionaler Text (max. 120 Zeichen):":"Optional text (max. 120 characters):","Farblook oder eigene LUT:":"Color look or custom LUT:","Lokale LUT":"Local LUT","Eigener oder lizenzierter Sound":"Custom or licensed sound","Pegel (dB)":"Gain (dB)","Lokale Bibliothek:":"Local library:","Sound importieren":"Import sound","Soundname":"Sound name","Eigene Aufnahme / Lizenz / Quellenhinweis:":"Own recording / license / source note:","Montageplan geändert":"Montage plan changed","Geänderter Plan: Editor-Kompositionen aus der aktuellen Sitzung neu erstellen?":"Plan changed: rebuild editor compositions from the current session?","Montageplan speichern":"Save montage plan","Montageplan öffnen":"Open montage plan","Montageplan":"Montage plan","Vorschau maximal 45 Sekunden; einzelnen kürzeren Abschnitt wählen.":"Preview limited to 45 seconds; select a shorter section.","Neuaufbau abgebrochen":"Rebuild cancelled","Montageplan gehört zu anderer Aufnahme":"Montage plan belongs to another recording","Ausgabezeit vor optionalem Szenenplan-Trim; Klick wählt Montageabschnitt":"Output time before optional scene-plan trim; click to select a montage section","Montage-Zeitachse (vor Szenenplan-Trim)":"Montage timeline (before scene-plan trim)","Highlights hinzufügen":"Add highlights","Montage-Vorschau rendern":"Render montage preview","Exportgetreue Vorschau wird erstellt …":"Rendering export-accurate preview …","Montage · exportgetreue Vorschau":"Montage · export-accurate preview"})
REVERSE={v:k for k,v in CATALOG.items()}
# Translation is presentation only. Never translate arbitrary file names,
# imported titles, transcript content, table data, IDs or combo userData.
_english=False

def tr(value,english=None):
    if not isinstance(value,str):return value
    return CATALOG.get(value,value) if (_english if english is None else english) else value

def preference_path():
    return installation_directory()/"data"/"settings"/"language.json"

def load_preference(path=None):
    try:
        p=Path(path or preference_path())
        if p.stat().st_size>4096:return False
        return json.loads(p.read_text(encoding="utf-8")).get("language")=="en"
    except (OSError,ValueError,TypeError,AttributeError):return False

def save_preference(english,path=None):
    atomic_json(Path(path or preference_path()),{"schema_version":1,"language":"en" if english else "de"})

def apply_language(window,english,*,persist=True):
    global _english
    from PySide6.QtWidgets import QAbstractButton,QLabel,QComboBox,QTabWidget,QGroupBox,QDockWidget,QTableWidget,QLineEdit,QTextEdit,QPlainTextEdit
    from PySide6.QtGui import QAction
    _english=bool(english)
    def present(obj,key,value,setter):
        prop="_sc_lang_"+key
        original=obj.property(prop)
        if original is None:
            if value not in CATALOG:return
            original=value;obj.setProperty(prop,original)
        # Do not rewrite dynamic state or user-supplied data when it changed.
        if value in (original,CATALOG[original]):
            setter(CATALOG[original] if _english else original)
    present(window,"title",window.windowTitle(),window.setWindowTitle)
    for obj in window.findChildren(QAbstractButton):
        present(obj,"text",obj.text(),obj.setText)
    for obj in window.findChildren(QLabel):
        if obj in (getattr(window,"caption_overlay",None),getattr(window,"source_label",None)):continue
        present(obj,"text",obj.text(),obj.setText)
    for obj in window.findChildren(QAction):
        present(obj,"text",obj.text(),obj.setText)
    for typ in (QGroupBox,QDockWidget):
        for obj in window.findChildren(typ):
            if typ is QGroupBox:present(obj,"title",obj.title(),obj.setTitle)
            else:present(obj,"title",obj.windowTitle(),obj.setWindowTitle)
    for obj in window.findChildren(QTabWidget):
        for i in range(obj.count()):present(obj,"tab"+str(i),obj.tabText(i),lambda s,i=i:obj.setTabText(i,s))
    # Only static combos with stable userData; workspace uses German keys.
    for attr in ("hardware_mode","mode","encoder_mode","proxy_mode"):
        obj=getattr(window,attr,None)
        if obj is None:continue
        blocked=obj.blockSignals(True)
        try:
            for i in range(obj.count()):present(obj,"item"+str(i),obj.itemText(i),lambda s,i=i:obj.setItemText(i,s))
        finally:obj.blockSignals(blocked)
    for obj in window.findChildren(QTableWidget):
        for i in range(obj.columnCount()):
            item=obj.horizontalHeaderItem(i)
            if item:present(obj,"header"+str(i),item.text(),item.setText)
    for typ in (QLineEdit,QTextEdit,QPlainTextEdit):
        for obj in window.findChildren(typ):present(obj,"placeholder",obj.placeholderText(),obj.setPlaceholderText)
    if persist:save_preference(_english)
    window.statusBar().showMessage("English interface (partial)" if _english else "Deutsche Oberfläche")

def english_enabled():return _english
