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


def test_legacy_wrapper_delegates_to_guarded_engine(tmp_path,monkeypatch):
    from streamclipper import video_import
    meta=object();calls=[]
    def preflight(url,**options):
        calls.append((url,options));return meta
    def download(value,folder,**options):
        assert value is meta and folder==tmp_path and options["authorized"] is True
        options["progress"]({"stage":"download","done":500,"total":1000})
        options["progress"]({"stage":"merge"})
        options["progress"]({"stage":"complete"})
        return folder/"twitch_123456.mp4"
    monkeypatch.setattr(video_import,"preflight",preflight)
    monkeypatch.setattr(video_import,"download",download)
    progress=[]
    result=download_twitch_vod("https://www.twitch.tv/videos/123456",tmp_path,progress=progress.append)
    assert result.name=="twitch_123456.mp4"
    assert progress==[48,96,100] and calls[0][1]["authorized"] is True

def test_legacy_wrapper_cancel_before_network(tmp_path,monkeypatch):
    from streamclipper import video_import
    monkeypatch.setattr(video_import,"preflight",lambda *a,**k:pytest.fail("No network after cancel"))
    with pytest.raises(CancelledError):
        download_twitch_vod("https://www.twitch.tv/videos/123456",tmp_path,cancelled=lambda:True)
