# M15 Audio & Speech Intelligence — implementation and acceptance

Owner scope: ROADMAP.md §5.5.2 M15a–f. M15 is not a released or fully
accepted milestone. The native Windows/GPU and independent gaming-quality
gates remain mandatory. Do not start M16 by treating this as accepted.

## Implemented paths

| Item | Technical scope | Remaining acceptance / limitations |
|---|---|---|
| M15a | Real stream inventory, explicit original and reconstructed speech selection, persisted per source, stale-selection rejection; time-aligned extraction and timeline import | Independent mixed/real multistream fixtures and native UI |
| M15b | Inworld and VoxLock local adapters; source-bound estimates and residual; up to 6h, RF64, bounded windows, continuous TSE state, opt-in checked foreground window reuse after restart | True 6h native VOD, native 16 GB CUDA behavior, model quality/licensing chain; persistent TSE resume deliberately disabled (no reference fingerprint stored); non-48 kHz inputs not supported by separation yet |
| M15c | Bounded VAD on explicit mic or estimate, review table, selectable padding, pause suggestions, optional VAD-estimated edge-word trimming, manual/legacy protection, undo and persistent provenance | Real speech/timing accuracy and rendering review; VAD edge estimate is NOT forced alignment; automatic natural-pause cue splitting is not implemented |
| M15d | Whisper metrics and heuristic flags, targeted selected-cue retry with optional DE/EN and glossary, raw report archive, model reuse on reconstructed windows, review and manual adoption | Actual DE/EN/code-switching WER and retry efficacy; no second ASR model selected until benchmark; original-stream long ASR still uses original path and no new session-wide ASR cache; no true word alignment |
| M15e | Verified pair import, independent track gain, original mix toggle, new processed WAV with cleanup, sidechain, loudness target and actual WAV loudness measurement; local voice-over file import; shared timeline graph | Native preview/export/queue listening, AAC true-peak measurement; no live microphone recorder, effects are rendered assets not live automatable plugins |
| M15f | Local benchmark runner and evaluator, split guards, WER/CER, SI-SDR, leakage proxy, edge errors, runtime and optional sampled RAM/VRAM, typed speech handoff; separate real-model smoke CI | Independent annotated gaming cases are not supplied; no gaming quality gate or GPU/6h acceptance claim |

## Automated evidence

- Baseline 83f90033: Linux 45632348605 PASS, Windows 45632348609 PASS.
- First full review/editor/cache regression head de0f18f4:
  Linux 45635847949 PASS, Windows 45635847952 PASS.
- Continuous streaming TSE head 6196ce55: Linux 45636939919 PASS,
  Windows 45636939554 PASS.
- Real VoxLock CPU smoke, continuous state: run 45637124101,
  job 139285479206 PASS. Generated TTS, target present/absent, 12s each.
  SI-SDR baseline -2.487938 dB, estimate +0.990607 dB,
  interference-projection ratio 0.555318 -> 0.009852;
  reconstruction maximum absolute error 1.490116e-08.
  Absent-target output RMS 0.0014935 versus mix 0.0220773.
  Not a measure of actual streamer/NPC quality or word leakage. This is
  one generated example, not a statistically meaningful benchmark.
- Initial real Inworld smoke 45636673650 FAIL: CPU torch was paired with
  CUDA torchaudio; import failed with libcudart.so.13 missing.
  CPU dependency repair e63b6155 installs matching CPU builds.
  Check current CI for new result; do not use old failure as a quality verdict.
- Most recent full source head before documentation: 4851e412. Fresh
  Linux 45637878575, Windows 45637878472 and model smoke 45637878427
  must be checked on exact head before acceptance. No automatic merge.

Public model test dependencies are downloaded only by explicit setup or
the separate hosted smoke workflow. App inference uses local files.
No user recordings in CI. Model sources and setup: docs/M15B_SEPARATION.md.

## Local setup and workflow (existing Windows venv)

Do not replace an established working CUDA Torch stack without checking
compatible Torch and Torchaudio builds. The optional extras use the local
installed stack; CPU or CUDA package variants must match.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[target-speaker,models,benchmark]"
.\.venv\Scripts\python.exe scripts/setup_target_speaker.py
```

For Inworld, separately install the optional `.[separation]` extra and
provide the published offline denoiser.safetensors file with its pinned
SHA-256. Model download is never implicit in the application.

1. Open VOD. Audio → Audioquellen / Originalspuren.
2. Prefer an actual mic stream if available; otherwise use KI-Audiotrennung.
   Pick Inworld or VoxLock (clean 3–30s authorized local reference).
3. Optional foreground cache stores reconstructed PCM windows in
   .streamclipper-separation-cache under the selected output folder.
   It is local audio, not a hidden upload. Re-run same model/input/output
   folder to reuse windows. Decode the aligned source again; no persisted
   enrollment for TSE and no partial published bundle. User may delete
   that cache directory explicitly. Disk budget includes reserve.
4. Audio → Audioquellen → KI-Sprachspur für Whisper wählen, choose
   voice_estimate.wav. Explicit source choice is saved locally per
   recording; missing/changed choice blocks ASR until reselected or reset.
5. Analyze with local Whisper enabled. The raw report is separately
   archived under data/projects/raw_asr; reviewed changes go to normal
   report/undo/checkpoint. Audio → Untertitel-Zeitstempel prüfen.
   Mark only proposals you approve; optional edge-word estimates are
   labeled estimated, not exact.
6. Audio → ASR-Qualität prüfen. Review suspicious cues, optional language
   and glossary, reprocess selected window and confirm corrected text.
7. Audio → KI-Stems / Audio-Mix. Separate tracks or baked processed WAV.
   Both disable base audio in the project (other tracks stay active).
   Voice-over file import is on selected audio track; check duplicate
   sources before rendering. WAV loudness measured in mix.json.
   Export and preview/queue use same local audio asset.

## Independent benchmark procedure

Supply authorized, aligned mono/stereo 48 kHz short (<=600s) recordings
from multiple DE/EN gaming sources, including known target voice,
interferer, reference cues and speaker groups. Freeze development and
unseen holdout by speaker/VOD before tuning. Example manifest (illustrative
paths only; no real data included):

```json
{
  "schema_version": 1,
  "evidence_kind": "real_authorized_gaming_holdout",
  "cases": [
    {
      "id": "case_01",
      "split": "holdout",
      "speaker_group": "anonymous_group_01",
      "language": "de",
      "conditions": ["overlapping speech", "game music"],
      "mix": "case01/mix.wav",
      "reference_voice": "case01/clean_target.wav",
      "reference_wav": "case01/enrollment.wav",
      "interferer": "case01/interferer.wav",
      "reference_cues": [{"start": 1.0, "end": 2.3, "text": "Das war knapp."}]
    }
  ]
}
```

```powershell
.\.venv\Scripts\python.exe scripts/run_m15_benchmark.py cases.json data/bench/m15-voxlock --backend voxlock --model data/models/voxlock/onnx/v2 --whisper PATH_TO_LOCAL_WHISPER --authorized-references --commit EXACT_COMMIT_SHA
```

Run same frozen cases for Inworld, with --backend inworld --model
PATH_TO_DENOISER and --device cuda or cpu. Compare metrics.json; preserve
raw logs, model hashes, environment and listen independently. Silence,
target absent, quiet voice, cross-talk and game/noise cases mandatory.
Null denotes unmeasured/undefined, not success. RSS is sampled process-tree
memory, may double-count shared pages; NVIDIA per-process VRAM can be
unavailable on WDDM. Initial model load is outside some per-case samples.
The runner evaluates timing proposals offline, not automatic production
edits. No claimed acceptance based on its own output. M16/M17 handoff
keeps speaker identity unverified and distinguishes estimated word timing.

Native gates: 6h VOD on RTX 5060 Ti 16 GB, verify RF64, source integrity,
actual peak RAM/VRAM, abort/restart, playback/export parity and audible
quality. Full cross-model comparative benchmark and final license review
remain outstanding. Record explicit PASS/FAIL/BLOCKED for these gates.
