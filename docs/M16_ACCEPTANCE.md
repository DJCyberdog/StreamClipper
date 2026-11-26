# M16 Gaming Intelligence — integrated experimental implementation

Owner direction 2026-11-26: develop M16a–f in parallel with local M15
testing, on a stacked branch. This does not waive M15 or M16 acceptance.
The M10.5/M15 analysis path remains default and unchanged unless M16 is
explicitly selected. No automatic merge or release.

## Delivered in the pilot

| Step | Implemented | Outstanding acceptance / engineering |
|---|---|---|
| M16a | Local corpus freeze with source hashes, creator split guard, uncertainty/negative coverage, paired runner, recall, reviewed top-8 precision, duplicates, boundary errors, partial annotation false-positive exposure, sampled RAM/VRAM/runtime | >=100 actual independently annotated authorized gaming moments not available; complete-duration annotation needed for full false alarms/hour; confidence intervals, final metrics and quality decision not yet available |
| M16b | Full VOD audio/optional ASR/motion scan, adaptive CLIP and object sampling with quiet controls, optional approximate common translation compensation and temporal tracklet changes, completed-stage cache with source/model hashes and cancellation, explicit visual CUDA retry | Model inference/quality, six-hour native RTX test, actual GPU resource telemetry, within-stage interruption recovery beyond existing M15 ASR facilities; camera rotation/zoom and HUD false positives not solved |
| M16c | Time-aligned weighted evidence, grouped image modalities and shared audio/speech, context-only audio/chat, candidate reasons, deduplication | Tune only on development set; validate on frozen holdout; no calibrated probabilities |
| M16d | Generic/open-world prompts and weights, ASR uncertainty attenuation, acoustic level-change hints on explicitly selected original microphone | Actual laugh/scream/pitch classifier absent; acoustic proxy only; per-game and DE/EN quality not yet validated |
| M16e | Local accept/reject and optional corrected bounds feedback, optional preference-based reranking, reset, benchmark does not use personal preferences | Native GUI and ranking efficacy, further learned timing model not implemented; corrected bounds captured, not automatically applied |
| M16f | Review menu, deduplication, contact sheets, timestamp-linked lexical and opt-in local embedding speech search, local relative-time chat JSONL counts stripped of identity/text | Native semantic model and search quality tests, visual-semantic video search and automatic Twitch chat retrieval not implemented; chat only contextual, no independent event trigger |

## Local operation

Existing GUI: Gaming Intelligence (M16) → enable experimental M16 analysis;
choose generic or open-world; optional cache, chat input and personal
ranking preference. Then Analyze as before. Cache contains raw local
transcript text; never uploaded. Chat requires an explicitly supplied
JSONL file with one object per line, e.g. {"at": 42.5}; time is in seconds
relative to this recording, not wall-clock time. Do not import unauthorized
chat or recordings. The input is parsed locally and only time retained.
The review menu also offers feedback, contact sheet, lexical search and
semantic speech search using an explicitly selected local compatible
encoder directory; no model is fetched and no embedding quality is claimed.

CLI example (local Windows standalone runtime):
```powershell
.\runtime\python.exe -m streamclipper.cli analyze "D:\VODs\stream.mp4" --m16-profile open-world --m16-cache data\projects\m16_cache --speech-model data\models\whisper-small --vision-model data\models\clip-vit-base-patch32
```

## Corpus and paired benchmark

Manifest format (illustrative only; not actual evidence):
```json
{"schema_version":1,"authorized":true,"vods":[
 {"id":"vod01","creator_group":"anon01","split":"development","duration":120,
  "path":"local/vod01.mp4","game":"GTA","language":"de",
  "moments":[{"id":"m01","start":10,"end":17,"label":"crash","uncertain":false},
             {"id":"m02","start":50,"end":70,"label":"none","negative_type":"ordinary_driving","uncertain":false}]}
]}
```

Use multiple creators and VODs, >=100 independent annotated moments,
including holdout positives and all documented difficult negative
categories. Freeze before tuning; never optimize against holdout.
Labels are independent human annotations, not model claims.

```powershell
.\runtime\python.exe -m streamclipper.m16_benchmark freeze cases.json cases.lock.json
.\runtime\python.exe scripts\run_m16_benchmark.py cases.json cases.lock.json data\bench\m16-01 --commit EXACT_COMMIT --profile open-world --speech-model data\models\whisper-small --vision-model data\models\clip-vit-base-patch32
```

Install the optional benchmark extra for RSS measurement if missing.
A sparse annotated set cannot establish false-positive rate over a whole
VOD: unknown predictions are counted separately, and precision is reported
only among reviewed top-eight results, not an unqualified Precision@8.
Do not claim quality improvements unless actual holdout evidence supports them.
Synthetic tests are implementation regression evidence, not gaming data.

## Gates
- Current CI must be checked for exact final head.
- M15 native/quality gates remain open; owner permitted stacked M16 development.
- No authorized annotated corpus provided: M16a independent data/quality gate BLOCKED.
- No real six-hour Windows RTX measurement: BLOCKED.
- No final model/search/profile validation or statistically defensible quality gain: OPEN.
- No M16 freeze or release. No automatic merge or start of M17.


## Second implementation pass — 2026-11-26

Owner requested full M16 continuation. M15 portability fixes are merged:
M15 0aec35eebb27cd03bbb1e995cd674b9a48a213d5 has CI, Windows portable build,
True portable runtime relocation, real ASR CPU and neural CPU workflows PASS.
This verifies M15 hosted checks, not native NVIDIA inference or M16 quality.

- M16a: fully-reviewed flag for fixed top-eight precision and full-VOD false
  alarms/hour (unreviewed/uncertain data remain unknown); creator-cluster
  paired bootstrap intervals. Benchmark optionally tunes only development
  data before holdout inference. Record exact corpus/model/settings and
  actual runtime/RAM/VRAM. No corpus has been fabricated.
- M16b: optional fast vision via CUDA autocast FP16 and automatic bounded
  CLIP batches of four / object batches of two, one image per batch on CPU;
  nonfinite outputs retried in FP32, recognized CUDA failure retried on CPU.
  Completed stage cache versioned; optional ASR window cache supports both
  default first audio stream (aligned) and selected/reconstructed speech.
  Native parity/speed still unmeasured. NVDEC experiment is deliberately
  separate: single-frame seeking can be slower on GPU due to initialization.
  Run scripts/benchmark_m16_nvdec.py on a local authorized video.
- M16c: explain excluded dependent audio separately; optional validated
  rank weight overrides and deterministic finite development-only grid.
  No learned probability calibration; quality gain requires holdout.
- M16d: bounded pitch-change proxy and optional local Hugging Face audio
  classifier with named laugh/scream/shout classes, on an explicitly
  designated original microphone stream only. Add soundfile and soxr to
  speech extras. No automatic classifier download, no speaker identity,
  no emotion assertion; mixed game audio is not treated as a microphone.
- M16e: previous local accept/reject/reset and optional reranking remain.
  Corrected times are recorded, not applied automatically; M17 owns dynamic
  timing. Verify actual GUI behavior and regression against manual clips.
- M16f: local CLIP text-to-image search over bounded representative and
  highlight samples, relative similarity and timestamp navigation. Optional
  explicit TwitchDownloader JSON import or user-supplied local
  TwitchDownloaderCLI.exe for chat replay fetch, only for authorized full
  VODs matching the import ID. No credentials/hidden network activity; raw
  temporary chat JSON deleted after parse, only time offsets enter analysis.
  Adapter needs real external-tool compatibility test. Helper is not bundled.
  Source: https://github.com/lay295/TwitchDownloader/blob/master/TwitchDownloaderCLI/README.md
  No official Twitch VOD chat retrieval endpoint is assumed.

### How to exercise the new paths

In Gaming Intelligence (M16), enable experimental M16 analysis; optionally
enable fast vision, choose a compatible local audio classifier, or choose
one chat source. Existing default analysis remains available. On upgraded
installations run the portable dependency setup to install new speech
dependencies; M15 preserves existing CUDA wheel pair. Select visual search
from menu, enter English description for CLIP. Results are similarities, not
verified actions. Chat replay download requires explicit selection of a
trusted local external helper and public authorized VOD URL; offline import
does not require the helper.

Native commands:
```powershell
.\runtime\python.exe scripts\benchmark_m16_nvdec.py "D:\VODs\stream.mp4" data\bench\nvdec.json
.\runtime\python.exe scripts\run_m16_benchmark.py cases.json cases.lock.json data\bench\m16-02 --commit EXACT_COMMIT --profile open-world --speech-model data\models\whisper-small --vision-model data\models\clip-vit-base-patch32 --tune-development --fast-vision
```

### Remaining hard gates

Latest M16 CI must be green before a source package is labelled verified.
No actual >=100-moment authorized corpus, untouched holdout results, 6h native
RTX 5060 Ti measurement, real acoustic classifier validation, real semantic
search quality or external Twitch helper run supplied. Native GPU speed and
FP16 parity are NOT MEASURED. Camera zoom/rotation and HUD false positives
remain limitations; the tracker estimates shared translation only. No
quality acceptance, release, automatic merge to main or M17 start.
