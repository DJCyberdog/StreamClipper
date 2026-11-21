"""Deterministic M2 detector-fusion tests (no model downloads or network)."""
from pathlib import Path
import shutil
import subprocess

import pytest

from streamclipper import analyze as analyzer
from streamclipper.media import CancelledError, probe_video, sampled_jpeg_frames
from streamclipper.models import VideoInfo
from streamclipper.semantic import (EventEvidence, fuse_events, transcript_cues,
                                    transcribe_reactions, recognize_gameplay, visual_match)


def test_transcript_reactions_are_explicit_and_timestamped():
    matches = transcript_cues([
        (1.0, 3.0, "Wir fahren ganz normal weiter."),
        (8.0, 9.5, "Oh mein Gott! Was war das denn?!"),
        (20.0, 21.0, "Aua, shit!!"),
        (25.0, 26.0, "ordinary narration"),
    ])
    assert len(matches) == 2
    assert matches[0].at == 8.75
    assert "Oh mein Gott" in matches[0].description
    assert all(e.kind == "speech" for e in matches)
    assert all(0 < e.strength <= 1 for e in matches)


def test_visual_classifier_needs_evidence_vs_neutral_controls():
    assert visual_match({"crash": 0.48, "menu": 0.07, "ordinary": 0.08}, 8.0)
    assert visual_match({"crash": 0.2, "menu": 0.6, "ordinary": 0.15}, 8.0) is None
    assert visual_match({"crash": 0.35, "menu": 0.32, "ordinary": 0.2}, 8.0) is None
    event = visual_match({"crash": 0.48, "menu": 0.07, "ordinary": 0.08}, 8.0)
    assert event.kind == "visual" and "nicht verifiziert" in event.description


def test_combination_ranks_better_than_loudness_alone():
    events = [
        EventEvidence(10.0, "audio", 0.28, "Audio-Peak"),
        EventEvidence(55.0, "speech", 0.67, "Transkript-Hinweis: „Alter!“"),
        EventEvidence(57.0, "visual", 0.65, "Bildähnlichkeit: Unfall"),
        EventEvidence(105.0, "audio", 0.28, "Audio-Peak"),
    ]
    result = fuse_events(events, 140, clip_seconds=25, max_clips=5)
    assert result[0].score > next(c.score for c in result if c.peak_at == 10.0)
    assert "Transkript" in result[0].reason and "Bildähnlichkeit" in result[0].reason
    assert all(0 <= c.start < c.end <= 140 for c in result)
    assert all(a.end <= b.start or b.end <= a.start
               for i, a in enumerate(result) for b in result[i + 1:])


def test_same_modality_does_not_fabricate_multimodal_bonus():
    events = [EventEvidence(21.0, "visual", 0.7, "Bild A"),
              EventEvidence(22.0, "visual", 0.7, "Bild B")]
    single = fuse_events(events[:1], 80)[0]
    repeated = fuse_events(events, 80)[0]
    assert single.score == repeated.score


def test_multimodal_analyze_calls_both_detectors(monkeypatch):
    video = VideoInfo("fake.mkv", 160.0, 1920, 1080, 60, True)
    monkeypatch.setattr(analyzer, "probe_video", lambda path: video)
    monkeypatch.setattr(analyzer, "audio_levels", lambda *_args, **_kwargs: [-45.0] * 160)
    called = []
    def fake_speech(*args, **kwargs):
        called.append(("speech", args[1]))
        return [EventEvidence(40, "speech", 0.65, "Transkript-Hinweis")]
    def fake_vision(*args, **kwargs):
        called.append(("vision", args[1], kwargs["max_frames"]))
        return [EventEvidence(41, "visual", 0.60, "Bildähnlichkeit")]
    monkeypatch.setattr(analyzer, "transcribe_reactions", fake_speech)
    monkeypatch.setattr(analyzer, "recognize_gameplay", fake_vision)
    percentages = []
    result = analyzer.analyze("fake.mkv", speech_model="whisper-dir", vision_model="clip-dir",
                              max_visual_frames=24, progress=percentages.append)
    assert called == [("speech", "whisper-dir"), ("vision", "clip-dir", 24)]
    assert result.method == "multimodal-evidence-v1"
    assert result.candidates[0].score >= 70
    assert percentages and percentages[-1] == 100
    assert all(0 <= p <= 100 for p in percentages)


def test_opt_in_without_model_fails_clearly():
    video = VideoInfo("unused.mp4", 30.0, 1920, 1080, 30.0, True)
    with pytest.raises(FileNotFoundError, match="Whisper-Modellordner"):
        transcribe_reactions(video, "no/such/model")
    with pytest.raises(FileNotFoundError, match="CLIP-Modellordner"):
        recognize_gameplay(video, "no/such/model")
    with pytest.raises(ValueError):
        fuse_events([], 120, clip_seconds=0)


@pytest.fixture
def synthetic_gameplay(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg tools missing")
    source = tmp_path / "Daueraufnahme Ö.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=180x120:rate=10:duration=9",
        "-c:v", "mpeg4", "-q:v", "6", str(source)
    ], check=True, capture_output=True, timeout=30)
    return source, probe_video(source)


def test_sampled_frame_stream_is_bounded_and_reaped(synthetic_gameplay):
    source, video = synthetic_gameplay
    frames = list(sampled_jpeg_frames(video, max_frames=6))
    assert 2 <= len(frames) <= 6
    assert all(jpg.startswith(b"\xff\xd8") and jpg.endswith(b"\xff\xd9")
               for _, jpg in frames)
    assert [time for time, _ in frames] == sorted(time for time, _ in frames)
    assert all(0 <= time <= video.duration for time, _ in frames)
    assert source.is_file()


def test_frame_sampling_cancellation(synthetic_gameplay):
    _, video = synthetic_gameplay
    with pytest.raises(CancelledError):
        list(sampled_jpeg_frames(video, max_frames=6, cancelled=lambda: True))


def test_audio_only_default_is_unchanged(synthetic_gameplay):
    source, _ = synthetic_gameplay
    result = analyzer.analyze(str(source))
    assert result.method == "audio-rms-peaks-v1"
    assert result.candidates


def test_faster_whisper_adapter_is_offline_and_timestamped(monkeypatch, tmp_path):
    import sys
    from types import ModuleType, SimpleNamespace

    model_dir = tmp_path / "local-whisper"
    model_dir.mkdir()
    captured = {}

    class FakeWhisper:
        def __init__(self, path, **kwargs):
            captured.update(path=path, **kwargs)
        def transcribe(self, path, **kwargs):
            assert path == "capture.mkv"
            assert kwargs["vad_filter"] is True
            return iter([SimpleNamespace(start=5.0, end=8.0,
                                         text="Oh mein Gott, Alter!")]), None

    mod = ModuleType("faster_whisper")
    mod.WhisperModel = FakeWhisper
    monkeypatch.setitem(sys.modules, "faster_whisper", mod)
    video = VideoInfo("capture.mkv", 40.0, 1920, 1080, 60.0, True)
    updates = []
    result = transcribe_reactions(video, str(model_dir), progress=updates.append)
    assert captured["local_files_only"] is True
    assert captured["path"] == str(model_dir)
    assert result and result[0].at == 6.5
    assert updates[-1] == 100


def test_faster_whisper_cancel_is_reported(monkeypatch, tmp_path):
    import sys
    from types import ModuleType, SimpleNamespace
    folder = tmp_path / "whisper"
    folder.mkdir()
    class FakeWhisper:
        def __init__(self, *args, **kwargs):
            pass
        def transcribe(self, *_args, **_kwargs):
            return iter([SimpleNamespace(start=5, end=6, text="Krass!")]), None
    mod = ModuleType("faster_whisper")
    mod.WhisperModel = FakeWhisper
    monkeypatch.setitem(sys.modules, "faster_whisper", mod)
    video = VideoInfo("capture.mkv", 40.0, 1920, 1080, 60.0, True)
    with pytest.raises(CancelledError):
        transcribe_reactions(video, str(folder), cancelled=lambda: True)
