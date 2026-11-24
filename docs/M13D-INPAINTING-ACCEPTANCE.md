# M13d – temporales KI-Inpainting: Modell- und Abnahmeprüfung

Stand 2026-11-24. Experimenteller lokaler VACE-Adapter vorhanden; kein für den Export abgenommenes KI-Modell. Maskierung funktioniert separat.
Kein Modell wird automatisch heruntergeladen oder als kommerziell freigegeben behandelt.

## Upstream-Lizenzprüfung
- ProPainter: https://github.com/sczhou/ProPainter — upstream ausdrücklich nur nichtkommerziell. Nicht als Standard für monetarisierte Creator-Workflows wählen.
- DiffuEraser: https://github.com/lixiaowen-xw/DiffuEraser — Apache-2.0 für Hauptprojekt, aber README nennt ProPainter als prior und dessen Lizenzpflicht ausdrücklich. Standardpipeline damit nicht ohne Weiteres freigegeben. Ersatz des prior separat prüfen.
- ROSE: https://github.com/Kunbyte-AI/ROSE und https://huggingface.co/Kunbyte/ROSE — möglicher weiterer Kandidat, basiert auf Wan2.1-Fun-1.3B-InP; upstream nennt auch Code aus ProPainter. Keine pauschale kommerzielle Freigabe, bis Komponenten, Gewichte und Lizenzketten konkret geprüft sind.

## Konkrete technische Abnahme
1. Gepinnte Modell-/Code-Version, vollständige Lizenzkette und lokaler Offline-Lauf.
2. Auf repräsentativer 16-GB-GPU kurze Clips prüfen, VRAM/RAM/Laufzeit messen; kein garantierter Hardware-PASS.
3. Saubere Referenzclips mit künstlich eingefügten HUDs, Top-Bars, Facecams und zeitlichen Alerts überlagern. Unabhängige Szenen mit Kamerafahrt, schnellen Schnitten und Bewegung.
4. Gegen unverändertes Overlay, schwarze Maske und einfache Rekonstruktion vergleichen. `inpainting_metrics.py` misst Fehler im Maskenbereich, außerhalb und im zeitlichen Residuum gegenüber sauberer Referenz. Masken außerhalb der jeweiligen Zeit dürfen keine Pixel verändern. Keine erfundenen Schwellenwerte oder Qualitätsaussagen.
5. Erst bei belegter Lizenz- und Qualitätsabnahme in den gemeinsamen RenderRequest/Queue- und Vorschaupfad integrieren. Explizite Aktivierung, Original unverändert, Crop vor Maske vor KI. Abbruch, temporäre Dateien und Modellausfall fail-closed.

M13d bleibt offen. Die vorhandenen Metriken sind keine KI-Rekonstruktion.


## Konkreter Kandidat: Wan2.1 VACE 1.3B

- Modellkarte: https://huggingface.co/Wan-AI/Wan2.1-VACE-1.3B-diffusers (Apache-2.0; Repository ca. 19 GB).
- Modellrevision für das Experiment: ec4d2cb062b548996b179d493fdd05340de702a1
- Upstream: https://github.com/ali-vilab/VACE (Apache-2.0).
- API: https://huggingface.co/docs/diffusers/v0.36.0/en/api/pipelines/wan
- VACE-Backend: src/streamclipper/vace_inpainting.py. Diffusers 0.36.0 festgelegt. Ein temporales Fenster, 9/17/33 Frames, begrenzte Auflösung, binäre Masken, BF16 CUDA, CPU-Offload. Außerhalb der Maske vor Encoding exakt unveränderte RGB-Pixel. Kein Netzwerkzugriff beim Modellladen; keine automatische Installation. Lokaler Modellordner muss vom Bediener mit der gepinnten Revision vorbereitet werden; die Revision wird derzeit nur als Sollwert dokumentiert, nicht durch Dateihashes attestiert.
- Keine Zusicherung, dass CPU-Offload mit 16 GB System-RAM funktioniert; der Modellordner ist groß. Erst kurze Fenster und kleine Auflösung messen.

### Lokaler GPU-Benchmark

In einer separaten experimentellen Python-Umgebung mit funktionierendem CUDA-Torch und den optionalen Abhängigkeiten `.[inpainting]` ausführen. Nicht ungeprüft die bestehende produktive .venv aktualisieren. Modell explizit herunterladen, z. B. mit huggingface_hub.snapshot_download(repo_id="Wan-AI/Wan2.1-VACE-1.3B-diffusers", revision="ec4d2cb062b548996b179d493fdd05340de702a1", local_dir="data/models/wan-vace-1.3b"). Download erfolgt ausschließlich durch diesen separaten manuellen Aufruf.

```powershell
python scripts/benchmark_vace.py --clean D:/Tests/clean-png --model data/models/wan-vace-1.3b --output data/benchmarks/vace-topbar-01 --kind topbar
```

Clean-Verzeichnis: 9, 17 oder 33 fortlaufend nummerierte PNG-Frames aus einem sauberen, zusammenhängenden Clip; z. B. 448×256. Der Runner synthetisiert genau eine Overlay-Art (hud/topbar/facecam/chat/alert), schreibt Masken, Overlay- und Schwarzmasken-Baseline, Restaurierung und report.json in ein neues Verzeichnis. Bericht enthält Laufzeit, Peak-VRAM und Referenzmetriken. Erfolg heißt MEASURED_NOT_ACCEPTED, nicht PASS. Mehrere unabhängige Clips, tatsächliche Lizenzkette, RAM-Messung und Übergänge zwischen Fenstern bleiben offen.

Mock-Test bestätigt ausschließlich Adaptervertrag und Kontext-Compositing. Noch kein echter VACE-Lauf und keine Aussage zur temporalen Qualität. Die nachfolgende experimentelle Renderanbindung ist nicht abgenommen.


## Experimentelle Renderintegration (nicht freigegeben)

Szeneneditor → Smart Director → VACE experimentell: explizites Opt-in, lokaler Modellordner, aktive Zone mit Maskierung. Ohne Opt-in bleibt die bisherige Schwarzmaske. Wenn ein sicherer Crop sämtliche aktiven Zonen entfernt, wird keine KI benötigt. Die experimentelle Integration verarbeitet höchstens 33 Frames bei Quellbildrate (z. B. 1,1 s bei 30 FPS), maximal Full HD als Quelle. Inferenzauflösung ist kleiner; unverdeckte Original-RGB-Pixel werden vor Encoding wieder eingesetzt. Bei VFR erfolgt CFR-Normalisierung, nicht als framegenauer Erhalt zu verstehen. Keine fensterübergreifende Rekonstruktion. Kein stiller Fallback bei Modellfehlern.

Gemeinsamer RenderRequest friert Modellordner und Zonen ein; keine Gewichts-Hash-Attestierung. Eine verkürzte Vorschau verwendet dieselbe vollständige Szene für die Inferenz. FFV1-Zwischendatei nur im privaten temporären Renderordner, ausschließlich als Bildinput; Audio und zusätzliche Spuren nutzen unveränderte Originalzeiten. M12-QA und atomare Publikation bleiben erhalten. GPU-Nichtdeterminismus kann trotz gleicher Parameter zu unterschiedlichen Resultaten führen; Preview-/Exportgleichheit mit echtem Modell offen.

Tests: echte FFmpeg-Dateien, aber absichtlich gemockte Modell-Inferenz. Kein Qualitätsnachweis für VACE, keine Empfehlung als produktive Creator-Funktion. CUDA, Modellgewichte und reale Referenzclips fehlen in der aktuellen Testumgebung. Nächster fachlicher Schritt: echte GPU-Messung und vollständige Modell-/Lizenz-/Qualitätsvalidierung, danach mehrfenstrige Verarbeitung und Nahtstellenprüfung.


## Mehrfenster-Experiment (aktueller Stand)

Die vorherige 33-Frame-Szenengrenze wurde durch ein hartes Limit von 600
Quellrate-Frames pro Szene ersetzt (20 s bei 30 FPS, 10 s bei 60 FPS).
Fenster maximal 33 Frames, 8 Frames Überlappung, 25 Frames Schrittweite.
Eine einmal lokal geladene VACE-Pipeline wird innerhalb der Szene
wiederverwendet. Die Überlappung wird ausschließlich innerhalb der
Originalmaske linear überblendet; außerhalb bleiben Original-RGB-Werte
vor Encoding exakt erhalten. Keine semantische Kontinuitätsgarantie.
Keine automatische Schnitterkennung innerhalb einer Szene.

FFmpeg dekodiert einmal CFR in eine begrenzte temporäre Raw-Datei.
Fensterweise Verarbeitung begrenzt den Bild-RAM; temporärer Plattenbedarf
wird vorab mit 3 × unkomprimierter Szenengröße plus 64 MiB geprüft.
Bei 600 Full-HD-RGB-Frames sind das rund 11,3 GB. Das ist eine
Platzreserve, keine gemessene tatsächliche Belegung. Die finale FFV1-
Zwischendatei wird ohne Überschreiben publiziert (Hardlink im selben
Dateisystem; bei nicht unterstütztem Dateisystem Fehler statt Fallback).
Temporäre Dateien werden bei Fehler und Abbruch entfernt.

Automatisierte Tests mit simulierter Inferenz prüfen Fensterabdeckung,
Überblendung, Pixel außerhalb der Maske, Framezahl, Abbruch und
Nichtüberschreiben. Keine Messung echter VACE-Übergänge. GPU-Abnahme,
Modellidentität und Qualität bleiben offen. Die älteren Abschnitte
dokumentieren den historischen Einzel-Fenster-Stand.
