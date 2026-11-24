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

Mock-Test bestätigt ausschließlich Adaptervertrag und Kontext-Compositing. Noch kein echter VACE-Lauf, keine GUI-/Exportintegration, keine Aussage zur temporalen Qualität.
