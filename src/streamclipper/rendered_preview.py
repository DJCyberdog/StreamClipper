"""M12a source-accurate rendered-clip preview, disposable after viewing."""
from __future__ import annotations

from dataclasses import dataclass
import tempfile
from pathlib import Path
from typing import Callable

from .media import CancelledError
from .portable import installation_directory
from .render_contract import RenderRequest, render_request


@dataclass(frozen=True)
class RenderedPreview:
    path: Path
    request: RenderRequest
    excerpt_of_longer_clip: bool


def render_clip_preview(
        request: RenderRequest, *,
        max_seconds: float = 20.0,
        cancelled: Callable[[], bool] | None = None,
        progress: Callable[[int], None] | None = None,
        encoder_notice: Callable[[str], None] | None = None,
        temp_root: Path | None = None) -> tuple[RenderedPreview, tempfile.TemporaryDirectory]:
    """Render a bounded preview MP4 with the same encoder as export.

    The caller owns and MUST clean up the returned TemporaryDirectory after
    QMediaPlayer releases the file. On failure/cancel it cleans up here.
    """
    excerpt = request.preview_excerpt(max_seconds)
    if cancelled and cancelled():
        raise CancelledError("Render-Vorschau abgebrochen")
    root = (Path(temp_root) if temp_root is not None
            else installation_directory() / "data" / "tmp")
    root.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix="m12-render-preview-", dir=root)
    try:
        destination = Path(temporary.name) / "preview.mp4"
        output = render_request(
            excerpt, destination, progress=progress, cancelled=cancelled,
            encoder_notice=encoder_notice)
        if cancelled and cancelled():
            raise CancelledError("Render-Vorschau abgebrochen")
        result = RenderedPreview(
            path=output, request=excerpt,
            excerpt_of_longer_clip=request.end > excerpt.end + 0.0001)
        return result, temporary
    except BaseException:
        temporary.cleanup()
        raise
