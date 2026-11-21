"""FFmpeg / FFprobe subprocess boundaries (never execute via shell)."""
from __future__ import annotations

from array import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable

from .models import VideoInfo

Progress = Callable[[int], None]
Cancelled = Callable[[], bool]


class CancelledError(RuntimeError):
    """Analysis or export was cancelled by the user."""


def tool_path(name: str) -> str:
    """Find FFmpeg next to a packaged app, in STREAMCLIPPER_FFMPEG_DIR, or PATH."""
    suffix = ".exe" if sys.platform == "win32" else ""
    executable = name + suffix
    locations: list[Path] = []
    env_dir = os.environ.get("STREAMCLIPPER_FFMPEG_DIR")
    if env_dir:
        locations.append(Path(env_dir))
    if getattr(sys, "frozen", False):
        locations.append(Path(sys.executable).resolve().parent)
    for directory in locations:
        path = directory / executable
        if path.is_file():
            return str(path)
    found = shutil.which(executable) or shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"{executable} nicht gefunden. FFmpeg und FFprobe in PATH "
        "oder neben die EXE legen (alternativ STREAMCLIPPER_FFMPEG_DIR setzen)."
    )


def probe_video(path: str | Path) -> VideoInfo:
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Videodatei fehlt: {source}")
    result = subprocess.run(
        [tool_path("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate", "-of", "json", str(source)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        timeout=40,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    if not videos:
        raise ValueError("Keine Videospur gefunden.")
    v = videos[0]
    duration = float(data.get("format", {}).get("duration") or 0)
    if duration <= 0 or not math.isfinite(duration):
        raise ValueError("Videodauer konnte nicht ermittelt werden.")
    ratio = str(v.get("avg_frame_rate", "0/1"))
    try:
        numerator, denominator = ratio.split("/")
        fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return VideoInfo(
        path=str(source), duration=duration, width=int(v.get("width") or 0),
        height=int(v.get("height") or 0), fps=fps,
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
    )


def audio_levels(video: VideoInfo, progress: Progress | None = None,
                 cancelled: Cancelled | None = None, sample_rate: int = 8000) -> list[float]:
    """Decode first audio track to mono PCM and calculate RMS dBFS in ~1s buckets.

    Streaming decoder: memory usage remains bounded regardless of recording length.
    No external Python DSP packages are required.
    """
    if not video.has_audio:
        return []
    cmd = [tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
           "-i", video.path, "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(sample_rate),
           "-f", "s16le", "pipe:1"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    values: list[float] = []
    bytes_per_bucket = sample_rate * 2
    try:
        assert process.stdout is not None
        while True:
            if cancelled and cancelled():
                raise CancelledError("Analyse abgebrochen")
            # BufferedReader.read(n) fills n bytes unless EOF.
            chunk = process.stdout.read(bytes_per_bucket)
            if not chunk:
                break
            samples = array("h")
            samples.frombytes(chunk[: len(chunk) // 2 * 2])
            if sys.byteorder != "little":
                samples.byteswap()
            if not samples:
                break
            # Faster than calling math.pow per sample and independent from numpy.
            mean_square = sum(int(x) * int(x) for x in samples) / len(samples)
            db = 10 * math.log10(max(mean_square / (32768 * 32768), 1e-10))
            values.append(db)
            if progress and len(values) % 5 == 0:
                progress(min(100, int(100 * len(values) / video.duration)))
        if process.wait() != 0:
            raise RuntimeError("FFmpeg konnte die Audiospur nicht dekodieren.")
        if progress:
            progress(100)
        return values
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if process.stdout:
            process.stdout.close()


def safe_destination(folder: str | Path, basename: str) -> Path:
    """Find a new filename without overwriting existing exports."""
    directory = Path(folder).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / basename
    index = 2
    while candidate.exists():
        candidate = directory / (Path(basename).stem + f"_{index}" + Path(basename).suffix)
        index += 1
    return candidate


def build_export_command(video: VideoInfo, start: float, end: float, destination: str | Path,
                         mode: str = "blur", width: int = 1080, height: int = 1920,
                         ffmpeg_executable: str = "ffmpeg") -> list[str]:
    if mode not in {"blur", "crop"}:
        raise ValueError("Ungültiger Bildmodus: blur oder crop")
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValueError("Breite und Höhe müssen positive gerade Zahlen sein")
    if not (0 <= start < end <= video.duration + 0.1):
        raise ValueError("Ungültiges Clip-Zeitfenster")
    if mode == "crop":
        chain = (
            f"[0:v:0]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,format=yuv420p[v]"
        )
    else:
        chain = (
            "[0:v:0]split=2[bg][fg];"
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=20:2[back];"
            f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            "pad=ceil(iw/2)*2:ceil(ih/2)*2:0:0[front];"
            "[back][front]overlay=(W-w)/2:(H-h)/2:shortest=1,"
            "setsar=1,format=yuv420p[v]"
        )
    return [ffmpeg_executable, "-hide_banner", "-nostdin", "-loglevel", "error", "-n",
            "-ss", f"{start:.3f}", "-i", video.path, "-t", f"{end-start:.3f}",
            "-filter_complex", chain, "-map", "[v]", "-map", "0:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            str(destination)]


def export_clip(video: VideoInfo, start: float, end: float, destination: str | Path,
                mode: str = "blur", width: int = 1080, height: int = 1920,
                cancelled: Cancelled | None = None) -> Path:
    output = Path(destination).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_export_command(video, start, end, output, mode, width, height, tool_path("ffmpeg"))
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    try:
        # communicate drains stderr and avoids pipe deadlocks. For v0.1 cancellation
        # is supported before each clip, not while an individual clip renders.
        _stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            if output.exists():
                output.unlink()
            raise RuntimeError(f"FFmpeg-Export fehlgeschlagen: {stderr[-2000:]}")
        if cancelled and cancelled():
            raise CancelledError("Export abgebrochen")
        return output
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
