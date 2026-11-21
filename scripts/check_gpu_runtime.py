"""True CUDA inference smoke test for Faster-Whisper, not just DLL discovery.

Run on Windows after `setup_gpu_windows.bat`; does not modify system settings,
requires local model weights, and never uploads any video or transcript.
"""
from __future__ import annotations

import sys

from streamclipper.portable import configure_portable_environment
configure_portable_environment()

from streamclipper.gpu_runtime import (enable_local_cuda_runtime,
                                       missing_runtime_dlls, runtime_directories)
from streamclipper.semantic import default_models_directory


def main() -> int:
    if sys.platform != "win32":
        print("Dieser GPU-Selbsttest ist fuer Windows 11 vorgesehen.")
        return 2
    enable_local_cuda_runtime()
    absent = missing_runtime_dlls()
    if absent:
        print("Fehlende CUDA-Laufzeit-DLLs in der lokalen .venv:", ", ".join(absent))
        for folder in runtime_directories():
            print("Pruefen:", folder)
        return 2
    model_path = default_models_directory() / "whisper-small"
    if not model_path.is_dir():
        print("Lokales Whisper-Modell fehlt:", model_path)
        print("Erst setup_windows.bat ausfuehren.")
        return 2
    try:
        import ctranslate2
        import numpy as np
        from faster_whisper import WhisperModel
        types = ctranslate2.get_supported_compute_types("cuda")
        print("CUDA-Compute-Typen:", sorted(types))
        print("Lade Whisper explizit auf NVIDIA CUDA ...")
        model = WhisperModel(str(model_path), device="cuda",
                             compute_type="float16", local_files_only=True)
        # A true inference is required; CTranslate2 sometimes fails only while
        # iterating the lazy result generator, not during model construction.
        # Synthetic silence is enough to exercise GPU kernels; it carries no
        # private audio or personal text and requires no FFmpeg process.
        silence = np.zeros(16000 * 3, dtype=np.float32)
        segments, _ = model.transcribe(silence, language="de", beam_size=1,
                                       vad_filter=False, condition_on_previous_text=False)
        list(segments)
    except Exception as exc:
        print(f"NVIDIA-GPU-Selbsttest fehlgeschlagen: {type(exc).__name__}: {exc}")
        print("Die CPU-Transkription bleibt als Ausweichweg erhalten.")
        return 1
    print("ERFOLG: Whisper-CUDA-Inferenz mit lokalen Bibliotheken abgeschlossen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
