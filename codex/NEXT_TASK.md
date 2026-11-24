# NEXT_TASK – M13b–M13e vervollständigen und abnehmen

Verbindlich ROADMAP.md §5.4; kein M14 vor Abschluss M13.
M13a f07739e6: automatisierte Linux-/Windows-Abnahme PASS; native Tests offen.
PR #50 1e75fe58: Linux-CI PASS; Windows beim ersten Abruf noch in Arbeit.

M13b: manuelle Keyframes, dynamische Zoomkurve, angeklickter lokaler Subject-Lock.
Neu: maximal 15,5 s pro Trackinglauf, Abbruch bei Zeitlücken >1 s.
Offen: Robustheit bei Verdeckung, schnellen Schnitten, längeren Szenen, native UI.

M13c: vorhandene statische und dynamische Zonen, Profile, Safe-Crop, Konflikte;
neu lokale CLIP-Klassifikation für HUD/Topbar/Chat/Facecam/Alert/Graphic mit
neutralen Kontrollen und zeitlichen Vorschlägen. Vorschläge deaktiviert.
Offen: echter CLIP-Modelllauf auf Testmaterial, präzise Lokalisierung,
Facecam-/Safe-Zone-Praxis und Qualitätsmessung; keine garantierte Erkennung.

M13d: explizite Schwarzmasken vorhanden. Neu: Referenzmetriken für
Rekonstruktions-, Kontext- und zeitliche Fehler, Lizenzprüfung unter
docs/M13D-INPAINTING-ACCEPTANCE.md. VACE 1.3B als Apache-2.0-Kandidat ausgewählt; lokaler experimenteller Adapter,
Mock-Tests und GPU-Benchmark implementiert. Experimentelle GUI-/Renderanbindung
für maximal 600 Quellrate-Frames, überlappende 33er-Fenster (8 Frames),
explizites Opt-in, temporärer FFV1-Bildinput,
Originalaudio und Crop-Vorrang. Echter Modelllauf, RAM/VRAM, Qualität,
Lizenzkette und Qualität der implementierten Fensterübergänge weiterhin offen.

M13e: gemeinsamer Renderpfad, voller Framing-Horizont, realer MP4-Keyframe-
Vergleich im bisherigen Stand; neu Test der zeitgesteuerten Maskenparität.
Neu: echter ASS-Safe-Zone-Vergleichstest geschrieben, M13-Suite in Windows-CI.
Neu: verkürzte Mehrszenenvorschau behält Kompositions-/Audionormalisierungspfad;
realer FFmpeg-Test mit später einsetzender zusätzlicher Audiospur geschrieben.
Offen: neue CI, umfassende Multitrack-/Mehrszene-/VFR-Parität und
native Windows/GPU-Abnahme.

Nächste Ausführung: finalen CI-Head prüfen, Fehler korrigieren; echte VACE-
und CLIP-Läufe auf lokaler GPU mit Referenzmaterial. Aktuelle Umgebung: CPU-Torch,
kein CUDA. M13d-Integration experimentell, noch nicht abgenommen; erst nach
Messungen Fensterübergänge bewerten und produktive Freigabe bearbeiten. Keine Statusschleife.
Python-Quellcode-Distribution analog M9 als Entwicklungsupdate, .venv/data
erhalten. PyInstaller separat, kein Ersatz für Source-Update.
