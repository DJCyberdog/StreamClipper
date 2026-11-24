"""M13a: ordered, non-destructive scene selection for one highlight."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import uuid

from .models import VideoInfo
from .portable import installation_directory
from .smart_director import Director, director_from_dict

MODES = ("manual", "automatic", "fixed")
MAX_SCENES = 500
VERSION = 1


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class SelectionScene:
    id: str
    start: float
    end: float
    included: bool = True
    mode: str = "automatic"
    region: tuple[float, float, float, float] = (0., 0., 1., 1.)
    director: Director = Director()

    def validate(self, start, end):
        if not isinstance(self.id, str) or not self.id or len(self.id) > 64:
            raise ValueError("Ungültige Szenen-ID")
        if not all(_number(v) for v in (self.start, self.end)) or not start <= self.start < self.end <= end:
            raise ValueError("Szenengrenzen außerhalb des Highlights")
        if type(self.included) is not bool or self.mode not in MODES:
            raise ValueError("Ungültiger Einschluss oder Kameramodus")
        if not isinstance(self.region, tuple) or len(self.region) != 4 or not all(_number(v) for v in self.region):
            raise ValueError("Ungültige Bildregion")
        self.director.validate()
        if any(not start <= k.at <= end for k in (*self.director.manual,*self.director.tracked)):
            raise ValueError("Kamerazeiten außerhalb des Highlights")
        x, y, w, h = self.region
        if not (0 <= x < 1 and 0 <= y < 1 and .01 <= w <= 1 and .01 <= h <= 1
                and x+w <= 1.000000001 and y+h <= 1.000000001):
            raise ValueError("Bildregion liegt außerhalb des Quellbildes")


@dataclass(frozen=True)
class SceneSelection:
    start: float
    end: float
    scenes: tuple[SelectionScene, ...]

    def validate(self):
        if not all(_number(v) for v in (self.start, self.end)) or not 0 <= self.start < self.end:
            raise ValueError("Ungültiges Highlight")
        if not isinstance(self.scenes, tuple) or not 1 <= len(self.scenes) <= MAX_SCENES:
            raise ValueError("Ungültige Szenenanzahl")
        ids = set()
        for scene in self.scenes:
            scene.validate(self.start, self.end)
            if scene.id in ids:
                raise ValueError("Doppelte Szenen-ID")
            ids.add(scene.id)
        ordered = sorted(self.scenes, key=lambda s: s.start)
        if any(a.end > b.start for a, b in zip(ordered, ordered[1:])):
            raise ValueError("Szenen dürfen sich zeitlich nicht überlappen")
        return self

    @property
    def output_scenes(self):
        return tuple(s for s in self.scenes if s.included)

    def edit(self, index, **changes):
        if not 0 <= index < len(self.scenes) or "id" in changes:
            raise ValueError("Ungültige Szenenauswahl")
        scenes = list(self.scenes)
        scenes[index] = replace(scenes[index], **changes)
        return replace(self, scenes=tuple(scenes)).validate()

    def split(self, index, at):
        if not 0 <= index < len(self.scenes):
            raise ValueError("Ungültige Szenenauswahl")
        scene = self.scenes[index]
        if not _number(at) or not scene.start < at < scene.end:
            raise ValueError("Schnittpunkt muss innerhalb der Szene liegen")
        return replace(self, scenes=(
            *self.scenes[:index], replace(scene, end=at),
            replace(scene, id=uuid.uuid4().hex, start=at),
            *self.scenes[index+1:])).validate()

    def move(self, index, direction):
        if direction not in (-1, 1) or not 0 <= index < len(self.scenes) or not 0 <= index+direction < len(self.scenes):
            raise ValueError("Szene kann nicht verschoben werden")
        scenes = list(self.scenes)
        scenes[index], scenes[index+direction] = scenes[index+direction], scenes[index]
        return replace(self, scenes=tuple(scenes)).validate()


def initial_selection(start, end):
    return SceneSelection(start, end, (SelectionScene(uuid.uuid4().hex, start, end),)).validate()


def _identity(video, start, end):
    if not all(_number(v) for v in (start, end, video.duration)) or not 0 <= start < end <= video.duration+.1:
        raise ValueError("Ungültiges Highlight für diese Aufnahme")
    return dict(path=os.path.normcase(os.path.abspath(video.path)), duration=video.duration,
                width=video.width, height=video.height, start=float(start), end=float(end))


def _path(video, start, end, root):
    identity = _identity(video, start, end)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    directory = Path(root) if root is not None else installation_directory() / "data" / "projects" / "scenes"
    return directory / (key + ".json"), identity


def save_selection(video: VideoInfo, selection: SceneSelection, *, root=None):
    selection.validate()
    path, identity = _path(video, selection.start, selection.end, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(version=VERSION, identity=identity, scenes=[asdict(s) for s in selection.scenes]),
                         allow_nan=False, ensure_ascii=False)
    stage = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False, suffix=".tmp") as stream:
            stage = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(stage, path)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
    return path


def load_selection(video: VideoInfo, start, end, *, root=None):
    path, identity = _path(video, start, end, root)
    if not path.exists():
        return initial_selection(start, end)
    if path.stat().st_size > 1024*1024:
        raise ValueError("Szenenplan zu groß")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc["version"] != VERSION or doc["identity"] != identity:
            raise ValueError("Szenenplan gehört nicht zu diesem Highlight")
        scenes = tuple(SelectionScene(**{**s, "region": tuple(s["region"]),
                                           "director": director_from_dict(s.get("director"))}) for s in doc["scenes"])
        return SceneSelection(start, end, scenes).validate()
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("Ungültiger Szenenplan") from exc


def require_unplanned_highlight(video, start, end, *, root=None):
    """Temporary fail-closed boundary until the shared renderer accepts plans."""
    path, _ = _path(video, start, end, root)
    if path.exists():
        raise ValueError("Für dieses Highlight ist ein Szenenplan gespeichert. "
                         "Szenenrendering ist noch nicht verfügbar; der Plan darf nicht ignoriert werden.")


def selection_from_dict(doc):
    if not isinstance(doc, dict):
        raise ValueError("Ungültiger Szenenplan")
    try:
        scenes = tuple(SelectionScene(**{**s, "region": tuple(s["region"]),
                                           "director": director_from_dict(s.get("director"))})
                       for s in doc["scenes"])
        return SceneSelection(doc["start"], doc["end"], scenes).validate()
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("Ungültiger Szenenplan") from exc


def excerpt_selection(plan, maximum):
    """Limit by OUTPUT time, retaining output order and source coordinates."""
    plan.validate()
    if not _number(maximum) or maximum <= 0:
        raise ValueError("Ungültige Vorschaudauer")
    scenes = []
    remaining = maximum
    for scene in plan.output_scenes:
        if remaining <= 0:
            break
        length = min(scene.end-scene.start, remaining)
        scenes.append(replace(scene, end=scene.start+length))
        remaining -= length
    if not scenes:
        raise ValueError("Keine eingeschlossene Szene")
    return replace(plan, scenes=tuple(scenes)).validate()


def output_duration(plan):
    return sum(s.end-s.start for s in plan.output_scenes)


def saved_selection_exists(video, start, end, *, root=None):
    return _path(video, start, end, root)[0].exists()
