"""Temporal gameplay scan: bounded 6-hour logic, real FFmpeg and honest evidence."""
from pathlib import Path
import shutil
import subprocess

import pytest

from streamclipper.gameplay import (change_metrics, scan_temporal_activity,
                                    select_scene_timestamps)
from streamclipper.media import CancelledError, probe_video, sampled_jpeg_frames
from streamclipper.models import VideoInfo
from streamclipper.semantic import EventEvidence, fuse_events, temporal_visual_consensus


def test_luma_diff_and_coverage_do_not_claim_actions():
    black = bytes(1000)
    half = bytes([250] * 500 + [0] * 500)
    score, coverage = change_metrics(black, half, stride=1)
    assert .48 < score < .50
    assert coverage == .5
    assert change_metrics(black, black) == (0.0, 0.0)
    with pytest.raises(ValueError):
        change_metrics(black, b"short")


def test_six_hour_targeted_shots_look_across_full_recording():
    duration = 6 * 3600
    events = []
    for minute in range(6 * 60):
        at = minute * 60 + 21
        events.append(EventEvidence(at, "motion", .55 if minute % 4 else .60,
                                    "Ungewöhnliche Bildbewegung"))
        if minute % 5 == 0:
            events.append(EventEvidence(at + 2, "speech", .7, "Oh mein Gott"))
    shots = select_scene_timestamps(events, duration, max_frames=180)
    assert 0 < len(shots) <= 180
    assert shots == sorted(set(shots))
    assert min(shots) < 60 * 60
    assert max(shots) > 5 * 60 * 60
    assert len({int(t // 3600) for t in shots}) == 6  # all six hours represented
    assert sum(1 for t in shots if t >= 4 * 3600) > 20  # not biased to early hours


def test_no_evidence_never_exhausts_frame_budget():
    assert 1 <= len(select_scene_timestamps([], 21600, max_frames=13)) <= 13
    assert select_scene_timestamps([], 12, max_frames=1)[0] < 12
    for max_frames in (0, 2001):
        with pytest.raises(ValueError):
            select_scene_timestamps([], 21600, max_frames=max_frames)


def test_close_clip_frames_are_combined_but_not_asserted_as_truth():
    hits = [EventEvidence(10, "visual", .55, "Bildähnlichkeit: Unfall (nicht verifiziert)"),
            EventEvidence(11, "visual", .59, "Bildähnlichkeit: Unfall (nicht verifiziert)"),
            EventEvidence(20, "visual", .60, "Bildähnlichkeit: Unfall (nicht verifiziert)")]
    result = temporal_visual_consensus(hits)
    assert len(result) == 2
    assert result[0].strength == pytest.approx(.66)
    assert "2 Frames ähnlich" in result[0].description
    assert "nicht verifiziert" in result[0].description


def test_multimodal_activity_promotes_verified_sources_not_certainty():
    motion = EventEvidence(40, "motion", .53, "Plötzliche Bildveränderung")
    audio = EventEvidence(41, "audio", .28, "Audio-Peak")
    clip = EventEvidence(41, "visual", .61, "Bildähnlichkeit: Unfall (nicht verifiziert)")
    solo = fuse_events([clip], 100, max_clips=1)[0]
    combined = fuse_events([motion, audio, clip], 100, max_clips=1)[0]
    assert combined.score > solo.score
    assert "Audio-Peak" in combined.reason
    assert "Bildveränderung" in combined.reason
    assert "nicht verifiziert" in combined.reason


@pytest.fixture
def sudden_change_video(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe unavailable")
    target = tmp_path / "synthetic scene change.mp4"
    width, height, fps, duration = 96, 54, 2, 12
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{width}x{height}",
               "-r", str(fps), "-i", "pipe:0", "-c:v", "mpeg4", "-q:v", "2", str(target)]
    # A bright rectangular flash (not an actual crash) at 6.0 s.
    raw = bytearray()
    for n in range(duration * fps):
        pixels = bytearray([45] * (width * height))
        if n in (12, 13):
            for y in range(8, 46):
                for x in range(18, 77):
                    pixels[y * width + x] = 245
        raw.extend(pixels)
    subprocess.run(command, input=bytes(raw), check=True, capture_output=True, timeout=35)
    return target, probe_video(target)


def test_real_ffmpeg_detects_temporal_flash_without_claiming_crash(sudden_change_video):
    path, video = sudden_change_video
    progress = []
    result = scan_temporal_activity(video, progress=progress.append)
    assert result and any(5.5 <= event.at <= 7.5 for event in result)
    assert all(event.kind == "motion" for event in result)
    assert all("kein bestätigtes Spielereignis" in event.description for event in result)
    assert progress[-1] == 100
    assert path.is_file()


def test_temporal_cancellation_prevents_ffmpeg_process(sudden_change_video):
    _, video = sudden_change_video
    with pytest.raises(CancelledError):
        scan_temporal_activity(video, cancelled=lambda: True)


def test_seek_exact_custom_clip_timestamps(sudden_change_video):
    _, video = sudden_change_video
    shots = list(sampled_jpeg_frames(video, timestamps=[1.0, 6.0, 6.5], max_frames=3))
    assert [t for t, _ in shots] == [1.0, 6.0, 6.5]
    assert all(image.startswith(b"\xff\xd8") for _, image in shots)
    with pytest.raises(ValueError):
        list(sampled_jpeg_frames(video, timestamps=[0, 99], max_frames=3))
    with pytest.raises(ValueError):
        list(sampled_jpeg_frames(video, timestamps=[1, 2, 3, 4], max_frames=3))


def test_vision_analysis_uses_targeted_positions_and_preserves_transcript(monkeypatch):
    from streamclipper import analyze as analyzer
    from streamclipper.models import TranscriptSegment
    video = VideoInfo("mock-video.mp4", 6*3600, 1920, 1080, 60, True)
    monkeypatch.setattr(analyzer, "probe_video", lambda path: video)
    monkeypatch.setattr(analyzer, "validate_clip_model", lambda path: None)
    monkeypatch.setattr(analyzer, "audio_levels", lambda *args, **kwargs: [-40] * 21600)
    monkeypatch.setattr(analyzer, "transcribe_video", lambda *args, **kwargs:
                        [TranscriptSegment(3600, 3603, "Oh mein Gott!")])
    calls = []
    def scan(*args, **kwargs):
        calls.append("scan")
        return [EventEvidence(3601, "motion", .55, "Ungewöhnliche Bildbewegung"),
                EventEvidence(21001, "motion", .60, "Ungewöhnliche Bildbewegung")]
    def vision(*args, **kwargs):
        calls.append("clip")
        shots = kwargs["timestamps"]
        assert len(shots) <= 30
        assert any(abs(t-3601) <= 1 for t in shots)
        assert any(abs(t-21001) <= 1 for t in shots)
        if kwargs.get("progress"):
            kwargs["progress"](100)
        return [EventEvidence(3601, "visual", .6,
                              "Bildähnlichkeit: Unfall (nicht verifiziert)")]
    monkeypatch.setattr(analyzer, "scan_temporal_activity", scan)
    monkeypatch.setattr(analyzer, "recognize_gameplay", vision)
    updates = []
    result = analyzer.analyze("mock-video.mp4", speech_model="whisper",
                              vision_model="clip", max_visual_frames=30,
                              progress=updates.append)
    assert calls == ["scan", "clip"]
    assert result.method == "multimodal-temporal-evidence-v2"
    assert result.transcript[0].text == "Oh mein Gott!"
    assert result.candidates[0].score >= 70
    assert updates[-1] == 100


def test_audio_only_skips_temporal_video_decode(monkeypatch):
    from streamclipper import analyze as analyzer
    video = VideoInfo("test.mp4", 40, 1920, 1080, 30, True)
    monkeypatch.setattr(analyzer, "probe_video", lambda path: video)
    monkeypatch.setattr(analyzer, "audio_levels", lambda *args, **kwargs: [-55.0]*40)
    def never_scan(*args, **kwargs):
        raise AssertionError("no temporal scan requested")
    monkeypatch.setattr(analyzer, "scan_temporal_activity", never_scan)
    result = analyzer.analyze("test.mp4")
    assert result.method == "audio-rms-peaks-v1"
