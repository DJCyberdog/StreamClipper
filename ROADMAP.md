# StreamClipper – Verbindliche Produkt-Roadmap

> **Owner-Beschluss vom 22.11.2026, fortgeschrieben: alle S–D-Features vor 1.0 · Verbindliche Zielplanung · Primärdokument: `/ROADMAP.md`**
>
> Bei Widersprüchen mit älteren Aufgaben und `docs/ROADMAP.md` gilt **diese Datei**. Änderungen der Tier-Prioritäten, Freigabe von D-Tier, Streichung von F-Tier-Ausschlüssen oder Umstellung der Release-Gates benötigen einen dokumentierten Owner-Beschluss.

## 1. Produktziel und verbindliche Grundsätze

**StreamClipper Studio**: Ein offline-first Windows-Produktionsstudio, das längere Gaming-, OBS- und Twitch-Aufnahmen in nachvollziehbare Highlight-Vorschläge, manuell editierbare Szenen und veröffentlichungsfertige Videos verwandelt. Kernversprechen: **Your Stream. Your Highlights. Your Control.**

- **Lokal zuerst:** Analyse, Editieren und Export ohne Video-Upload/Cloud-Zwang. Online nur nach ausdrücklicher Aktion (z. B. Twitch-VOD-URL-Import, Modell-Download, autorisiertes Publishing).
- **Manueller Vorrang:** KI schlägt vor, Nutzende entscheiden. Manuelle Highlight-, Wort-, Szenen-, Overlay- und Kamera-Edits werden nicht durch Automatik überschrieben.
- **Keine erfundenen Fakten:** Audio, CLIP, Bewegungs-/Objekt-Tracklets und Sprachmuster sind erklärbare **Evidenz**, keine sichere Ereignisdiagnose, keine kalibrierte Viralitätsvorhersage.
- **Nichtdestruktiv und updatefest:** Originalvideos niemals überschreiben; bearbeitete Transkripte, User-Wörter, Szenen und OBS-Profile bleiben erhalten.
- **Referenzsystem:** Windows 11, i5-11400F, 16 GB RAM, RTX 5060 Ti 16 GB; Basisfunktionen ohne GPU/Cloud. Mindestens **6 Stunden VOD** mit begrenztem RAM-/VRAM-Verbrauch.
- **Keine ungefragte Veröffentlichung, keine stillen Modell-Downloads.** Explizite Zustimmung für externe Aktionen.
- **Reproduzierbare Entwicklung:** Kleine PRs, Unit-/Integrationstests, reale Windows-/GPU-Tests, dokumentierte Fehlalarme, Risiken und Lizenzprüfung.

## 2. Verbindliche Tierlist – 60 Hauptfeatures

**10 bisherige + genau 50 neue (#01–#50)**. Die sieben Teilfunktionen von A-11 sowie die manuelle Szenenauswahl sind Bestandteile ihrer Hauptfeatures und erhöhen die Anzahl nicht. **S** = Kernqualität, **A** = Premiumkreativität, **B** = Produktionswerkzeuge, **C** = Komfort, **D** = niedrig priorisiert, **aber vor 1.0 eingeplant**, **F** = bewusst ausgeschlossen und als Negativanforderung zu prüfen. Die Tierliste beschreibt Priorität; die **Meilensteine bündeln fachlich verwandte Arbeit unabhängig vom Tier**.

### S-Tier – 11 Hauptfeatures (3 bisherige, 8 neue)

**Kernqualität, vor Release 1.0 abzunehmen.**

| ID | Feature | Umfang |
|---|---|---|
| S-B1 | **Professionelle Timeline** | Wellenform, Zoom, Schnittgrenzen, Clip-Vorschau; M6-Prototyp |
| S-B2 | **Wortgenaue Untertitel** | Whisper-Wortzeiten; Text/Zeiten direkt an Highlights in der Timeline editierbar; M7-Prototyp |
| S-B3 | **Intelligente Gameplay-Erkennung** | Erklärbare Sprach-, Audio-, CLIP-, Bewegungs- und Objektspuren; M8–M10-Prototypen |
| #01 | **Exportgetreue Live-Vorschau** | Szenen, Crop, Keyframes, Untertitel und Effekte wie im MP4 |
| #02 | **Mehrspur-Timeline** | Gameplay, Mikrofon, Musik, Untertitel und Overlays getrennt |
| #03 | **Undo/Redo** | Verlässliche Bearbeitungshistorie |
| #04 | **Crash Recovery & Autosave** | Editorzustand sicher wiederherstellen; kein umfangreiches Projektmanagement |
| #05 | **Proxy-Editing** | Flüssige Vorschau bei langen/hochaufgelösten VODs |
| #06 | **GPU-Export-Engine** | NVENC H.264/HEVC mit geprüften Fallbacks |
| #07 | **Automatische Exportkontrolle** | Schwarze Frames, Audiopegel, Untertitel-Safe-Zones, Ausgabedatei prüfen |
| #08 | **Render-Warteschlange** | Mehrere Exporte, Abbruch, Fortschritt, Wiederholung, sichere Teilergebnisse |

### A-Tier – 14 Hauptfeatures (2 bisherige, 12 neue)

**Premium-Kreativfunktionen.**

| ID | Feature | Umfang |
|---|---|---|
| A-B1 | **Smart Director** | Automatische und manuelle szenenweise Kamerasteuerung, manuelle Entscheidung vor KI |
| A-B2 | **Branding Studio** | Vorlagen, Logos, Untertitelstile, Farben und Stream-Gestaltung |
| #09 | **Subject Lock** | Fahrzeug/Person in der Videovorschau als Tracking-Ziel wählen |
| #10 | **Kamera-Keyframes** | Crop, Kameraposition, Zoom und Übergänge pro Szene |
| #11 | **HUD-, Overlay- und Safe-Zone-Management (A-11)** | Spiel-HUD **und** Twitch-/OBS-Overlays; siehe verbindliche Erweiterung |
| #12 | **Gameplay + Facecam Layouts** | Split-Screen, Picture-in-Picture und frei positionierte Kamera |
| #13 | **KI-Audiotrennung** | Sprach-/Spielaudio aus Mischspuren, mit Qualitätswarnung |
| #14 | **Loudness Normalization** | Einheitliche wahrgenommene Lautstärke, True-Peak-Kontrolle |
| #15 | **Mikrofonbereinigung** | Rauschen, Brummen, Störgeräusche reduzieren |
| #16 | **Smart Silence Removal** | Pausenvorschläge mit manueller Kontrolle |
| #17 | **Duplicate Highlight Detection** | Überschneidungen und ähnliche Clips erkennen |
| #18 | **Highlight Feedback Learning** | Lokal aus angenommenen/verworfenen Vorschlägen lernen |
| #19 | **Animated Word Captions** | Wortweise Untertitelanimation und Hervorhebung |
| #20 | **Game-Specific Intelligence** | Messbare Profile für GTA, Shooter, Rennspiele, Minecraft usw. |

### B-Tier – 15 Hauptfeatures (2 bisherige, 13 neue)

**Produktion und Veröffentlichung.**

| ID | Feature | Umfang |
|---|---|---|
| B-B1 | **Montage Builder** | Best-of aus mehreren Highlights und manueller Reihenfolge |
| B-B2 | **Publishing Center** | Vorbereitung und nur ausdrücklich freigegebenes Veröffentlichen |
| #21 | **Hook Generator** | Einstieg aus geeigneten Highlight-Momenten vorschlagen |
| #22 | **Auto Chapters** | Aufnahmen grob in Spielabschnitte gliedern |
| #23 | **Subtitle Translation** | Lokal übersetzen und manuell korrigieren |
| #24 | **Speed Ramping** | Variable Geschwindigkeit innerhalb eines Clips |
| #25 | **Freeze Frame Effects** | Standbild mit Zoom und Text |
| #26 | **Musik-Ducking** | Musik während Sprache absenken |
| #27 | **Sound Effects Library** | Eigene oder lizenziert verfügbare Sounds |
| #28 | **Text- und Callout-Editor** | Pfeile, Sprechblasen, Bildmarkierungen |
| #29 | **Color-Grading & LUTs** | Farbkorrektur und wiederverwendbare Looks |
| #30 | **Thumbnail Designer** | Vorschaubilder aus Clips gestalten |
| #31 | **Clip-Length Variants** | 15-, 30- und 60-Sekunden-Versionen |
| #32 | **A/B Clip Variations** | Mehrere Einstiege, Stile, Ausschnitte vergleichen |
| #33 | **Voice-over Recording** | Kommentar direkt auf die Timeline aufnehmen |

### C-Tier – 10 Hauptfeatures (0 bisherige, 10 neue)

**Komfort und Integrationen.**

| ID | Feature | Umfang |
|---|---|---|
| #34 | **OBS Live Markers** | Während des Streamings Zeitmarken setzen |
| #35 | **Stream Deck Integration** | Tasten für Markierungen und Editing |
| #36 | **Custom Keyboard Shortcuts** | Eigene Tastenkombinationen |
| #37 | **NLE Export** | EDL/XML für kompatible externe Schnittprogramme |
| #38 | **Speaker Diarization** | Sprecher auseinanderhalten |
| #39 | **Visual Contact Sheets** | Übersichten aus Vorschaubildern |
| #40 | **Performance Benchmarking** | Modellgeschwindigkeit, GPU-/RAM-Nutzung messen |
| #41 | **Mehrsprachige Oberfläche** | Deutsch/Englisch und später weitere |
| #42 | **GIF- und WebM-Export** | Alternative Kurzformat-Ausgaben |
| #43 | **Watch Folders** | Neue lokale Aufnahmen erkennen |

### D-Tier – 8 Hauptfeatures (3 bisherige, 5 neue)

**Niedrige Priorität, durch den aktuellen Owner-Beschluss aber vollständig vor 1.0 eingeplant.** Die D-Tier-Einstufung bleibt bestehen; die bisherige Verschiebung auf 2.0 wird aufgehoben.

| ID | Feature | Umfang |
|---|---|---|
| D-B1 | **Projektverwaltung mit Checkpoints** | Umfangreiche Projektverwaltung und Analysefortsetzung; **nicht** Autosave/Datenintegrität |
| D-B2 | **Twitch-Chat-Analyse** | Chat-Reaktionen als Highlight-Signale |
| D-B3 | **Durchsuchbares Video** | Semantische Suche in Bild/Transkript |
| #44 | **Cloud Review** | Cloud-basierte gemeinsame Sichtung |
| #45 | **Cloud Synchronization** | Projekte zwischen Rechnern synchronisieren |
| #46 | **Content Performance Analytics** | Reichweiten-/Engagementanalyse |
| #47 | **Mobile Companion App** | Mobil sichten/freigeben |
| #48 | **Automatic Channel Ingestion** | Neue Twitch-/Kick-/YouTube-Videos automatisch importieren |

### F-Tier – 2 Hauptfeatures (0 bisherige, 2 neue)

**Bewusst ausgeschlossen.**

| ID | Feature | Umfang |
|---|---|---|
| #49 | **Verpflichtende Cloud-Verarbeitung** | Widerspricht Offline-first |
| #50 | **Ungefragtes automatisches Publishing** | Ohne ausdrückliche Freigabe niemals veröffentlichen |

## 3. Verbindliche Erweiterung von A-11 (Feature #11)

**Wichtig:** A-11 ist *nicht* auf Twitch-Overlays reduziert worden. Der bisherige Umfang für Spiel-HUDs und Safe-Zones bleibt bestehen; Twitch-/OBS-Overlays kommen **zusätzlich** hinzu. **A-11 (Feature)** und **M13 (neuer fachlich zugehöriger Meilenstein)** sind verschiedene Kennungen.

- **A-11a – Erkennung:** Spiel-HUDs **und** Twitch-/OBS-Overlays, einschließlich Top-Bar, Chatbox, Facecam, Stream-Grafiken und Alerts.
- **A-11b – Manuelle Overlay-Zonen:** Regionen markieren, verschieben, deaktivieren und für einzelne Szenen anpassen.
- **A-11c – Safe-Zones:** Untertitel und relevante Spielinhalte so anordnen, dass Plattform-UI und Overlays sie nicht unbrauchbar machen.
- **A-11d – Tatsächliche Overlay-Entfernung:** Maskierung und optional zeitlich konsistentes KI-Inpainting. **M13d, vor Release 1.0**; fortgeschrittene Opt-in-Funktion mit dokumentierten Qualitätsgrenzen.
- **A-11e – Twitch Overlay-Aware Smart Cropping:** Der Kameraausschnitt schließt OBS-Top-Bar, Chat, Facecam usw. soweit geometrisch möglich durch **Zuschneiden statt KI-Retuschieren** aus.
- **A-11f – OBS-Layout-Profile:** Wiederverwendbare Sperrzonen für verschiedene Stream-Szenen/OBS-Layouts (z. B. Top-Bar oben, Chat rechts).
- **A-11g – Dynamische Sperrzonen:** Vorübergehende Alerts/Einblendungen während eines Clips berücksichtigen, Unsicherheit anzeigen.

**Präferenz:** Wegschneiden vor Maskierung vor Inpainting. Falls ein 9:16-/16:9-Crop die Overlays nicht vollständig entfernen *und* die relevante Szene bewahren kann, wird der Konflikt angezeigt; keine perfekte unsichtbare Entfernung behaupten.

## 4. Technischer Ist-Stand: M0–M10

Vorhandene *experimentelle* Implementierungen umfassen Audio-Highlighting, nichtdestruktiven Videoexport, lokale Whisper-/CLIP-Analyse, manuelle Highlights, öffentlichen Twitch-VOD-Import, Audio-Timeline, Word-Level-Untertitel, zeitliche Gameplay-Evidenz, optionale DETR-/RT-DETR-Tracklets, Modellwahl und ein gepflegtes deutsch-/englisches Sprachlexikon.

**Stand 22.11.2026:** M6–M10 liegen auf **gestapelten offenen Draft-PRs #26–#30**. Das ist **keine** bestätigte vollständige Integration auf `main`, kein gesamter Windows-Praxistest und kein Stable-Release. Frühere Detailprüfungen stehen in `docs/ROADMAP.md` (historisches Prüfdokument). Immer zwischen **Code vorhanden**, **Tests bestanden**, **unter Windows abgenommen** und **releasefähig** unterscheiden.

## 5. Vereinfachte Meilensteinfolge – **alles vor 1.0**

**Owner-Änderung vom 22.11.2026:** Die 60 Hauptfeatures werden **nach zusammengehörigem Arbeitsbereich** statt nach Tier abgearbeitet. S/A/B/C/D bleiben **Prioritätsstufen innerhalb** der jeweiligen Meilensteine. **Alle 58 umsetzbaren S–D-Features sind vor 1.0 verpflichtend eingeplant.** D bleibt niedrig priorisiert und wird nach den essenziellen Teilen seines Meilensteins umgesetzt, ist aber **nicht mehr auf 2.0 verschoben**. Die zwei F-Tier-Ideen werden nicht implementiert und vor Release als Negativanforderungen geprüft.

| Milestone | Zusammengehöriger Bereich | Zugeordnete Feature-IDs nach Tier | Definition of Done |
|---|---|---|---|
| **M10.5** | Integration & Baseline | Bestehende Arbeit konsolidieren (keine zusätzlichen IDs) | Eine konsistente, start- und updatefähige Baseline ohne Import-/Modulkonflikte. |
| **M11** | Editor, Timeline & Datenhaltung | S: S-B1, #02, #03, #04, #05 · C: #36 · D: D-B1 | Sechsstündiges VOD flüssig navigieren, Schnitte/Spuren editieren und nach Neustart inkl. Checkpoints wiederherstellen. |
| **M12** | Preview, Render & Export-Engine | S: #01, #06, #07, #08 | Crop, Effekte und Untertitel laufen durch dieselbe Exportlogik; reproduzierbare Preview/Render-Vergleiche und geprüfte Job-Abbrüche. |
| **M13** | Szenen, Smart Director & Overlays | A: A-B1, #09, #10, #11, #12 | Je Szene manuelle/automatische Kamera, 9:16-/16:9-Crop, Sperrzonen, Profile und Rendervergleich; manuelle Vorgaben haben Vorrang. |
| **M14** | Untertitel, Branding & visuelle Gestaltung | S: S-B2 · A: A-B2, #19 · B: #23, #28, #30 | Untertitel/Text/Grafiken inklusive Übersetzung werden ohne neue Whisper-Analyse korrigiert und exportgetreu dargestellt. |
| **M15** | Audio & Sprache | A: #13, #14, #15, #16 · B: #26, #33 · C: #38 | Reproduzierbare Audiomischung ohne Quellenüberschreibung, verständliche Artefakt-/Lautstärkewarnungen. |
| **M16** | Gaming Intelligence, Review & Suche | S: S-B3 · A: #17, #18, #20 · C: #39, #40 · D: D-B2, D-B3 | Annotierte Spielszenen evaluieren, Chat/Suche optional halten, Treffer und Fehlalarme statt unvalidierter KI-Behauptungen messen. |
| **M17** | Montage, Effekte & Clip-Varianten | B: B-B1, #21, #22, #24, #25, #27, #29, #31, #32 | Mehrere Highlights mit bewusst gewählter Reihenfolge und Effekten zu stabilen Exportvarianten zusammenstellen. |
| **M18** | Stream-Workflow & Integrationen | C: #34, #35, #37, #41, #42, #43 · D: #48 | Import/Marker/Exporte funktionieren nachvollziehbar; externe Zugriffe sind explizit aktivierbar und widerrufbar. |
| **M19** | Publishing, Zusammenarbeit & Reichweite | B: B-B2 · D: #44, #45, #46, #47 | Bewusste Veröffentlichung, nachvollziehbare Freigaben, Rechte- und Datenschutzkontrollen; offline vollständig nutzbare Basis. |
| **M20** | Feature Freeze, Gesamt-Abnahme & 1.0 | F: #49, #50 | Alle 58 umsetzbaren Features aus S–D abgenommen oder ausdrücklich durch Owner neu beschlossen; beide F-Prinzipien nachweislich nicht implementiert; erst dann 1.0 Stable. |

**Vollständigkeitsnachweis:** 11 S-Features, 14 A-Features, 15 B-Features, 10 C-Features, 8 D-Features und 2 F-Ausschlüsse = **60 eindeutige Kennungen**. **58 zu implementierende** Funktionen + **2 dauerhaft ausgeschlossene** Funktionen. Jeder Hauptfeature-ID ist **genau ein führender Milestone** zugewiesen; Vorarbeiten und Integration dürfen milestoneübergreifend stattfinden, ohne die Zuordnung zu doppeln. Alle S–D-Features sind im Scope von **StreamClipper 1.0**.

### 5.1 Meilensteinregeln und Abhängigkeiten

1. **M10.5 zuerst:** Bestehende gestapelte Code-PRs integrieren und mit realen Windows-Daten testen, bevor neue komplexe Workflows darauf aufbauen.
2. **M11 (Editor) → M12 (Render-Vertrag) → M13 (Kamera):** Persistente Timeline-/Szenenstruktur und verlässliche Renderpipeline sind Voraussetzung für den Smart Director. M12 stellt die exportgetreue Grundlage bereit; M13 und M14 erweitern und verifizieren sie für ihre jeweiligen Effekte.
3. **M14 (Captions) und M15 (Audio) → M16 (Intelligence):** Korrigierte Sprachdaten und Audiosignale können für hochwertige, nachvollziehbare Analyse genutzt werden.
4. **M17 (Montage) → M19 (Publishing):** Clips müssen vollständig bearbeitbar und exportierbar sein, bevor sie über Dienste veröffentlicht werden.
5. **M18 (Integrationen) und M19 (Online):** Netzwerkabhängige D-Tier-Funktionen sind **opt-in**. Keine verpflichtende Kontoverknüpfung, keine Cloud-Abhängigkeit der Basisapp.
6. **M20 ist kein zusätzlicher Feature-Bucket:** Erst ein Gesamt-Regressionstest, Windows-End-to-End-Abnahme und nachweislich bestandene F-Tier-Schutzregeln erlauben den Release.
7. **Kein D-Tier-Schlupfloch:** Ein niedrig priorisiertes Feature bleibt zwar innerhalb seines Milestones nachrangig, wird aber nicht still auf „nach 1.0“ verschoben. Soll es doch entfallen, ist ein **neuer Owner-Beschluss** erforderlich.

### 5.2 M11 – Editor, Timeline & Projektlebenszyklus

- Eine Timeline mit mehreren Spuren, zuverlässigem Undo/Redo, Proxy-Medien und nutzbaren Shortcuts.
- Autosave/Crash Recovery (**#04**) und vollwertige Projektverwaltung mit Analyse-Checkpoints (**D-B1**) als **getrennte** Leistungsmerkmale im gleichen Editor-Datenmodell.
- Lange Aufnahmen navigieren und Clipgrenzen editieren, ohne Videos erneut zu transkribieren; Datei- und Projektzustand nichtdestruktiv speichern.

### 5.3 M12 – Vorschau & gemeinsame Renderpipeline

- Rendergraph/-Parameter für Vorschau und MP4-Export gemeinschaftlich definieren (**#01**).
- NVENC (H.264/HEVC), sichere CPU-Fallbacks, stapelbare Renderjobs und Exportqualitätsprüfung (**#06–#08**).
- Die Vorschau darf nicht nur „ungefähr“ stimmen: Kamerafahrt- und Untertiteltests werden in **M13/M14** gegen denselben Rendervertrag erweitert.

### 5.4 M13 – Manuelle Szenen, Smart Director und **vollständiges** A-11

**M13a – Szenenauswahl:** Highlight in mehrere Szenen aufteilen; In/Out, Reihenfolge und Einschluss editieren. Bildregion pro Szene manuell markieren; Modus *Manuell/Automatisch/Fester Crop*. **Manuell vor KI.**

**M13b – Kameraführung:** Subject Lock durch Anklicken, Kamera-Keyframes, Crop-/Zoomkurven und weiche Übergänge; per Szene übersteuerbar.

**M13c – Overlay-aware Cropping:** **Spiel-HUD und Twitch-/OBS-Overlays** erkennen, Sperrzonen, Safe-Zones, OBS-Profile, temporäre Alerts und Facecam-Layouts; nach Möglichkeit wegschneiden, Konflikte zeigen.

**M13d – Overlay Removal:** **A-11d (Maskierung und optionales KI-Inpainting)** gehört **jetzt ebenfalls vor 1.0 zu M13**. Es bleibt eine fortgeschrittene, explizit aktivierte Option mit Qualitätsgrenzen; nicht als verlässliche unsichtbare Rekonstruktion bewerben.

**M13e – Exportgetreue Kamera-Vorschau:** Keyframes, Sperrzonen, Crop und spätere Untertitel gegen tatsächlichen Render abgleichen.

### 5.5 M14–M19 – Domänenweise fertigstellen

- **M14 Untertitel & Branding:** Worttiming, Word Captions, Übersetzung, Callouts und Thumbnails in **einem** Bearbeitungsworkflow.
- **M15 Audio & Sprache:** Mischspuren, Cleanup, Sprechererkennung, Ducking und Voice-over teilen sich die Audiotimeline.
- **M16 Gameplay Intelligence:** Ereignissignale, Spielprofile, Bewertungsfeedback, Dubletten und Kontaktbögen **mit** Twitch-Chat und semantischer Suche, aber optional und nach messbaren Tests.
- **M17 Montage:** Hooks/Kapitel, Geschwindigkeit, Standbilder, Sounds, Farbe, mehrere Längen und A/B-Varianten in einem Montage-Workflow.
- **M18 Streaming-Integrationen:** OBS, Stream Deck, NLE, Tastatur-/Sprachoberfläche, Watch Folders und Kanalimport. **#36 Shortcuts sind bereits M11 zugeordnet**, damit sie von Beginn an editorweit wirken.
- **M19 Publishing & Collaboration:** Veröffentlichung nur mit Freigabe; Cloud Review, Sync, Analytics und Companion App ergänzen den Publishing-Workflow, erzwingen aber **keinen** Cloud-Zugang für lokales Editing.

## 6. Ein einziger Release-Pfad: Alles vor 1.0

| Zielmarke | Zugehörige Meilensteine | Auslieferungszustand |
|---|---|---|
| **0.x – Engineering Preview** | M0–M10.5 | Experimenteller Bestand + konsolidierte, geprüfte Baseline |
| **0.8 – Editor Preview** | M11–M14 | Editor, Rendering, Smart Director inkl. A-11d, Branding und Untertitel |
| **0.9 – Production Preview** | M15–M19 | Audio, Gameplay-KI, Montage, Integrationen, Publishing **einschließlich D-Tier** |
| **1.0 – Stable** | **Erst nach M20** | Vollständige S–D-Abnahme und geprüfte F-Tier-Ausschlüsse |

**Keine bislang geplante Implementierung für M21 oder eine exklusive Post-1.0-/2.0-Featureliste.** Spätere Produktversionen sind offen und werden erst mit neuer Owner-Entscheidung geplant. Diese Roadmap ist ein **Scope-Beschluss**, keine Terminzusage.

## 7. Definition of Done / Release-Gates

Für relevante Meilensteine sind reproduzierbare Nachweise im Issue/PR vorzulegen:

- [ ] Tests für Normalfälle, Fehler, Abbruch und Datenmigration; kein nicht nachvollzogener Branch-Merge.
- [ ] **Reale Windows-11-Abnahme:** GUI starten, mindestens einen vollständigen Workflow durchlaufen, mit installierten optionalen Modellgewichten testen; CI allein ist nicht ausreichend.
- [ ] **Sechsstündiges VOD:** Import, Analyse, Bearbeitung und Export mit dokumentiertem RAM-/VRAM-Verbrauch und ohne unkontrolliertes Speicherwachstum.
- [ ] **Korrekturpersistenz:** Transkript-Wörter/Zeiten, eigene Highlight-Wörter, Kamera-Keyframes und Overlay-Zonen über Neustart und Export erhalten.
- [ ] **Editor-WYSIWYG:** Untertitel, Crop, Safe-Zones und Kamerafahrt anhand tatsächlicher gerenderter Frames verifiziert.
- [ ] **KI-Qualität:** Annotierte GTA-/Gameplay-Szenen, Trefferquote, Fehlalarme, Laufzeit und Klassenbegrenzungen dokumentiert. Kein sicherer „Unfall erkannt“-Claim bei bloßer Heuristik.
- [ ] **Sichere Dateiverarbeitung:** Rohvideo bleibt unverändert; atomare Ausgabe, Abbruch, beschädigte Eingaben und überschreibgeschützte Namen korrekt behandelt.
- [ ] **GPU/Export:** NVENC-/Fallback-Profile, Ton, Untertitel, Ausgabequalität und Clipgrenzen geprüft.
- [ ] **Produktvertrauen:** Kein Cloud-/Download-/Publishing-Zugriff ohne ausdrückliche Aktion; Lizenz-, Datenschutz- und Modellabhängigkeiten geprüft.
- [ ] **Vollständige Scope-Abnahme:** Alle **58 S–D-Features** jeweils genau einmal einem Meilenstein zugeordnet und vor 1.0 funktionsgeprüft; A-11a–g inklusive A-11d, D-Tier-Opt-in-Features eingeschlossen.
- [ ] **F-Tier-Negativprüfung:** #49 (Cloud-Zwang) und #50 (ungefragte Veröffentlichung) sind **nachweislich nicht vorhanden**.
- [ ] **Dokumentation:** Bekannte Grenzen, Abnahmeprotokoll, installierbarer Windows-Build, verbleibende Blocker und Risiken festgehalten.

**Abnahmebegriffe:** „implementiert“ = Code vorhanden; „automatisiert getestet“ = entsprechende Tests; „Windows-abgenommen“ = echte Windows-Prüfung; „releasefähig“ = alle erforderlichen Gates. Diese Begriffe nicht gleichsetzen.

## 8. Governance / Änderungsregeln

1. `/ROADMAP.md` ist **bindend**; `docs/ROADMAP.md` bleibt historische technische Prüfliste. `AGENTS.md` und neue PRs müssen auf die Root-Datei verweisen.
2. **Owner-Änderung vom 22.11.2026:** Die **D-Tier-Funktionen D-B1–D-B3 und #44–#48 sind ausdrücklich für 1.0 freigegeben** und nach fachlicher Zugehörigkeit in M11/M16/M18/M19 eingeplant. **D bleibt niedrige Priorität**, ist aber kein Post-Release-Platzhalter mehr.
3. **F-Tier #49/#50** wird **nicht entwickelt**. M20 prüft ausdrücklich, dass Cloud-Verarbeitung nicht verpflichtend und Publishing nie ungefragt erfolgt.
4. **Alle 58 S–D-Funktionen** gehören verbindlich zum 1.0-Scope. Streichen, auf nach 1.0 verschieben oder Priorität ändern erfordert neuen ausdrücklichen Owner-Beschluss.
5. Die bisher erst nach 1.0 vorgesehene Overlay-Entfernung **A-11d** wird in **M13d** zusammen mit der übrigen Overlay-/Kamera-Arbeit umgesetzt und vor 1.0 abgenommen; verständliche Grenzen bei Inpainting bleiben Pflicht.
6. Basis-Datenintegrität/Autosave (#04) und umfangreiche Projektverwaltung (D-B1) bleiben getrennte Funktionen, können technisch aber ein Speichermodell nutzen.
7. Die Standard-Highlight-Wortliste wird **in künftigen Entwicklungsrunden** gepflegt; keine angebliche permanente Hintergrundarbeit ohne separate Automation.
8. Meilensteine dürfen in kleine PRs gesplittet werden. **Keine stillen Scope-Reduktionen** und kein „fertig“ ohne Test- und Windows-Evidenz.
9. Nächster Schritt bleibt **M10.5 – Integration & Stabilisierung**, anschließend **M11 – Editor, Timeline & Datenhaltung**.


---
*Owner-Beschluss: 22. November 2026 · aktualisierte, thematisch gebündelte Release-1.0-Planung · StreamClipper – Your Stream. Your Highlights. Your Control.*
