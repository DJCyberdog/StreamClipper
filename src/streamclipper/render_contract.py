"""Shared immutable render request for legacy clips and opt-in M12b audio graph.

Both preview and export use the identical FFmpeg boundary. Project snapshots
are explicit and opt-in: unimplemented video/graphic composition fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
from typing import Callable

from .media import (build_export_command, export_clip, video_dimensions)
from .models import TranscriptSegment, VideoInfo
from .editor_project import EditorProject
from .render_graph import build_render_graph

PREVIEW_MAX_SECONDS = 20.0


@dataclass(frozen=True)
class RenderRequest:
    video: VideoInfo
    start: float
    end: float
    mode: str
    burn_subtitles: bool = False
    subtitle_offset: float = 0.0
    transcript: tuple[TranscriptSegment, ...] = ()
    width: int = 1080
    height: int = 1920
    project: EditorProject | None = None  # opt-in M12b graph snapshot

    def validate(self) -> "RenderRequest":
        times = (self.start, self.end, self.video.duration, self.subtitle_offset)
        if not all(math.isfinite(t) for t in times):
            raise ValueError("Renderzeiten und Untertitelversatz müssen endlich sein")
        if not 0 <= self.start < self.end <= self.video.duration + 0.1:
            raise ValueError("Ungültiges Renderintervall")
        if not -5 <= self.subtitle_offset <= 5:
            raise ValueError("Untertitelversatz außerhalb -5 bis +5 Sekunden")
        width, height = video_dimensions(self.mode, self.width, self.height)
        build_export_command(
            self.video, self.start, self.end, "validation.mp4",
            mode=self.mode, width=width, height=height,
            burned_captions=self.burn_subtitles)
        if self.burn_subtitles and not self.transcript:
            raise ValueError("Zum Einbrennen der Untertitel fehlt das Transkript")
        if self.project is not None:
            build_render_graph(self.project, self.video, self.start, self.end)
        return self

    def preview_excerpt(self, maximum: float = PREVIEW_MAX_SECONDS) -> "RenderRequest":
        self.validate()
        if not math.isfinite(maximum) or maximum <= 0 or maximum > 60:
            raise ValueError("Render-Vorschau muss auf maximal 60 Sekunden begrenzt sein")
        return replace(self, end=min(self.end, self.start + maximum)).validate()

    @property
    def is_excerpt(self) -> bool:
        return self.end - self.start < PREVIEW_MAX_SECONDS


def render_request(
        request: RenderRequest, destination: str | Path, *,
        progress: Callable[[int], None] | None = None,
        cancelled: Callable[[], bool] | None = None) -> Path:
    """One true FFmpeg render boundary for exported and rendered preview clips.

    No proxy input or timeline metadata is substituted. Fail closed before
    spawning FFmpeg and preserve atomic/non-overwriting export_clip semantics.
    """
    request.validate()
    options = {}
    if request.project is not None:
        graph = build_render_graph(
            request.project, request.video, request.start, request.end)
        options["audio_layers"] = graph.audio_layers
    return export_clip(
        request.video, request.start, request.end, destination,
        mode=request.mode, width=request.width, height=request.height,
        transcript=list(request.transcript),
        burn_subtitles=request.burn_subtitles,
        subtitle_offset=request.subtitle_offset,
        progress=progress, cancelled=cancelled, **options,
    )
