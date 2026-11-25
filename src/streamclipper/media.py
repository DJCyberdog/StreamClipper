"""FFmpeg / FFprobe subprocess boundaries (never execute via shell)."""
from __future__ import annotations

from array import array
import queue
import json
import math
import tempfile
import threading
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable

from .models import VideoInfo, TranscriptSegment
from .render_graph import AudioLayer, VisualLayer, MAX_VISUAL_LAYERS
from .encoders import ENCODERS, encoder_options, resolve_encoder

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


def probe_audio_duration(path: str | Path) -> float:
    """Validate a local audio-bearing file and retrieve finite duration."""
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise ValueError("Audiodatei ist kein regulärer Dateipfad")
    report = subprocess.run(
        [tool_path("ffprobe"), "-v", "error",
         "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", str(source)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=40)
    data = json.loads(report.stdout)
    duration = float(data.get("format", {}).get("duration") or 0)
    if (not any(x.get("codec_type") == "audio" for x in data.get("streams", []))
            or not math.isfinite(duration) or duration <= 0):
        raise ValueError("Die Datei enthält keine gültige Audiospur")
    return duration


def probe_still_image(path: str | Path) -> tuple[int, int]:
    """Preflight a single local image without loading it into process memory."""
    source = Path(path).resolve(strict=True)
    if (not source.is_file()
            or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}):
        raise ValueError("Nur lokale PNG/JPEG/WebP-Bilder werden unterstützt")
    result = subprocess.run(
        [tool_path("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_type,width,height",
         "-of", "json", str(source)], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=40)
    data = json.loads(result.stdout)
    # -select_streams v:0 already filters to the first video decoder.
    # Some FFprobe releases omit codec_type in reduced -show_entries output.
    stream = next(iter(data.get("streams", [])), None)
    if (stream is None or not 1 <= int(stream.get("width") or 0) <= 16384
            or not 1 <= int(stream.get("height") or 0) <= 16384):
        raise ValueError("Grafikdatei enthält kein gültiges Einzelbild")
    return int(stream["width"]), int(stream["height"])


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


def video_dimensions(mode: str, width: int = 1080, height: int = 1920) -> tuple[int, int]:
    """Keep old 9:16 default but make smart16 landscape by default."""
    if mode == "smart16" and (width, height) == (1080, 1920):
        return 1920, 1080
    return width, height


def build_export_command(video: VideoInfo, start: float, end: float, destination: str | Path,
                         mode: str = "blur", width: int = 1080, height: int = 1920,
                         ffmpeg_executable: str = "ffmpeg", *,
                         motion_points=None, burned_captions: bool = False,
                         audio_layers: tuple[AudioLayer, ...] = (),
                         visual_layers: tuple[VisualLayer, ...] = (),
                         encoder: str = "cpu_h264", region=None,
                         fit_region: bool = False, force_audio: bool = False,
                         director=None, restored_video=None, base_audio_enabled: bool = True) -> list[str]:
    """Construct command without a shell. Optional captions use a local ASS file.

    If burned_captions, the caller must write `captions.ass` in the FFmpeg cwd.
    Paths never enter the filtergraph, avoiding Windows `C:`/Unicode escaping.
    """
    if mode not in {"blur", "crop", "smart16", "smart9"}:
        raise ValueError("Ungültiger Bildmodus: blur, crop, smart16 oder smart9")
    width, height = video_dimensions(mode, width, height)
    if width <= 0 or height <= 0 or width % 2 or height % 2:
        raise ValueError("Breite und Höhe müssen positive gerade Zahlen sein")
    if not (0 <= start < end <= video.duration + 0.1):
        raise ValueError("Ungültiges Clip-Zeitfenster")
    final_label = "base" if (burned_captions or visual_layers) else "v"
    if director is not None:
        director.validate()
    if director is not None and director.keys:
        from .smart_director import camera_filter
        chain = f"[0:v:0]{camera_filter(director.keys, video, width, height, start)}[{final_label}]"
    elif region is not None:
        if (len(region) != 4 or not all(math.isfinite(v) for v in region)):
            raise ValueError("Ungültige Bildregion")
        x, y, w, h = region
        if not (0 <= x < 1 and 0 <= y < 1 and .01 <= w <= 1 and .01 <= h <= 1
                and x+w <= 1.000000001 and y+h <= 1.000000001):
            raise ValueError("Ungültige Bildregion")
        # Explicit normalized source rectangle; even edges for 4:2:0.
        left = max(0, math.ceil((x*video.width-1e-8)/2)*2)
        top = max(0, math.ceil((y*video.height-1e-8)/2)*2)
        right = min(video.width, math.floor(((x+w)*video.width+1e-8)/2)*2)
        bottom = min(video.height, math.floor(((y+h)*video.height+1e-8)/2)*2)
        cw, ch = right-left, bottom-top
        if min(cw,ch) < 2:
            raise ValueError("Bildregion zu klein")
        framing = (f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2" if fit_region else
                   f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                   f"crop={width}:{height}")
        chain = (f"[0:v:0]crop={cw}:{ch}:{left}:{top},{framing},"
                 f"setsar=1,format=yuv420p[{final_label}]")
    elif mode in {"smart16", "smart9"}:
        from .reframe import FocusPoint, smart_crop_filter
        if not motion_points:
            motion_points = [FocusPoint(0., .5, .5)]
        zoom = 1.18 if mode == "smart16" else 1.0
        chain = f"[0:v:0]{smart_crop_filter(width, height, motion_points, zoom=zoom)}[{final_label}]"
    elif mode == "crop":
        chain = (
            f"[0:v:0]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,format=yuv420p[{final_label}]"
        )
    else:
        chain = (
            "[0:v:0]split=2[bg][fg];"
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=20:2[back];"
            f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            "pad=ceil(iw/2)*2:ceil(ih/2)*2:0:0[front];"
            "[back][front]overlay=(W-w)/2:(H-h)/2:shortest=1,"
            f"setsar=1,format=yuv420p[{final_label}]"
        )
    if director is not None:
        from .smart_director import mask_filters
        masks = mask_filters(director, video, start, end)
        if masks:
            chain = "[0:v:0]setpts=PTS-STARTPTS," + masks + "[masked];" + chain.replace("[0:v:0]", "[masked]", 1)
    inputs = [ffmpeg_executable, "-hide_banner", "-nostdin", "-loglevel", "error", "-n",
              "-ss", f"{start:.3f}", "-i", video.path]
    if len(visual_layers) > MAX_VISUAL_LAYERS:
        raise ValueError("Zu viele Video-/Grafik-Layer")
    base_label = "base"
    duration = end-start
    for i, layer in enumerate(visual_layers, start=1):
        values = (layer.source_start, layer.source_end,
                  layer.timeline_offset, layer.x, layer.y,
                  layer.width, layer.height, layer.opacity)
        if (layer.kind not in {"video", "overlay"}
                or not os.path.isabs(layer.source_path)
                or not all(math.isfinite(v) for v in values)
                or not 0 <= layer.source_start < layer.source_end <= 86400
                or not 0 <= layer.timeline_offset < duration
                or layer.timeline_offset+layer.source_end-layer.source_start >
                   duration+.005
                or not 0 <= layer.x <= 1 or not 0 <= layer.y <= 1
                or not .05 <= layer.width <= 1
                or not .05 <= layer.height <= 1
                or layer.x+layer.width > 1.000001
                or layer.y+layer.height > 1.000001
                or not 0 <= layer.opacity <= 1):
            raise ValueError("Ungültiger Bild-Layer im Rendergraph")
        if layer.kind == "video":
            inputs += ["-ss", f"{layer.source_start:.6f}",
                       "-i", layer.source_path]
        else:
            inputs += ["-loop", "1", "-framerate", "30",
                       "-i", layer.source_path]
        # Pad with transparent borders to preserve aspect ratio. Every
        # dimension is bounded and numeric (no filenames inside filtergraph).
        box_w = min(width, max(2, round(width * layer.width / 2) * 2))
        box_h = min(height, max(2, round(height * layer.height / 2) * 2))
        x = max(0, min(width-box_w, round(width*layer.x)))
        y = max(0, min(height-box_h, round(height*layer.y)))
        length = layer.source_end-layer.source_start
        chain += (
            f";[{i}:v:0]trim=duration={length:.6f},"
            f"setpts=PTS-STARTPTS+{layer.timeline_offset:.6f}/TB,"
            f"scale={box_w}:{box_h}:force_original_aspect_ratio=decrease,"
            f"format=rgba,"
            f"pad={box_w}:{box_h}:(ow-iw)/2:(oh-ih)/2:color=black@0,"
            f"colorchannelmixer=aa={layer.opacity:.6f}[visual_{i}]"
            f";[{base_label}][visual_{i}]overlay={x}:{y}:"
            f"shortest=0:repeatlast=0:eof_action=pass:format=auto[composed_{i}]")
        base_label = f"composed_{i}"
    if visual_layers:
        if burned_captions:
            chain += f";[{base_label}]ass=filename=captions.ass,format=yuv420p[v]"
        else:
            chain += f";[{base_label}]format=yuv420p[v]"
    elif burned_captions:
        chain += ";[base]ass=filename=captions.ass,format=yuv420p[v]"
    if type(base_audio_enabled) is not bool:raise ValueError("Ungültiger Originalton-Schalter")
    base_audio = video.has_audio and base_audio_enabled
    audio_map = "0:a:0?" if base_audio_enabled else None
    if audio_layers:
        if len(audio_layers) > 16:
            raise ValueError("Zu viele gleichzeitige Audioquellen")
        duration = end - start
        if base_audio:
            chain += (
                f";[0:a:0]aresample=async=1:first_pts=0,"
                f"aformat=sample_rates=48000:channel_layouts=stereo,"
                f"apad,atrim=duration={duration:.6f}[base_audio]")
        else:
            chain += (
                f";anullsrc=r=48000:cl=stereo,"
                f"atrim=duration={duration:.6f}[base_audio]")
        labels = ["[base_audio]"]
        for i, layer in enumerate(audio_layers, start=1+len(visual_layers)):
            if (not os.path.isabs(layer.source_path)
                    or not 0 <= layer.source_start < layer.source_end
                    or layer.timeline_offset < 0
                    or not -60 <= layer.gain_db <= 12
                    or not all(math.isfinite(v) for v in (
                        layer.source_start,layer.source_end,
                        layer.timeline_offset,layer.gain_db))
                    or layer.timeline_offset + layer.source_end-layer.source_start >
                    duration + .005):
                raise ValueError("Ungültiger Audio-Clip im Rendergraph")
            inputs += ["-ss", f"{layer.source_start:.6f}", "-i", layer.source_path]
            segment = layer.source_end-layer.source_start
            delay = round(layer.timeline_offset * 1000)
            chain += (
                f";[{i}:a:0]atrim=duration={segment:.6f},"
                "asetpts=PTS-STARTPTS,"
                "aformat=sample_rates=48000:channel_layouts=stereo,"
                f"volume={layer.gain_db:.3f}dB,"
                f"adelay={delay}:all=1,apad,"
                f"atrim=duration={duration:.6f}[audio_{i}]")
            labels.append(f"[audio_{i}]")
        chain += (
            ";" + "".join(labels)
            + f"amix=inputs={len(labels)}:duration=first:"
              "normalize=0:dropout_transition=0,"
            + f"atrim=duration={duration:.6f}[audio_out]")
        audio_map = "[audio_out]"
    if force_audio and not (base_audio or audio_layers):
        chain += f";anullsrc=r=48000:cl=stereo,atrim=duration={duration:.6f}[scene_silence]"
        audio_map = "[scene_silence]"
    if restored_video is not None:
        # Append after all existing media inputs so A/V layer indices stay
        # unchanged. Original audio keeps its original seek and timing.
        index = 1 + len(visual_layers) + len(audio_layers)
        inputs += ["-i", str(restored_video)]
        chain = chain.replace("[0:v:0]", f"[{index}:v:0]")
    return inputs + [
            "-t", f"{end-start:.3f}",
            "-filter_complex", chain, "-map", "[v]", *(["-map", audio_map] if audio_map is not None else ["-an"]),
            *encoder_options(encoder),
            "-c:a", "aac", "-b:a", "160k",
            *(["-ar", "48000", "-ac", "2"] if force_audio else []),
            "-movflags", "+faststart",
            str(destination)]


def _stop_process(proc: subprocess.Popen) -> None:
    """Reap a directly spawned FFmpeg process, even if it ignores terminate."""
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except (subprocess.TimeoutExpired, OSError):
            if proc.poll() is None:
                proc.kill()
    proc.wait()  # Important on POSIX: never leave a zombie process.


def _progress_seconds(key: str, value: str) -> float | None:
    """FFmpeg emits microseconds in both out_time_us and legacy out_time_ms."""
    try:
        if key in {"out_time_us", "out_time_ms"}:
            return max(0.0, int(value) / 1_000_000)
        if key == "out_time":
            hours, minutes, seconds = value.split(":")
            return max(0.0, int(hours) * 3600 + int(minutes) * 60 + float(seconds))
    except (ValueError, OverflowError):
        pass
    return None


def _publish_without_overwrite(partial: Path, requested: Path) -> Path:
    """Publish a *finished* MP4 atomically, without a check-then-move race.

    Hard-link creation is an exclusive, atomic operation on the same filesystem.
    Windows os.rename also fails when the destination already exists, so it is
    a fallback for volumes without hard-link support (such as some shares).
    """
    for index in range(1, 100001):
        if index == 1:
            target = requested
        else:
            target = requested.with_name(
                f"{requested.stem}_{index}{requested.suffix}"
            )
        try:
            os.link(partial, target)
        except FileExistsError:
            continue
        except OSError:
            if os.name != "nt":
                raise
            try:
                os.rename(partial, target)
            except FileExistsError:
                continue
        return target
    raise FileExistsError("Kein freier Export-Dateiname gefunden.")


def export_clip(video: VideoInfo, start: float, end: float, destination: str | Path,
                mode: str = "blur", width: int = 1080, height: int = 1920,
                cancelled: Cancelled | None = None,
                progress: Progress | None = None, *,
                transcript: list[TranscriptSegment] | None = None,
                burn_subtitles: bool = False,
                subtitle_offset: float = 0.0,
                audio_layers: tuple[AudioLayer, ...] = (),
                visual_layers: tuple[VisualLayer, ...] = (),
                encoder: str = "cpu_h264",
                encoder_notice: Callable[[str], None] | None = None,
                region=None, fit_region: bool = False, force_audio: bool = False,
                director=None, motion_analysis_end=None, caption_style=None, base_audio_enabled: bool = True) -> Path:
    """Encode with cancellable progress and publish only validated, complete MP4s.

    The temporary file is on the destination filesystem for atomic publication.
    Existing outputs and the source video are never opened for writing.
    A cancelled or failed export leaves no final MP4 and cleans its temporary dir.
    The *returned* path can differ from destination if another export reserved it.
    """
    output = Path(destination).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if cancelled and cancelled():
        raise CancelledError("Export abgebrochen")
    duration = end - start
    # Validate parameters before allocating temp files or starting FFmpeg.
    width, height = video_dimensions(mode, width, height)
    if encoder not in ENCODERS:
        raise ValueError("Unbekanntes Encoderprofil")
    # Validate the graph without GPU calls; actual NVENC probing happens
    # inside this export worker only after source preflight.
    validation_encoder = "cpu_hevc" if encoder.endswith("hevc") else "cpu_h264"
    build_export_command(
        video, start, end, output, mode, width, height,
        audio_layers=audio_layers, visual_layers=tuple(layer for layer in visual_layers if layer.callout is None),
        encoder=validation_encoder, region=region, fit_region=fit_region,
        force_audio=force_audio, director=director,base_audio_enabled=base_audio_enabled)
    for layer in visual_layers:
        if layer.callout is not None:
            layer.callout.validate()
            continue
        if cancelled and cancelled():
            raise CancelledError("Export abgebrochen")
        if layer.kind == "video":
            other = probe_video(layer.source_path)
            if layer.source_end > other.duration+.1:
                raise ValueError(
                    f"Videodatei für Clip {layer.id} ist zu kurz oder wurde ausgetauscht")
        else:
            probe_still_image(layer.source_path)
    for layer in audio_layers:
        actual_duration = probe_audio_duration(layer.source_path)
        if layer.source_end > actual_duration + .1:
            raise ValueError(
                f"Audioquelle des Spurclips {layer.id} ist zu kurz oder wurde ausgetauscht")
    if not math.isfinite(subtitle_offset) or abs(subtitle_offset) > 5:
        raise ValueError("Untertitelversatz muss zwischen -5 und +5 Sekunden liegen")
    if burn_subtitles and not transcript:
        raise ValueError("Untertitel benötigen zuerst ein Whisper-Transkript.")

    with tempfile.TemporaryDirectory(prefix=f".{output.stem}-", dir=output.parent) as workdir:
        partial = Path(workdir) / f"{output.stem}.partial.mp4"
        if any(layer.callout is not None for layer in visual_layers):
            from dataclasses import replace
            from .callouts import rasterize
            materialized=[]
            for i,layer in enumerate(visual_layers):
                if cancelled and cancelled():raise CancelledError('Export abgebrochen')
                if layer.callout is not None:
                    target=Path(workdir)/f'callout-{i}.png'
                    rasterize(layer.callout,max(2,round(width*layer.width/2)*2),max(2,round(height*layer.height/2)*2)).save(target)
                    layer=replace(layer,source_path=str(target.resolve()),callout=None)
                materialized.append(layer)
            visual_layers=tuple(materialized)
        restored_video = None
        if director is not None and director.inpaint_model:
            from .scene_restoration import restore_scene_video
            if encoder_notice:
                encoder_notice("Experimentelles VACE-Inpainting · lokales Modell wird geladen")
            restored_video = restore_scene_video(video,start,motion_analysis_end or end,
                director,Path(workdir)/"restored.mkv",cancelled=cancelled,
                progress=(lambda i,n: encoder_notice(f"VACE {i}/{n}")) if encoder_notice else None)
        motion_points = None
        if region is None and not (director and director.keys) and mode in {"smart16", "smart9"}:
            from .reframe import clip_motion_path
            motion_points = clip_motion_path(video, start, motion_analysis_end or end, cancelled=cancelled)
        if burn_subtitles:
            from .captioning import render_ass
            from .caption_style import CaptionStyle
            (Path(workdir) / "captions.ass").write_text(
                render_ass(transcript or [], start, end, width=width, height=height,
                           offset_seconds=subtitle_offset,
                           safe_position=director.caption_safe if director else 'bottom',
                           caption_style=caption_style or CaptionStyle()),
                encoding="utf-8-sig", newline="\n")
        if cancelled and cancelled():
            raise CancelledError("Export abgebrochen")
        ffmpeg_exe = tool_path("ffmpeg")
        plan = resolve_encoder(encoder, ffmpeg_exe)
        if encoder_notice:
            if plan.probe_failed:
                encoder_notice(
                    "NVENC-Test fehlgeschlagen; CPU-Encoding (" +
                    ("HEVC" if encoder.endswith("hevc") else "H.264") +
                    ") wird verwendet.")
            else:
                encoder_notice("Encoder: " + plan.primary.replace("_", " "))
        candidates = (plan.primary,) + (
            (plan.fallback,) if plan.fallback else ())
        for attempt, profile in enumerate(candidates):
            if cancelled and cancelled():
                raise CancelledError("Export abgebrochen")
            # Every retry starts with a clean partial, never appends to an
            # incomplete GPU output. Final MP4 publication happens once.
            partial.unlink(missing_ok=True)
            cmd = build_export_command(
                video, start, end, partial, mode, width, height,
                ffmpeg_exe, motion_points=motion_points,
                burned_captions=burn_subtitles,
                audio_layers=audio_layers, visual_layers=visual_layers,
                encoder=profile, region=region, fit_region=fit_region,
                force_audio=force_audio, director=director, restored_video=restored_video,base_audio_enabled=base_audio_enabled)
            cmd[1:1] = ["-progress", "pipe:1", "-stats_period", "0.25"]
            with tempfile.TemporaryFile(mode="w+b") as stderr_log:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=stderr_log,
                    text=True, encoding="utf-8", errors="replace",
                    cwd=workdir)
                updates: queue.Queue[float] = queue.Queue()

                def read_progress() -> None:
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        key, separator, value = line.strip().partition("=")
                        if separator:
                            seconds = _progress_seconds(key, value)
                            if seconds is not None:
                                updates.put(seconds)

                reader = threading.Thread(
                    target=read_progress, daemon=True,
                    name="streamclipper-ffmpeg-progress")
                reader.start()
                last_progress = -1
                try:
                    while (proc.poll() is None or reader.is_alive()
                           or not updates.empty()):
                        if cancelled and cancelled():
                            raise CancelledError("Export abgebrochen")
                        try:
                            seconds = updates.get(timeout=0.10)
                        except queue.Empty:
                            continue
                        value = max(0, min(99, int(seconds / duration * 100)))
                        if progress and value > last_progress:
                            progress(value)
                            last_progress = value
                    proc.wait()
                    if cancelled and cancelled():
                        raise CancelledError("Export abgebrochen")
                    if proc.returncode != 0:
                        stderr_log.flush()
                        stderr_log.seek(0, os.SEEK_END)
                        stderr_log.seek(max(0, stderr_log.tell() - 2000))
                        details = stderr_log.read().decode(
                            "utf-8", errors="replace")
                        if attempt == 0 and plan.fallback:
                            if encoder_notice:
                                encoder_notice(
                                    "NVENC-Encoding fehlgeschlagen; "
                                    "unvollständiges Ergebnis verworfen, "
                                    "CPU-Encoding wird neu gestartet.")
                            if progress:
                                progress(0)
                            continue
                        raise RuntimeError(
                            f"FFmpeg-Export fehlgeschlagen ({profile}): {details}")
                    if not partial.is_file() or partial.stat().st_size == 0:
                        raise RuntimeError(
                            "FFmpeg hat keine fertige MP4-Datei erzeugt.")
                    # M12d: validate actual decode, codec, stream timing and
                    # bounded audio samples BEFORE exposing the finished MP4.
                    # No finished result is published if any QA gate fails.
                    from .export_qa import inspect_export, write_report
                    expected_codec = (
                        "hevc" if profile.endswith("hevc") else "h264")
                    if encoder_notice:
                        encoder_notice("Render abgeschlossen · MP4-Qualitätsprüfung …")
                    quality = inspect_export(
                        partial, expected_codec=expected_codec,
                        width=width, height=height, duration=duration,
                        audio_expected=((video.has_audio and base_audio_enabled) or bool(audio_layers) or force_audio))
                    if cancelled and cancelled():
                        raise CancelledError("Export abgebrochen")
                    published = _publish_without_overwrite(partial, output)
                    # A failure here leaves a verified standalone MP4 but no
                    # queue receipt. Recovery intentionally BLOCKS this path
                    # instead of duplicating an already completed file.
                    write_report(quality, published)
                    if encoder_notice:
                        encoder_notice(
                            "MP4-QA bestanden · " + str(len(quality.warnings))
                            + " Hinweis(e) · Bericht neben der MP4")
                    if progress:
                        progress(100)
                    return published
                finally:
                    _stop_process(proc)
                    reader.join(timeout=2)
                    if proc.stdout:
                        proc.stdout.close()
        raise RuntimeError("Alle Encoder-Versuche sind fehlgeschlagen.")


def sampled_jpeg_frames(video: VideoInfo, *, max_frames: int = 180,
                        cancelled: Cancelled | None = None,
                        timestamps: list[float] | None = None):
    """Seek across the entire VOD; do not decode hours of intervening frames.

    Each requested timestamp is decoded into one JPEG via FFmpeg. Peak resident
    memory stays bounded, processing is interruptible even during a slow seek,
    and timestamps represent requested sampling positions, not verified events.
    """
    if max_frames < 1 or max_frames > 2000:
        raise ValueError("max_frames muss zwischen 1 und 2000 liegen")
    if video.duration <= 0:
        raise ValueError("Ungültige Videodauer")
    if timestamps is not None:
        if len(timestamps) > max_frames or any(
                not math.isfinite(at) or at < 0 or at >= video.duration
                for at in timestamps):
            raise ValueError("Ungültige CLIP-Zeitstempel")
        positions = sorted(set(timestamps))
    else:
        count = max(1, min(max_frames, int(math.ceil(video.duration / 3.0))))
        interval = video.duration / count
        positions = [(index + 0.5) * interval for index in range(count)]
    ffmpeg = tool_path("ffmpeg")
    for at in positions:
        if cancelled and cancelled():
            raise CancelledError("Analyse abgebrochen")
        cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
               "-ss", f"{at:.3f}", "-i", video.path,
               "-map", "0:v:0", "-an", "-sn", "-frames:v", "1",
               "-vf", "scale=320:-2:flags=fast_bilinear", "-q:v", "6",
               "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                if cancelled and cancelled():
                    raise CancelledError("Analyse abgebrochen")
                try:
                    frame, _ = proc.communicate(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg konnte Frame bei {at:.2f}s nicht dekodieren.")
            if not frame.startswith(b"\xff\xd8") or not frame.endswith(b"\xff\xd9"):
                raise RuntimeError(f"Ungültiger JPEG-Frame bei {at:.2f}s.")
            if len(frame) > 8_000_000:
                raise RuntimeError("Ein einzelnes Video-Frame überschreitet 8 MB.")
            yield round(at, 3), frame
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if proc.stdout:
                proc.stdout.close()


def waveform_peaks(video: VideoInfo, *, max_bins: int = 8192,
                   cancelled: Cancelled | None = None,
                   sample_rate: int = 600) -> list[float]:
    """Compute a bounded audio waveform suitable for a 6+ hour Qt timeline.

    Stream decoded mono PCM at a low sample rate; never buffer the entire
    recording. The result holds <= max_bins normalized RMS amplitudes.
    This is optional and independent of Whisper/CLIP and highlight scoring.
    """
    if not video.has_audio:
        return []
    if not 100 <= max_bins <= 65536 or not 100 <= sample_rate <= 8000:
        raise ValueError("Ungültige Wellenform-Auflösung")
    if cancelled and cancelled():
        raise CancelledError("Wellenform abgebrochen")
    # ceil ensures the whole recording needs at most max_bins output buckets.
    samples_per_bin = max(1, math.ceil(video.duration * sample_rate / max_bins))
    command = [tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
               "-i", video.path, "-map", "0:a:0", "-vn", "-ac", "1",
               "-ar", str(sample_rate), "-f", "s16le", "pipe:1"]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    levels: list[float] = []
    try:
        assert proc.stdout is not None
        while True:
            if cancelled and cancelled():
                raise CancelledError("Wellenform abgebrochen")
            blob = proc.stdout.read(samples_per_bin * 2)
            if not blob:
                break
            data = array("h")
            data.frombytes(blob[:len(blob) // 2 * 2])
            if sys.byteorder != "little":
                data.byteswap()
            if not data:
                break
            rms = math.sqrt(sum(int(v) * int(v) for v in data) / len(data)) / 32768
            if len(levels) < max_bins:
                levels.append(rms)
        if proc.wait() != 0:
            raise RuntimeError("FFmpeg konnte die Wellenform nicht erzeugen.")
        high = max(levels, default=0.0)
        return [round(math.sqrt(v / high), 5) for v in levels] if high > 0 else levels
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()


def stream_offsets(source: str | Path) -> tuple[float, float]:
    """Return video-vs-container and audio-vs-video start offsets in seconds.

    A preview proxy is permitted only for near-aligned streams. Large PTS
    discontinuities must not be silently converted into a shifted timeline.
    """
    cmd = [tool_path("ffprobe"), "-v", "error", "-show_entries",
           "format=start_time:stream=codec_type,start_time",
           "-of", "json", str(source)]
    result = subprocess.run(
        cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=40)
    document = json.loads(result.stdout)
    streams = document.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise ValueError("Proxy-Zeitbasis: Videospur fehlt")
    format_start = float(document.get("format", {}).get("start_time") or 0)
    video_start = float(video_stream.get("start_time") or format_start)
    audio_start = float(audio_stream.get("start_time") or video_start) if audio_stream else video_start
    if not all(math.isfinite(t) for t in (format_start, video_start, audio_start)):
        raise ValueError("Proxy-Zeitbasis ist ungültig")
    return video_start - format_start, audio_start - video_start


def encode_preview_proxy(
        video: VideoInfo, target: str | Path, *,
        progress: Progress | None = None,
        cancelled: Cancelled | None = None) -> None:
    """Transcode a complete, small MP4 with VFR PTS spacing preserved.

    This is a streaming FFmpeg operation: no video/audio bytes are buffered
    in Python. Proxies are only preview media and never used for export.
    The caller owns the temporary path and validates before publication.
    """
    if cancelled and cancelled():
        raise CancelledError("Proxy-Erstellung abgebrochen")
    if not math.isfinite(video.duration) or video.duration <= 0:
        raise ValueError("Proxy benötigt eine gültige Videodauer")
    command = [
        tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-stats_period", "0.5", "-progress", "pipe:1", "-y",
        "-i", video.path, "-map", "0:v:0", "-map", "0:a:0?",
        "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn",
        "-vf", ("setpts=PTS-STARTPTS,"
                "scale=854:480:force_original_aspect_ratio=decrease:"
                "force_divisible_by=2,setsar=1,format=yuv420p"),
        "-fps_mode:v", "passthrough",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "29",
        "-pix_fmt", "yuv420p",
    ]
    if video.has_audio:
        command += ["-af", "aresample=async=1:first_pts=0"]
    command += [
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart",
        "-f", "mp4", str(target)]
    with tempfile.TemporaryFile(mode="w+b") as stderr_log:
        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=stderr_log,
            text=True, encoding="utf-8", errors="replace")
        updates: queue.Queue[float] = queue.Queue(maxsize=2)
        def drain_progress() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                key, sep, value = line.strip().partition("=")
                if sep and key in {"out_time_us", "out_time_ms", "out_time"}:
                    seconds = _progress_seconds(key, value)
                    if seconds is not None:
                        try:
                            updates.put_nowait(seconds)
                        except queue.Full:
                            pass
        reader = threading.Thread(
            target=drain_progress, daemon=True, name="streamclipper-proxy-progress")
        reader.start()
        last = -1
        try:
            while proc.poll() is None or reader.is_alive() or not updates.empty():
                if cancelled and cancelled():
                    raise CancelledError("Proxy-Erstellung abgebrochen")
                try:
                    at = updates.get(timeout=0.15)
                except queue.Empty:
                    continue
                percent = min(99, max(0, int(at / video.duration * 100)))
                if progress and percent > last:
                    progress(percent)
                    last = percent
            proc.wait()
            if cancelled and cancelled():
                raise CancelledError("Proxy-Erstellung abgebrochen")
            if proc.returncode:
                stderr_log.seek(0, os.SEEK_END)
                stderr_log.seek(max(0, stderr_log.tell() - 1800))
                error = stderr_log.read().decode("utf-8", errors="replace")
                raise RuntimeError("FFmpeg-Proxy fehlgeschlagen: " + error)
            if not Path(target).is_file() or Path(target).stat().st_size <= 0:
                raise RuntimeError("FFmpeg hat keinen vollständigen Proxy erzeugt")
            if progress:
                progress(100)
        finally:
            _stop_process(proc)
            reader.join(timeout=2)
            if proc.stdout:
                proc.stdout.close()


def concatenate_scene_parts(parts: list[Path], destination: Path, *, cancelled=None) -> None:
    """Join only internally generated, same-format scene segments.
    No original path enters the concat manifest or shell. Final QA is separate.
    """
    if not parts or any(p.parent != destination.parent for p in parts):
        raise ValueError("Ungültige Szenendateien")
    manifest = destination.parent / "scenes.ffconcat"
    for part in parts:
        if (not part.name.startswith("part-") or not part.name.endswith(".mp4")
                or not part.name[5:-4].isascii() or not part.name[5:-4].isdigit()
                or not part.is_file()):
            raise ValueError("Ungültige temporäre Szenendatei")
    manifest.write_text("ffconcat version 1.0\n" + "".join(
        f"file '{p.name}'\n" for p in parts), encoding="ascii")
    with tempfile.TemporaryFile(mode="w+b") as errors:
        proc = subprocess.Popen([
            tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
            "-n", "-f", "concat", "-safe", "1", "-i", manifest.name,
            "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", destination.name
        ], cwd=destination.parent, stdout=subprocess.DEVNULL, stderr=errors)
        try:
            while proc.poll() is None:
                if cancelled and cancelled():
                    raise CancelledError("Szenenkomposition abgebrochen")
                try:
                    proc.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    pass
            if proc.returncode:
                errors.seek(0, os.SEEK_END)
                errors.seek(max(0, errors.tell()-2000))
                raise RuntimeError("Szenenkomposition fehlgeschlagen: " +
                                   errors.read().decode("utf-8", "replace"))
        finally:
            _stop_process(proc)


def process_stem_mix(voice,residual,destination,*,duration,channels,voice_gain=0.,background_gain=0.,
                     cleanup=False,ducking=False,normalize=False,cancelled=None):
    """Bake a non-destructive local mix for identical preview/export/queue.
    Loudnorm is single-pass dynamic normalization, not a verified final MP4
    true-peak ceiling. Input estimates remain untouched.
    """
    import time
    if not 0<duration<=21600 or channels not in (1,2) or any(not math.isfinite(g) or not -60<=g<=12 for g in (voice_gain,background_gain)):
        raise ValueError("Ungültige Mixparameter")
    if not all(type(x) is bool for x in (cleanup,ducking,normalize)):raise ValueError("Ungültige Audioeffekte")
    out=Path(destination)
    if out.exists():raise FileExistsError(out)
    if cancelled and cancelled():raise CancelledError("Audiomix abgebrochen")
    layout="mono" if channels==1 else "stereo"
    fmt=f"aformat=sample_rates=48000:channel_layouts={layout}"
    clean=",highpass=f=75,afftdn=nf=-35" if cleanup else ""
    chain=f"[0:a:0]{fmt},volume={voice_gain:.3f}dB{clean}[voice];[1:a:0]{fmt},volume={background_gain:.3f}dB[bg]"
    if ducking:
        chain+=";[voice]asplit=2[lead][key];[bg][key]sidechaincompress=threshold=0.025:ratio=6:attack=15:release=350[back];[lead][back]"
    else:chain+=";[voice][bg]"
    chain+="amix=inputs=2:duration=first:normalize=0:dropout_transition=0"
    if normalize:chain+=",loudnorm=I=-16:TP=-1.5:LRA=11"
    chain+=f",aresample=48000,apad,atrim=end_sample={round(duration*48000)}[mix]"
    cmd=[tool_path("ffmpeg"),"-nostdin","-hide_banner","-loglevel","error","-n",
         "-i",str(voice),"-i",str(residual),"-filter_complex",chain,"-map","[mix]",
         "-ar","48000","-ac",str(channels),"-c:a","pcm_f32le","-rf64","auto",str(out)]
    with tempfile.TemporaryFile() as errors:
        proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors)
        try:
            deadline=time.monotonic()+max(120,duration*3+60)
            while proc.poll() is None:
                if cancelled and cancelled():raise CancelledError("Audiomix abgebrochen")
                if time.monotonic()>deadline:raise RuntimeError("Audiomix: Zeitlimit")
                time.sleep(.1)
            if proc.returncode:
                errors.seek(0,os.SEEK_END);errors.seek(max(0,errors.tell()-4000))
                raise RuntimeError("Audiomix: "+errors.read().decode("utf-8","replace"))
        finally:_stop_process(proc)
    if cancelled and cancelled():raise CancelledError("Audiomix abgebrochen")
    if abs(probe_audio_duration(out)-duration)>.002:raise ValueError("Audiomix-Zeitbasis ungültig")
    return out


def measure_loudness(path,*,duration,cancelled=None):
    """Measure the actual audio asset with FFmpeg loudnorm input metrics.
    Null values for silent/undefined loudness. Not an AAC export guarantee.
    """
    import time
    if not math.isfinite(duration) or not 0<duration<=21600:raise ValueError("Ungültige Messdauer")
    with tempfile.TemporaryFile() as log:
        cmd=[tool_path("ffmpeg"),"-nostdin","-hide_banner","-loglevel","info","-i",str(Path(path).resolve(strict=True)),
             "-vn","-af","loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json","-f","null","-"]
        proc=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=log,stdin=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+max(120,duration*3+60)
            while proc.poll() is None:
                if cancelled and cancelled():raise CancelledError("Lautheitsmessung abgebrochen")
                if time.monotonic()>deadline:raise RuntimeError("Lautheitsmessung: Zeitlimit")
                time.sleep(.1)
            if proc.returncode:raise RuntimeError("FFmpeg-Lautheitsmessung fehlgeschlagen")
            log.seek(0,os.SEEK_END);log.seek(max(0,log.tell()-65536))
            text=log.read().decode("utf-8","replace")
        finally:_stop_process(proc)
    i,j=text.rfind("{"),text.rfind("}")
    if i<0 or j<=i:raise ValueError("FFmpeg-Lautheitsmesswerte fehlen")
    doc=json.loads(text[i:j+1])
    values={}
    for key,label in (("input_i","integrated_lufs"),("input_tp","true_peak_dbtp"),("input_lra","loudness_range_lu")):
        value=float(doc[key]);values[label]=value if math.isfinite(value) else None
    return values
