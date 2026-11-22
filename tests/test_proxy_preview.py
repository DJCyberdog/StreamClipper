"""M11c-4 proxy preview: source-binding, VFR time mapping and crash safety."""
from dataclasses import replace
import json
from pathlib import Path
import pytest

from streamclipper.media import CancelledError
from streamclipper.models import VideoInfo
from streamclipper.proxy import (
    ProxyTiming, original_to_proxy_ms, proxy_to_original_ms,
    cache_path, cached_proxy, ensure_proxy, fingerprint,
)


def video(tmp_path):
    p = tmp_path / "stream 6h ü.mkv"
    p.write_bytes(b"unaltered video")
    return VideoInfo(str(p), 21600.0, 1920, 1080, 59.94, True)


def test_timing_with_vfr_offset_roundtrip_and_boundaries():
    timing = ProxyTiming(21600.0, 21600.02, 0.072, 0.0)
    for millis in (0, 75, 120000, 10_000_000, 21_599_999):
        proxy = original_to_proxy_ms(millis, timing)
        restored = proxy_to_original_ms(proxy, timing)
        assert abs(millis - restored) <= 72  # first-frame offset
    assert original_to_proxy_ms(-300, timing) == 0
    assert original_to_proxy_ms(21601 * 1000, timing) <= 21600.02 * 1000
    assert proxy_to_original_ms(-20, timing) >= 0
    assert proxy_to_original_ms(99999999, timing) <= 21600 * 1000


def test_cached_proxy_roundtrip_and_source_invalidation(tmp_path, monkeypatch):
    import streamclipper.proxy as module
    info = video(tmp_path)
    calls = []
    def fake_timing(path):
        # first source video frame is 50ms after format start
        return (0.050, 0.030) if Path(path).suffix == ".mkv" else (0., 0.)
    def fake_encode(_video, target, *, progress, cancelled):
        calls.append(str(target))
        Path(target).write_bytes(b"complete MP4")
        if progress:
            progress(100)
    def fake_probe(path):
        return replace(info, path=str(path), duration=21600.06, width=854, height=480)
    monkeypatch.setattr(module, "stream_offsets", fake_timing)
    monkeypatch.setattr(module, "encode_preview_proxy", fake_encode)
    monkeypatch.setattr(module, "probe_video", fake_probe)
    root = tmp_path / "proxies"
    state = ensure_proxy(info, root=root)
    assert state.media_path.is_file()
    assert state.timing.original_video_offset == pytest.approx(.05)
    assert cached_proxy(info, root=root) == state
    assert ensure_proxy(info, root=root) == state
    assert len(calls) == 1
    original = Path(info.path)
    original.write_bytes(b"changed content!")
    assert cached_proxy(info, root=root) is None
    assert original.read_bytes() == b"changed content!"


def test_failed_encode_and_cancel_do_not_publish(tmp_path, monkeypatch):
    import streamclipper.proxy as module
    info = video(tmp_path)
    root = tmp_path / "cache"
    monkeypatch.setattr(module, "stream_offsets", lambda p: (0., 0.))
    def fail(*args, **kwargs):
        raise RuntimeError("codec missing")
    monkeypatch.setattr(module, "encode_preview_proxy", fail)
    with pytest.raises(RuntimeError, match="codec"):
        ensure_proxy(info, root=root)
    assert cached_proxy(info, root=root) is None
    assert not list(root.rglob("*.partial.mp4"))
    monkeypatch.setattr(module, "encode_preview_proxy",
                        lambda *args, **kw: (_ for _ in ()).throw(CancelledError("Abgebrochen")))
    with pytest.raises(CancelledError):
        ensure_proxy(info, root=root)
    assert cached_proxy(info, root=root) is None


def test_invalid_output_duration_does_not_publish(tmp_path, monkeypatch):
    import streamclipper.proxy as module
    info = video(tmp_path)
    root = tmp_path / "cache"
    monkeypatch.setattr(module, "stream_offsets", lambda p: (0., 0.))
    monkeypatch.setattr(module, "encode_preview_proxy",
                        lambda _i,p,**kw: Path(p).write_bytes(b"valid-ish"))
    monkeypatch.setattr(module, "probe_video",
                        lambda p: replace(info, path=str(p), duration=21580, width=854, height=480))
    with pytest.raises(ValueError, match="Zeitdrift"):
        ensure_proxy(info, root=root)
    assert cached_proxy(info, root=root) is None


def test_corrupt_manifest_is_ignored_without_destroying_source(tmp_path, monkeypatch):
    import streamclipper.proxy as module
    info = video(tmp_path)
    root = tmp_path / "cache"
    monkeypatch.setattr(module, "stream_offsets", lambda p: (0., 0.))
    monkeypatch.setattr(module, "encode_preview_proxy",
                        lambda _i,p,**kw: Path(p).write_bytes(b"valid-ish"))
    monkeypatch.setattr(module, "probe_video",
                        lambda p: replace(info, path=str(p), duration=21600.0, width=854, height=480))
    state = ensure_proxy(info, root=root)
    metadata = cache_path(info, root=root).with_suffix(".json")
    metadata.write_text("{invalid", encoding="utf-8")
    assert cached_proxy(info, root=root) is None
    assert Path(info.path).read_bytes() == b"unaltered video"
    assert state.media_path.is_file()


def test_source_changed_during_encode_fails_closed(tmp_path, monkeypatch):
    import streamclipper.proxy as module
    info = video(tmp_path)
    root = tmp_path / "cache"
    monkeypatch.setattr(module, "stream_offsets", lambda p: (0., 0.))
    def mutate(_info, target, **kwargs):
        Path(target).write_bytes(b"complete MP4")
        Path(info.path).write_bytes(b"new source")
    monkeypatch.setattr(module, "encode_preview_proxy", mutate)
    monkeypatch.setattr(module, "probe_video",
                        lambda p: replace(info, path=str(p), duration=21600.0, width=854, height=480))
    with pytest.raises(ValueError, match="während"):
        ensure_proxy(info, root=root)
    assert cached_proxy(info, root=root) is None


def test_nonzero_timebase_or_audio_offset_rejected(tmp_path, monkeypatch):
    import streamclipper.proxy as module
    info = video(tmp_path)
    monkeypatch.setattr(module, "stream_offsets", lambda p: (0.7, 0.0))
    with pytest.raises(ValueError, match="Startversatz"):
        ensure_proxy(info, root=tmp_path / "cache")
    monkeypatch.setattr(module, "stream_offsets", lambda p: (0.0, 0.9))
    with pytest.raises(ValueError, match="Audio"):
        ensure_proxy(info, root=tmp_path / "cache")
