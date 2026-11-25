# M15b candidate decision (25.11.2026)

| Candidate | Published scope | Decision |
| --- | --- | --- |
| Demucs HTDemucs | Music stem separation, MIT code | Comparator only; not trained as a gaming microphone selector |
| Inworld Voice Isolator v1 offline | Foreground speech enhancement, 48 kHz mono, Apache-2.0 code and weights | First experimental adapter |
| WeSep | Reference-conditioned target speaker extraction, Apache-2.0 toolkit subject to third-party notices | Research next; verify exact checkpoint terms and inference API |

Primary sources:
- https://github.com/facebookresearch/demucs
- https://github.com/inworld-ai/voice-isolator
- https://huggingface.co/inworld/voice-isolator/blob/main/denoiser.safetensors
- https://pypi.org/project/inworld-voice-isolation/1.0.0/
- https://github.com/wenet-e2e/WeSep

Pinned Python distribution 1.0.0, offline checkpoint denoiser.safetensors,
published SHA-256 647335a6aeb4dc706b895532c209d51e0e84a4849d17b339f00d4392a050ae53.
The model is very recent; publisher tested datacenter GPUs and CPU, not our
consumer GPU. Claims from publisher are not independent results. Comparable
level voices may remain; voice identity is not determined by this model.

## Pilot acceptance boundary

Explicit local checkpoint, no model download in runtime. 48 kHz mono/stereo,
up to 600 s. Chunks 8 s, overlap 2 s, float32 residual equals original aligned
PCM minus identical-channel mono estimate, within rounding error. No clipping
or per-stem normalization. Output stems are estimates, not recovered originals.
No whole-VOD or GPU-quality acceptance. No automatic ASR or timeline import.

Install into the existing venv only on explicit request:
`python -m pip install -e ".[separation]"`
Download the offline checkpoint separately from the model file link above,
verify SHA-256 and select it in Audio → Audioquellen → KI-Audiotrennung.
Do not select the realtime model. Keep existing Torch/CUDA installation in
mind; dependency compatibility and real inference still need native validation.
 
Future evaluation: independent annotated streamer/NPC/noise/music mixes;
SI-SDR improvement against mix and microphone reference, leakage, WER and
cue-end timing errors, clipping/artifacts/listening tests, runtime and peak
RAM/VRAM. Compare with Demucs and a verified target-speaker adapter; do not
equate signal reconstruction with separation quality. Test quiet streamer,
equal-loudness and louder NPC, code switching, pauses and chunk boundaries.

## Reference-conditioned candidate: VoxLock (25.11.2026)

WeSep main still marks official pretrained packages/CLI as pending validation.
REAL-TSE's baseline publishes model weights and inference instructions, but
retained third-party speaker encoder parameters have separate license terms.
Do not import arbitrary pickle checkpoints or claim their full license chain.
VoxLock 1.3.0 is the alternative experimental candidate; its public package
and model card declare Apache-2.0. Its upstream dependency/license chain
still requires distribution review. No weights bundled in StreamClipper.

Sources:
- https://github.com/wenet-e2e/wesep
- https://github.com/REAL-TSE/wesep-real-tse
- https://github.com/arbazsiddiqui/voxlock/tree/v1.3.0
- https://huggingface.co/arbazsiddiqui/voxlock
- https://pypi.org/project/voxlock/1.3.0/

Inspected v1.3.0 voxlock/core.py: explicit model_dir prevents download;
VoxLock(...,precision="int8",threads=2), isolate(audio,sample=reference),
16 kHz mono, minimum 3 s reference. Upstream pinned revision is
2413b292bc2c337bfc19a9802aaf3e011e68e9c4.

Opt-in installation in existing virtual environment:
```powershell
python -m pip install -e ".[target-speaker,models]"
python scripts/setup_target_speaker.py
```
Select data/models/voxlock/onnx/v2 and a clean authorized reference WAV
(3–30 s) in Audio → Audioquellen → KI-Audiotrennung → Referenzstimme.
Only the setup script downloads models, not the inference path. Local model
hashes are recorded, not verified against a separately authenticated publisher
hash. Reference audio is read locally and not copied into output/provenance;
no automatic enrollment or voiceprint persistence. No speaker identification.

Existing 48 kHz input/output, 10 min cap and 8s/2s overlap reused. VoxLock
resamples to 16 kHz and back, so estimated voice is bandwidth-limited.
Recurrent state resets per overlapping window; continuous state and longer
VOD support remain future work. CPU/ONNX first, no GPU acceleration claim.
Synthetic/injected tests validate lengths, explicit reference, failure paths;
actual model inference, target-absent rejection, speaker leakage, WER,
German gaming quality and performance require real independent fixtures.
