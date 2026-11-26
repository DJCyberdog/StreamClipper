"""Offline tests: CUDA wheel paths are registered without global side effects."""
from pathlib import Path
import os

import pytest

import streamclipper.gpu_runtime as gpu


def _fake_wheels(tmp_path):
    site = tmp_path / "venv" / "Lib" / "site-packages"
    files = {"cublas": "cublas64_12.dll", "cudnn": "cudnn64_9.dll",
             "cuda_runtime": "cudart64_12.dll"}
    for folder, dll in files.items():
        target = site / "nvidia" / folder / "bin"
        target.mkdir(parents=True)
        (target / dll).write_bytes(b"test-placeholder")
    return site


def test_wheel_locations_and_missing_dependencies(tmp_path):
    site = _fake_wheels(tmp_path)
    assert len(gpu.runtime_directories(site)) == 3
    assert gpu.missing_runtime_dlls(site) == []
    (site / "nvidia" / "cudnn" / "bin" / "cudnn64_9.dll").unlink()
    assert gpu.missing_runtime_dlls(site) == ["cudnn64_9.dll"]


def test_windows_registration_keeps_handles_and_doesnt_duplicate(monkeypatch, tmp_path):
    site = _fake_wheels(tmp_path)
    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    registered = []
    monkeypatch.setattr(os, "add_dll_directory", lambda directory: registered.append(directory) or object(), raising=False)
    monkeypatch.setattr(gpu, "_DLL_DIRECTORY_HANDLES", [])
    folders = gpu.enable_local_cuda_runtime(site, platform="win32")
    assert folders == list(gpu.runtime_directories(site))
    assert registered == [str(p) for p in folders]
    assert str(folders[0]) in os.environ["PATH"]
    assert os.environ["PATH"].endswith("C:\\Windows\\System32")
    gpu.enable_local_cuda_runtime(site, platform="win32")
    assert len(registered) == 3
    assert os.environ["PATH"].count(str(folders[0])) == 1


def test_non_windows_does_not_modify_process(monkeypatch, tmp_path):
    site = _fake_wheels(tmp_path)
    monkeypatch.setenv("PATH", "original")
    assert gpu.enable_local_cuda_runtime(site, platform="linux") == []
    assert os.environ["PATH"] == "original"


def test_no_wheels_does_not_pollute_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "original")
    assert gpu.enable_local_cuda_runtime(tmp_path, platform="win32") == []
    assert os.environ["PATH"] == "original"


def test_wheel_requirements_are_pinned_and_local():
    root = Path(__file__).resolve().parents[1]
    reqs = (root / "requirements-gpu-windows.txt").read_text()
    assert "nvidia-cublas-cu12==12.9.2.10" in reqs
    assert "nvidia-cudnn-cu12==9.28.1.4" in reqs
    assert "nvidia-cuda-runtime-cu12==12.9.79" in reqs
    setup = (root / "setup_gpu_windows.bat").read_text()
    assert "portable_env.bat" in setup
    assert "runtime\\python.exe" in setup
    assert "scripts\\setup_gpu_runtime.py" in setup
    installer = (root / "scripts" / "setup_gpu_runtime.py").read_text(encoding="utf-8")
    assert 'root / "runtime" / "python.exe"' in installer
    assert '"-m", "pip"' in installer
    assert '"check_gpu_runtime.py"' in installer
    assert '"check_torch_gpu.py"' in installer
    assert "torch==2.15.0+cu132" in installer
    assert "setx" not in setup.lower()
