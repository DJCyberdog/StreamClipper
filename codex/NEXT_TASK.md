# NEXT_TASK – M13b–M13e vervollständigen und abnehmen

Verbindlich ROADMAP.md §5.4; kein M14 vor Abschluss M13.
M13a f07739e6: automatisierte Linux-/Windows-Abnahme PASS; native Tests offen.
PR #50 a5260a18: Linux-/Windows-CI PASS vor den aktuellen Änderungen.

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
docs/M13D-INPAINTING-ACCEPTANCE.md. KI-Inpainting weiterhin offen:
gepinnten, lizenzkompatiblen Backend-Kandidaten evaluieren und integrieren.

M13e: gemeinsamer Renderpfad, voller Framing-Horizont, realer MP4-Keyframe-
Vergleich im bisherigen Stand; neu Test der zeitgesteuerten Maskenparität.
Offen: tatsächliche ASS-/Multitrack-/Mehrszene-/VFR-Parität, neue CI und
native Windows/GPU-Abnahme.

Nächste Ausführung: finalen CI-Head prüfen, Fehler korrigieren; lokale
Modell-/Praxistests und M13d-Backend. Keine bloße Wiederholung des Status.
Python-Quellcode-Distribution analog M9 als Entwicklungsupdate, .venv/data
erhalten. PyInstaller separat, kein Ersatz für Source-Update.
