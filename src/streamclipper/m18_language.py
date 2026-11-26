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
