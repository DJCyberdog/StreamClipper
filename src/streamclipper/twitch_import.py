"""Optional explicit download of public Twitch VODs into a user-selected folder.

Nothing is downloaded by ordinary analysis. yt-dlp is imported only if the
user explicitly chooses Twitch import. Access restrictions are not bypassed.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Callable
from urllib.parse import urlsplit

from .media import CancelledError

Progress = Callable[[int], None]
Cancelled = Callable[[], bool]

_ALLOWED_HOSTS = frozenset({"twitch.tv", "www.twitch.tv", "m.twitch.tv"})
_VOD_PATH = re.compile(r"/videos/([1-9][0-9]*)/?")
_VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".webm", ".mov", ".ts"})


def parse_twitch_vod_url(raw: str) -> tuple[str, str]:
    """Only public VOD links, not arbitrary URLs, channels or live streams."""
    try:
        parsed = urlsplit(raw.strip())
        # Accessing .port rejects syntactically malformed ports.
        if (parsed.scheme.lower() != "https" or parsed.hostname not in _ALLOWED_HOSTS
                or parsed.username or parsed.password or parsed.port is not None):
            raise ValueError
    except ValueError as exc:
        raise ValueError("Bitte eine gültige Twitch-VOD-URL angeben (https://www.twitch.tv/videos/123456).") from exc
    match = _VOD_PATH.fullmatch(parsed.path)
    if not match:
        raise ValueError("Bitte eine Twitch-VOD-URL verwenden (https://www.twitch.tv/videos/123456).")
    video_id = match.group(1)
    return f"https://www.twitch.tv/videos/{video_id}", video_id


def download_twitch_vod(url: str, directory: str | Path, *,
                        progress: Progress | None = None,
                        cancelled: Cancelled | None = None) -> Path:
    """Download one VOD, retaining .part files for resumption on interrupted jobs.

    yt-dlp owns retries, fragment downloads and final publication. Only finished
    files matching the validated VOD ID are returned to the player.
    """
    canonical, vod_id = parse_twitch_vod_url(url)
    if cancelled and cancelled():
        raise CancelledError("Twitch-Import abgebrochen")
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            'Twitch-Import benötigt yt-dlp. Im Projektordner ausführen: '
            r'.\.venv\Scripts\python.exe -m pip install -e ".[twitch]"'
        ) from exc
    folder = Path(directory).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    pattern = f"twitch_{vod_id}.%(ext)s"

    def on_progress(entry: dict) -> None:
        if cancelled and cancelled():
            raise CancelledError("Twitch-Import abgebrochen; Teildownload bleibt zum Fortsetzen erhalten")
        if progress and entry.get("status") == "downloading":
            total = entry.get("total_bytes") or entry.get("total_bytes_estimate")
            done = entry.get("downloaded_bytes") or 0
            if isinstance(total, (float, int)) and total > 0:
                progress(max(0, min(95, round(95 * done / total))))
        elif progress and entry.get("status") == "finished":
            progress(96)

    options = {
        "format": "best", "noplaylist": True, "quiet": True,
        "noprogress": True, "no_warnings": True,
        "outtmpl": str(folder / pattern),
        "overwrites": False, "continuedl": True,
        "retries": 5, "fragment_retries": 10,
        "progress_hooks": [on_progress],
        "windowsfilenames": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(canonical, download=True)
    except Exception as exc:
        if cancelled and cancelled():
            raise CancelledError("Twitch-Import abgebrochen; Download kann später fortgesetzt werden") from exc
        raise RuntimeError(f"Twitch-VOD konnte nicht heruntergeladen werden: {exc}") from exc
    if cancelled and cancelled():
        raise CancelledError("Twitch-Import abgebrochen")
    if not isinstance(info, dict) or str(info.get("id", vod_id)) != vod_id:
        raise RuntimeError("Twitch-Download lieferte keine passende Video-ID")
    finished = [path for path in folder.glob(f"twitch_{vod_id}.*")
                if path.is_file() and path.suffix.lower() in _VIDEO_EXTENSIONS and path.stat().st_size > 0]
    if not finished:
        raise RuntimeError("Twitch-Download meldet Erfolg, aber die fertige Videodatei fehlt")
    output = max(finished, key=lambda path: path.stat().st_mtime)
    if progress:
        progress(100)
    return output
