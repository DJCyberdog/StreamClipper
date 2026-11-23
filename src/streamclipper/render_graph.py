"""M12b v1: deterministic, versioned, fail-closed render graph from M11 tracks.

The graph retains *all* semantic track types. Rendering currently supports
one unchanged gameplay video lane + finite, optional local audio lanes.
Extra video, caption or overlay clip-composition is explicitly rejected
instead of being invisibly dropped. Captions from RenderRequest still work.

Timeline/source times are separate. A source clip occupying time 120..130
may be placed at timeline time 20..30, and is correctly clipped by a
requested render interval such as 25..28.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os

from .editor_project import EditorProject
from .models import VideoInfo

RENDER_GRAPH_VERSION = 1
MAX_MIXED_AUDIO_CLIPS = 16


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


@dataclass(frozen=True)
class AudioLayer:
    id: str
    track_id: str
    source_path: str
    source_start: float
    source_end: float
    timeline_offset: float  # seconds into the selected render clip
    gain_db: float


@dataclass(frozen=True)
class RenderGraph:
    schema_version: int
    video: VideoInfo
    start: float
    end: float
    nodes: tuple[GraphNode, ...]
    audio_layers: tuple[AudioLayer, ...]
    base_audio_enabled: bool

    def validate(self) -> "RenderGraph":
        if self.schema_version != RENDER_GRAPH_VERSION:
            raise ValueError("Unbekannte Rendergraph-Version")
        if not 0 <= self.start < self.end <= self.video.duration + .1:
            raise ValueError("Rendergraph-Zeitfenster ungültig")
        if len(self.audio_layers) > MAX_MIXED_AUDIO_CLIPS:
            raise ValueError("Zu viele überlappende Audiospuren für diesen Renderjob")
        for layer in self.audio_layers:
            if (not layer.source_path or not os.path.isabs(layer.source_path)
                    or not all(math.isfinite(x) for x in (
                        layer.source_start, layer.source_end,
                        layer.timeline_offset, layer.gain_db))
                    or not 0 <= layer.source_start < layer.source_end <= 24 * 3600
                    or not 0 <= layer.timeline_offset < self.end-self.start
                    or layer.timeline_offset+layer.source_end-layer.source_start >
                    self.end-self.start + .005
                    or not -60 <= layer.gain_db <= 12):
                raise ValueError("Ungültige oder nichtlokale Audiospur")
        return self


def _same_source(left: VideoInfo, right: VideoInfo) -> bool:
    return (os.path.normcase(os.path.abspath(left.path)) ==
            os.path.normcase(os.path.abspath(right.path))
            and abs(left.duration-right.duration) <= .25
            and (left.width,left.height)==(right.width,right.height))


def build_render_graph(project: EditorProject, video: VideoInfo,
                       start: float, end: float) -> RenderGraph:
    """Snapshot the project into a deterministic ordered clip composition.

    Hidden only affects the editor's display; muted suppresses playback of
    the whole track. Locked protects editing only and does not suppress sound.
    """
    project.validate()
    if not _same_source(project.source, video):
        raise ValueError("Rendergraph gehört zu einer anderen Quellaufnahme")
    if not all(math.isfinite(x) for x in (start,end)):
        raise ValueError("Rendergraph enthält ungültige Zeitwerte")
    track_by_id = {t.id:t for t in project.tracks}
    index = {track.id:i for i,track in enumerate(project.tracks)}
    nodes = []
    active_audio = []
    has_gameplay = False
    for item in sorted(project.items, key=lambda i: (
            index[i.track_id], i.timeline_start, i.id)):
        track = track_by_id[item.track_id]
        end_on_timeline = item.timeline_start + item.source_end-item.source_start
        left, right = max(item.timeline_start,start), min(end_on_timeline,end)
        node = GraphNode(
            item.id,item.track_id,track.kind,
            item.media_path or project.source.path,
            item.source_start,item.source_end,item.timeline_start,
            track.muted,track.locked,track.hidden,item.gain_db)
        nodes.append(node)
        if right <= left:
            continue
        if track.kind == "video":
            if item.id == "source" and item.track_id == "gameplay":
                if track.muted:
                    raise ValueError("Stummgeschaltetes Basisvideo kann noch nicht komponiert werden")
                if (abs(item.source_start) > .001
                        or abs(item.timeline_start) > .001
                        or abs(item.source_end-project.source.duration) > .1):
                    raise ValueError("Basisvideo wurde verändert; M12b unterstützt nur ein unverändertes Quellvideo")
                has_gameplay = True
            elif not track.muted:
                raise ValueError("Mehrere Videoclips sind in M12b noch nicht zusammensetzbar")
        elif track.kind in {"captions","overlay"}:
            if not track.muted:
                raise ValueError("Timeline-Grafik/Untertitelclips benötigen den späteren Mehrspur-Compositor")
        elif track.kind == "audio" and not track.muted:
            source_left = item.source_start + (left-item.timeline_start)
            source_right = source_left + (right-left)
            path = item.media_path or project.source.path
            if item.media_path is None and not video.has_audio:
                raise ValueError("Die Originalaufnahme enthält keine Audiospur")
            active_audio.append(AudioLayer(
                item.id,item.track_id,path,
                round(source_left,6),round(source_right,6),
                round(left-start,6),item.gain_db))
    if not has_gameplay:
        raise ValueError("Keine gültige Gameplay-Basisspur im Renderzeitfenster")
    return RenderGraph(
        RENDER_GRAPH_VERSION, video, start, end, tuple(nodes),
        tuple(active_audio), video.has_audio).validate()
