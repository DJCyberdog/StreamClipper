"""M12c: conservative FFmpeg CPU/NVIDIA encoder selection (no CUDA decode).

A listing from `ffmpeg -encoders` does not prove the GPU/driver can start
NVENC. Probe a tiny real encode, then still handle runtime encoder failures
with at most one CPU retry. No hardware is required in CI.
"""
from __future__ import annotations

from dataclasses import dataclass
import subprocess

ENCODERS = (
    "auto_h264", "cpu_h264", "nvenc_h264",
    "auto_hevc", "cpu_hevc", "nvenc_hevc",
)

_CODEC = {
    "cpu_h264": "libx264",
    "nvenc_h264": "h264_nvenc",
    "cpu_hevc": "libx265",
    "nvenc_hevc": "hevc_nvenc",
}


@dataclass(frozen=True)
class EncoderPlan:
    requested: str
    primary: str
    fallback: str | None = None
    probe_failed: bool = False


def encoder_options(profile: str) -> list[str]:
    """Constant argv chunks, no shell or untrusted FFmpeg option strings."""
    if profile == "cpu_h264":
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-pix_fmt", "yuv420p"]
    if profile == "nvenc_h264":
        return ["-c:v", "h264_nvenc", "-preset", "p5",
                "-rc", "vbr", "-cq", "23", "-b:v", "0",
                "-pix_fmt", "yuv420p"]
    if profile == "cpu_hevc":
        return ["-c:v", "libx265", "-preset", "fast", "-crf", "26",
                "-pix_fmt", "yuv420p", "-tag:v", "hvc1"]
    if profile == "nvenc_hevc":
        return ["-c:v", "hevc_nvenc", "-preset", "p5",
                "-rc", "vbr", "-cq", "26", "-b:v", "0",
                "-pix_fmt", "yuv420p", "-tag:v", "hvc1"]
    raise ValueError(f"Unbekanntes Encoderprofil: {profile}")


def probe_nvenc(ffmpeg_executable: str, codec: str) -> bool:
    """Actually encode two black frames: checks FFmpeg build, driver and GPU.

    -encoders is insufficient. Input uses FFmpeg's lavfi generator; no user
    media is touched. A 15-second bound avoids hanging UI/worker forever.
    This is run from the export worker, never from MainWindow setup.
    """
    if codec not in {"h264_nvenc", "hevc_nvenc"}:
        raise ValueError("Nur NVENC-Encoder können geprüft werden")
    try:
        result = subprocess.run([
            ffmpeg_executable, "-hide_banner", "-nostdin", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:r=25:d=0.08",
            "-frames:v", "2", "-an", "-c:v", codec, "-pix_fmt",
            "yuv420p", "-f", "null", "-"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def resolve_encoder(requested: str, ffmpeg_executable: str) -> EncoderPlan:
    """Explicit GPU-only never silently changes codec or backend.

    Auto modes try actual NVENC, gracefully fall back to same-codec CPU.
    CPU profiles never probe hardware. A failed *real* NVENC export is
    handled by export_clip with exactly one fresh CPU re-encode.
    """
    if requested not in ENCODERS:
        raise ValueError("Unbekanntes Hardware-/Encoderprofil")
    if requested.startswith("cpu_"):
        return EncoderPlan(requested, requested)
    kind = "hevc" if requested.endswith("hevc") else "h264"
    gpu, cpu = "nvenc_" + kind, "cpu_" + kind
    supported = probe_nvenc(ffmpeg_executable, _CODEC[gpu])
    if requested.startswith("auto_"):
        return EncoderPlan(
            requested, gpu if supported else cpu,
            cpu if supported else None, not supported)
    if not supported:
        raise ValueError(
            "NVIDIA NVENC konnte keine Testframes kodieren. "
            "Treiber, GPU und FFmpeg-Build prüfen oder Auto/CPU wählen.")
    return EncoderPlan(requested, gpu)
