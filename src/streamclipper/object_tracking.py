"""Sparse offline object detection + temporal association for gameplay evidence.

COCO-trained DETR-family detectors recognize ordinary categories (car, truck,
person, etc.), not GTA VI missions, explosions, collisions, weapons or plot.
Tracklets are joined by class and bounding-box overlap in close video frames.
Motion/camera cuts can cause false or missing tracks. Evidence is advisory.
No model download is performed during video analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import math
from typing import Callable, Iterable, Sequence

from .gameplay import select_scene_timestamps
from .media import CancelledError, sampled_jpeg_frames
from .model_catalog import validate_model_dir
from .models import VideoInfo
from .semantic import EventEvidence

Cancelled = Callable[[], bool]
Progress = Callable[[int], None]
CATEGORIES = frozenset({'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'person'})
VEHICLES = frozenset({'car', 'truck', 'bus', 'motorcycle', 'bicycle'})


@dataclass(frozen=True)
class Detection:
    at: float
    label: str
    confidence: float
    box: tuple[float, float, float, float]  # normalized x1,y1,x2,y2


def intersection_over_union(a: tuple[float, float, float, float],
                            b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    area_a, area_b = max(0, ax2 - ax1) * max(0, ay2 - ay1), max(0, bx2 - bx1) * max(0, by2 - by1)
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    return intersection / max(area_a + area_b - intersection, 1e-9)


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0]+box[2])/2, (box[1]+box[3])/2)


def _close(a: Detection, b: Detection, max_gap: float = 1.35) -> bool:
    if b.at <= a.at or b.at - a.at > max_gap or a.label != b.label:
        return False
    if intersection_over_union(a.box, b.box) >= .16:
        return True
    x, y = _center(a.box)
    xx, yy = _center(b.box)
    return math.hypot(x - xx, y - yy) < .10


def group_tracklets(detections: Iterable[Detection], *, max_gap: float = 1.35) -> list[list[Detection]]:
    """Greedy one-to-one matching across adjacent sampled frames.

    Never connect a track across a long unsampled region of the VOD, even if
    a matching car reappears. These IDs are ephemeral, *not* persistent IDs.
    """
    by_time: dict[float, list[Detection]] = {}
    for item in detections:
        if (not math.isfinite(item.at) or not math.isfinite(item.confidence)
                or item.confidence < 0 or item.label not in CATEGORIES
                or any(not math.isfinite(v) or v < 0 or v > 1 for v in item.box)
                or item.box[0] >= item.box[2] or item.box[1] >= item.box[3]):
            continue
        by_time.setdefault(item.at, []).append(item)
    tracks: list[list[Detection]] = []
    for at in sorted(by_time):
        # Restrict predecessors to the immediately preceding sampled moment;
        # no stitching past a missing detection or scene cut.
        candidates = sorted(by_time[at], key=lambda det: -det.confidence)
        active = [i for i, track in enumerate(tracks)
                  if track[-1].at < at and at - track[-1].at <= max_gap]
        used_tracks: set[int] = set()
        for item in candidates:
            scores: list[tuple[float,int]] = []
            for idx in active:
                if idx in used_tracks or not _close(tracks[idx][-1], item, max_gap):
                    continue
                prior = tracks[idx][-1]
                scores.append((intersection_over_union(prior.box, item.box), idx))
            if scores:
                _, chosen = max(scores)
                tracks[chosen].append(item)
                used_tracks.add(chosen)
            else:
                tracks.append([item])
    return tracks


def object_track_evidence(detections: Sequence[Detection],
                          motion: Sequence[EventEvidence], *,
                          max_evidence: int = 120) -> list[EventEvidence]:
    """Require temporal persistence AND a nearby visual-activity cue.

    Otherwise routine traffic would be misrepresented as an interesting event.
    The signal says object(s) were tracked in active footage, *not* that they
    collided or that an explosion/shot happened.
    """
    if max_evidence < 1:
        raise ValueError('Ungültiges Objektbudget')
    tracks = group_tracklets(detections)
    candidates: list[EventEvidence] = []
    for track in tracks:
        if len(track) < 2:
            continue
        mid = (track[0].at + track[-1].at)/2
        if not any(ev.kind == 'motion' and abs(mid - ev.at) <= 3.0 for ev in motion):
            continue
        shifted = math.hypot(*tuple(b-a for a,b in zip(_center(track[0].box), _center(track[-1].box))))
        label = {'car':'Auto', 'truck':'LKW', 'bus':'Bus', 'motorcycle':'Motorrad',
                 'bicycle':'Fahrrad', 'person':'Person'}[track[0].label]
        # Repeated detection establishes a tracklet, not object identity or incident.
        description = (f'Objektspur: {label} über {len(track)} Bilder, '
                       f'Bildverschiebung {shifted:.2f} (kein bestätigtes Ereignis)')
        candidates.append(EventEvidence(round(mid,3), 'object', min(.62, .40 + .035*len(track)),
                                        description))
    # Collapse multiple tracked vehicles in a single temporal window to avoid
    # saturating the multimodal ranker with densely populated city traffic.
    best: dict[int, EventEvidence] = {}
    for ev in candidates:
        key = int(ev.at // 4)
        if key not in best or ev.strength > best[key].strength:
            best[key] = ev
    return sorted(best.values(), key=lambda ev: (-ev.strength, ev.at))[:max_evidence]


def _load_detector_model(model_class, folder: Path):
    """Load locally; explain optional timm dependency problems to Windows users."""
    try:
        return model_class.from_pretrained(str(folder), local_files_only=True)
    except (ImportError, RuntimeError) as exc:
        message = str(exc).lower()
        if "timm" in message and (
            "not found" in message or "no module named" in message
            or "requires the timm" in message
        ):
            raise RuntimeError(
                "Für den DETR-Objektdetektor fehlt das Python-Paket 'timm'. "
                "StreamClipper schließen und im Projektordner Folgendes ausführen: "
                r'.\runtime\python.exe -m pip install "timm>=1.0,<2"'
                " – anschließend StreamClipper neu starten."
            ) from exc
        raise


def relative_motion_evidence(detections, *, max_evidence=120):
    """Sparse camera-relative track motion. Not a calibrated physical velocity."""
    import statistics
    tracks=group_tracklets(detections)
    pairs={}
    for idx,track in enumerate(tracks):
        for a,b in zip(track,track[1:]):
            dt=b.at-a.at
            if not 0<dt<=1.35:continue
            x,y=_center(a.box);xx,yy=_center(b.box)
            pairs.setdefault((a.at,b.at),[]).append((idx,(xx-x)/dt,(yy-y)/dt))
    residuals={}
    for (a,b),rows in sorted(pairs.items()):
        # A shared translation from >=3 simultaneous tracks is only an
        # approximate camera motion estimate; zoom/rotation remain unresolved.
        if len(rows)<3:continue
        for idx,x,y in rows:
            others=[r for r in rows if r[0]!=idx]
            dx=statistics.median(r[1] for r in others)
            dy=statistics.median(r[2] for r in others)
            residuals.setdefault(idx,[]).append((a,b,x-dx,y-dy))
    hints=[]
    for idx,rows in residuals.items():
        for left,right in zip(rows,rows[1:]):
            if abs(left[1]-right[0])>.01:continue
            delta=math.hypot(right[2]-left[2],right[3]-left[3])
            if delta<.045:continue
            hints.append(EventEvidence(round(right[0],3),"object",min(.68,.40+delta),
                "Relative Tracklet-Bewegung ändert sich; gemeinsame Bildverschiebung näherungsweise entfernt; kein bestätigtes Ereignis"))
    return sorted(hints,key=lambda e:(-e.strength,e.at))[:max_evidence]


def detect_and_track(video: VideoInfo, model_directory: str | Path, *,
                     anchors: Sequence[EventEvidence], max_frames: int = 90,
                     cancelled: Cancelled | None = None,
                     progress: Progress | None = None,
                     timestamps: list[float] | None = None, device_override: str | None = None,
                     relative_motion: bool = False, batch_size: int = 1,
                     mixed_precision: bool = False) -> list[EventEvidence]:
    """Sample <=90 images (default) around interesting timestamps, track locally.

    Uses existing optional torch/transformers/Pillow installation. No remote
    model identifiers or implicit downloads may reach from this runtime.
    """
    if not 3 <= max_frames <= 300:
        raise ValueError('Objektanalyse: 3–300 Bilder erlaubt')
    folder = validate_model_dir('detector', model_directory)
    if cancelled and cancelled():
        raise CancelledError('Objektanalyse abgebrochen')
    try:
        import torch
        from PIL import Image
        from transformers import AutoImageProcessor, AutoModelForObjectDetection
    except ImportError as exc:
        raise RuntimeError('Objekterkennung benötigt das optionale Paket .[vision]') from exc
    processor = AutoImageProcessor.from_pretrained(str(folder), local_files_only=True)
    model = _load_detector_model(AutoModelForObjectDetection, folder)
    device = device_override or ('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device).eval()
    from .vision_device import report_vision_device
    report_vision_device("DETR / Objekterkennung",device)
    stamps = timestamps if timestamps is not None else select_scene_timestamps(anchors, video.duration, max_frames=max_frames)
    detections: list[Detection] = []
    from .vision_batch import frame_batches, inference_context, vision_batch_size
    frames=sampled_jpeg_frames(video,timestamps=stamps,max_frames=max_frames,cancelled=cancelled)
    processed=0
    for rows in frame_batches(frames,vision_batch_size(device,batch_size,2),cancelled):
        sizes=[(image.height,image.width) for _,image in rows]
        inputs=processor(images=[image for _,image in rows],return_tensors='pt')
        inputs={key:value.to(device) for key,value in inputs.items()}
        with torch.no_grad():
            with inference_context(torch,device,mixed_precision):
                prediction=model(**inputs)
            if not (bool(torch.isfinite(prediction.logits).all()) and bool(torch.isfinite(prediction.pred_boxes).all())):
                if not mixed_precision:raise RuntimeError("DETR non-finite output")
                prediction=model(**inputs)
            if not (bool(torch.isfinite(prediction.logits).all()) and bool(torch.isfinite(prediction.pred_boxes).all())):
                raise RuntimeError("DETR non-finite output")
            prediction.logits=prediction.logits.float()
            prediction.pred_boxes=prediction.pred_boxes.float()
            found=processor.post_process_object_detection(prediction,threshold=.55,target_sizes=sizes)
        for (at,_),(height,width),objects in zip(rows,sizes,found,strict=True):
            for score,label_id,coordinates in zip(objects['scores'],objects['labels'],objects['boxes']):
                label=str(model.config.id2label[int(label_id)]).lower()
                if label not in CATEGORIES:continue
                bbox=tuple(max(0.,min(1.,float(v)/dim)) for v,dim in zip(coordinates.tolist(),(width,height,width,height)))
                detections.append(Detection(at,label,float(score),bbox))
        processed+=len(rows)
        if progress:progress(min(99,round(100*processed/max(len(stamps),1))))
    if progress:
        progress(100)
    standard=object_track_evidence(detections, anchors)
    return standard+relative_motion_evidence(detections) if relative_motion else standard
