# M15 portable hotfix consolidation (2026-11-26)

HF1.1–HF1.5 remain in history: standalone local CPython discovery, private
prefix/PEP668 handling, verified FFmpeg ZIP fallback and real media smoke.
HF1.6 addresses the owner's confirmed CPU-only torch 2.15.0+cpu and missing
Whisper-small on clean install. The explicit GPU setup now offers the model
download/repair, installs separate CTranslate2 CUDA 12 libraries and the pinned
PyTorch 2.15.0+cu132 / TorchVision 0.29.2+cu132 wheel pair from the official
index, runs actual CUDA kernels (matmul, convolution, NMS), Whisper inference,
and joint-process smoke tests in both import orders. Status 3 means model
pending, not full PASS; status 1 means setup/test failure. No default app-start
downloads or global installs. Regular portable setup constrains an existing
CUDA wheel pair and verifies that it was not replaced. CLIP and DETR announce
their selected device, including CPU selection; shortcut generation is part
of bootstrap. An existing approved assets/StreamClipper.ico is preserved;
the original binary icon from the separately delivered complete ZIP is not
yet committed to GitHub.

Native Windows GPU acceptance still required: run setup_gpu_windows.bat on the
RTX 5060 Ti, confirm both individual and combined CUDA tests, then rerun
setup_windows.bat and confirm CUDA versions persist. Compare actual DETR/CLIP
inference and confirm no DLL conflicts, no system Python or FFmpeg dependence,
and that runtime/data are retained after folder relocation. Hosted CPU-only
unit tests cannot establish GPU correctness. Pin compatibility and model
quality remain acceptance checks. No automatic merge to main or release.
M16 and later inherit this consolidated M15 implementation.
