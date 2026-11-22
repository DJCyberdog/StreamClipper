# StreamClipper – Verbindliche Produkt-Roadmap

> **Owner-Beschluss vom 22.11.2026 · Verbindliche Zielplanung · Primärdokument: `/ROADMAP.md`**
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

**10 bisherige + genau 50 neue (#01–#50)**. Die sieben Teilfunktionen von A-11 sowie die manuelle Szenenauswahl sind Bestandteile ihrer Hauptfeatures und erhöhen die Anzahl nicht. **S** = Kernqualität, **A** = Premiumkreativität, **B** = Produktionswerkzeuge, **C** = Komfort, **D** = zurückgestellt, **F** = ausgeschlossen.

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

**Explizit zurückgestellt.**

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

**Wichtig:** A-11 ist *nicht* auf Twitch-Overlays reduziert worden. Der bisherige Umfang für Spiel-HUDs und Safe-Zones bleibt bestehen; Twitch-/OBS-Overlays kommen **zusätzlich** hinzu. **A-11 (Feature)** und **M11 (Meilenstein)** sind verschiedene Kennungen.

- **A-11a – Erkennung:** Spiel-HUDs **und** Twitch-/OBS-Overlays, einschließlich Top-Bar, Chatbox, Facecam, Stream-Grafiken und Alerts.
- **A-11b – Manuelle Overlay-Zonen:** Regionen markieren, verschieben, deaktivieren und für einzelne Szenen anpassen.
- **A-11c – Safe-Zones:** Untertitel und relevante Spielinhalte so anordnen, dass Plattform-UI und Overlays sie nicht unbrauchbar machen.
- **A-11d – Tatsächliche Overlay-Entfernung:** Maskierung und optional zeitlich konsistentes KI-Inpainting. **Erst M19**, nicht Voraussetzung für M11/1.0.
- **A-11e – Twitch Overlay-Aware Smart Cropping:** Der Kameraausschnitt schließt OBS-Top-Bar, Chat, Facecam usw. soweit geometrisch möglich durch **Zuschneiden statt KI-Retuschieren** aus.
- **A-11f – OBS-Layout-Profile:** Wiederverwendbare Sperrzonen für verschiedene Stream-Szenen/OBS-Layouts (z. B. Top-Bar oben, Chat rechts).
- **A-11g – Dynamische Sperrzonen:** Vorübergehende Alerts/Einblendungen während eines Clips berücksichtigen, Unsicherheit anzeigen.

**Präferenz:** Wegschneiden vor Maskierung vor Inpainting. Falls ein 9:16-/16:9-Crop die Overlays nicht vollständig entfernen *und* die relevante Szene bewahren kann, wird der Konflikt angezeigt; keine perfekte unsichtbare Entfernung behaupten.

## 4. Technischer Ist-Stand: M0–M10

Vorhandene *experimentelle* Implementierungen umfassen Audio-Highlighting, nichtdestruktiven Videoexport, lokale Whisper-/CLIP-Analyse, manuelle Highlights, öffentlichen Twitch-VOD-Import, Audio-Timeline, Word-Level-Untertitel, zeitliche Gameplay-Evidenz, optionale DETR-/RT-DETR-Tracklets, Modellwahl und ein gepflegtes deutsch-/englisches Sprachlexikon.

**Stand 22.11.2026:** M6–M10 liegen auf **gestapelten offenen Draft-PRs #26–#30**. Das ist **keine** bestätigte vollständige Integration auf `main`, kein gesamter Windows-Praxistest und kein Stable-Release. Frühere Detailprüfungen stehen in `docs/ROADMAP.md` (historisches Prüfdokument). Immer zwischen **Code vorhanden**, **Tests bestanden**, **unter Windows abgenommen** und **releasefähig** unterscheiden.

## 5. Verbindliche Entwicklungsreihenfolge

| Meilenstein | Scope | Abnahmekriterium |
|---|---|---|
| **M10.5 – Integration & Stabilisierung** | Gestapelte PRs sauber konsolidieren, Imports/API/JSON-Kompatibilität, echte Windows-/Modell-/VOD-Proben | Konsistente Baseline ohne gemischte Dateiversionen |
| **M11 – Smart Director 2.0** | Manuelle Szenen, #01, #09–#12, A-11a/b/c/e/f/g | Kamerasteuerung, 9:16/16:9-Crops und Overlay-Zonen wirklich editierbar |
| **M12 – Professional Timeline** | #02–#06, #08, grundlegende Editierintegration für #14/#16 | Mehrspur, Undo/Redo, Autosave, Proxy, zuverlässiges Rendering |
| **M13 – Branding Studio** | Branding Studio, #19, #27–#30 | Stile, Animationen, Overlays, Callouts, Thumbnails |
| **M14 – Montage Builder** | Montage Builder, #17, #21/#22/#24/#25/#31/#32 | Highlights zu Best-of und Varianten kombinieren |
| **M15 – Gaming Intelligence 2.0** | #18, #20, #39, #40 | Spielbezogene Erkennung auf dokumentierten Testsets bewertet |
| **M16 – Audio & Language Studio** | #13–#16, #23, #26, #33, #38 | Sprach-/Audiobearbeitung, Übersetzung, Sprechertrennung |
| **M17 – Creator Integrations** | #34–#37, #41–#43 | OBS/Stream Deck, NLE, Shortcuts, GIF/WebM, Watch Folders |
| **M18 – Publishing & Release** | Publishing Center, #07, Abschluss #06/#08, Installer, End-to-End-Gates | **1.0 Stable** nur nach bestandener Gesamtabnahme |
| **M19 – Advanced Overlay Removal** | A-11d: Maskierung/Inpainting mit zeitlicher Kontinuität | Optionaler Premiumbaustein; **nicht** 1.0-Blocker |
| **M20–M21 – Optionales 2.0-Paket** | D-Tier nur **nach erneutem Owner-Beschluss** | Platzhalter, **keine aktuelle Freigabe** |

### 5.1 M11a – Manueller Szeneneditor

- Ein bereits ausgewähltes Highlight ohne KI in **mehrere Szenen** aufteilen.
- Pro Szene In-/Out-Punkte anpassen, Szenen ein-/ausschließen und für Montagezwecke optional neu anordnen.
- **Bildbereich manuell in der Videovorschau wählen** (nicht bloß Zeitfenster).
- Pro Szene den Modus **„Manuell“, „Automatisch“ oder „Fester Crop“** festlegen.
- Szenen- und Crop-Änderungen speichern, wieder öffnen und nichtdestruktiv exportieren.
- Manuelle Entscheidungen **immer** vor automatischer Kamera-/KI-Steuerung.

### 5.2 M11b – Smart Director & Keyframes

- Auf Wunsch Fahrzeug/Person in der Vorschau **anklicken und verfolgen** (Subject Lock).
- Pro Szene Crop, Position und Zoom mit Kamera-Keyframes; sanfte Übergänge.
- Ungeeignete automatische Verfolgung jederzeit per manuellem Keyframe überschreiben.
- Unterstützt unterschiedliche Kameramodi pro Szene.

### 5.3 M11c – HUD-, Twitch-Overlay- und Safe-Zone-Management

- **Spiel-HUDs und Twitch-/OBS-Overlays** beibehalten, nicht auf eine Overlay-Art einschränken.
- Statische Sperrzonen und zeitweise Alerts markieren; OBS-Profile wiederverwenden.
- Beim **intelligenten Cropping** Top-Bar, Chat, Facecam usw. möglichst **außerhalb** des Ausgabe-Bildausschnitts halten.
- Wenn vollständiges Wegschneiden ohne Verlust wichtiger Spielinhalte unmöglich ist: sichtbare Warnung/Fallback; **kein vorgetäuschtes Entfernen**.
- KI-Inpainting bleibt **A-11d/M19**, nicht M11.

### 5.4 M11d – Exportgetreue Vorschau

- Szene, Crop, Keyframes, Overlay-Sperrzonen und Wortuntertitel gemeinsam sichtbar machen.
- Repräsentative Frames mit echtem FFmpeg-Render vergleichen und Abweichungen dokumentieren.
- Keine bloß angenäherte Vorschau als vollständig WYSIWYG ausgeben.

## 6. Release-Phasen

| Release-Ziel | Meilensteine | Charakter |
|---|---|---|
| **0.x – Engineering Preview** | M0–M10.5 | Entwicklung und Stabilisierung der Basis |
| **0.8 – Creator Preview** | M11–M13 | Szeneneditor, Smart Director, professionelle Timeline und Branding |
| **0.9 – Feature Complete** | M14–M17 | Montage, Audio, KI, Creator-Integrationen |
| **1.0 – Stable** | M18 nach Release-Gates | Produktionsreife Windows-Version |
| **2.0 – Advanced** | M19; M20–M21 nur bei Neufreigabe | Erweiterte Overlay-Entfernung, optional D-Tier |

Release-Nummern sind **Planungsziele, keine Zeitversprechen**. Es dürfen Teilfunktionen iterativ ausgeliefert werden; die Freigabe einer höheren Version setzt die definierten Gates voraus.

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
- [ ] **Dokumentation:** Bekannte Grenzen, Abnahmeprotokoll, installierbarer Windows-Build, verbleibende Blocker und Risiken festgehalten.

**Abnahmebegriffe:** „implementiert“ = Code vorhanden; „automatisiert getestet“ = entsprechende Tests; „Windows-abgenommen“ = echte Windows-Prüfung; „releasefähig“ = alle erforderlichen Gates. Diese Begriffe nicht gleichsetzen.

## 8. Governance / Änderungsregeln

1. `/ROADMAP.md` ist **bindend**; `docs/ROADMAP.md` ist nur ältere technische Historie. `AGENTS.md` und neue PRs müssen darauf verweisen.
2. Tierlisten-Änderungen, Freigabe von **D** oder Änderung von **F** nur nach explizitem Owner-Beschluss. Die drei zurückgestellten Punkte **Projektverwaltung, Twitch-Chat, durchsuchbares Video** bleiben D.
3. Technische Basissicherheit (**Autosave, Datenintegrität, Export/Abbruch**) ist keine Reaktivierung des D-Tier-Projektmanagements.
4. M19-Inpainting ist Teil der vollständigen A-11-Zielplanung, aber für 1.0 **nicht verpflichtend**.
5. Die kuratierte Highlight-Sprachliste wird **bei künftiger Entwicklungsarbeit** gepflegt und anhand echter Fehler gemessen; es gibt **keine** automatisch laufende Hintergrundpflege ohne separat eingerichtete Automation.
6. Eine neue Funktion darf in kleine PRs zerlegt werden. **Keine stillschweigenden Scope-Senkungen** oder als fertig markierten Funktionen ohne Beleg.
7. Der **nächste verbindliche Schritt ist M10.5**, danach M11a (manueller Szeneneditor).

---
*Owner-Beschluss: 22. November 2026 · StreamClipper – Your Stream. Your Highlights. Your Control.*
