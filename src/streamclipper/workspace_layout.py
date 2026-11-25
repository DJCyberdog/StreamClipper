"""Versioned, local, atomic persistence for the M12-UX dock workspace.

Qt saveState() contains object-name/size data, not media, credentials or
project contents. Only the user interface configuration lives here.
Do not persist absolute window geometry: multi-monitor changes must not
leave StreamClipper opening off-screen.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import binascii
import json
import os
from pathlib import Path
import tempfile

from .portable import installation_directory

SCHEMA_VERSION = 1
MAX_STATE_BYTES = 256 * 1024
MAX_DOCUMENT_BYTES = 384 * 1024
WORKSPACE_NAMES = ("Highlights", "Schnitt", "Audio", "Untertitel", "Export")
FILE_NAME = "workspace-layout-v1.json"


@dataclass(frozen=True)
class WorkspaceLayout:
    active: str
    state: bytes


def _location(root: Path | None = None) -> Path:
    directory = (Path(root) if root is not None
                 else installation_directory() / "data" / "ui")
    return directory / FILE_NAME


def save_workspace(layout: WorkspaceLayout, *, root: Path | None = None) -> Path:
    if (layout.active not in WORKSPACE_NAMES
            or not isinstance(layout.state, bytes)
            or not 0 < len(layout.state) <= MAX_STATE_BYTES):
        raise ValueError("Arbeitsbereich kann nicht gespeichert werden")
    target = _location(root)
    payload = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "active": layout.active,
        "state_base64": base64.b64encode(layout.state).decode("ascii"),
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise ValueError("Arbeitsbereichskonfiguration ist zu groß")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, delete=False,
                prefix=f".{target.name}.", suffix=".tmp") as file:
            staging = Path(file.name)
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(staging, target)
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)
    return target


def load_workspace(*, root: Path | None = None) -> WorkspaceLayout | None:
    target = _location(root)
    try:
        if target.stat().st_size > MAX_DOCUMENT_BYTES:
            return None
        record = json.loads(target.read_text(encoding="utf-8"))
        if (not isinstance(record, dict)
                or record.get("schema_version") != SCHEMA_VERSION
                or record.get("active") not in WORKSPACE_NAMES
                or not isinstance(record.get("state_base64"), str)):
            return None
        value = base64.b64decode(record["state_base64"], validate=True)
        if not 0 < len(value) <= MAX_STATE_BYTES:
            return None
        return WorkspaceLayout(record["active"], value)
    except (FileNotFoundError, OSError, ValueError, TypeError,
            binascii.Error, UnicodeError, json.JSONDecodeError):
        return None


def delete_workspace(*, root: Path | None = None) -> None:
    _location(root).unlink(missing_ok=True)
