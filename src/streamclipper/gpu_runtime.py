"""Discover NVIDIA runtime wheels inside this Python venv on Windows.

CUDA 12/cuBLAS and cuDNN 9 libraries are installed separately by the user.
Never download or install anything on import; paths are only changed inside
this process, and DLL-directory handles must remain alive for Python's lifetime.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import sysconfig

_DLL_DIRECTORY_HANDLES: list[object] = []

_WHEEL_BINS = (
    ("cublas", "cublas64_12.dll"),
    ("cudnn", "cudnn64_9.dll"),
    ("cuda_runtime", "cudart64_12.dll"),
)


def runtime_directories(site_packages: str | Path | None = None) -> tuple[Path, ...]:
    """Only find venv-local NVIDIA wheel binaries; do not search system CUDA."""
    root = Path(site_packages) if site_packages is not None else Path(sysconfig.get_paths()["platlib"])
    return tuple(root / "nvidia" / name / "bin" for name, _ in _WHEEL_BINS)


def missing_runtime_dlls(site_packages: str | Path | None = None) -> list[str]:
    return [filename for folder, (_, filename) in zip(runtime_directories(site_packages), _WHEEL_BINS)
            if not (folder / filename).is_file()]


def enable_local_cuda_runtime(site_packages: str | Path | None = None,
                              platform: str | None = None) -> list[Path]:
    """Make local wheel DLLs visible to CTranslate2's native Windows loader.

    Some CTranslate2 versions use LoadLibrary by bare DLL name, for which PATH
    remains important. os.add_dll_directory covers dependent Python extensions.
    PATH is process-local, not persisted via setx or Windows registry.
    """
    if (platform or sys.platform) != "win32":
        return []
    folders = [p for p in runtime_directories(site_packages) if p.is_dir()]
    if not folders:
        return []
    prefix = [str(p) for p in folders]
    current = os.environ.get("PATH", "")
    seen = {value.casefold() for value in current.split(os.pathsep) if value}
    fresh = [item for item in prefix if item.casefold() not in seen]
    if fresh:
        os.environ["PATH"] = os.pathsep.join(fresh + ([current] if current else []))
    add_directory = getattr(os, "add_dll_directory", None)
    if add_directory is not None:
        registered = {str(handle[0]).casefold() for handle in _DLL_DIRECTORY_HANDLES}
        for folder in folders:
            if str(folder).casefold() not in registered:
                handle = add_directory(str(folder))
                _DLL_DIRECTORY_HANDLES.append((folder, handle))
    return folders
