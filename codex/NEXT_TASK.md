# NEXT_TASK – M15 implementation / acceptance

Owner asked to complete M15a–f. Technical paths across all six implemented;
not accepted or merged. See docs/M15F_ACCEPTANCE.md for exact scope, evidence,
remaining gates, local model/setup and benchmark runner. Latest code
4851e412 before documentation. Check exact final CI, no false green.

Immediate acceptance sequence:
1. Verify latest Linux/Windows and neural smoke. Fix concrete failures.
   Real continuous VoxLock CPU smoke 45637124101 job 139285479206 PASS.
   Initial Inworld CPU import mismatch fixed in e63b6155; new result pending.
2. Complete genuinely open engineering: persistent TSE resume without
   voiceprint persistence, broader sample-rate handling, bounded original-
   stream ASR and resumable ASR cache, optional validated alignment and
   pause-based splitting. Do not represent these as accepted.
3. Actual annotated DE/EN gaming holdout, native Windows/RTX 5060 Ti 16 GB,
   six-hour VOD, listening, cancel/restart, render parity, model licensing.
   User-supplied authorized fixtures needed; do not substitute generated TTS.
4. Record M15f gate results; only then propose M15 acceptance/merge and M16.
   M14 #51 native acceptance still open. No automatic release.

Source ZIP analog M9; preserve .venv and data. No automatic merges.

## Historical development notes

# NEXT_TASK – M15 Audio & Speech Intelligence

Owner-Auftrag 25.11.2026: besprochene Erweiterungen zu dynamischer
Cliplänge, Whisper-Qualität, nachlaufender Stille und KI-Audiotrennung
umsetzen. ROADMAP.md §5.5.2 M15a–M15f verbindlich. M17a bleibt dynamischer
Schnitt; keine neuen Hauptfeature-IDs.

Stacked auf M14 PR #51 (78cee7b0). M14 Head 7ec32c3c Linux 45464642687
und Windows 45464642673 PASS; native Bedienungs-/Marian-Abnahme und
Workflow-Feinschliff auf PR #51 offen. Kein 0.8-Release oder Merge.
M13 lokal Owner-abgenommen.

M15a erster Funktionsschnitt:
- FFprobe Audio-Stream-Inventar, absolute Stream-IDs, Format-/Streamzeit,
  Codec, Rate, Kanäle, Sprache und Titel. Benutzerzuordnung, keine
  behauptete Stem-Erkennung.
- Lokale Extraktion ausgewählter Originalspur als PCM-Float32 WAV
  mit Containerzeitbasis, führender/nachlaufender Auffüllung, Quellenprüfung,
  Speicherplatzgrenze, Abbruch und provenance.json. Kein Quellüberschreiben.
- Qt Audio-Menü und Worker; echte Mehrspur-/Zeitversatz-/Einspur-Tests
  hinzugefügt. Head 46ee8158 Linux 397 passed/19 skipped, PASS;
  Windows 204 passed/1 skipped, danach Exit 1, Build nicht ausgeführt.
  Ursache ungeklärt. Windows-CI trennt GUI-/Legacy-Suite und M15-Audiotests
  in eigene Prozesse und protokolliert Exitcodes; keine Fehlerunterdrückung.
- Neu: Sprachspur-Auswahl im Audio-Dialog für nächste Whisper-Analyse;
  temporäre zeitbasierte WAV, ASR-Provenienz im method-Feld (Stream-ID,
  Rolle, Quellgröße/mtime), keine stille Rückkehr zum Mix; Originalvideo
  bleibt Analyseidentität. Standard-RMS/Visualanalyse unverändert.
- Extrahierte Audio-WAV auf Timeline übernehmen; expliziter, persistenter
  Originalton-Schalter, Undo/Redo, Checkpoints, Queue und Szenenrender.
  Import deaktiviert den Originalmix erst nach Bestätigung; keine
  automatische Stem-Erkennung. Tests mit realem Audio und Mock-ASR
  geschrieben. Head 64248971 Linux 45609780087 PASS, Windows 45609780028 PASS.

Nächste Schritte:
1. Neue CI auswerten und reale Zeitbasis-/Mehrspurtests korrigieren falls nötig.
2. M15a: neue Tests/GUI abnehmen; persistente Sprachspur-/Cacheverwaltung,
   VAD-Anbindung, Mehrspur-/Einspur-Holdouts und echte Whisper-Inferenz.
   Sprachspurwahl bisher sitzungslokal; kein automatischer Import bei Wiederöffnung.
3. M15b: Modell-/Lizenz-/Ressourcenvergleich für Trennung und TSE.
   M15c: VAD und Alignment-basierte Korrekturvorschläge, manuelle Zeiten
   schützen, nachlaufende Stille messen. Kein globales Spielton-Lautstärkegate.
4. M15d–f: robuste ASR, Audioeditor, Benchmarks und M16/M17-Handoff.
   RTX 5060 Ti 16 GB native Abnahme und längere VODs nicht durch Mock ersetzen.

Quellcode-Update analog M9; .venv und data erhalten. Keine automatischen Merges.

M15c Vorarbeit: speech_timing.py erzeugt konservative, explizit zu bestätigende
Kürzungsvorschläge aus Sprachintervallen; Wortzeiten unverändert, geschützte
Zeilen und manuelle Wörter ausgeschlossen, stale Vorschläge abgelehnt.
speech_activity.py: lokaler Faster-Whisper-Silero-VAD auf ausdrücklich
als Mikrofon zugeordneter Originalspur, maximal 10 Minuten, kein RMS-Fallback.
Noch keine GUI-Anbindung, keine persistente manuelle Cue-Provenienz, kein
realer VAD-Modelllauf, keine Chunk-Verarbeitung oder TSE. Tests eingecheckt.
Nächster Schritt: M15b Modellvergleich und M15c Review-UI mit persistenter
manueller Cue-Provenienz; keine automatische Anwendung auf Alttranskripte.

## M15b erster Pilot (25.11.2026)
- Konsolidierung #53 ist in main; M14/M15-Baselines bdaa1d7d/7e035755
  jeweils Linux+Windows PASS. Neue M15b-CI ausstehend.
- Inworld Voice Isolator 1.0.0, veröffentlichter Offline-Safetensors-Checkpoint
  SHA256 647335a6aeb4dc706b895532c209d51e0e84a4849d17b339f00d4392a050ae53.
  Explizite lokale Dateiwahl, kein automatischer Download. Optionales Extra.
- WAV-Schätzung der Vordergrundsprache und rechnerischer Restton, 48 kHz,
  Mono/Stereo, max. zehn Minuten; acht Sekunden Fenster, zwei Sekunden
  Überlappung, samplegenaue Dauer, Hashes, temporäre Extraktion und Abbruch.
  Stereoprojektion als identische Mono-Stimme je Kanal; Rest ist keine
  Original-Spielspur. Kein Sprecher-ID-/TSE-Versprechen.
- Tests mit injiziertem synthetischem Backend prüfen Rekonstruktion,
  Überlappung, Zeitbasis, Abbruch, Modellintegrität. Echte Inferenz fehlt.
- Nächster Schritt: CI auswerten; unabhängiger Benchmark echter Sprach-/NPC-/
  Musikmischungen, native RTX-5060-Ti-Inferenz; WeSep Referenzstimme und
  Modelllizenz/Checkpoint prüfen; lange VODs mit Resume und Cache; geprüfte
  rekonstruierte Sprachspur optional in ASR/VAD/Timeline übernehmen.
  Keine automatische Ersetzung der Originalspur.

### M15b TSE pilot
- Inworld 549e6edb CI Linux 45620170431 and Windows 45620170628 PASS.
- WeSep standard release gate not met; VoxLock 1.3.0 alternative, explicit
  reference WAV and local INT8 ONNX files, pinned opt-in download script.
  Actual model license chain/bytes and inference quality not independently
  accepted. CPU first; no automatic enrollment. New tests and CI pending.
- Next: confirm CI; run actual model smoke and controlled target-present,
  target-absent and overlapping speech benchmark; continuous recurrent
  state, long VOD/cache, source-bound reconstructed-stem import to ASR/VAD.
  No claims of recovered original mic or reliable speaker identification.


### M15b/c longer recordings and reconstructed speech
- VoxLock 809c076a Linux 45630605232 / Windows 45630605342 PASS.
- Separation cap raised to 6h, RF64 for large files, disk estimate and guard.
  Cancellation removes partial work; resume and continuous model state open.
- Reconstructed estimate selection in Audio dialog, strict source/format/
  hash validation; ASR bounded 300s + 2s context and VAD 60s + 1s context.
  Original stream and original video unchanged; VAD available as core API,
  not review GUI. ASR model loaded per window; boundary quality unverified.
- New CI not confirmed. Next: confirm checks; source-bound timing review UI
  and persistent manual cue provenance, then explicit cache/resume and actual
  native model/6h VOD benchmark. No automatic timing edits.
