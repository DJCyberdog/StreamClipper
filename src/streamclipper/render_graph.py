"""M12b2 deterministic offline multitrack graph, explicit supported composition.

V2 supports a fixed original gameplay base, optional local audio clips,
picture-in-picture video and still-image graphic overlays. External video and
graphic sources MUST be explicitly linked; M11 metadata-only clips remain
fail-closed. Caption timeline clips remain unsupported (ASS transcript burn
is still supported by RenderRequest). No implicit audio from PiP videos.

Times are separate: a source interval is clipped to a timeline interval and
placed at an offset relative to this exact export/preview request. Track
order and clip order define deterministic image stacking, independent of
editor Hidden/Locked controls (Muted does suppress rendered track contents).
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os

from .editor_project import EditorProject
from .models import VideoInfo
from .callouts import Callout

RENDER_GRAPH_VERSION = 2
MAX_MIXED_AUDIO_CLIPS = 16
MAX_VISUAL_LAYERS = 8


@dataclass(frozen=True)
class GraphNode:
    id: str
    track_id: str
    kind: str
    source_path: str
    source_start: float
    source_end: float
    timeline_start: float
    muted: bool
    locked: bool
    hidden: bool
    gain_db: float
    x: float = .68
    y: float = .08
    width: float = .28
    height: float = .28
    opacity: float = 1.0
    callout: Callout | None = None


@dataclass(frozen=True)
class AudioLayer:
    id: str
    track_id: str
    source_path: str
    source_start: float
    source_end: float
    timeline_offset: float
    gain_db: float


@dataclass(frozen=True)
class VisualLayer:
    id: str
    track_id: str
    kind: str  # video = moving PiP, overlay = still PNG/JPEG/WebP
    source_path: str
    source_start: float
    source_end: float
    timeline_offset: float
    x: float
    y: float
    width: float
    height: float
    opacity: float
    callout: Callout | None = None


@dataclass(frozen=True)
class RenderGraph:
    schema_version: int
    video: VideoInfo
    start: float
    end: float
    nodes: tuple[GraphNode, ...]
    audio_layers: tuple[AudioLayer, ...]
    base_audio_enabled: bool
    visual_layers: tuple[VisualLayer, ...] = ()

    def validate(self) -> "RenderGraph":
        if self.schema_version != RENDER_GRAPH_VERSION:
            raise ValueError("Unbekannte Rendergraph-Version")
        if not 0 <= self.start < self.end <= self.video.duration + .1:
            raise ValueError("Rendergraph-Zeitfenster ungültig")
        if len(self.audio_layers) > MAX_MIXED_AUDIO_CLIPS:
            raise ValueError("Zu viele überlappende Audiospuren für diesen Renderjob")
        if len(self.visual_layers) > MAX_VISUAL_LAYERS:
            raise ValueError("Zu viele visuelle Layer für diesen Renderjob")
        window = self.end-self.start
        for layer in self.audio_layers:
            if (not layer.source_path or not os.path.isabs(layer.source_path)
                    or not all(math.isfinite(x) for x in (
                        layer.source_start, layer.source_end,
                        layer.timeline_offset, layer.gain_db))
                    or not 0 <= layer.source_start < layer.source_end <= 24 * 3600
                    or not 0 <= layer.timeline_offset < window
                    or layer.timeline_offset+layer.source_end-layer.source_start >
                    window + .005
                    or not -60 <= layer.gain_db <= 12):
                raise ValueError("Ungültige oder nichtlokale Audiospur")
        for layer in self.visual_layers:
            if layer.callout is not None:layer.callout.validate()
            values = (layer.source_start, layer.source_end,
                      layer.timeline_offset, layer.x, layer.y,
                      layer.width, layer.height, layer.opacity)
            if (layer.kind not in {"video", "overlay"}
                    or (layer.callout is None and (not layer.source_path or not os.path.isabs(layer.source_path)))
                    or (layer.callout is not None and (layer.kind!='overlay' or layer.source_path))
                    or not all(math.isfinite(x) for x in values)
                    or not 0 <= layer.source_start < layer.source_end <= 24 * 3600
                    or not 0 <= layer.timeline_offset < window
                    or layer.timeline_offset+layer.source_end-layer.source_start >
                    window+.005
                    or not 0 <= layer.x <= 1 or not 0 <= layer.y <= 1
                    or not .05 <= layer.width <= 1
                    or not .05 <= layer.height <= 1
                    or layer.x+layer.width > 1.000001
                    or layer.y+layer.height > 1.000001
                    or not 0 <= layer.opacity <= 1):
                raise ValueError("Ungültiger Bild-/Grafik-Layer im Rendergraph")
        return self


def _same_source(left: VideoInfo, right: VideoInfo) -> bool:
    return (os.path.normcase(os.path.abspath(left.path)) ==
            os.path.normcase(os.path.abspath(right.path))
            and abs(left.duration-right.duration) <= .25
            and (left.width,left.height)==(right.width,right.height))


def build_render_graph(project: EditorProject, video: VideoInfo,
                       start: float, end: float) -> RenderGraph:
    """Snapshot tracks in deterministic layer order, clipping the output window.

    For PiP layers, independent video audio is never included automatically.
    For muted layers, nothing is rendered, but GraphNode remains audit-visible.
    """
    project.validate()
    if not _same_source(project.source, video):
        raise ValueError("Rendergraph gehört zu einer anderen Quellaufnahme")
    if not all(math.isfinite(x) for x in (start,end)):
        raise ValueError("Rendergraph enthält ungültige Zeitwerte")
    track_by_id = {t.id:t for t in project.tracks}
    index = {track.id:i for i,track in enumerate(project.tracks)}
    nodes: list[GraphNode] = []
    active_audio: list[AudioLayer] = []
    active_visual: list[VisualLayer] = []
    has_gameplay = False
    for item in sorted(project.items, key=lambda i: (
            index[i.track_id], i.timeline_start, i.id)):
        track = track_by_id[item.track_id]
        end_on_timeline = item.timeline_start + item.source_end-item.source_start
        left, right = max(item.timeline_start,start), min(end_on_timeline,end)
        nodes.append(GraphNode(
            item.id, item.track_id, track.kind,
            item.media_path or ('' if item.callout else project.source.path),
            item.source_start, item.source_end, item.timeline_start,
            track.muted, track.locked, track.hidden, item.gain_db,
            item.x, item.y, item.width, item.height, item.opacity, item.callout))
        if right <= left:
            continue
        if track.kind == "video" and item.id == "source" and item.track_id == "gameplay":
            if track.muted:
                raise ValueError("Stummgeschaltetes Basisvideo kann noch nicht komponiert werden")
            if (item.media_path is not None
                    or abs(item.source_start) > .001
                    or abs(item.timeline_start) > .001
                    or abs(item.source_end-project.source.duration) > .1):
                raise ValueError("Basisvideo muss die unveränderte Originalaufnahme bleiben")
            has_gameplay = True
            continue
        if track.muted:
            continue
        if track.kind in {"video", "overlay"}:
            if not item.media_path and item.callout is None:
                if track.kind == "video":
                    raise ValueError(
                        "Mehrere Videoclips benötigen eine eigene lokale Videodatei (PiP)")
                raise ValueError("Grafik-Overlay benötigt eine lokale Bilddatei")
            source_left = item.source_start + (left-item.timeline_start)
            source_right = source_left + (right-left)
            active_visual.append(VisualLayer(
                item.id, item.track_id, track.kind, item.media_path or '',
                round(source_left,6), round(source_right,6),
                round(left-start,6), item.x, item.y,
                item.width, item.height, item.opacity, item.callout))
        elif track.kind == "captions":
            raise ValueError(
                "Timeline-Untertitelclips benötigen einen eigenen Text-Compositor; "
                "Whisper-ASS-Untertitel funktionieren weiterhin")
        elif track.kind == "audio":
            source_left = item.source_start + (left-item.timeline_start)
            source_right = source_left + (right-left)
            path = item.media_path or project.source.path
            if item.media_path is None and not video.has_audio:
                raise ValueError("Die Originalaufnahme enthält keine Audiospur")
            active_audio.append(AudioLayer(
                item.id, item.track_id, path,
                round(source_left,6), round(source_right,6),
                round(left-start,6), item.gain_db))
    if not has_gameplay:
        raise ValueError("Keine gültige Gameplay-Basisspur im Renderzeitfenster")
    return RenderGraph(
        RENDER_GRAPH_VERSION, video, start, end, tuple(nodes),
        tuple(active_audio), video.has_audio, tuple(active_visual)).validate()
