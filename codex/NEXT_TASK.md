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
  hinzugefügt. Neue CI offen, keine native Abnahme.

Nächste Schritte:
1. Neue CI auswerten und reale Zeitbasis-/Mehrspurtests korrigieren falls nötig.
2. M15a: ausgewählte vorhandene Sprachspur als explizite Analysequelle in
   Whisper/VAD und Audio-Timeline übernehmen; Mehrspur-Remix ohne doppelten
   Originalmix, Quellenprovenienz/Cache, Mehrspur-/Einspur-Holdouts.
3. M15b: Modell-/Lizenz-/Ressourcenvergleich für Trennung und TSE.
   M15c: VAD und Alignment-basierte Korrekturvorschläge, manuelle Zeiten
   schützen, nachlaufende Stille messen. Kein globales Spielton-Lautstärkegate.
4. M15d–f: robuste ASR, Audioeditor, Benchmarks und M16/M17-Handoff.
   RTX 5060 Ti 16 GB native Abnahme und längere VODs nicht durch Mock ersetzen.

Quellcode-Update analog M9; .venv und data erhalten. Keine automatischen Merges.
