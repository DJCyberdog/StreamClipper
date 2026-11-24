# NEXT_TASK – M12c NVENC/CPU-Fallback abnehmen; danach M12d Export-QA

**Stack (Draft, main unverändert):** M10.5 #31 →
M11a #34 → M11b #36 → M11c #37/#38/#39/#40 →
HF UX #41 → M12a #42 → M12b Audio #43 →
Premium Dock #44 → Unified Timeline #45 →
M12b2 Facecam/Logo #46 → **M12c Encoder** (aktueller Draft).

## Aktuell implementiert (nicht vor CI als vollständig abgenommen melden)

- `encoders.py`: H264/HEVC CPU (`libx264/libx265`) und NVENC
  (`h264_nvenc/hevc_nvenc`), echte Zwei-Frame-
  Initialisierungsprobe mit 15s-Timeout statt bloßer
  `-encoders`-Textsuche; CPU-only prüft niemals NVIDIA.
- `RenderRequest.encoder` als optionaler append-only Parameter;
  alte Aufrufpositionen erhalten. Ein FFmpeg-Compositor mit
  identischer Crop-/PiP-/Logo-/Untertitel-/Audio-Filtergraph-
  Semantik für Vorschau und MP4.
- Auto-H264/Auto-HEVC nutzt NVENC nur bei echtem PASS;
  bei initialem PROBE_FAIL CPU gleicher Codec; bei späterem
  FFmpeg-GPU-FAIL **genau ein** CPU-Encode nach Löschen des
  unfertigen temporären MP4. NVENC-only fail-closed, nie
  transparent umdeuten. Abbruch stoppt vor einem neuen Versuch;
  veröffentlichte MP4 sind geprüft und nicht überschreibend.
- GUI Export-Workspace sechs Encoder-Optionen (Default
  Auto-H264), asynchrone GPU-Probe im Exportworker,
  Status-Meldungen für gewählten Codec, Fallback, Fehler.
- Tests realer FFmpeg-Fehler/Fallback/Abbruch, Profile/
  NVENC-Probe, Qt-Selection und Legacy-Rendervertrag.

## Jetzt als Nächstes

1. Exakten PR-HEAD: vollständige Linux Python + reale
   FFmpeg-Integration, Windows Qt-Offscreen + portables
   ZIP. Fehler gezielt beheben; keine neuen Branches zum
   Verstecken fehlgeschlagener CI.
2. Echte RTX 5060 Ti auf Windows 11:
   Nvidia-Driver/FFmpeg-Build und NVENC H264/HEVC
   **beide tatsächlich** testen; GPU-Auslastung, CPU-Last,
   Encodezeit und Qualitäts-/Dateigrößenunterschied.
   Bei nicht verfügbarer User-Hardware sauber als
   `NOT_RUN` abgrenzen, keine erfundenen Zahlen.
3. **M12d – Export-QA:** MP4-Golden/Framezeiten und
   Audio-/Videolippen-Sync, Loudness, Clipping,
   Container-/Codec-Probes und Exportbericht,
   H264/HEVC-Upload-Kompatibilität; reale VFR-
   OBS-Multitrack-/Captions-Tests.
4. **M12e – Renderqueue:** Resume/Recovery, Job-
   Persistenz, begrenzte Parallelität, sichere
   Fortschritts- und GPU-/CPU-Scheduling-Regeln.
5. M13–M19 UX, Effekte, KI-Highlights und explizit
   freigegebenes Publishing; keine automatisch
   veröffentlichten Videos.
6. Realer 6h-VOD-/Windows-11-E2E-Test und
   1366×768/1920×1080-Premium-Layout-Abnahme.

**Grenzen:** NVENC kann Encoding beschleunigen, nicht
automatisch alle CPU-Filter/Decodes. Keine ungetestete
Performance- oder Qualitätsgarantie und kein Auto-Publish.
