"""Bounded, explainable temporal activity scan and targeted CLIP scheduling.

This is a *signal detector*, not an action-recognition oracle. Abrupt frame
changes may mean camera pans, HUD changes, cuts, or gameplay incidents. The
multimodal ranker must distinguish this evidence from confirmed game events.
"""
from __future__ import annotations

from collections import deque
import math
import statistics
import subprocess
from typing import Callable, Iterable

from .media import CancelledError, tool_path
from .models import VideoInfo
from .semantic import EventEvidence

Progress = Callable[[int], None]
Cancelled = Callable[[], bool]


def change_metrics(previous: bytes, current: bytes, *, stride: int = 4) -> tuple[float, float]:
    """Mean sampled luma difference and fraction of pixels changing markedly.

    Operates on bytes, not full-resolution arrays. All returned values 0..1.
    A pixel change alone cannot establish a specific gameplay event.
    """
    if not previous or len(previous) != len(current) or stride < 1:
        raise ValueError("Unvergleichbare Bilddaten")
    old = previous[::stride]
    new = current[::stride]
    change = 0
    changed = 0
    for a, b in zip(old, new):
        delta = abs(a - b)
        change += delta
        changed += delta >= 36
    return change / (255 * len(old)), changed / len(old)


def _scan_temporal_activity(
    video: VideoInfo, *, fps: float = 2.0, max_events: int = 360,
    cancelled: Cancelled | None = None, progress: Progress | None = None,
    gpu_decode: bool = False,
) -> list[EventEvidence]:
    """Stream low-resolution grayscale frames from FFmpeg (fixed memory).

    Uses one 96x54 frame buffer and a short rolling baseline. At most
    `max_events` local maxima are retained across the *entire* VOD, not only
    its beginning. A 6-hour video uses <=360 chronological evidence slots.
    No network, CLIP inference or model downloads are involved here.
    """
    if not math.isfinite(video.duration) or video.duration <= 0:
        raise ValueError("Ungültige Videodauer")
    if not math.isfinite(fps) or not 0.5 <= fps <= 4 or not 12 <= max_events <= 2000:
        raise ValueError("Ungültige Analyse-Auflösung")
    if cancelled and cancelled():
        raise CancelledError("Gameplay-Analyse abgebrochen")
    width, height = 96, 54
    frame_size = width * height
    from .hardware_media import decode_options,notify
    prefix,filters=decode_options(width,height) if gpu_decode else ([],f"scale={width}:{height}:flags=fast_bilinear")
    if gpu_decode:
        filters += f",fps={fps:.3f},format=gray"
    else:
        filters = f"fps={fps:.3f},"+filters+",format=gray"
    notify("Szenenscan: "+("NVDEC / scale_cuda → CPU-Luma" if gpu_decode else "FFmpeg CPU"))
    cmd = [tool_path("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
           *prefix,"-i", video.path, "-map", "0:v:0", "-an", "-sn",
           "-vf",filters,"-f","rawvideo","-pix_fmt","gray","pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    baseline: deque[float] = deque(maxlen=24)
    best: dict[int, EventEvidence] = {}
    bucket_span = max(6.0, video.duration / max_events)
    previous: bytes | None = None
    index = 0
    try:
        assert proc.stdout is not None
        while True:
            if cancelled and cancelled():
                raise CancelledError("Gameplay-Analyse abgebrochen")
            frame = proc.stdout.read(frame_size)
            if not frame:
                break
            if len(frame) != frame_size:
                raise RuntimeError("Unvollständiger FFmpeg-Bilddatenstrom")
            if previous is not None:
                difference, coverage = change_metrics(previous, frame)
                reference = statistics.median(baseline) if baseline else 0.03
                # A *spike* relative to recent activity, not just perpetual
                # camera motion while driving. Cuts remain weak evidence.
                if (difference >= 0.095 and coverage >= 0.20 and
                        difference >= max(0.115, 1.65 * reference)):
                    at = index / fps
                    is_cut = coverage >= 0.78 and difference >= 0.25
                    strength = (0.32 if is_cut else 0.43) + min(0.16, difference * 0.30)
                    label = ("Abrupter Bildwechsel (Schnitt/Kamera möglich)" if is_cut
                             else "Ungewöhnliche Bildbewegung/-veränderung")
                    evidence = EventEvidence(round(at, 3), "motion", round(strength, 3),
                                             label + " – kein bestätigtes Spielereignis")
                    bucket = min(max_events - 1, int(at / bucket_span))
                    if bucket not in best or best[bucket].strength < evidence.strength:
                        best[bucket] = evidence
                baseline.append(difference)
            previous = frame
            index += 1
            if progress and index % 20 == 0:
                progress(min(99, round(100 * index / max(1, video.duration * fps))))
        if proc.wait() != 0:
            raise RuntimeError("FFmpeg konnte den zeitlichen Szenenverlauf nicht lesen")
        if progress:
            progress(100)
        return sorted(best.values(), key=lambda ev: ev.at)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()


def scan_temporal_activity(video: VideoInfo, *,fps=2.0,max_events=360,cancelled=None,progress=None):
    from .hardware_media import choose_decode,retry_decode
    if cancelled and cancelled():raise CancelledError("Gameplay-Analyse abgebrochen")
    enabled=choose_decode(tool_path("ffmpeg"),video)
    return retry_decode(lambda gpu:_scan_temporal_activity(video,fps=fps,max_events=max_events,
                         cancelled=cancelled,progress=progress,gpu_decode=gpu),enabled)


def select_scene_timestamps(
    events: Iterable[EventEvidence], duration: float, max_frames: int = 180,
) -> list[float]:
    """Choose CLIP screenshots near evidence anchors, not only uniform samples.

    Budget is strictly bounded: up to 3 screenshots per selected anchor.
    Balance image activity, spoken reactions, audio, and quiet/uniform controls.
    This limits sparse sampling of 3–6-hour recordings without claiming full
    event recall; short isolated incidents can still be missed.
    """
    if not math.isfinite(duration) or duration <= 0 or not 1 <= max_frames <= 2000:
        raise ValueError("Ungültige CLIP-Stichprobe")
    anchors = max(1, max_frames // 3)
    quotas = {"motion": round(anchors * .48), "speech": round(anchors * .25),
              "audio": round(anchors * .17)}
    pool: dict[str, list[EventEvidence]] = {key: [] for key in quotas}
    for event in events:
        if (event.kind in pool and math.isfinite(event.at) and
                0 <= event.at <= duration and math.isfinite(event.strength)):
            pool[event.kind].append(event)
    for group in pool.values():
        group.sort(key=lambda item: (-item.strength, item.at))
    centers: list[float] = []
    spacing = max(4.0, min(15.0, duration / max(anchors * 3, 1)))

    def add(t: float) -> bool:
        if any(abs(t - earlier) < spacing for earlier in centers):
            return False
        centers.append(t)
        return True

    # Stratify each modality across the entire video; taking the strongest
    # N globally would bias a long recording toward its earliest equally
    # ranked moments and miss later incidents.
    for category, quota in quotas.items():
        if quota <= 0:
            continue
        for bucket in range(quota):
            lower = duration * bucket / quota
            upper = duration * (bucket + 1) / quota
            for event in pool[category]:
                if lower <= event.at < upper and add(event.at):
                    break
    # Ensure some routine/neutral contexts are also sampled, then backfill.
    for i in range(max(1, anchors // 10)):
        if len(centers) < anchors:
            add(duration * (i + 0.5) / max(1, anchors // 10))
    remaining = sorted((ev for entries in pool.values() for ev in entries),
                       key=lambda ev: (-ev.strength, ev.at))
    for event in remaining:
        if len(centers) >= anchors:
            break
        add(event.at)
    # A recording with no interesting evidence still gets representative views.
    for i in range(anchors):
        if len(centers) >= anchors:
            break
        add(duration * (i + 0.5) / anchors)
    offsets = (0.0, -1.0, 1.0)
    shots = set()
    for center in sorted(centers):
        for offset in offsets:
            shots.add(round(max(0.0, min(duration - 0.03, center + offset)), 3))
            if len(shots) >= max_frames:
                break
        if len(shots) >= max_frames:
            break
    return sorted(shots)
