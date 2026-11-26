"""Portable GPU installer. Explicit invocation only; no downloads during app startup."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from streamclipper.portable import configure_portable_environment
from streamclipper.model_catalog import is_installed

TORCH = "torch==2.15.0+cu132"
VISION = "torchvision==0.29.2+cu132"
INDEX = "https://download.pytorch.org/whl/cu132"

def run(args):
    print(">", " ".join(map(str,args)), flush=True)
    return subprocess.call([str(x) for x in args])

def setup(root, *, consent, execute=run, installed=is_installed):
    """Return 0 for verified GPU backends, 3 for pending Whisper model, 1 on failure."""
    py = root / "runtime" / "python.exe"
    if not py.is_file():
        print("Portable Runtime fehlt. Zuerst setup_windows.bat ausführen.")
        return 1
    pip = [py, "-m", "pip", "--isolated", "install", "--cache-dir", root / "data" / "cache" / "pip", "--no-user"]
    # Model consent happens before the inference test, never silently.
    has_model = installed("whisper-small", root / "data" / "models")
    if not has_model and consent():
        if execute([py, root / "scripts" / "setup_local_models.py",
                    "--model", "whisper-small", "--directory", root / "data" / "models"]):
            print("Modell-Download fehlgeschlagen; GPU-Installation nicht abgeschlossen.")
            return 1
        has_model = installed("whisper-small", root / "data" / "models")
        if not has_model:
            print("Whisper-Modell nach Download weiterhin unvollständig.")
            return 1
    print("Installiere lokale Whisper-CUDA-12-Bibliotheken.", flush=True)
    if execute(pip + ["--index-url", "https://pypi.org/simple", "-r", root / "requirements-gpu-windows.txt"]):
        return 1
    print("Installiere PyTorch/TorchVision mit CUDA 13.2 (mehrere GB).", flush=True)
    if execute(pip + [TORCH, VISION, "--index-url", INDEX]):
        return 1
    # Distinct subprocesses avoid a misleading PASS from merely importing a DLL.
    torch_status = execute([py, root / "scripts" / "check_torch_gpu.py"])
    whisper_status = execute([py, root / "scripts" / "check_gpu_runtime.py"])
    if torch_status or whisper_status not in (0, 3):
        print("GPU-Einrichtung nicht vollständig verifiziert. Siehe Backend-Ausgaben.")
        return 1
    if whisper_status == 3:
        print("PyTorch-CUDA: PASS. Whisper-CUDA: ausstehend (Modell fehlt).")
        return 3
    # Verify both stacks within one process as used by the app, in both orders.
    for order in ("whisper-first", "torch-first"):
        if execute([py, root / "scripts" / "check_torch_gpu.py", "--combined", order]):
            print("GPU-Kombinationstest fehlgeschlagen; keine vollständige Freigabe.")
            return 1
    print("PASS: PyTorch, TorchVision, Whisper und gemeinsame CUDA-Nutzung verifiziert.")
    return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--skip-model-download", action="store_true")
    args = parser.parse_args()
    if args.download_model and args.skip_model_download:
        parser.error("Widersprüchliche Modelloptionen")
    root = configure_portable_environment()
    if Path(sys.executable).resolve() != (root / "runtime" / "python.exe").resolve():
        print("Nur die lokale portable Runtime ist zugelassen.")
        return 1
    def consent():
        if args.download_model:return True
        if args.skip_model_download:return False
        try:
            return input("Whisper-Small für GPU-Selbsttest herunterladen/reparieren? [J/n] ").strip().lower() in ("","j","ja","y","yes")
        except EOFError:return False
    return setup(root,consent=consent)

if __name__ == "__main__":
    raise SystemExit(main())
