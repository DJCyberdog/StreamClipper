"""Shared immutable render request for M12b deterministic A/V composition.

Preview and final MP4 share exactly one FFmpeg graph and validated
source/project contract. Unsupported caption timeline clips fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import tempfile
from pathlib import Path
from typing import Callable

from .media import (build_export_command, export_clip, video_dimensions,
                    concatenate_scene_parts, probe_video, CancelledError)
from .models import TranscriptSegment, VideoInfo
from .editor_project import EditorProject
from .render_graph import build_render_graph
from .encoders import ENCODERS
from .scene_selection import SceneSelection, excerpt_selection, output_duration
from .smart_director import crop_for_scene

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
    encoder: str = "cpu_h264"  # append-only, old positional API stays stable
    scene_plan: SceneSelection | None = None

    def validate(self) -> "RenderRequest":
        times = (self.start, self.end, self.video.duration, self.subtitle_offset)
        if not all(math.isfinite(t) for t in times):
            raise ValueError("Renderzeiten und Untertitelversatz müssen endlich sein")
        if not 0 <= self.start < self.end <= self.video.duration + 0.1:
            raise ValueError("Ungültiges Renderintervall")
        if not -5 <= self.subtitle_offset <= 5:
            raise ValueError("Untertitelversatz außerhalb -5 bis +5 Sekunden")
        if self.encoder not in ENCODERS:
            raise ValueError("Unbekanntes H.264-/HEVC-Encoderprofil")
        width, height = video_dimensions(self.mode, self.width, self.height)
        build_export_command(
            self.video, self.start, self.end, "validation.mp4",
            mode=self.mode, width=width, height=height,
            burned_captions=self.burn_subtitles)
        if self.burn_subtitles and not self.transcript:
            raise ValueError("Zum Einbrennen der Untertitel fehlt das Transkript")
        if self.scene_plan is not None:
            self.scene_plan.validate()
            if (self.scene_plan.start, self.scene_plan.end) != (self.start, self.end):
                raise ValueError("Szenenplan gehört zu einem anderen Highlight")
            if not self.scene_plan.output_scenes:
                raise ValueError("Keine eingeschlossene Szene")
            for scene in self.scene_plan.output_scenes:
                crop_for_scene(scene, self.video, width, height)
            if self.project is not None:
                for scene in self.scene_plan.output_scenes:
                    build_render_graph(self.project, self.video, scene.start, scene.end)
        elif self.project is not None:
            build_render_graph(self.project, self.video, self.start, self.end)
        return self

    def preview_excerpt(self, maximum: float = PREVIEW_MAX_SECONDS) -> "RenderRequest":
        self.validate()
        if not math.isfinite(maximum) or maximum <= 0 or maximum > 60:
            raise ValueError("Render-Vorschau muss auf maximal 60 Sekunden begrenzt sein")
        if self.scene_plan is not None:
            return replace(self, scene_plan=excerpt_selection(self.scene_plan, maximum)).validate()
        return replace(self, end=min(self.end, self.start + maximum)).validate()

    @property
    def duration(self) -> float:
        return output_duration(self.scene_plan) if self.scene_plan is not None else self.end-self.start

    @property
    def is_excerpt(self) -> bool:
        return self.duration < PREVIEW_MAX_SECONDS


def render_request(
        request: RenderRequest, destination: str | Path, *,
        progress: Callable[[int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        encoder_notice: Callable[[str], None] | None = None) -> Path:
    """One true FFmpeg render boundary for exported and rendered preview clips.

    No proxy input or timeline metadata is substituted. Fail closed before
    spawning FFmpeg and preserve atomic/non-overwriting export_clip semantics.
    """
    request.validate()
    if request.scene_plan is not None:
        return _render_scenes(request, destination, progress, cancelled, encoder_notice)
    options = {}
    if request.project is not None:
        graph = build_render_graph(
            request.project, request.video, request.start, request.end)
        options["audio_layers"] = graph.audio_layers
        options["visual_layers"] = graph.visual_layers
    return export_clip(
        request.video, request.start, request.end, destination,
        mode=request.mode, width=request.width, height=request.height,
        transcript=list(request.transcript),
        burn_subtitles=request.burn_subtitles,
        subtitle_offset=request.subtitle_offset,
        progress=progress, cancelled=cancelled,
        encoder=request.encoder, encoder_notice=encoder_notice,
        **options,
    )


def _render_scenes(request, destination, progress, cancelled, encoder_notice):
    """Render included scenes in sequence, not source-time order.

    Scene layers and captions retain original source time. Temporary normalized
    H264/AAC parts are joined and then encoded with the selected final profile.
    The final export uses the same atomic publish/QA as a normal clip.
    """
    scenes = request.scene_plan.output_scenes
    width, height = video_dimensions(request.mode, request.width, request.height)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    graphs = [build_render_graph(request.project, request.video, s.start, s.end)
              if request.project is not None else None for s in scenes]
    any_audio = request.video.has_audio or any(g and g.audio_layers for g in graphs)
    def check_cancel():
        if cancelled and cancelled():
            raise CancelledError("Szenenrendering abgebrochen")
    def render_part(scene, graph, target, encoder, callback, normalize):
        check_cancel()
        mode = ("smart16" if width >= height else "smart9") if scene.mode == "automatic" else "crop"
        options = dict(audio_layers=graph.audio_layers, visual_layers=graph.visual_layers) if graph else {}
        # Manual: preserve entire marked rectangle, pad to aspect ratio.
        # Fixed: center-crop the marked rectangle to output aspect ratio.
        safe_region = crop_for_scene(scene, request.video, width, height)
        if safe_region is not None:
            options.update(region=safe_region, fit_region=False)
        elif scene.mode != "automatic":
            options.update(region=scene.region, fit_region=scene.mode == "manual")
        director = scene.director
        if scene.mode != "automatic" and not director.manual:
            director = replace(director, tracked=())
        options["director"] = director
        options["motion_analysis_end"] = scene.framing_end or scene.end
        return export_clip(request.video, scene.start, scene.end, target,
                           mode=mode, width=width, height=height,
                           transcript=list(request.transcript),
                           burn_subtitles=request.burn_subtitles,
                           subtitle_offset=request.subtitle_offset,
                           encoder=encoder, encoder_notice=encoder_notice,
                           cancelled=cancelled, progress=callback,
                           force_audio=normalize and bool(any_audio), **options)
    if len(scenes) == 1:
        return render_part(scenes[0], graphs[0], destination, request.encoder, progress, False)
    with tempfile.TemporaryDirectory(prefix=".scene-render-", dir=destination.parent) as temp:
        folder = Path(temp)
        parts = []
        elapsed = 0.
        total = request.duration
        for index, (scene, graph) in enumerate(zip(scenes, graphs)):
            length = scene.end-scene.start
            def report(value, offset=elapsed, length=length):
                if progress:
                    progress(min(79, int(80*(offset+length*value/100)/total)))
            parts.append(render_part(scene, graph, folder / f"part-{index:04d}.mp4",
                                     "cpu_h264", report, True))
            elapsed += length
        check_cancel()
        joined = folder / "joined.mp4"
        concatenate_scene_parts(parts, joined, cancelled=cancelled)
        info = probe_video(joined)
        if abs(info.duration-total) > .55:
            raise ValueError("Szenenkomposition hat eine unerwartete Gesamtdauer")
        check_cancel()
        return export_clip(info, 0, min(total, info.duration), destination,
                           mode="crop", width=width, height=height,
                           encoder=request.encoder, encoder_notice=encoder_notice,
                           cancelled=cancelled,
                           progress=(lambda value: progress(80+int(value*.2))) if progress else None)
