# Technische Architektur – StreamClipper 0.1

## Ziel

Offline-first, Windows-first Desktopprogramm für lokale OBS-/Twitch-Aufnahmen.
Deterministische, debugbare Highlight-Vorschläge und manuell kontrollierter
Export. Kein Streaming-/TikTok-Login in v0.1.

## Pipeline

```text
Videodatei (.mkv/.mp4/.mov)
    |
    v
[FFprobe] -> VideoInfo {duration, fps, streams, dimensions}
    |
    v
[FFmpeg Decoder] -> mono 8000 Hz PCM -> RMS je 1 s
    |
    v
[AudioPeakDetector] -> Candidate{start,end,score,reason,peak_at}
    |
    +-> JSON Bericht (spätere Detector Fusion kompatibel)
    |
    v
[PySide6 GUI] -> Qt Multimedia Vorschau -> Kandidaten auswählen
    |
    v
[FFmpeg Export] -> crop oder blurred background -> 1080x1920 H.264/AAC
```

## Module / Grenzen

- `models.py`: eingefrorene Schnittstellen auf MVP-Niveau. Daten exportierbar.
- `media.py`: einziger Ort für externe FFmpeg-Prozesse und Pfadauflösung.
- `analyze.py`: keine GUI-Abhängigkeiten, testbarer Baseline-Detektor.
- `gui.py`: Anzeige und Thread-Orchestrierung. Kein Video-/Audio-DSP im UI-Thread.
- `cli.py`: CLI-Reproduzierbarkeit, später Batchbetrieb.

Kandidaten sind Heuristiken, keine gesicherten Gameplay-Events. Nie Emotionen,
Humor oder Viralität behaupten, wenn die verwendeten Detektoren das nicht testen.

## Nächste API-Grenze

Ein künftiger `Detector` sollte Methoden/Datentypen liefern:

```python
class Detector(Protocol):
    name: str
    def detect(self, video: VideoInfo, context: AnalysisContext) -> list[EventEvidence]: ...

@dataclass(frozen=True)
class EventEvidence:
    start: float
    end: float
    kind: str                # audio_peak, speech, scene_change, explosion, etc.
    confidence: float | None # None wenn Detektor nicht kalibriert
    description: str
    detector_id: str
```

Ein eigenständiger `CandidateRanker` fusioniert Evidenz, legt zeitliche Fenster
fest, erklärt warum er Vorschläge macht, und erfindet keine Evidenz. Die
vorhandene `AnalysisResult`-Schnittstelle darf mit sauberer Versionierung
migriert werden.

## Sicherheit und Privatheit

- Nur lokale Medien, keine Netzwerkanfrage durch die Analyse.
- Subprocess-Aufrufe als Argumentlisten und `shell=False`.
- Keine Überschreibung vorhandener Exporte (`ffmpeg -n`).
- Rohvideo unverändert. Berichte enthalten Dateipfade, daher nicht blind öffentlich teilen.
- Keine Zugangsdaten oder OBS-/Twitch-Tokens.

## Technische Entscheidungen

| Thema | Entscheidung | Warum |
|---|---|---|
| GUI | PySide6 / Qt Multimedia | native Desktop-Bedienung, Preview |
| Core | Python 3.12, nur Standardbibliothek | schlank und unabhängig testbar |
| Videotechnik | FFmpeg + FFprobe | robuste Eingabeformate, CLI-stabil |
| Audioanomalien | PCM 8 kHz / RMS | schnell, speicherschonend, beweisbare Baseline |
| Persistenz | JSON | leicht überprüfbare MVP-Artefakte |
| Zielvideo | 9:16 H.264/AAC | breite Kompatibilität |
| Packaging | PyInstaller on Windows CI | automatisierbare portable Ausgabe |

## Noch zu validieren

Windows-11-GUI, Qt-Multimedia-Codecs, lange OBS-MKV-Dateien, variable FPS,
Mehrspur-Audio, GPU-/CPU-Last auf echtem Zielsystem, Unterbrechungen im Export,
Sonderzeichen/Unicode-Pfade. CI auf Windows plus Testdatensatz erforderlich.
