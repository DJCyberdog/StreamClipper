"""M12e: durable, single-worker, crash-aware local render queue.

At-most-once automatic output: each job uses a unique stable target path.
After a crash, an existing target with a verified job receipt is recovered as
COMPLETE; an unreceipted target is BLOCKED, never silently rendered again.
An OS advisory file lock protects against two app instances processing the
same queue. Restart never auto-starts FFmpeg, and source files stay untouched.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid
from typing import Callable

from .editor_project import EditorProject, TimelineItem, Track
from .export_qa import read_report
from .media import CancelledError
from .models import TranscriptSegment, TranscriptWord, VideoInfo
from .portable import installation_directory
from .render_contract import RenderRequest, render_request
from .scene_selection import selection_from_dict
from .caption_style import caption_style_from_dict
from .editor_project import item_from_dict

QUEUE_VERSION = 1
MAX_JOBS = 200
MAX_BYTES = 20 * 1024 * 1024
STATES = frozenset({
    "QUEUED", "RUNNING", "INTERRUPTED", "COMPLETE",
    "FAILED", "CANCELLED", "BLOCKED"})
RESUMABLE = frozenset({"INTERRUPTED", "FAILED", "CANCELLED"})
_JOB_ID = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class QueueJob:
    id: str
    label: str
    request: dict
    request_sha256: str
    destination: str
    status: str = "QUEUED"
    progress: int = 0
    result: str | None = None
    detail: str = ""


def _snapshot(request: RenderRequest) -> dict:
    from .montage_request import MontageRequest,snapshot
    if isinstance(request,MontageRequest):return snapshot(request.validate(verify_media=True))
    request.validate()
    return asdict(request)


def _rehydrate(record: dict) -> RenderRequest:
    if not isinstance(record, dict) or not isinstance(record.get("video"), dict):
        raise ValueError("Renderqueue-Request beschädigt")
    if record.get("kind")=="montage-v1":
        from .montage_request import rehydrate
        return rehydrate(record)
    if record.get("kind") is not None:raise ValueError("Unbekannter Renderjob-Typ")
    doc = dict(record)
    doc["video"] = VideoInfo(**doc["video"])
    doc["transcript"] = tuple(
        TranscriptSegment(**{
            **segment,
            "words": tuple(TranscriptWord(**word)
                           for word in segment.get("words", []))})
        for segment in doc.get("transcript", []))
    project = doc.get("project")
    if project is not None:
        doc["project"] = EditorProject(
            project["schema_version"], VideoInfo(**project["source"]),
            tuple(Track(**t) for t in project["tracks"]),
            tuple(item_from_dict(item) for item in project["items"]),
            tuple(selection_from_dict(p) for p in project.get("scene_plans", [])),
            caption_style_from_dict(project.get("caption_style")),project.get("base_audio_enabled",True))
    if doc.get('scene_plan') is not None:
        doc['scene_plan'] = selection_from_dict(doc['scene_plan'])
    doc['caption_style']=caption_style_from_dict(doc.get('caption_style'))
    request = RenderRequest(**doc)
    return request.validate()


def _fingerprint(record: dict) -> str:
    payload = json.dumps(
        record, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, record: dict) -> None:
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, indent=2).encode("utf-8")
    if len(payload) > MAX_BYTES:
        raise ValueError("Renderqueue-Datei überschreitet maximale Größe")
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, delete=False,
                prefix="." + path.name + ".", suffix=".tmp") as stream:
            staging = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)


def _read_jobs(file: Path) -> list[QueueJob]:
    if not file.exists():
        return []
    if file.stat().st_size > MAX_BYTES:
        raise ValueError("Gespeicherte Renderqueue ist zu groß")
    doc = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema_version") != QUEUE_VERSION:
        raise ValueError("Unbekannte Renderqueue-Version")
    if not isinstance(doc.get("jobs"), list) or len(doc["jobs"]) > MAX_JOBS:
        raise ValueError("Ungültige Anzahl von Renderjobs")
    jobs = [QueueJob(**job) for job in doc["jobs"]]
    if len({x.id for x in jobs}) != len(jobs):
        raise ValueError("Doppelte Renderjob-IDs")
    for job in jobs:
        if (not _JOB_ID.fullmatch(job.id)
                or job.status not in STATES
                or not os.path.isabs(job.destination)
                or not isinstance(job.label, str)
                or len(job.label) > 160
                or not 0 <= job.progress <= 100
                or job.request_sha256 != _fingerprint(job.request)):
            raise ValueError("Renderjob-Daten ungültig")
        _rehydrate(job.request)
    return jobs


def _lock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Renderqueue wird bereits von einer anderen Instanz benutzt") from exc
    else:
        import fcntl
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Renderqueue wird bereits von einer anderen Instanz benutzt") from exc


def _unlock_file(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _receipt_path(path: Path) -> Path:
    return path.with_name(path.name + ".scjob.json")


class RenderQueue:
    """Own one queue lock for its lifetime. One run_next at a time."""

    def __init__(self, *, root: Path | None = None):
        self.root = (Path(root) if root is not None
                     else installation_directory() / "data" / "queue")
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock_handle = (self.root / ".queue.lock").open("a+b")
        try:
            _lock_file(self._lock_handle)
            self._file = self.root / "render-queue-v1.json"
            self._jobs = _read_jobs(self._file)
        except BaseException:
            self._lock_handle.close()
            raise
        self._mutex = threading.RLock()
        self._active = threading.Lock()
        self._cancel = threading.Event()
        self._closed = False
        self._recover()

    def close(self) -> None:
        if not self._closed:
            if self._active.locked():
                raise RuntimeError("Eine laufende Renderqueue darf nicht geschlossen werden")
            self._closed = True
            _unlock_file(self._lock_handle)
            self._lock_handle.close()

    def _save(self) -> None:
        _write_json(self._file, {
            "schema_version": QUEUE_VERSION,
            "jobs": [asdict(job) for job in self._jobs]})

    def jobs(self) -> tuple[QueueJob, ...]:
        with self._mutex:
            return tuple(self._jobs)

    def _set(self, job_id: str, **fields) -> QueueJob:
        with self._mutex:
            index = next(i for i, j in enumerate(self._jobs) if j.id == job_id)
            item = replace(self._jobs[index], **fields)
            old = self._jobs[index]
            self._jobs[index] = item
            try:
                self._save()
            except BaseException:
                self._jobs[index] = old
                raise
            return item

    def _receipt_valid(self, job: QueueJob) -> bool:
        output = Path(job.destination)
        receipt = _receipt_path(output)
        if not output.is_file() or not receipt.is_file():
            return False
        try:
            if receipt.stat().st_size > 10_000:
                return False
            data = json.loads(receipt.read_text(encoding="utf-8"))
            qa = read_report(output)
            return (
                data.get("job_id") == job.id
                and data.get("request_sha256") == job.request_sha256
                and data.get("file_sha256") == qa.file_sha256
                and output.stat().st_size == qa.file_bytes
                # SHA of full file is necessary for crash recovery trust.
                and _hash_file(output) == qa.file_sha256)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
            return False

    def _recover(self) -> None:
        changed = False
        new = []
        for job in self._jobs:
            path = Path(job.destination)
            if path.exists():
                if self._receipt_valid(job):
                    status = "COMPLETE"
                    detail = "Fertige Ausgabe mit Jobbeleg nach Neustart geprüft"
                    progress = 100
                    result = job.destination
                else:
                    status = "BLOCKED"
                    detail = "Datei am Ziel ohne gültigen Jobbeleg – kein automatischer Doppel-Export"
                    progress = job.progress
                    result = None
            elif job.status in {"RUNNING", "COMPLETE"}:
                status, detail, progress, result = (
                    "INTERRUPTED", "Job nach Neustart unterbrochen; manuell fortsetzen",
                    0, None)
            else:
                status, detail, progress, result = (
                    job.status, job.detail, job.progress, job.result)
            updated = replace(job, status=status, detail=detail,
                              progress=progress, result=result)
            changed |= updated != job
            new.append(updated)
        if changed:
            self._jobs = new
            self._save()

    def enqueue(self, request: RenderRequest, directory: str | Path,
                *, label: str = "Highlight") -> QueueJob:
        if self._closed:
            raise RuntimeError("Renderqueue wurde geschlossen")
        record = _snapshot(request)
        dest_dir = Path(directory).expanduser().resolve()
        if not dest_dir.is_dir():
            raise ValueError("Render-Zielordner existiert nicht")
        if not isinstance(label, str) or not label.strip() or len(label) > 160:
            raise ValueError("Ungültiger Renderjob-Name")
        with self._mutex:
            if len(self._jobs) >= MAX_JOBS:
                raise ValueError("Renderqueue enthält bereits 200 Jobs")
            job_id = uuid.uuid4().hex
            source = Path(request.video.path).stem
            # Only safe filename characters; unique ID prevents collisions.
            stem = re.sub(r"[^a-zA-Z0-9_-]", "_", source).strip("_")[:48]
            target = dest_dir / f"{stem or 'clip'}_sc_{job_id[:16]}.mp4"
            job = QueueJob(job_id, label.strip(), record,
                           _fingerprint(record), str(target))
            self._jobs.append(job)
            try:
                self._save()
            except BaseException:
                self._jobs.pop()
                raise
            return job

    def cancel(self, job_id: str | None = None) -> None:
        if job_id is None:
            self._cancel.set()
            return
        with self._mutex:
            job = next(j for j in self._jobs if j.id == job_id)
            if job.status == "RUNNING":
                self._cancel.set()
            elif job.status == "QUEUED":
                self._set(job_id, status="CANCELLED",
                          detail="Noch nicht gestarteter Job abgebrochen")

    def resume(self, job_id: str) -> QueueJob:
        with self._mutex:
            job = next(j for j in self._jobs if j.id == job_id)
            if job.status not in RESUMABLE:
                raise ValueError("Nur fehlgeschlagene oder unterbrochene Jobs sind fortsetzbar")
            if Path(job.destination).exists():
                return self._set(job_id, status="BLOCKED",
                    detail="Ausgabe liegt bereits am Ziel: manuelle Prüfung statt Doppel-Export")
            return self._set(job_id, status="QUEUED", progress=0, detail="",
                             result=None)

    def discard(self, job_id: str) -> None:
        """Remove only queue metadata, never any media or QA reports."""
        with self._mutex:
            job = next(j for j in self._jobs if j.id == job_id)
            if job.status == "RUNNING":
                raise ValueError("Laufender Job kann nicht aus Liste entfernt werden")
            old = self._jobs
            self._jobs = [j for j in old if j.id != job_id]
            try:
                self._save()
            except BaseException:
                self._jobs = old
                raise

    def run_next(
            self, *, progress: Callable[[QueueJob], None] | None = None,
            notice: Callable[[str], None] | None = None) -> QueueJob | None:
        if self._closed:
            raise RuntimeError("Queue wurde geschlossen")
        if not self._active.acquire(blocking=False):
            raise RuntimeError("Es rendert bereits ein Queue-Job")
        try:
            self._cancel.clear()
            with self._mutex:
                job = next((j for j in self._jobs if j.status == "QUEUED"), None)
                if job is None:
                    return None
                # Never start a job whose destination is already occupied.
                if Path(job.destination).exists():
                    return self._set(job.id, status="BLOCKED",
                        detail="Ziel bereits belegt – Export nicht überschrieben")
                self._set(job.id, status="RUNNING", progress=0,
                          detail="Rendern / QA")
            try:
                request = _rehydrate(job.request)

                def update(percent: int) -> None:
                    if self._cancel.is_set():
                        return
                    if progress:
                        progress(replace(job, status="RUNNING", progress=percent))
                    if percent == 100 or (percent >= 0 and percent % 10 == 0):
                        with self._mutex:
                            actual = next(j for j in self._jobs if j.id == job.id)
                            if percent > actual.progress:
                                self._set(job.id, progress=percent)

                from .montage_request import MontageRequest
                if isinstance(request,MontageRequest):
                    result=request.render(job.destination,progress=update,cancelled=self._cancel.is_set,encoder_notice=notice)
                else:
                    result = render_request(
                        request, job.destination, progress=update,
                        cancelled=self._cancel.is_set, encoder_notice=notice)
                if self._cancel.is_set():
                    return self._set(job.id, status="INTERRUPTED",
                        detail="Nach Rendern abgebrochen; vorhandene MP4 manuell prüfen")
                output = Path(result)
                if output.resolve() != Path(job.destination).resolve():
                    return self._set(job.id, status="BLOCKED",
                        detail="Dateikollision; anderes Ausgabeziel erzeugt: " + str(output))
                qa = read_report(output)
                if _hash_file(output) != qa.file_sha256:
                    raise ValueError("QA-Hash passt nicht zur fertigen MP4")
                _write_json(_receipt_path(output), {
                    "schema_version": QUEUE_VERSION, "job_id": job.id,
                    "request_sha256": job.request_sha256,
                    "file_sha256": qa.file_sha256})
                return self._set(job.id, status="COMPLETE", progress=100,
                                 result=str(output), detail="QA bestanden")
            except CancelledError:
                return self._set(job.id, status="CANCELLED", progress=0,
                                 detail="Rendering vom Benutzer abgebrochen")
            except Exception as exc:
                # Do not retry when an MP4 may already have been published.
                if Path(job.destination).exists():
                    return self._set(job.id, status="BLOCKED",
                        detail="MP4 vorhanden, aber Jobbeleg fehlt: " + str(exc)[:320])
                return self._set(job.id, status="FAILED", progress=0,
                                 detail=str(exc)[:500])
        finally:
            self._active.release()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
