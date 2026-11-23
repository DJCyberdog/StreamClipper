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
| **M10.5** | Integration & Baseline; **P1-UX-Fix #32: Modelldownload-Fortschritt + optionaler HF-Token** | Bestehende Arbeit konsolidieren (keine zusätzlichen Feature-IDs) | Start-/updatefähige Baseline; Modellgewichte laden mit sichtbarem, korrektem Downloadstatus im App-Fortschrittsbalken. |
| **M11** | Editor, Timeline & Datenhaltung | S: S-B1, #02, #03, #04, #05 · C: #36 · D: D-B1 | Sechsstündiges VOD flüssig navigieren, Schnitte/Spuren editieren und nach Neustart inkl. Checkpoints wiederherstellen. |
| **M12** | Preview, Render & Export-Engine | S: #01, #06, #07, #08 | Crop, Effekte und Untertitel laufen durch dieselbe Exportlogik; reproduzierbare Preview/Render-Vergleiche und geprüfte Job-Abbrüche. |
| **M13** | Szenen, Smart Director & Overlays | A: A-B1, #09, #10, #11, #12 | Je Szene manuelle/automatische Kamera, 9:16-/16:9-Crop, Sperrzonen, Profile und Rendervergleich; manuelle Vorgaben haben Vorrang. |
| **M14** | Untertitel, Branding & visuelle Gestaltung | S: S-B2 · A: A-B2, #19 · B: #23, #28, #30 | Untertitel/Text/Grafiken inklusive Übersetzung werden ohne neue Whisper-Analyse korrigiert und exportgetreu dargestellt. |
| **M15** | Audio & Sprache | A: #13, #14, #15, #16 · B: #26, #33 · C: #38 | Reproduzierbare Audiomischung ohne Quellenüberschreibung, verständliche Artefakt-/Lautstärkewarnungen. |
| **M16** | Gaming Intelligence, Review & Suche | S: S-B3 · A: #17, #18, #20 · C: #39, #40 · D: D-B2, D-B3 | Erst Benchmark/Baseline, dann zweistufige und temporale Erkennung, kalibrierbare Fusion, Sprach-/Spielprofile und Feedback; P@8, Recall, Fehlalarme und Laufzeit auf unabhängigen VODs nachweisen. |
| **M17** | Montage, Effekte & Clip-Varianten | B: B-B1, #21, #22, #24, #25, #27, #29, #31, #32 | Story-aware Clipgrenzen (Aufbau → Ereignis → Reaktion), mehrere Highlights und Exportvarianten mit kontrollierbaren manuellen Korrekturen zusammenstellen. |
| **M18** | Stream-Workflow, **Multi-Plattform-Videoimport** & Integrationen | C: #34, #35, #37, #41, #42, #43 · D: #48 | Einzelauswahl per URL für Twitch, YouTube, Kick und weitere validierte Quellen; Import/Marker/Exporte mit Fortschritt, Abbruch und klarer Rechte-/Fehlerbehandlung. Automatischer Kanalimport bleibt getrennt, opt-in. |
| **M19** | Publishing, Zusammenarbeit & Reichweite | B: B-B2 · D: #44, #45, #46, #47 | Bewusste Veröffentlichung, nachvollziehbare Freigaben, Rechte- und Datenschutzkontrollen; offline vollständig nutzbare Basis. |
| **M20** | Feature Freeze, Gesamt-Abnahme & 1.0 | F: #49, #50 | Alle 58 umsetzbaren Features aus S–D abgenommen oder ausdrücklich durch Owner neu beschlossen; beide F-Prinzipien nachweislich nicht implementiert; erst dann 1.0 Stable. |

**Vollständigkeitsnachweis:** 11 S-Features, 14 A-Features, 15 B-Features, 10 C-Features, 8 D-Features und 2 F-Ausschlüsse = **60 eindeutige Kennungen**. **58 zu implementierende** Funktionen + **2 dauerhaft ausgeschlossene** Funktionen. Jeder Hauptfeature-ID ist **genau ein führender Milestone** zugewiesen; Vorarbeiten und Integration dürfen milestoneübergreifend stattfinden, ohne die Zuordnung zu doppeln. Alle S–D-Features sind im Scope von **StreamClipper 1.0**.

### 5.1 Meilensteinregeln und Abhängigkeiten

1. **M10.5-Baseline und Review:** Bestehende gestapelte Code-PRs integrieren und mit realen Windows-Daten testen. **P1-UX-Wunsch #32** (Modellfortschritt/HF-Token) wird im Entwicklungszweig ergänzt, **ist aber kein technischer oder zeitlicher Blocker für M11/M12**. Seine eigenen Abnahmekriterien bleiben bis zur Release-Freigabe nachvollziehbar.
2. **M11 (Editor) → M12 (Render-Vertrag) → M13 (Kamera):** Persistente Timeline-/Szenenstruktur und verlässliche Renderpipeline sind Voraussetzung für den Smart Director. M12 stellt die exportgetreue Grundlage bereit; M13 und M14 erweitern und verifizieren sie für ihre jeweiligen Effekte.
3. **M14 (Captions) und M15 (Audio) → M16 (Intelligence) → M17 (Montage):** Wortkorrekturen und Audiosignale in die zweistufige Erkennung übernehmen, dann die Ereignisfenster in Story-aware Clipgrenzen überführen. Vor dem Ausbau der KI steht immer ein unabhängiger Qualitäts-Benchmark; Qualitätsgewinn wird nicht allein aus Modellgröße abgeleitet.
4. **M17 (Montage) → M19 (Publishing):** Clips müssen vollständig bearbeitbar und exportierbar sein, bevor sie über Dienste veröffentlicht werden.
5. **M18 (Integrationen) und M19 (Online):** Netzwerkabhängige D-Tier-Funktionen sind **opt-in**. Keine verpflichtende Kontoverknüpfung, keine Cloud-Abhängigkeit der Basisapp.
6. **M20 ist kein zusätzlicher Feature-Bucket:** Erst ein Gesamt-Regressionstest, Windows-End-to-End-Abnahme und nachweislich bestandene F-Tier-Schutzregeln erlauben den Release.
7. **Kein D-Tier-Schlupfloch:** Ein niedrig priorisiertes Feature bleibt zwar innerhalb seines Milestones nachrangig, wird aber nicht still auf „nach 1.0“ verschoben. Soll es doch entfallen, ist ein **neuer Owner-Beschluss** erforderlich.

### M10.5-P1-01 – Modelldownload-Fortschritt in der GUI ([Issue #32](https://github.com/DJCyberdog/StreamClipper/issues/32))

**Fehlerbild:** Beim explizit gestarteten Download lokaler Whisper-/CLIP-/DETR-Modellgewichte zeigt die Konsole den Fortschritt von `huggingface_hub.snapshot_download`; der **untere Fortschrittsbalken in StreamClipper bleibt bei 0 %**. Das ist eine Regression/fehlende Anbindung des **bestehenden** Modell-Workflows (M9), **kein neues Hauptfeature und kein M12-Renderjob**.

**P1-UX-Wunsch, zur Prüfung im Draft (kein Blocker für nachfolgende Entwicklung):**

- [ ] `ModelDownloadThread` sendet **thread-sichere Progress-Events** an die GUI; die untere Leiste zeigt den Download **sofort** und nennt das aktuell geladene Modell.
- [ ] Wenn Bytes und Gesamtgröße tatsächlich bekannt sind: Fortschritt auf Basis **der aufsummierten heruntergeladenen Bytes über alle Dateien**; Nachladungen wie `pytorch_model.bin` korrekt berücksichtigen. **Keine** fiktiven Prozentwerte anhand des Dateizählers.
- [ ] Bei unbekanntem Downloadumfang sowie Metadaten- oder Rekonstruktionsphasen: sichtbarer **unbestimmter Fortschritt (Busy/Indeterminate)** statt statischer `0 %`.
- [ ] **100 %/Bereit erst nach vollständig validiertem Modell**; bei Fehler oder Abbruch verständlicher Zustand, Wiederholbarkeit und Erhalt bereits vorhandener Modelldateien.
- [ ] Progress-Zustand für Modell, Twitch-Import, Analyse und Export überschreibt sich nicht gegenseitig; GUI bleibt bedienbar.
- [ ] Reproduzierbare automatisierte Unit-/Qt-Offscreen-Tests mit simulierten Download-Events **und** realer Windows-Test mit mindestens einer großen Modellvariante (z. B. CLIP ViT-L/14).

**Zusätzlicher Umfang: optionaler Hugging-Face-Token in derselben M10.5-Aufgabe**

- [ ] Im Modellmanagement ein **maskiertes Eingabefeld für HF-Tokens** sowie **„Verbindung prüfen“, „Entfernen“** und einen lesbaren Status für anonyme versus authentifizierte Downloads anbieten. Bei vorhandener `HF_TOKEN`-/HF-Login-Konfiguration deren Nutzung anzeigen, ohne geheime Werte einzublenden.
- [ ] **Keine Pflichtanmeldung:** Öffentliche Modelle bleiben auch ohne Token ladbar. Authentifizierung kann HF-Ratenlimits verbessern; **keine garantierte Downloadgeschwindigkeit** versprechen.
- [ ] Sitzungstoken standardmäßig **nur im Speicher** halten; optionale dauerhafte Speicherung ausschließlich nach ausdrücklicher Auswahl in einem **geschützten OS-Credential-Store** (Windows Credential Manager). Ohne sicheren Store nur Sitzungsmodus. **Kein Klartext** in `data/settings`, JSON, `.env`, Git, Logs, Tracebacks oder Fehlermeldungen.
- [ ] Authentifizierung über HF-Hub-API testen; ungültige/abgelaufene Tokens und fehlende Modellberechtigungen nachvollziehbar unterscheiden. Kein Token an Drittanbieter oder in URLs, Kommandos und Diagnoseprotokolle schreiben.
- [ ] `snapshot_download(..., token=...)` für Haupt- und Gewichts-Fallback-Downloads verwenden; Verbindung, Fehler, Retry und **Downloadfortschritt** im gleichen GUI-Workflow miteinander koordinieren.
- [ ] Automatisierte Sicherheitstests mit **Fake-Tokens** einschließlich Qt-Offscreen-Test; echter HF-Windows-Test nur mit lokal bereitgestelltem Token, **niemals** Test-Tokens ins Repo committen.

**Priorisierung:** **M10.5, P1-Wunsch ohne Entwicklungsblockade**; Implementierung im späteren gestapelten Draft nach M11c, sodass M11-Arbeit nicht neu aufgebaut werden muss. Reale Modell-/Token-Windows-Prüfung bleibt Release-Gate. Die Tierlist bleibt **60 Hauptfeatures** mit **58 vorgesehenen Implementierungen und zwei F-Ausschlüssen**.

### 5.2 M11 – Editor, Timeline & Projektlebenszyklus

**Umsetzungsstatus (experimentell):** M11a (PR #34) bietet kompaktes Undo/Redo und atomare Recovery für bestehende Clip-/Transkript-Edits. **M11b-Spurplan und GUI-Aufräumung** werden im gestapelten Branch `feat/sc-m11b-tracks-workspace` umgesetzt: versioniertes, lokal gespeichertes Spur-/Clip-Metadatenmodell; scrollbare Seitenregister **Highlights / Untertitel / KI & Modelle / Spuren / Export**, dauerhafte Vorschau + Timeline und einklappbarer Worteditor. **Die Spuren haben derzeit noch keinen Effekt auf Audio-/Video-Rendering**; Mehrspur-Komposition benötigt weitere Entwicklung und den M12-Render-Vertrag. **M11c Teil 4 (Draft):** Optionale 480p-Proxy-Vorschau im bestehenden Preview-Bereich; CPU-FFmpeg-Transcode im Hintergrund mit Fortschritt/Abbruch, quellengebundener Cache unter `data/proxies/`, VFR-PTS-Abstände und zeitbasierte Rückabbildung, Dauer-/Startoffsetprüfung, atomische Cachepublikation und Original-Fallback. Kein Proxy-Rendering in M12 vorgetäuscht; reale Windows-/6h-VOD-Abnahme bleibt offen. **M11c Teil 3 (Draft):** Explizite Übernahme von Analyse-Highlights als source-gebundene Spurplan-Metadaten in eigene oder gewählte Videospur; stabile IDs, Schutz vor Duplikaten, Sperrprüfung, atomische Speicherung und einheitliches Undo. Keine automatische Migration bei jeder Analyse; weder Sync zurück zur Analyse noch Rendering. Tests/CI und Windows-End-to-End sind separate Abnahme-Gates. **M11c Teil 2 (Draft):** Ein gemeinsamer, chronologisch geordneter Undo-/Redo-Verlauf ersetzt die getrennten History-Stapel für Spurplan und Analyse; globale Strg+Z/Strg+Umschalt+Z behandeln aktive Texteingaben gesondert, doppelte Spur-Undo-Buttons entfallen. Kompakte Transkript-Deltas bleiben erhalten; fehlgeschlagene Spur-Speicherung darf den Verlaufszeiger nicht verschieben. CI/Qt-Offscreen sind Review-Gates, reale Windows-Ergonomie und lange VOD-Tests weiterhin offen. **M11c Teil 1 (Draft):** Benannte, versionierte Projektstände für Spurplan und optionale Analyse werden lokal atomisch gespeichert, mit Quellbindung, Integritätsprüfung, begrenzter Aufbewahrung und Wiederherstellung über das Menü **Datei & Projekt** (ohne zusätzlichen Reiter). Core- und Qt-Offscreen-Tests sind vorgesehen; reale Windows-Abnahme bleibt offen. **M11 insgesamt NICHT abgenommen:** vollständige Checkpoints, Proxy-Medien, gemeinsame Undo-/Shortcut-Verwaltung, tatsächliche Mehrspur-Wiedergabe/-Export und Windows-/6h-Abnahme sind offen.

- Eine Timeline mit mehreren Spuren, zuverlässigem Undo/Redo, Proxy-Medien und nutzbaren Shortcuts.
- Autosave/Crash Recovery (**#04**) und vollwertige Projektverwaltung mit Analyse-Checkpoints (**D-B1**) als **getrennte** Leistungsmerkmale im gleichen Editor-Datenmodell.
- Lange Aufnahmen navigieren und Clipgrenzen editieren, ohne Videos erneut zu transkribieren; Datei- und Projektzustand nichtdestruktiv speichern.

#### 5.2.1 M11-UX – Navigation und Editor-Informationsarchitektur

**Ausdrückliche Owner-Anforderung (22.11.2026):** Die GUI muss mit jedem
Meilenstein übersichtlicher statt überladener werden. Der **M11b-Prototyp**
strukturiert die bisher auf einer Seite verteilten Werkzeuge als Seitenregister
**Highlights / Untertitel / KI & Modelle / Spuren / Export**. Videovorschau und
Haupt-Timeline bleiben unabhängig vom aktiven Register sichtbar. Die
umfangreichen Modell-/Exportoptionen sind scrollbar, der detaillierte
Worteditor einklappbar und bei Wortauswahl automatisch erreichbar.

Die Spurenübersicht erhält **grafische Clip-Zeitblöcke je Spur** mit
Klick-Auswahl und Dragging der Timeline-Position; daneben bleiben
präzise Tabellen-/Dialogeingaben nutzbar. Ein editierbarer Spurplan darf
**nicht** als bereits exportgetreue Mehrspur-Vorschau bezeichnet werden.

**M11-UX-Abnahmekriterien vor 1.0:**

- [ ] Hauptfunktionen bei **1366×768 und 1920×1080** ohne abgeschnittene
      essenzielle Buttons bedienbar; kurze Wege für Öffnen → Prüfen →
      Schneiden → Untertitel → Export. Seitenregisternavigation und
      Tastaturbedienung getestet.
- [ ] Vorschau und Timeline bleiben beim Wechsel von Modell-/Spuren-/
      Untertitel-/Exportregistern sichtbar. Lange Einstellungsbereiche
      bekommen Scrollflächen statt unbegrenzter Fensterbreite/-höhe.
- [ ] Einsteiger:innen sehen nicht gleichzeitig alle KI-Parameter,
      Wortzeitfelder, Exportoptionen und Spurwerkzeuge; Bedienelemente
      bleiben schnell wiederauffindbar und Zustände nachvollziehbar.
- [ ] Track-Canvas synchronisiert den angezeigten Timeline-Zeitbereich,
      ausgewählte Clip-IDs und Drag-Bearbeitungen; Sperrregeln, Undo/Redo
      und atomische Speichervorgänge greifen auch bei Mausinteraktion.
- [ ] Keine falsche UI-Zusicherung: bis zur späteren M11/M12-Komposition
      sind unabhängige Audiospuren und grafische Effekte **Metadaten**,
      noch keine abgemischten Video-/Audio-Exporte.

#### 5.2.2 Owner-Entscheidung (23.11.2026): Premiere-inspirierte Editor-UI

**Zielbild:** StreamClipper Studio bekommt eine **professionelle,
panelbasierte, frei anpassbare NLE-Arbeitsfläche**, inspiriert von den
Bedienprinzipien von Adobe Premiere Pro, jedoch **kein Design-/Markenklon**.
Die Kernstärke **KI-Highlights → schnelle Überprüfung → gezielter Schnitt
→ Export** bleibt ein erster, gleichberechtigter Workflow und wird nicht
hinter tiefen Profi-Menüs versteckt. Die bestehenden fünf Reiter sind eine
Zwischenlösung, **nicht** die endgültige Informationsarchitektur.

**Zielaufbau:**

- Obere Menü-/Workspace-Leiste: **Highlights**, **Schnitt**, **Audio**,
  **Untertitel**, **Export**; optional **Einfach-/Expertenansicht**.
- **Projekt-/Medien-Browser und KI-Highlight-Liste** links, in Panels
  als Tabs oder per Drag-and-Drop andockbar. Medienimport, Suche,
  Kandidatenscores, Quellinformationen und Batch-Vorschau.
- **Programmmonitor** zentral/rechts mit transport-/framegenauem
  Scrubbing und gut sichtbarer Zeitcodeanzeige; optionaler Quellmonitor.
  Sichtbarer Modusstatus: Original/Proxy/echte Render-Vorschau.
- **Mehrspur-Timeline unten als primärer Arbeitsbereich**, frei
  höhenverstellbar, Video-/Audiolanes, Waveforms, Clipkanten, Zoom,
  magnetisches Snapping, Playhead, Marker, Lock/Mute/Solo und
  Tastaturbefehle; keine doppelte Timeline in parallelen Tabs.
- **Eigenschaften/Effekte/Audiomixer rechts** als Kontextpanel,
  nur zur aktuellen Auswahl; Worteditor und Modellkonfiguration
  einklappbar. Exportjobs mit sichtbarer Fortschritts-/Fehlerliste.
- Panel-Docking/-Undocking, anpassbare Splitter und mehrere
  **gespeicherte Workspace-Layouts** inklusive „Layout zurücksetzen“;
  kein Verlust von Timeline-/Projektzuständen durch Layoutwechsel.

**Etappen nach fachlicher Zugehörigkeit statt separater UI-Neubau:**

1. **M12-UX:** Qt-Dock-/Splitter-Shell, Workspace-Presets,
   Programmmonitor + Projekt/Highlights + Timeline sowie persistierte
   Layoutzustände auf der bestehenden PySide6-Anwendung; funktionales
   Behavior aus M11 erhalten, keine neue App/Portierung.
2. **M13-UX:** Echtzeitnahe Parameter-/Keyframe-/Camera-Controls
   im Auswahl- und Effektpanel, Drag&Drop/Snapping/Multi-Clip-Editing.
3. **M14/M15-UX:** Direkt bearbeitbare Untertitelspuren, Audiopegel,
   Audiomixer, Effekt- und Musik-Panels; einheitliche Preview-/Exportzustände.
4. **M16–M19:** KI-Hit-Browser, Varianten/Montage, Quellenimport,
   optionaler Publish-Workflow als zusätzliche Workspaces statt immer
   längerer Tab-Formulare.
5. **M20:** Verbindliche End-to-End-UX-Abnahme, Accessibility,
   Shortcuts, Layoutmigration, Projektkonsistenz und Regression.

**Abnahmekriterien (vor 1.0):**

- [ ] Bei **1366×768** und **1920×1080** sind Timeline,
      Monitor, Medienbrowser und Hauptaktionen ohne abgeschnittene
      Bedienelemente erreichbar; auch mit vielen Tracks/Long-VODs.
- [ ] Panels andocken, verschieben, ein-/ausblenden, Layout
      speichern/laden/zurücksetzen; Wechsel während Wiedergabe
      verliert weder Playhead, Selektion noch offene Edits.
- [ ] Bedienung mit Maus und Tastatur, eindeutiger aktiver Fokus,
      Undo/Redo und Snapping, kein doppeltes Shortcut-Handling.
- [ ] **Highlights-first** und **professioneller Mehrspurschnitt**
      sind gleichwertig nutzbar; neue Nutzer:innen müssen keine
      Expert:innenkonfiguration öffnen, um einen Clip zu erstellen.
- [ ] Panelzustände lokal und versionsverträglich speichern,
      alte M11/M12-Projekte ohne Datenverlust übernehmen; keine
      erzwungene Cloud-/Adobe-Abhängigkeit.
- [ ] Keine bloße „Premiere-Optik“ vortäuschen: Monitor/Timeline
      zeigen die tatsächliche Renderfähigkeit und kennzeichnen
      noch nicht implementierte Video-/Audio-Funktionen.

**Status:** Entwurf/Owner-Beschluss, **noch nicht implementiert**.
Die M12b-Mehrspur-Audiofunktion ist kein Ersatz für die Dock-UI.
Das übergeordnete 60-Feature-Inventar bleibt unverändert; diese
Entscheidung beschreibt eine durchgängige **UX-Architektur**.

### 5.3 M12 – Vorschau & gemeinsame Renderpipeline

**M12a (Draft):** Gemeinsamer, unveränderlicher `RenderRequest` für
den bestehenden Single-Source-FFmpeg-Export und die ausdrücklich
ausgelöste, auf 20 Sekunden begrenzte Render-Vorschau (MP4).
Identische Crop-/Reframe-/ASS-Untertitelparameter in beiden Pfaden,
separater Qt-Player, Hintergrundjob, Abbruch und temporäre Datei.
Dies ist **noch kein M12-Freeze**: reale Windows-/6h-Abnahme,
Mehrspur-Komposition, Live-WYSIWYG, NVENC, Export-QA und Renderqueue
bleiben offen. M11-Metadaten-Spuren wirken weiterhin nicht auf den
Rendergraph.

**M12b Teil 1 (Draft):** Versionierter, deterministischer Rendergraph
und Projektformat v2 (v1-Dateien und v1-Checkpoints beim Lesen migrieren).
Editor kann lokale WAV/MP3/FLAC-Audiomedien mit Quellzeit, Zielzeit
und Pegel als Spurclips referenzieren. Opt-in FFmpeg-Audio-Compositor
mit Stumm-/Sperr-/Ausblenden-Semantik; Ausgaben aus MP4-Export und
20-s-Render-Vorschau haben identische Graph-Parameter und Audiomischung.
Noch keine Mehrspur-Videokomposition, kein Overlay-Compositing,
keine durchgehende Live-WYSIWYG-Vorschau. Diese werden bei angeforderter
Graph-Verarbeitung ausdrücklich abgelehnt statt ignoriert. Echte
Windows-/6h-VOD-Abnahme noch offen.

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
- **M16 Gameplay Intelligence:** Benchmark, zweistufiges temporales Screening, bessere multimodale Fusion, Sprachreaktionen, Spielprofile, Feedback-Learning, Dubletten/Kontaktbögen sowie optional Twitch-Chat und semantische Suche – **mit unabhängigen Vergleichstests**; siehe M16a–M16f.
- **M17 Montage:** Story-aware Clipgrenzen (Aufbau, Aktion, Pointe/Reaktion), Hooks/Kapitel, Geschwindigkeit, Standbilder, Sounds, Farbe, mehrere Längen und A/B-Varianten; siehe M17a.
- **M18 Streaming-Integrationen & Multi-Plattform-Import:** Einmalige URL-Imports für Twitch/YouTube/Kick und weitere unterstützte Plattformen mit einer gemeinsamen Download-Engine; OBS, Stream Deck, NLE, Tastatur-/Sprachoberfläche, Watch Folders und **separater** optionaler Kanalimport. **#36 Shortcuts sind bereits M11 zugeordnet**, damit sie von Beginn an editorweit wirken.
- **M19 Publishing & Collaboration:** Veröffentlichung nur mit Freigabe; Cloud Review, Sync, Analytics und Companion App ergänzen den Publishing-Workflow, erzwingen aber **keinen** Cloud-Zugang für lokales Editing.

### 5.6 M16 – Gaming Intelligence: verbindlicher Qualitätsausbau

**Owner-Erweiterung vom 22.11.2026:** Keine neuen Hauptfeatures; diese Arbeitspakete vertiefen **S-B3**, **#17**, **#18**, **#20**, **#39**, **#40**, **D-B2** und **D-B3**. Die Frage ist nicht, wie viele Modelle geladen werden, sondern ob die besten Vorschläge auf unbekannten Streams **messbar häufiger echte Highlights** sind. Der bestehende M10.5-Code gilt als Vergleichsbasis, **nicht als bereits validierte Ereigniserkennung**.

**M16a – Ground Truth und Qualitäts-Baseline (zuerst, Pflicht-Gate)**

- Ein versioniertes, manuell annotiertes **Evaluationsset von zunächst mindestens 100 Momenten** aus mehreren unabhängigen Gaming-/Twitch-VODs zusammenstellen: echte Highlights, absichtlich langweilige/gewöhnliche Szenen und schwierig zu unterscheidende Negativbeispiele (Kameraschwenk, Menüs, UI/Alerts, reines lautes Audio, normales Autofahren, Gespräche). Spiel, Sprache und Quelle dokumentieren, soweit Nutzungsrechte bestehen.
- Pro Szene Zeitintervalle und Highlight-Typ erfassen: z. B. Unfall, Verfolgung, Kampf, Erfolg, Überraschung, Lachen, erzählerischer Moment sowie **„kein Highlight“**. Grenzfälle/Unsicherheit kennzeichnen; keine künstlichen Gewissheitslabels.
- Trennung nach **VOD/Streamer:in**, nicht nur nach einzelnen Frames: Entwicklungs-/Tuning-Videos und ein **ungesehener Holdout** werden vorab festgelegt, um Datenleckage zu vermeiden. Bei strittigen Szenen zweite manuelle Prüfung vorsehen.
- M10.5-Baseline und neue Varianten auf identischen Daten/Modellständen vergleichen: **Precision@8** (Anteil relevanter Treffer unter den Top 8), Recall auf annotierte relevante Ereignisse mit dokumentierter Zeit-Toleranz, Fehlalarme pro Stunde, Dubletten/Überlappungen, Qualität von Clipbeginn/-ende sowie Analysezeit, CPU/RAM/GPU/VRAM pro Stunde VOD.
- Erkenntnis in ein reproduzierbares Offline-Reportformat schreiben (Konfiguration, Seed, Version/Commit, Modellgewichte, VOD-IDs ohne Veröffentlichung privater Dateien). **Vor einem Benchmark keine behauptete Prozentverbesserung.**

**M16b – Zweistufige, adaptive Analyse und temporale Ereigniserkennung**

- **Pass 1:** Das gesamte VOD ressourcenschonend mit Audio, Whisper-Cues und niedrig aufgelöstem Bewegungs-/Szenenscan abdecken. Es dürfen nicht nur die lautesten oder frühesten Minuten berücksichtigt werden; auch ruhige/unerwartete Events können potenzielle Kandidaten bilden.
- **Pass 2:** Nur priorisierte Zeitfenster **plus eine kontrollierte Stichprobe unauffälliger Fenster** mit dichterem Frame-Sampling, mehreren aufeinanderfolgenden Sekunden, CLIP-/Objekt-Tracklets und optional einem temporalen Videomodell untersuchen.
- Relative Objektbewegung, Richtungs-/Geschwindigkeitswechsel und Szenenkontext bewerten; abrupte Kamera-/HUD-Wechsel durch lokale Vergleichswerte und Bewegungskompensation soweit sinnvoll von tatsächlichen Ereignissignalen unterscheiden.
- Modelle optional, lokal und manuell installiert; CPU-/GPU-Fallback, begrenzte Analyse-Budgets, Abbruch und Wiederaufnahme. Ergebnisse je Phase in versionierten Artefakten wiederverwenden: **keine erneute sechsstündige Whisper-Transkription nur wegen Ranking-Tuning.**
- „Umgekippter LKW“/„Unfall“ nicht als bewiesenes Spielereignis aus Einzelbild-Ähnlichkeit oder einem Tracklet ausgeben; konkrete Aktionslabels erst nach separater Klassenvalidierung.

**M16c – Kalibrierbare multimodale Fusion**

- Evidenzen von Sprache, Stimmreaktion, Audio, Bilddynamik, CLIP und Objekten **zeitlich ausrichten** (Vorzeichen, Abstand, Dauer, Reihenfolge). Gleiche Quelle nicht mehrfach als unabhängige Bestätigung zählen.
- Abhängige Signale, niedrige Zuverlässigkeit, fehlende Modalitäten und typische Fehlalarme transparent behandeln. Ein Wort wie „Polizei“ darf **nicht allein** einen Highlight-Clip auslösen; ein hoher Audiopegel ebenso wenig automatisch ein Ereignis.
- Gewichte, Zeitfenster und per-Spiel-Profile auf Entwicklungsdaten optimieren, mit Holdout vergleichen. **Kalibrierung nur behaupten, wenn sie tatsächlich gemessen** ist; sonst weiterhin „heuristischer Score, keine Wahrscheinlichkeit“.
- Für jeden Vorschlag die wichtigsten beitragenden Signale, gegebenenfalls widersprechende Evidenz und die ungefähre Ereigniszeit anzeigen; manuelle Korrektur hat Vorrang.

**M16d – Sprachreaktionen und spielspezifische Profile**

- Zusätzlich zum kuratierten DE/EN-Sprachlexikon **akustische Hinweise auf Lachen, Schreien, plötzliche Stimmlage/Lautheitsänderungen und überraschtes Sprechen** optional testen; ASR-Satzzeichen oder Schimpfwörter allein sind kein verlässlicher Emotionsbeweis.
- Spielprofile (zuerst z. B. GTA-/Open-World-Fahren, dann weitere Kategorien) mit eigenen visuellen Prompts, Negativbeispielen, Ereignisfenstern und Schwellenwerten; **Generisches Profil** bleibt für unbekannte Spiele nutzbar.
- Getrennte Evaluation pro Sprache, Spiel und Aufnahmeart; Overlays, Mitspielende und gemischte Audiospuren dürfen die Aussagekraft nicht heimlich überschätzen.

**M16e – Nutzerfeedback und persönliche Relevanz**

- Annehmen/Ablehnen, Korrektur des Zeitfensters und explizite Bewertung als **lokale, optionale Feedbackdaten** erfassen; keine stillen Uploads.
- Persönliche Präferenzen und eventuelle Spielprofile verändern künftige **Vorschlagsreihenfolgen**, nicht ungefragt manuell gesetzte Highlights oder Untertitel.
- Regressionstests gegen Vorher-/Nachher-Rankings; nur auf Entwicklungs-/Tuningdaten lernen, **Holdout nicht zum Trainieren benutzen**. Profil-Reset und reproduzierbares Standard-Ranking vorsehen.

**M16f – Review, Dubletten, Chat und Suche**

- Dubletten/überlappende Vorschläge zusammenfassen, visuelle Kontaktbögen bereitstellen und Zeitstempel zur schnellen Sichtung verlinken.
- Die bereits für 1.0 freigegebenen **D-B2 Twitch-Chat-Analyse** und **D-B3 semantische Videosuche** als **optionale** zusätzliche Evidenz-/Review-Schicht implementieren, mit klarer Datenherkunft und Datenschutzgrenzen; ohne Chat muss die Kern-KI vollständig funktionieren.
- Keine Chat-Anzahl, Textsuche oder Stimmreaktion als alleinigen „viral“-Beweis verkaufen.

**Abnahme-Gates für M16:**

- [ ] Reproduzierbares, versioniertes Evaluationsset mit mindestens 100 annotierten Momenten, Negativfällen und festem unabhängigen Holdout vorhanden; Lizenz und Privatsphäre der VODs gewahrt.
- [ ] Für **M10.5-Baseline vs. M16** Precision@8, Recall (mit dokumentierter Toleranz), Fehlalarme/h, Clipgrenzen und Laufzeit/RAM/VRAM auf **denselben** VODs berichtet; Konfidenzintervalle/kleine Stichprobe bei der Interpretation berücksichtigen.
- [ ] Neues Ranking zeigt auf dem Holdout **einen nachvollziehbaren Qualitätsgewinn bei Precision@8 oder Recall ohne wesentliche Verschlechterung des anderen Werts**. Falls nicht: Ursachen und Trade-offs dokumentieren, Ansatz überarbeiten und **keinen unbelegten Qualitätsvorsprung behaupten**.
- [ ] Ein echtes, mindestens sechsstündiges VOD vollständig analysierbar; Sampling-Budgets und Caching verhindern unkontrollierte Mehrkosten. Abbruch, Wiederaufnahme, CPU/GPU-Fallback und Offlinebetrieb nachgewiesen.
- [ ] Testfälle für Kamera-/HUD-Bewegung, normales Gameplay, ruhige relevante Szenen, doppelte Modalitäten, Kontextwörter und fehlende Modelle bestanden.
- [ ] Erklärbare Kandidaten einschließlich Score-Art, Quellen und zeitlicher Evidenz; keine unvalidierten Aktionsbehauptungen.
- [ ] Feedback sowie Chat/Suche sind optional, lokal/transparent und verändern niemals ungefragt gespeicherte manuelle Entscheidungen.

### 5.7 M17a – Story-aware Clipping und dynamische Highlightgrenzen

Dieses Paket gehört zu **M17 (Montage/Clip-Varianten)**, nutzt **M16-Ereigniszeiten** und vertieft **B-B1, #21, #22 und #31** – **kein neues Hauptfeature**.

- Aus dem Verlauf **Aufbau → Ereignis → Reaktion/Pointe** einen sinnvollen In-/Out-Vorschlag ableiten, statt pauschal 25 Sekunden mit acht Sekunden Vorlauf abzuschneiden.
- Wechselnde Clipdauer mit gewünschter Zielplattform, Mindest-/Maximaldauer, Sprach-/Satzgrenzen, Kameraschnitt und Bewegungsabschluss vereinbaren. Bei einer späteren Pointe darf das Ende entsprechend verlängert werden, wenn das Längenbudget es erlaubt.
- Mehrteilige Ereignisse zusammenfassen und offensichtliche Dubletten vermeiden; bei mehreren Storybeats optional Montagevarianten anbieten.
- **Vorschlag statt Zwang:** Nutzer:innen können alle Grenzen in der Timeline verändern; ein manuell gesetztes Intervall wird nicht durch erneute Analyse überschrieben.
- Gegen M10.5-Fixfenster auf annotierten Momenten vergleichen: Anteil vollständig enthaltener Ereignisse, abgeschnittene Anfänge/Pointen, unnötige Leerlaufsekunden, Exportkonformität. Ein Quality-Gate darf nicht nur auf höheren Ranking-Scores basieren.

### 5.8 M18a – Plattformübergreifender Videoimport (verbindlicher Erweiterungsauftrag)

**Owner-Wunsch 22.11.2026:** Der bisherige manuelle Twitch-VOD-Import aus M5 wird zu einem **gemeinsamen Videoimport** erweitert, ohne pro Plattform einen unverbundenen Downloader zu implementieren. Der vorhandene `yt-dlp`-Adapter (`src/streamclipper/twitch_import.py`) liefert die Basis, erhält aber eine providerneutrale Schnittstelle. Dieses Paket ist **keine neue Hauptfeature-ID**; die Tierlist bleibt bei 60 und der Milestone bei M18. **D-Tier #48 bezeichnet dagegen die spätere optionale automatische Kanalaufnahme, nicht den manuellen URL-Import.**

**M18a.1 – Einheitliche Importoberfläche**

- Ein gemeinsames Eingabefeld für **YouTube (Einzelvideos, Shorts, veröffentlichte Aufzeichnungen), Kick (VODs/Clips), Twitch (VODs/Clips)** und nachweislich unterstützte weitere Plattformen (z. B. Vimeo/Dailymotion) sowie zulässige direkte Video-URLs.
- Vor dem Download per Metadaten-Preflight anzeigen: Plattform, Titel/Kanal, Länge, verfügbare Bild-/Tonqualitäten, Ton-/Untertitelspuren (soweit geliefert), geschätzter Speicherbedarf und Downloadziel. Bei fehlenden Metadaten nichts erfinden.
- Manuelle Wahl von Qualität (z. B. beste verfügbare, 1080p, 720p), Dateiformat/Audio soweit verfügbar; Originalqualität möglichst erhalten, keine unbeabsichtigte Neukodierung. Nach Download automatisch im Editor öffnen **nur auf ausdrückliche Auswahl**.
- Klar zwischen einem Einzelvideo, einer Playlist und einem ganzen Kanal unterscheiden: **Standardmäßig genau ein Video**, kein stilles Playlist-/Kanal-Crawling oder Auto-Ingestion. Größere Stapel erst nach gesonderter Auswahl mit Mengen-/Speicherschutz.

**M18a.2 – Gemeinsame Download-Engine und Zuverlässigkeit**

- `yt-dlp`-/FFmpeg-Backend für die Provider gemeinsam nutzen, aber **Plattform-URL-Erkennung und erlaubte Hosts/Protokolle kontrollieren**. Keine blind akzeptierten lokalen Dateipfade, Loopback-/Privatnetz-Adressen oder unkontrollierten URL-Redirects (SSRF-Schutz).
- Fortschrittsanzeige im **bestehenden unteren GUI-Fortschrittsbalken** einschließlich Dateigröße/Geschwindigkeit/Restzeit nur, wenn messbar. Bei unbekannter Größe Busy-Zustand; Download, Fragment-Reassembly und FFmpeg-Merge korrekt unterscheiden.
- Abbruch, Wiederaufnahme (`.part`), Fehler/Netzausfall/Rate-Limits, sichere Zielnamen, kein Überschreiben, Speicherplatzprüfung, Mehrspur-Container und temporäre Dateien robust behandeln. Bestehenden Twitch-Import ohne Regression migrieren.
- Vorhandene Untertiteldateien und Metadaten optional übernehmen, ohne unnötige Neutranskription. Importquellen/Zeitstempel dokumentieren; local-first Editor bleibt unabhängig vom Netzwerk.
- Plattformen sind **Best-Effort**, nicht garantiert dauerhaft verfügbar. Browser-/Plattformänderungen, unzugängliche Videos und entfernte VODs erzeugen verständliche Fehler.

**M18a.3 – Sicherheit, Rechte und Opt-in**

- Download nur nach **explizitem Klick** und bei vorhandener Nutzungsberechtigung; öffentlich abrufbar ist **keine** pauschale Download-/Wiederveröffentlichungserlaubnis. Nutzende auf Plattformbedingungen und Rechte Dritter hinweisen.
- Keine DRM-, Paywall-, Alters-/Zugangskontroll- oder Authentifizierungssperren umgehen. Falls eine Plattform erlaubte Authentifizierung für **eigene oder autorisierte Inhalte** bereitstellt, nur per gesondertem Opt-in und sicherer, nicht protokollierter Credential-Verwaltung.
- Keine Tokens/Cookies in Logs, JSON-Projektdateien oder Repository; gültige URL-/Dateinamen nicht als Shell-Kommando interpretieren. Keine automatische Veröffentlichung.
- Die Option **#48 – Automatic Channel Ingestion** wird in **M18b** getrennt implementiert und bleibt standardmäßig deaktiviert.

**M18a-Abnahme vor 1.0:**

- [ ] Für Twitch-, YouTube- und Kick-Testvideos **mit klarer Nutzungsberechtigung** je mindestens ein reproduzierbarer Import- und Fehlertest, einschließlich YouTube Shorts und Kick Clip soweit öffentlich und technisch unterstützt.
- [ ] Plattformübergreifender Parser, Single-Video-Default, Quality-Preflight, Fortschritt, Abbruch/Wiederaufnahme, Datei-Integrität und fehlende Tonspuren automatisiert getestet; echte Windows-11-End-to-End-Testläufe dokumentiert.
- [ ] Download-URL-/Redirect-/SSRF-/Pfadsicherheitsprüfungen sowie sicherer Umgang mit Metadaten und optionaler Authentifizierung abgenommen.
- [ ] Vorhandene Twitch-M5-Workflows funktionieren weiter; kein unerwarteter Download einer Playlist/eines Kanals, keine kaputten Import-Dateien oder überschriebenen Originale.
- [ ] Das importierte Video kann lokal sofort gesichtet, geschnitten und analysiert werden; Download bleibt optional und vollständig vom offline-first Editor getrennt.

### 5.9 M18b – Automatische Kanalaufnahme (D-Tier #48)

- **Nur opt-in**: Einzeln autorisierte Creator-/Kanalquellen auswählen, erlaubten Abrufrhythmus, Mengen-/Größenlimit und Zielordner festlegen.
- Bereits importierte Video-IDs deduplizieren; klare Pause-/Löschen-/Fehlerfunktionen, keine Endlosschleifen oder ungefragten Downloads.
- D-Tier bleibt niedriger priorisiert, wird nach dem manuellen M18a-Import umgesetzt und gehört gemäß Owner-Beschluss trotzdem zum 1.0-Umfang.

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
- [ ] **M16/M17-Qualitätsvergleich:** Versionsfestes Evaluationsset mit unabhängigen VODs, Precision@8, Recall, Fehlalarme/h, Clipgrenzen und Ressourcenverbrauch vor/nach Ausbau belegt. Verbesserungen nur nach gemessenem Holdout-Vergleich behaupten.
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
9. Nächster Schritt: M10.5-/M11-Review und Abnahme; die nichtblockierende UX-Ergänzung #32 läuft im gestapelten Draft. Danach M12.


---
*Owner-Beschluss: 22. November 2026 · aktualisierte, thematisch gebündelte Release-1.0-Planung · StreamClipper – Your Stream. Your Highlights. Your Control.*
