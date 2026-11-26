# M15 Audio & Speech Intelligence — implementation and acceptance

Owner scope: ROADMAP.md §5.5.2 M15a–f. M15 is not a released or fully
accepted milestone. The native Windows/GPU and independent gaming-quality
gates remain mandatory. Do not start M16 by treating this as accepted.

## Implemented paths

| Item | Technical scope | Remaining acceptance / limitations |
|---|---|---|
| M15a | Real stream inventory, explicit original and reconstructed speech selection, persisted per source, stale-selection rejection; time-aligned extraction and timeline import | Independent mixed/real multistream fixtures and native UI |
| M15b | Inworld and VoxLock local adapters; source-bound estimates and residual; up to 6h, RF64, bounded windows, continuous TSE state, opt-in checked foreground window reuse after restart | True 6h native VOD, native 16 GB CUDA behavior, model quality/licensing chain; opt-in segmented TSE resume (local reference-bound cache keys; no stored embedding); 8–192 kHz inputs resampled to 48 kHz; broader multichannel input remains unsupported |
| M15c | Bounded VAD on explicit mic or estimate, review table, selectable padding, pause suggestions, optional VAD-estimated edge-word trimming, manual/legacy protection, undo and persistent provenance | Real speech/timing accuracy and rendering review; VAD edge estimate is NOT forced alignment; reviewed natural-pause splitting implemented, no automatic adoption |
| M15d | Whisper metrics and heuristic flags, targeted selected-cue retry with optional DE/EN and glossary, raw report archive, model reuse on reconstructed windows, review and manual adoption | Actual DE/EN/code-switching WER and retry efficacy; no second ASR model selected until benchmark; explicit original and reconstructed sources use bounded windows, optional raw ASR cache; implicit default mix retains legacy path; no true word alignment |
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


## Acceptance pass 2026-11-25 — evidence and remaining gates

Exact prior head c8f688cb: Linux 45638259699 PASS; Windows 45638259628 PASS;
real neural CPU smoke (both models) 45638259732 PASS. Inworld dependency
repair confirmed; do not reopen the old import failure.

- e8798a79: rate support 8–192 kHz mono/stereo -> 48 kHz output; real
  FFmpeg fixtures at 16, 44.1, 96 kHz; aligned resampled PCM reconstruction,
  source SHA-256 unchanged. Linux 45649537824, Windows 45649536934,
  neural smoke 45649536883 all PASS.
- a25fb7c9: selected original/reconstructed ASR share bounded 300 s windows,
  local opt-in raw JSON cache with decoded PCM and model-content keys.
  Linux 45649986614, Windows 45649986787, neural smoke 45649986587 PASS.
  Cache contains private transcript text; enable only explicitly in Audio.
  Cache identity includes requested device and package versions, not a
  guarantee of bit-identical GPU/CPU inference. Clear to force new inference.
- 013610b3: Linux 45650311783 PASS (426 passed, 19 skipped);
  Windows 45650311471 PASS. Real encoded MP4 audio equal in direct,
  preview and queue snapshot render; loudnorm measurement on AAC.
  Hosted tests, not native listening approval.
- Actual multilingual Whisper Tiny + Silero VAD and cache smoke
  45650311628 PASS (generated TTS). Auto-language WER German 112.5%,
  English 0%, one example each. This is a technical PASS, NOT a language
  quality pass. Tiny is a smoke-test model, not selected as production ASR.
- 2f2bf061: optional segmented VoxLock restart, source + exact normalized
  reference bytes bound with a random local cache key. No reference PCM,
  reference pathname or neural embedding persisted in the manifest or cache.
  Derived filenames may permit exact-input matching by someone who has
  both the cache directory and a candidate recording; opt in only.
  Cache contains estimated speech PCM. Continuous mode remains default and
  cannot resume from persistent state. Segment mode resets state per 8 s
  with 2 s overlap; quality may differ. Linux 45650630318 PASS.
- faa1925f: optional pause split review requires exact Whisper word sequence,
  measured inter-word VAD silence, and preserves words. Manually edited,
  estimated and translated cues excluded. Linux 45650803398 PASS, actual ASR
  smoke 45650803505 PASS. No automatic video cutting or exact forced alignment.
- Latest neural smoke now also tests interruption and segmented VoxLock
  resume using actual ONNX weights. Check exact new CI head.

### Model license review — preliminary pass, distribution gate remains open

Sources inspected 2026-11-25:
- Inworld code/model Apache-2.0: https://github.com/inworld-ai/voice-isolator ;
  https://huggingface.co/inworld/voice-isolator .
- VoxLock model Apache-2.0 and ancestry (REAL-TSE, WeSep, WeSpeaker):
  https://huggingface.co/arbazsiddiqui/voxlock .
- REAL-TSE baseline parameters/inference code Apache-2.0, upstream retained
  parameters subject to their own licenses:
  https://github.com/REAL-TSE/wesep-real-tse .
- Named upstream ECAPA checkpoint declared Apache-2.0:
  https://huggingface.co/Wespeaker/wespeaker-voxceleb-ecapa-tdnn512 .
- Smoke-test Whisper Tiny MIT:
  https://huggingface.co/Systran/faster-whisper-tiny .

This is a source-level check of declarations, not full distribution audit:
exact inherited weight lineage and all runtime notices still need review.
No weights bundled. Do not approve redistributed model package yet.

### Native local evidence runner

```powershell
.\.venv\Scripts\python.exe scripts/run_m15_native_acceptance.py --source "D:\VODs\stream.mkv" --output "D:\M15-Acceptance" --stream-index 1 --backend inworld --model "PATH_TO_DENOISER" --device cuda --whisper "PATH_TO_LOCAL_WHISPER" --commit EXACT_COMMIT_SHA
```

Example placeholders, use actual stream index, model paths and commit.
Requires an authorized almost-exact six-hour VOD (5:59:55–6:00:00),
Windows RTX 5060 Ti 16 GB, enough free disk; --short-smoke tests procedure
only. Native report records separate cancel/resume, RF64 geometry, output
hashes, source SHA-256, local ASR/cache, actual AAC preview/export/queue,
and resource telemetry. For VoxLock CPU add --reference and
--authorized-reference; this exercises segmented restart, not native CUDA.
User must listen to rendered clips, and perform independent annotated
gaming tests using the existing benchmark runner. No private data upload.
Reports contain local paths/possibly private transcript separately; review
before sharing.

### Remaining acceptance gates (not waived)

| Gate | Status | Required evidence |
|---|---|---|
| Independent DE/EN gaming holdout, mixed speech/music, target absent, code switching, quiet speech | BLOCKED | Authorized aligned recordings and independent cue/stem labels, not generated TTS |
| Native Windows RTX 5060 Ti six-hour VOD, resource limits, native playback and interaction | BLOCKED | Actual hardware and local footage, native report + listening |
| Full third-party weight distribution / runtime notices | BLOCKED | Verified exact inherited lineage and distribution review |
| Final ASR model selection / optional forced alignment | BLOCKED | Compare candidates on frozen real holdout before selection; no fabricated exact alignment |

No final M15 acceptance, no M16 start and no merge. Remaining quality gates
cannot be closed by green hosted CI. 

## Consolidated acceptance follow-up (2026-11-26)

Exact head 1a346205: Linux 45651346938 PASS, Windows 45651346920 PASS,
real neural CPU smoke 45651346962 PASS, real ASR CPU smoke 45651346998 PASS.
All M15a–f technical paths present, no repeated development of completed work.

New M15f gate: before real model benchmarks, freeze the actual local corpus.
Use anonymized `speaker_group` and `vod_group` (neither may span development
and holdout); use condition labels overlapping_speech, game_music,
target_absent, quiet_voice, code_switching, languages de/en/mixed.
Reference voice, mix and optional interferer must be aligned 48 kHz WAV;
reference_wav is a separate authorized 3–30 s enrollment. Empty reference
cues permitted for target-absent cases. The lock records hashes, geometry,
annotation hashes and coverage gaps, not audio or transcript text.
Coverage labels are user annotations, not independently certified; the
minimum structural coverage is not a statistically sufficient sample size.

```powershell
.\.venv\Scripts\python.exe -m streamclipper.m15_corpus freeze cases.json cases.lock.json
.\.venv\Scripts\python.exe scripts/run_m15_benchmark.py cases.json data/bench/m15-voxlock --backend voxlock --model data/models/voxlock/onnx/v2 --whisper PATH_TO_LOCAL_WHISPER --authorized-references --commit EXACT_COMMIT_SHA --corpus-lock cases.lock.json
.\.venv\Scripts\python.exe scripts/run_m15_benchmark.py cases.json data/bench/m15-inworld --backend inworld --model PATH_TO_DENOISER --device cuda --whisper PATH_TO_LOCAL_WHISPER --commit EXACT_COMMIT_SHA --corpus-lock cases.lock.json
.\.venv\Scripts\python.exe -m streamclipper.m15_corpus compare data/bench/m15-inworld/metrics.json data/bench/m15-voxlock/metrics.json data/bench/m15-comparison.json
```

The real benchmark now requires the lock and validates it again before
publishing metrics; also fingerprints ASR model bytes. Pair comparison
requires the same source commit, corpus, ASR model and case hashes.
It reports holdout-only micro-averaged WER/CER, unexpected words in empty
references, cue matching coverage and weighted timing error, SI-SDR and
leakage with measured sample counts, by language and condition. It does not
certify a quality pass or require identical CPU/GPU numerical behavior.
Do not tune against holdout. Real independent recordings and native local
RTX/6h listening evidence are still unavailable; distribution review stays
open, no weights bundled, optional alignment/model selection deferred until
actual evidence. No merge or M16 start.
