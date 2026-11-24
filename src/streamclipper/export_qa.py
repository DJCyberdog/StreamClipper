"""M12d: evidence-based MP4 acceptance, with bounded decode/loudness samples.

A completed render is only published after codec, dimensions, duration,
stream timestamps and real decoded frames pass. Audio loudness is sampled
(max 2 × 8 seconds) and *never* misrepresented as whole-VOD integrated LUFS.
No network, UI, source changes, or external Python dependencies.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .media import tool_path

SCHEMA_VERSION = 1
MAX_PROBE_BYTES = 1_000_000


@dataclass(frozen=True)
class QualityReport:
    schema_version: int
    status: str
    expected_codec: str
    actual_codec: str
    width: int
    height: int
    duration: float
    expected_duration: float
    video_start: float
    audio_present: bool
    audio_codec: str | None
    audio_start: float | None
    audio_end_delta: float | None
    sample_lufs: float | None
    sample_peak_dbfs: float | None
    sampled_seconds: float
    warnings: tuple[str, ...]
    file_sha256: str
    file_bytes: int
    created_utc: str


def _float(value: object) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def _run_probe(path: Path) -> dict:
    result = subprocess.run([
        tool_path("ffprobe"), "-v", "error",
        "-show_entries",
        "format=format_name,duration:stream=codec_type,codec_name,codec_tag_string,width,height,pix_fmt,start_time,duration,sample_rate",
        "-of", "json", str(path)], capture_output=True, check=True,
        timeout=45)
    if len(result.stdout) > MAX_PROBE_BYTES:
        raise ValueError("FFprobe-Antwort ist unerwartet groß")
    record = json.loads(result.stdout.decode("utf-8"))
    if not isinstance(record, dict):
        raise ValueError("Ungültige FFprobe-Metadaten")
    return record


def _decode_frame(path: Path, second: float) -> None:
    # A short decode is a stronger check than just reading the MP4 header.
    result = subprocess.run([
        tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-ss", f"{second:.3f}", "-i", str(path), "-map", "0:v:0",
        "-frames:v", "1", "-f", "framemd5", "-"],
        capture_output=True, timeout=60)
    # Some FFmpeg builds report exit status 0 for an empty 0-frame decode.
    # Require an actual frame checksum, not merely a successful process.
    frame_rows = [line for line in result.stdout.splitlines()
                  if line.strip() and not line.lstrip().startswith(b"#")]
    if result.returncode or not frame_rows:
        raise ValueError("Videoframe konnte nicht decodiert werden")


def _sample_loudness(path: Path, offset: float, seconds: float
                     ) -> tuple[float | None, float | None]:
    """Read FFmpeg ebur128 end summary; sampled, not program-wide loudness."""
    proc = subprocess.run([
        tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-nostats",
        "-loglevel", "info", "-ss", f"{offset:.3f}", "-i", str(path),
        "-t", f"{seconds:.3f}", "-map", "0:a:0", "-vn",
        "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, timeout=70)
    if proc.returncode:
        raise ValueError("Audiobereich konnte für den QA-Check nicht decodiert werden")
    output = proc.stderr.decode("utf-8", errors="replace")
    summary = output.rsplit("Summary:", 1)
    if len(summary) < 2:
        return None, None
    text = summary[-1]
    lufs = re.search(r"Integrated loudness:.*?\bI:\s*(-?(?:\d+(?:\.\d+)?|inf))\s+LUFS", text, re.S)
    peak = re.search(r"True peak:.*?\bPeak:\s*(-?(?:\d+(?:\.\d+)?|inf))\s+dBFS", text, re.S)
    return (_float(lufs.group(1)) if lufs else None,
            _float(peak.group(1)) if peak else None)


def inspect_export(path: str | Path, *, expected_codec: str,
                   width: int, height: int, duration: float,
                   audio_expected: bool) -> QualityReport:
    """Strict acceptance gates + advisory audio/compatibility observations.

    No live user media is read. Missing/damaged video and gross timestamp
    mismatches fail. Loudness thresholds are advisory, not false 'fixed' audio.
    """
    file = Path(path).resolve(strict=True)
    if not file.is_file() or file.stat().st_size < 512:
        raise ValueError("MP4 ist leer oder offensichtlich beschädigt")
    if expected_codec not in {"h264", "hevc"}:
        raise ValueError("Unbekannter QA-Zielcodec")
    if not 0 < duration <= 86400 or width < 2 or height < 2:
        raise ValueError("Ungültiger erwarteter Exportumfang")
    record = _run_probe(file)
    container = str(record.get("format", {}).get("format_name", ""))
    if "mp4" not in container and "mov" not in container:
        raise ValueError("Ausgabecontainer ist kein MP4")
    streams = record.get("streams", [])
    if not isinstance(streams, list):
        raise ValueError("Keine gültigen MP4-Streams")
    video = next((v for v in streams if v.get("codec_type") == "video"), None)
    audio = next((a for a in streams if a.get("codec_type") == "audio"), None)
    if video is None or video.get("codec_name") != expected_codec:
        raise ValueError("Ausgabevideocodec stimmt nicht mit dem Encoderprofil überein")
    if (video.get("width"), video.get("height")) != (width, height):
        raise ValueError("Falsche Ausgabeauflösung")
    if video.get("pix_fmt") != "yuv420p":
        raise ValueError("MP4 verwendet kein kompatibles yuv420p")
    actual_duration = _float(record.get("format", {}).get("duration"))
    if actual_duration is None or abs(actual_duration-duration) > max(.55, 1.0/24):
        raise ValueError("MP4-Dauer unterscheidet sich erheblich vom Clipfenster")
    vstart = _float(video.get("start_time"))
    if vstart is None or abs(vstart) > .55:
        raise ValueError("Ausgabevideospur beginnt nicht synchron bei Null")
    if audio_expected and (audio is None or audio.get("codec_name") != "aac"):
        raise ValueError("Audio fehlt oder ist kein AAC")
    warnings = []
    if expected_codec == "hevc":
        if video.get("codec_tag_string") != "hvc1":
            raise ValueError("HEVC-MP4 fehlt die hvc1-Kompatibilitätskennung")
        warnings.append("HEVC kann auf älteren Geräten/Uploadplattformen inkompatibel sein")
    if actual_duration < duration-.10:
        warnings.append("Ausgabe ist leicht kürzer als das gewünschte Clipfenster")
    audio_start = _float(audio.get("start_time")) if audio else None
    audio_duration = _float(audio.get("duration")) if audio else None
    audio_end_delta = None
    if audio is not None:
        if audio.get("codec_name") != "aac":
            warnings.append("Audiospur ist nicht AAC")
        if audio_start is not None and abs(audio_start-vstart) > .25:
            raise ValueError("Audio-/Videostart weicht erheblich voneinander ab")
        if audio_start is not None and audio_duration is not None:
            audio_end_delta = audio_start+audio_duration-actual_duration
            if abs(audio_end_delta) > .6:
                raise ValueError("Audio-/Video-Endzeit nicht ausreichend synchron")
    # Sample start, center, and last decodable frame; no 6h decode sweep.
    offsets = sorted(set((0.0, max(0.0, actual_duration/2-.05),
                          max(0.0, actual_duration-min(1.0,actual_duration/2)))))
    for timestamp in offsets:
        _decode_frame(file, timestamp)
    levels = []
    seconds_sampled = 0.0
    if audio:
        sample_at = (0.0, max(0.0, actual_duration/2-4))
        seen = set()
        for at in sample_at:
            at = round(at, 2)
            if at in seen:
                continue
            seen.add(at)
            length = min(8.0, actual_duration-at)
            if length <= .05:
                continue
            level = _sample_loudness(file, at, length)
            levels.append(level)
            seconds_sampled += length
    valid_lufs = [x for x, _ in levels if x is not None]
    valid_peak = [x for _, x in levels if x is not None]
    integrated = max(valid_lufs) if valid_lufs else None
    peak = max(valid_peak) if valid_peak else None
    if peak is not None and peak > -.1:
        warnings.append("Audio-True-Peak nahe 0 dBFS – mögliche Übersteuerung")
    if integrated is not None and integrated < -23:
        warnings.append("Audio im geprüften Sample ungewöhnlich leise")
    if integrated is None and audio is not None:
        warnings.append("Sample-Lautheit nicht bestimmbar (z. B. Stille)")
    checksum = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            checksum.update(chunk)
    return QualityReport(
        SCHEMA_VERSION, "PASS", expected_codec, str(video["codec_name"]),
        width, height, actual_duration, duration, vstart,
        audio is not None, str(audio["codec_name"]) if audio else None,
        audio_start, audio_end_delta,
        integrated, peak, seconds_sampled,
        tuple(warnings), checksum.hexdigest(), file.stat().st_size,
        datetime.now(timezone.utc).isoformat())


def report_path(video: str | Path) -> Path:
    path = Path(video)
    return path.with_name(path.name + ".qa.json")


def write_report(report: QualityReport, video: str | Path) -> Path:
    """Atomic sidecar; no media file is ever rewritten."""
    target = report_path(video)
    payload = json.dumps(asdict(report), ensure_ascii=False,
                         sort_keys=True, indent=2).encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, delete=False,
                prefix="." + target.name + ".", suffix=".tmp") as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def read_report(video: str | Path) -> QualityReport:
    target = report_path(video)
    if target.stat().st_size > 100_000:
        raise ValueError("QA-Bericht ist zu groß")
    record = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("QA-Berichtsversion ungültig")
    result = QualityReport(**{
        **record, "warnings": tuple(record.get("warnings", []))})
    if result.status != "PASS":
        raise ValueError("QA-Bericht nicht bestanden")
    return result
