"""Deterministic transcription and safe export tests (no model download)."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from streamclipper.models import AnalysisResult, Candidate, TranscriptSegment, VideoInfo
from streamclipper.semantic import transcribe_video, transcript_cues
from streamclipper.transcript import render_transcript, save_transcript


def test_srt_vtt_txt_unicode_and_timestamp_rounding():
    spans = [TranscriptSegment(61.2349, 62.6, "  Oh mein Gott!  "),
             TranscriptSegment(3600, 3601.5, "Grüße aus Köln 🎮")]
    srt = render_transcript(spans, "srt")
    assert "1\n00:01:01,235 --> 00:01:02,600\nOh mein Gott!\n" in srt
    assert "2\n01:00:00,000 --> 01:00:01,500\nGrüße aus Köln 🎮" in srt
    vtt = render_transcript(spans, "vtt")
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:01:01.235 --> 00:01:02.600" in vtt
    txt = render_transcript(spans, "txt")
    assert txt == "[00:01:01.235] Oh mein Gott!\n[01:00:00.000] Grüße aus Köln 🎮\n"


def test_skip_blank_sort_segments_and_validate():
    spans = [TranscriptSegment(4.5, 6, "später"),
             TranscriptSegment(1, 2, "früher"),
             TranscriptSegment(7, 8, " \t ")]
    assert render_transcript(spans, "srt").index("früher") < render_transcript(spans, "srt").index("später")
    assert render_transcript(spans, "srt").count(" --> ") == 2
    with pytest.raises(ValueError):
        render_transcript([TranscriptSegment(2, 1, "Fehler")], "srt")
    with pytest.raises(ValueError):
        render_transcript(spans, "csv")


def test_atomic_exclusive_transcript_destination(tmp_path):
    target = tmp_path / "Clip Ö.srt"
    segments = [TranscriptSegment(0, 2.5, "Hallo, Welt")]
    assert save_transcript(segments, target) == target
    assert "Hallo, Welt" in target.read_text(encoding="utf8")
    target_bytes = target.read_bytes()
    with pytest.raises(FileExistsError):
        save_transcript([TranscriptSegment(0, 2, "NEU")], target)
    assert target.read_bytes() == target_bytes


def test_analysis_result_serializes_entire_transcript(tmp_path):
    video = VideoInfo("hello.mkv", 30, 1920, 1080, 60, True)
    result = AnalysisResult(video, [Candidate(0, 25, 70, "Sprechhinweis", 4)],
                            method="multimodal-evidence-v1",
                            transcript=[TranscriptSegment(3.25, 4.5, "Hallo Welt")])
    path = tmp_path / "report.json"
    result.save_json(path)
    saved = json.loads(path.read_text(encoding="utf8"))
    assert saved["transcript"] == [{"start": 3.25, "end": 4.5, "text": "Hallo Welt"}]


def test_whisper_video_transcribes_once_and_cues_reuse_segments(monkeypatch, tmp_path):
    path = tmp_path / "whisper"
    path.mkdir()
    recorded = {"model": 0, "transcribe": 0}
    class FakeWhisper:
        def __init__(self, *args, **kwargs):
            recorded["model"] += 1
            assert kwargs["local_files_only"] is True
        def transcribe(self, *args, **kwargs):
            recorded["transcribe"] += 1
            return iter([SimpleNamespace(start=1.5, end=3, text="   Hallo ihr Lieben "),
                         SimpleNamespace(start=5, end=7, text="  Wow, Alter!  ")]), None
    mod = ModuleType("faster_whisper")
    mod.WhisperModel = FakeWhisper
    monkeypatch.setitem(sys.modules, "faster_whisper", mod)
    vid = VideoInfo("aufnahme.mkv", 10, 1920, 1080, 60, True)
    spans = transcribe_video(vid, str(path))
    assert spans == [TranscriptSegment(1.5, 3, "Hallo ihr Lieben",review_origin="asr"),
                     TranscriptSegment(5, 7, "Wow, Alter!",review_origin="asr")]
    assert len(transcript_cues((s.start, s.end, s.text) for s in spans)) == 1
    assert recorded == {"model": 1, "transcribe": 1}


def test_cli_transcribe_writes_both_formats_without_retranscribing(monkeypatch, tmp_path):
    from streamclipper import cli
    source = tmp_path / "Aufnahme.mkv"
    source.touch()
    vid = VideoInfo(str(source), 42, 1920, 1080, 30, True)
    calls = []
    monkeypatch.setattr(cli, "probe_video", lambda path: vid)
    def fake_transcribe(*args, **kwargs):
        calls.append(args)
        return [TranscriptSegment(1, 2, "Wirklich gut!")]
    monkeypatch.setattr(cli, "transcribe_video", fake_transcribe)
    cli.main(["transcribe", str(source), "--speech-model", str(tmp_path / "models")])
    assert len(calls) == 1
    assert (tmp_path / "Aufnahme.transkript.srt").is_file()
    assert (tmp_path / "Aufnahme.transkript.txt").is_file()
    assert "Wirklich gut" in (tmp_path / "Aufnahme.transkript.txt").read_text(encoding="utf8")


def test_audio_only_reports_no_transcript(monkeypatch):
    from streamclipper import analyze as analyzer
    video = VideoInfo("sample.mp4", 30, 1920, 1080, 30, True)
    monkeypatch.setattr(analyzer, "probe_video", lambda _: video)
    monkeypatch.setattr(analyzer, "audio_levels", lambda *_a, **_kw: [-45] * 30)
    result = analyzer.analyze("sample.mp4")
    assert result.transcript == []
