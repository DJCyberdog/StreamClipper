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
