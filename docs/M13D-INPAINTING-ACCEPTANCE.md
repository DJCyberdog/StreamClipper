# M13d – temporales KI-Inpainting: Modell- und Abnahmeprüfung

Stand 2026-11-24. Kein integriertes, abgenommenes KI-Modell; Maskierung funktioniert separat.
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
