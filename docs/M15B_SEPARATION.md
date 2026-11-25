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
