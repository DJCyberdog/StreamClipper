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
    """M5 compatibility entry point; delegate to the same guarded M18 engine."""
    from .video_import import preflight,download
    canonical,_=parse_twitch_vod_url(url)
    if cancelled and cancelled():raise CancelledError("Twitch-Import abgebrochen")
    folder=Path(directory).expanduser().resolve();folder.mkdir(parents=True,exist_ok=True)
    meta=preflight(canonical,authorized=True,cancelled=cancelled)
    def report(row):
        if not progress:return
        if row["stage"]=="complete":progress(100)
        elif row["stage"]=="merge":progress(96)
        elif row.get("total") and row.get("done") is not None:progress(min(95,round(95*row["done"]/row["total"])))
    return download(meta,folder,authorized=True,progress=report,cancelled=cancelled)
