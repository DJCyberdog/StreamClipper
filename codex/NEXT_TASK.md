# NEXT_TASK – M12d Export-QA + M12e persistente Renderqueue abnehmen

**Stack:** M10.5 #31 → M11a #34 → M11b #36 →
M11c #37–#40 → HF #41 → M12a #42 →
M12b Audio #43 → Premium Dock #44 →
Unified Timeline #45 → M12b2 Video/Grafik #46 →
M12c NVENC/CPU #47 → **M12d/M12e (aktueller Draft)**.

## Implementierungsumfang

- **M12d** `export_qa.py`:
  FFprobe von tatsächlichen MP4-Streams, Codec/Format/Pixel-
  format/Duration/AV-Start-/Endzeit; je Anfang/Mitte/Ende
  einen Frame decodieren; 2×max. 8s EBU-R128-True-Peak-
  Samples mit ausdrücklicher Sample-Einschränkung.
  Harte Fehler verhindern Veröffentlichung, Warnungen zu
  Cliplautheit und HEVC bleiben transparent.
  Atomischer `<video>.mp4.qa.json`-Bericht nach bestandener
  Kontrolle, SHA-256, Bytezahl, UTC-Zeit.
- **M12e** `render_queue.py`:
  Atomische Version-1-Queue-Datei mit immutable `RenderRequest`
  samt Projekt/Spuren/Transkript/Encoder; dedizierte Job-ID/
  Ausgabedatei; maximal ein Worker. OS-Dateilock schützt
  gegen parallele Instanzen. Kein automatisches Resume:
  RUNNING beim Crash→INTERRUPTED; manuelles Resume
  startet Clip von vorne. `.mp4.scjob.json` bindet Job-ID,
  Request-Hash und Datei-SHA. Vorhandene/unklare Datei
  → BLOCKED statt Doppel-Export. COMPLETE wird bei
  nachweisbar gültigem Beleg wiederhergestellt.
  Qt-Exporttab mit Einreihen, Start, Stop, Retry,
  Entfernen. Keine Projekt-/Quelldateimutation.
- **Tests:** Real-MP4-QA/HEVC, M12c-GPU-Fallback + QA,
  Crash nach Publish vor Receipt, falscher SHA,
  falscher Queue-Schema-Stand, Lock,
  Source-Schutz, GUI-Status/Encoder-Snapshot,
  Windows-Portabilität.

## Als Nächstes exakt abarbeiten

1. Linux Python Full CI + Windows GUI/PyInstaller **auf dem
   finalen PR-Head** durchführen. Regression gezielt fixen.
2. End-to-End-Größentest mit >6h-VFR-OBS, Mic/Music,
   PiP/ASS-Untertiteln auf Windows 11.
3. Real NVENC H264/HEVC der RTX 5060 Ti,
   CPU/GPU-Auslastung, Frames/s, Ton-Sync und
   QA-Bericht – ohne geprüfte Hardware kein PASS.
4. Im nächsten Draft **M13** Kamera-/Overlay-Keyframes,
   manuelle Szene und Program-Monitor-Manipulation;
   M14/15 Subtitle+Audio-Finish; M16–M18 KI/Import.
5. M19 Publishing nur mit offizieller API,
   geprüftem Provider-Konto und explizitem
   Freigabeschritt; keine Auto-Veröffentlichung.

**Nicht behaupten:** Keine FFmpeg-Frame-Level-Recovery
bei Crash, keine Voll-VOD-LUFS aus den 16s-Samples,
keine vollständige GPU-Verifikation durch CI,
keine Plattform-Veröffentlichungsfreigabe.
