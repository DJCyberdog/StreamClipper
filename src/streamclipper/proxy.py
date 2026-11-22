"""M11c-4: offline preview proxies with source-bound, atomic cache records.

Only the original VideoInfo and AnalysisResult define editing/export times.
A proxy is display media, never a source for analysis or final rendering.
O(1) source fingerprints use file metadata rather than hashing 6h VODs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable

from .media import CancelledError, encode_preview_proxy, probe_video, stream_offsets
from .models import VideoInfo
from .portable import installation_directory

PROXY_VERSION = 1
MAX_OFFSET_SECONDS = .15
MAX_DURATION_DRIFT_SECONDS = .30


@dataclass(frozen=True)
class ProxyTiming:
    original_duration: float
    proxy_duration: float
    original_video_offset: float  # video stream relative to original container
    proxy_video_offset: float     # video stream relative to proxy container


@dataclass(frozen=True)
class ProxyState:
    media_path: Path
    timing: ProxyTiming
    source_fingerprint: str


def _bound_ms(value: int | float, duration: float) -> int:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Ungültige Vorschau-Zeit")
    return max(0, min(round(duration * 1000), round(value)))


def original_to_proxy_ms(position_ms: int | float, timing: ProxyTiming) -> int:
    """PTS-based mapping, *not* frame-index/CFR mapping; clamps first frame."""
    original = _bound_ms(position_ms, timing.original_duration) / 1000
    return _bound_ms(
        (original - timing.original_video_offset + timing.proxy_video_offset) * 1000,
        timing.proxy_duration)


def proxy_to_original_ms(position_ms: int | float, timing: ProxyTiming) -> int:
    proxy = _bound_ms(position_ms, timing.proxy_duration) / 1000
    return _bound_ms(
        (proxy - timing.proxy_video_offset + timing.original_video_offset) * 1000,
        timing.original_duration)


def fingerprint(video: VideoInfo) -> str:
    path = Path(video.path).resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError("Die Originalaufnahme fehlt")
    stat = path.stat()
    if stat.st_size <= 0 or video.duration <= 0 or not math.isfinite(video.duration):
        raise ValueError("Originalaufnahme ist ungültig")
    details = {
        "version": PROXY_VERSION, "path": os.path.normcase(str(path)),
        "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "duration": video.duration, "width": video.width, "height": video.height,
        "fps": video.fps, "has_audio": video.has_audio,
        "preset": "h264-854x480-vfr-aac-96k-v1",
    }
    return hashlib.sha256(json.dumps(details, sort_keys=True, allow_nan=False)
                          .encode("utf-8")).hexdigest()[:40]


def cache_path(video: VideoInfo, *, root: Path | None = None) -> Path:
    directory = Path(root) if root is not None else (
        installation_directory() / "data" / "proxies")
    return directory / (fingerprint(video) + ".mp4")


def _validate_timing(timing: ProxyTiming) -> None:
    nums = (timing.original_duration, timing.proxy_duration,
            timing.original_video_offset, timing.proxy_video_offset)
    if not all(isinstance(n, (int, float)) and math.isfinite(n) for n in nums):
        raise ValueError("Proxy-Zeitbasis enthält ungültige Werte")
    if timing.original_duration <= 0 or timing.proxy_duration <= 0:
        raise ValueError("Proxy hat keine gültige Zeitbasis")
    if abs(timing.proxy_duration - timing.original_duration) > MAX_DURATION_DRIFT_SECONDS:
        raise ValueError("Proxy-Zeitdrift gegenüber Originalaufnahme zu groß")
    if abs(timing.original_video_offset) > MAX_OFFSET_SECONDS:
        raise ValueError("Proxy-Startversatz der Originalaufnahme zu groß")
    if abs(timing.proxy_video_offset) > MAX_OFFSET_SECONDS:
        raise ValueError("Proxy-Startversatz der Vorschau zu groß")


def cached_proxy(video: VideoInfo, *, root: Path | None = None) -> ProxyState | None:
    """Fast metadata-only lookup on the GUI thread; never decode here."""
    try:
        target = cache_path(video, root=root)
        metadata = target.with_suffix(".json")
        if metadata.is_symlink() or target.is_symlink() or not target.is_file():
            return None
        if not metadata.is_file() or metadata.stat().st_size > 8192:
            return None
        record = json.loads(metadata.read_text(encoding="utf-8"))
        if (record["version"] != PROXY_VERSION
                or record["source_fingerprint"] != fingerprint(video)):
            return None
        stat = target.stat()
        if stat.st_size <= 0 or stat.st_size != record["proxy_bytes"] or (
                stat.st_mtime_ns != record["proxy_mtime_ns"]):
            return None
        timing = ProxyTiming(**record["timing"])
        _validate_timing(timing)
        if abs(timing.original_duration - video.duration) > .01:
            return None
        return ProxyState(target, timing, record["source_fingerprint"])
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None


def ensure_proxy(video: VideoInfo, *, root: Path | None = None,
                 cancelled: Callable[[], bool] | None = None,
                 progress: Callable[[int], None] | None = None) -> ProxyState:
    """Make/reuse a complete proxy; never expose temporary or invalid files."""
    if cancelled and cancelled():
        raise CancelledError("Proxy-Erstellung abgebrochen")
    current = cached_proxy(video, root=root)
    if current is not None:
        if progress:
            progress(100)
        return current
    expected = fingerprint(video)
    source_offset, source_audio_offset = stream_offsets(video.path)
    if not math.isfinite(source_audio_offset) or abs(source_audio_offset) > MAX_OFFSET_SECONDS:
        raise ValueError("Audio-Startversatz der Aufnahme zu groß für Proxy")
    if abs(source_offset) > MAX_OFFSET_SECONDS or not math.isfinite(source_offset):
        raise ValueError("Proxy-Startversatz der Aufnahme zu groß")

    destination = cache_path(video, root=root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".proxy-", dir=destination.parent) as temp:
        work = Path(temp)
        partial = work / "render.partial.mp4"
        encode_preview_proxy(
            video, partial, cancelled=cancelled,
            progress=(lambda p: progress(min(99, p))) if progress else None)
        if cancelled and cancelled():
            raise CancelledError("Proxy-Erstellung abgebrochen")
        if fingerprint(video) != expected:
            raise ValueError("Originalaufnahme wurde während der Proxy-Erstellung verändert")
        encoded = probe_video(partial)
        if not (0 < encoded.width <= 854 and 0 < encoded.height <= 480
                and encoded.width % 2 == 0 and encoded.height % 2 == 0):
            raise ValueError("Proxy-Auflösung ist ungültig")
        proxy_offset, proxy_audio_offset = stream_offsets(partial)
        if not math.isfinite(proxy_audio_offset) or abs(proxy_audio_offset) > MAX_OFFSET_SECONDS:
            raise ValueError("Audio-Startversatz des Proxys zu groß")
        timing = ProxyTiming(
            video.duration, encoded.duration, source_offset, proxy_offset)
        _validate_timing(timing)
        if fingerprint(video) != expected:
            raise ValueError("Originalaufnahme wurde während der Proxy-Erstellung verändert")
        stat = partial.stat()
        record = {
            "version": PROXY_VERSION,
            "source_fingerprint": expected,
            "timing": asdict(timing),
            "proxy_bytes": stat.st_size,
            "proxy_mtime_ns": stat.st_mtime_ns,
        }
        staged_meta = work / "proxy.json"
        with staged_meta.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        if cancelled and cancelled():
            raise CancelledError("Proxy-Erstellung abgebrochen")
        # The manifest is published last. If power fails after the media move,
        # no valid new proxy will be offered before a complete manifest exists.
        os.replace(partial, destination)
        os.replace(staged_meta, destination.with_suffix(".json"))
    verified = cached_proxy(video, root=root)
    if verified is None:
        raise RuntimeError("Proxy wurde nicht vollständig veröffentlicht")
    if progress:
        progress(100)
    return verified
