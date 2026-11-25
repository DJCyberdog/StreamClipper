"""M13a: deterministic scene-local camera model, independent of Qt and ML.

Times are absolute source seconds for scenes, relative seconds for keyframes.
Manual paths are never modified by automatic suggestions.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from bisect import bisect_right
import math
from .reframe import FocusPoint

MAX_SCENES = 5000
MAX_KEYS = 120


def _finite(value: float) -> bool:
    return type(value) in (float, int) and math.isfinite(value)


@dataclass(frozen=True)
class CameraKeyframe:
    at: float
    x: float = .5
    y: float = .5
    zoom: float = 1.0

    def validate(self) -> None:
        if not all(_finite(v) for v in (self.at, self.x, self.y, self.zoom)):
            raise ValueError("Kamera-Keyframe enthält ungültige Zahlen")
        if not (self.at >= 0 and 0 <= self.x <= 1 and 0 <= self.y <= 1
                and 1 <= self.zoom <= 1.6):
            raise ValueError("Kamera-Keyframe außerhalb der Grenzen")


@dataclass(frozen=True)
class Scene:
    id: str
    start: float
    end: float
    manual: tuple[CameraKeyframe, ...] = ()
    suggested: tuple[CameraKeyframe, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip() or len(self.id) > 64:
            raise ValueError("Ungültige Szenen-ID")
        if not all(_finite(v) for v in (self.start, self.end)) or not 0 <= self.start < self.end:
            raise ValueError("Ungültiges Szenenintervall")
        for path in (self.manual, self.suggested):
            if not isinstance(path, tuple) or len(path) > MAX_KEYS:
                raise ValueError("Ungültiger Kamerapfad")
            previous = -1.0
            for key in path:
                if not isinstance(key, CameraKeyframe):
                    raise ValueError("Ungültiger Keyframe")
                key.validate()
                if not previous < key.at <= self.end - self.start:
                    raise ValueError("Keyframes müssen aufsteigend und innerhalb der Szene liegen")
                previous = key.at

    @property
    def effective_path(self) -> tuple[CameraKeyframe, ...]:
        return self.manual or self.suggested or (CameraKeyframe(0),)

    def with_suggestion(self, keys: tuple[CameraKeyframe, ...]) -> Scene:
        result = replace(self, suggested=keys)
        result.validate()
        return result

    def with_manual(self, keys: tuple[CameraKeyframe, ...]) -> Scene:
        result = replace(self, manual=keys)
        result.validate()
        return result

    def camera_at(self, source_time: float) -> CameraKeyframe:
        self.validate()
        if not _finite(source_time) or not self.start <= source_time <= self.end:
            raise ValueError("Zeit außerhalb der Szene")
        return interpolate(self.effective_path, source_time - self.start)


def interpolate(keys: tuple[CameraKeyframe, ...], at: float) -> CameraKeyframe:
    if not keys or not _finite(at) or at < 0:
        raise ValueError("Ungültige Kamera-Abfrage")
    i = bisect_right([key.at for key in keys], at)
    if i == 0:
        return replace(keys[0], at=at)
    if i == len(keys):
        return replace(keys[-1], at=at)
    a, b = keys[i-1], keys[i]
    t = (at-a.at)/(b.at-a.at)
    return CameraKeyframe(at, a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t,
                          a.zoom+(b.zoom-a.zoom)*t)


@dataclass(frozen=True)
class ScenePlan:
    duration: float
    scenes: tuple[Scene, ...] = ()

    def validate(self) -> None:
        if not _finite(self.duration) or self.duration <= 0:
            raise ValueError("Ungültige Aufnahmedauer")
        if not isinstance(self.scenes, tuple) or len(self.scenes) > MAX_SCENES:
            raise ValueError("Zu viele Szenen")
        previous = 0.0
        ids = set()
        for scene in self.scenes:
            scene.validate()
            if scene.id in ids or scene.start < previous or scene.end > self.duration:
                raise ValueError("Szenen überlappen, sind unsortiert oder außerhalb der Aufnahme")
            previous = scene.end
            ids.add(scene.id)

    def scene_at(self, source_time: float) -> Scene | None:
        self.validate()
        if not _finite(source_time) or not 0 <= source_time <= self.duration:
            raise ValueError("Zeit außerhalb der Aufnahme")
        # Half-open intervals; a shared boundary belongs to the next scene.
        return next((s for s in self.scenes if s.start <= source_time < s.end), None)

    def with_scene(self, scene: Scene) -> ScenePlan:
        result = replace(self, scenes=tuple(sorted(
            (*[s for s in self.scenes if s.id != scene.id], scene),
            key=lambda s: s.start)))
        result.validate()
        return result


def fixed_zoom_crop(scene: Scene, start: float, end: float
                    ) -> tuple[list[FocusPoint], float]:
    """Bridge to the existing M12 crop filter for one scene/excerpt.

    Dynamic zoom is represented in the scene model but not supported by
    the current fixed-size crop filter. Reject it rather than silently
    rendering a different camera path.
    """
    scene.validate()
    if not all(_finite(v) for v in (start, end)) or not scene.start <= start < end <= scene.end:
        raise ValueError("Renderintervall muss innerhalb einer Szene liegen")
    keys = [scene.camera_at(start)]
    keys.extend(k for k in scene.effective_path
                if start-scene.start < k.at < end-scene.start)
    keys.append(scene.camera_at(end))
    zoom = keys[0].zoom
    if any(abs(k.zoom-zoom) > 1e-9 for k in keys):
        raise ValueError("Dynamischer Zoom wird vom aktuellen Renderer noch nicht unterstützt")
    return [FocusPoint(k.at-(start-scene.start), k.x, k.y) for k in keys], zoom
