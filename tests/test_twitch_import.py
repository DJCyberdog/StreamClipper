"""Offline Twitch VOD import contract; fake yt-dlp, no network requests."""
from pathlib import Path
import sys
from types import ModuleType

import pytest

from streamclipper.media import CancelledError
from streamclipper.twitch_import import download_twitch_vod, parse_twitch_vod_url


@pytest.mark.parametrize("url,normalized", [
    ("https://www.twitch.tv/videos/1234567890", "https://www.twitch.tv/videos/1234567890"),
    ("https://twitch.tv/videos/1234?filter=archives", "https://www.twitch.tv/videos/1234"),
    ("https://m.twitch.tv/videos/12345/", "https://www.twitch.tv/videos/12345"),
])
def test_url_canonicalization(url, normalized):
    assert parse_twitch_vod_url(url)[0] == normalized


@pytest.mark.parametrize("url", [
    "", "http://www.twitch.tv/videos/123", "https://www.twitch.tv.evil.com/videos/123",
    "https://www.twitch.tv/videos/123/../456", "https://www.twitch.tv/a_channel",
    "file:///home/a.mp4", "https://www.twitch.tv:444/videos/123",
    "https://user:pass@www.twitch.tv/videos/123",
    "https://clips.twitch.tv/funny", "https://www.twitch.tv/videos/not_an_id",
])
def test_reject_non_public_vod_urls(url):
    with pytest.raises(ValueError, match="Twitch"):
        parse_twitch_vod_url(url)


def test_download_progress_and_complete_file(tmp_path, monkeypatch):
    calls = []

    class FakeDownloader:
        def __init__(self, opts):
            self.opts = opts
            calls.append(opts)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download):
            assert url == "https://www.twitch.tv/videos/123456"
            assert download is True
            target = Path(self.opts["outtmpl"].replace("%(ext)s", "mp4"))
            target.write_bytes(b"a real download in production")
            self.opts["progress_hooks"][0](
                {"status": "downloading", "downloaded_bytes": 500, "total_bytes": 1000})
            self.opts["progress_hooks"][0]({"status": "finished"})
            return {"id": "123456"}

    module = ModuleType("yt_dlp")
    module.YoutubeDL = FakeDownloader
    monkeypatch.setitem(sys.modules, "yt_dlp", module)
    progress = []
    result = download_twitch_vod("https://www.twitch.tv/videos/123456", tmp_path,
                                 progress=progress.append)
    assert result.name == "twitch_123456.mp4"
    assert progress == [48, 96, 100]
    assert calls[0]["continuedl"] is True
    assert calls[0]["overwrites"] is False
    assert calls[0]["noplaylist"] is True


def test_cancel_keeps_resumable_partial(tmp_path, monkeypatch):
    module = ModuleType("yt_dlp")
    class FakeDownloader:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def extract_info(self, url, download):
            (tmp_path / "twitch_123456.mp4.part").write_bytes(b"partial")
            self.opts["progress_hooks"][0]({"status": "downloading"})
    module.YoutubeDL = FakeDownloader
    monkeypatch.setitem(sys.modules, "yt_dlp", module)
    with pytest.raises(CancelledError):
        download_twitch_vod("https://www.twitch.tv/videos/123456", tmp_path,
                            cancelled=lambda: (tmp_path / "twitch_123456.mp4.part").exists())
    assert (tmp_path / "twitch_123456.mp4.part").is_file()


def test_missing_finished_file_cannot_fake_success(tmp_path, monkeypatch):
    module = ModuleType("yt_dlp")
    class FakeDownloader:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def extract_info(self, url, download):
            return {"id": "123456"}
    module.YoutubeDL = FakeDownloader
    monkeypatch.setitem(sys.modules, "yt_dlp", module)
    with pytest.raises(RuntimeError, match="fertige Videodatei fehlt"):
        download_twitch_vod("https://www.twitch.tv/videos/123456", tmp_path)
