"""Clip-local camera motion proxy (not semantic subject tracking).

The analysis is confined to the selected short clip, never a full multi-hour VOD.
Small grayscale frames keep RAM bounded. A smooth path follows concentrations
of temporal differences, which can reflect gameplay motion *or* camera motion.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import statistics
import subprocess
from typing import Callable, Iterable

from .models import VideoInfo

Cancelled = Callable[[], bool]


@dataclass(frozen=True)
class FocusPoint:
    at: float  # clip-relative seconds
    x: float   # normalized subject center in source image, 0 .. 1
    y: float


def motion_focus(previous: bytes, current: bytes, *, width: int = 160,
                 height: int = 90) -> tuple[float, float] | None:
    """Centroid of localized temporal contrast; uniform motion is ignored.

    Images are small monochrome frames, sampled from an FFmpeg rawvideo pipe.
    The 10x6 grid suppresses transient pixel flicker and avoids heavy ML deps.
    """
    if len(previous) != width * height or len(current) != width * height:
        raise ValueError("Ungültige Rohbildgröße")
    columns, rows = 10, 6
    cell_width, cell_height = width // columns, height // rows
    cells = []
    for row in range(rows):
        for col in range(columns):
            samples = []
            for y in range(row * cell_height + 1, (row + 1) * cell_height, 3):
                for x in range(col * cell_width + 1, (col + 1) * cell_width, 3):
                    index = y * width + x
                    samples.append(abs(current[index] - previous[index]))
            cells.append(sum(samples) / max(1, len(samples)))
    median = statistics.median(cells)
    # Reject lighting changes, menu fades and whole-screen camera movement.
    local = [max(0.0, value - max(6.0, median * 1.35)) for value in cells]
    total = sum(local)
    if total < 9 or sum(value > 2.0 for value in local) > 45:
        return None
    cx = sum(((idx % columns + .5) / columns) * value
             for idx, value in enumerate(local)) / total
    cy = sum(((idx // columns + .5) / rows) * value
             for idx, value in enumerate(local)) / total
    return cx, cy


def smooth_focus(samples: Iterable[tuple[float, tuple[float, float] | None]],
                 *, max_points: int = 40) -> list[FocusPoint]:
    """Low-pass temporal centroids, gently reverting toward image center."""
    points = [FocusPoint(0.0, .5, .5)]
    x = y = .5
    for at, focus in samples:
        if not math.isfinite(at) or at <= points[-1].at:
            continue
        target_x, target_y = focus if focus is not None else (.5, .5)
        target_x = max(.13, min(.87, target_x))
        target_y = max(.18, min(.82, target_y))
        # Limit pan rate: avoids instant camera jumps between video frames.
        alpha = min(.35, .16 * (at - points[-1].at) + .10)
        x += (target_x - x) * alpha
        y += (target_y - y) * alpha
        if abs(x - .5) < .012:
            x = .5
        if abs(y - .5) < .012:
            y = .5
        points.append(FocusPoint(round(at, 3), round(x, 4), round(y, 4)))
    if len(points) > max_points:
        step = (len(points) - 1) / (max_points - 1)
        points = [points[round(i * step)] for i in range(max_points)]
    return points


def clip_motion_path(video: VideoInfo, start: float, end: float, *,
                     cancelled: Cancelled | None = None,
                     fps: int = 2, max_frames: int = 120) -> list[FocusPoint]:
    """Sample only the chosen short clip. Entire decode stream is never buffered."""
    from .media import CancelledError, tool_path
    if cancelled and cancelled():
        raise CancelledError("Kameratracking abgebrochen")
    if not (0 <= start < end <= video.duration + 0.1):
        raise ValueError("Ungültiges Clip-Zeitfenster")
    if fps <= 0 or max_frames < 2:
        raise ValueError("Ungültige Sampling-Parameter")
    frame_bytes = 160 * 90
    duration = end - start
    effective_fps = min(fps, max(1, int(max_frames / max(duration, 1))))
    cmd = [tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-i", video.path, "-t", f"{duration:.3f}",
           "-an", "-vf", f"fps={effective_fps},scale=160:90:flags=fast_bilinear,format=gray",
           "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    previous = None
    candidates: list[tuple[float, tuple[float, float] | None]] = []
    try:
        assert proc.stdout is not None
        for i in range(max_frames):
            if cancelled and cancelled():
                raise CancelledError("Kameratracking abgebrochen")
            frame = proc.stdout.read(frame_bytes)
            if not frame:
                break
            if len(frame) != frame_bytes:
                raise RuntimeError("FFmpeg hat ein unvollständiges Tracking-Bild geliefert")
            if previous is not None:
                candidates.append((i / effective_fps, motion_focus(previous, frame)))
            previous = frame
        if proc.wait() != 0:
            raise RuntimeError("FFmpeg konnte Kamerabewegungen nicht auswerten")
        return smooth_focus(candidates)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()


def camera_expression(points: list[FocusPoint], axis: str) -> str:
    """FFmpeg crop evaluation expression for a smooth, clip-relative pan.

    FFmpeg uses nested if(lt(t, ...), ..., ...). Avoid multiple filter parse
    levels by quoting the full expression in crop's x/y arguments.
    """
    if axis not in {"x", "y"}:
        raise ValueError("Unknown axis")
    if not points:
        return "0.5"
    coords = [(max(0., p.at), max(0., min(1., getattr(p, axis)))) for p in points]
    expression = f"{coords[-1][1]:.4f}"
    for i in range(len(coords) - 2, -1, -1):
        t0, v0 = coords[i]
        t1, v1 = coords[i+1]
        if t1 <= t0:
            continue
        interpolated = f"({v0:.4f}+({v1-v0:+.4f})*(t-{t0:.3f})/{t1-t0:.3f})"
        expression = f"if(lt(t,{t1:.3f}),{interpolated},{expression})"
    return expression


def smart_crop_filter(width: int, height: int, points: list[FocusPoint],
                      *, zoom: float) -> str:
    """FFmpeg video filter segment; x/y computed from observed motion centroids."""
    if not (1.0 <= zoom <= 1.6):
        raise ValueError("Ungültiger Zoomfaktor")
    scale_w = int(math.ceil(width * zoom / 2) * 2)
    scale_h = int(math.ceil(height * zoom / 2) * 2)
    x = camera_expression(points, "x")
    y = camera_expression(points, "y")
    # Text expression needs commas protected from the FFmpeg filtergraph parser.
    return (
        f"setpts=PTS-STARTPTS,scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}:"
        f"x='max(0,min(in_w-out_w,in_w*({x})-out_w/2))':"
        f"y='max(0,min(in_h-out_h,in_h*({y})-out_h/2))',"
        "setsar=1,format=yuv420p"
    )
