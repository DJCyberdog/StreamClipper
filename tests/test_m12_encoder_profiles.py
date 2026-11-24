"""M12c encoder profiles: real capability probing, explicit/auto contracts."""
from dataclasses import replace
import subprocess

import pytest

import streamclipper.encoders as enc
from streamclipper.encoders import (
    EncoderPlan, ENCODERS, encoder_options, probe_nvenc, resolve_encoder)
from streamclipper.media import build_export_command
from streamclipper.models import VideoInfo
from streamclipper.render_contract import RenderRequest


def video():
    return VideoInfo("/tmp/not-opened-source.mp4", 3600, 1920, 1080, 60, True)


@pytest.mark.parametrize("profile,expected", [
    ("cpu_h264", "libx264"), ("nvenc_h264", "h264_nvenc"),
    ("cpu_hevc", "libx265"), ("nvenc_hevc", "hevc_nvenc"),
])
def test_encoder_command_options_do_not_change_filtergraph(profile, expected):
    flags = encoder_options(profile)
    assert flags[flags.index("-c:v")+1] == expected
    assert flags[flags.index("-pix_fmt")+1] == "yuv420p"
    if profile.endswith("hevc"):
        assert flags[flags.index("-tag:v")+1] == "hvc1"
    a = build_export_command(
        video(), 10, 12, "/tmp/a.mp4", mode="crop", width=320,
        height=180, encoder=profile)
    b = build_export_command(
        video(), 10, 12, "/tmp/b.mp4", mode="crop", width=320,
        height=180, encoder="cpu_h264")
    assert a[a.index("-filter_complex")+1] == b[b.index("-filter_complex")+1]
    assert a[a.index("-c:v")+1] == expected


def test_unknown_encoder_is_rejected_in_command_and_render_contract():
    request = RenderRequest(video(), 0, 10, "crop")
    assert request.encoder == "cpu_h264"  # legacy render jobs stay CPU
    assert request.preview_excerpt(2).encoder == "cpu_h264"
    for choice in ("-f null", "auto_av1", "", "h264_nvenc", "cpu-h264", None):
        with pytest.raises(ValueError):
            replace(request, encoder=choice).validate()
    with pytest.raises(ValueError):
        encoder_options("auto_h264")  # resolve before building ffmpeg argv


def test_cpu_mode_never_attempts_gpu_probe(monkeypatch):
    def unexpected(*args):
        raise AssertionError("CPU-only must not probe NVIDIA")
    monkeypatch.setattr(enc, "probe_nvenc", unexpected)
    assert resolve_encoder("cpu_h264", "ffmpeg") == EncoderPlan(
        "cpu_h264", "cpu_h264")
    assert resolve_encoder("cpu_hevc", "ffmpeg") == EncoderPlan(
        "cpu_hevc", "cpu_hevc")


@pytest.mark.parametrize("kind", ["h264", "hevc"])
def test_auto_uses_gpu_only_after_real_probe_and_cpu_fallback(monkeypatch, kind):
    calls = []
    monkeypatch.setattr(
        enc, "probe_nvenc",
        lambda ffmpeg, codec: calls.append((ffmpeg, codec)) or True)
    gpu = resolve_encoder("auto_"+kind, "ffmpeg.exe")
    assert gpu == EncoderPlan(
        "auto_"+kind, "nvenc_"+kind, "cpu_"+kind, False)
    assert calls == [("ffmpeg.exe", kind+"_nvenc")]
    monkeypatch.setattr(enc, "probe_nvenc", lambda *a: False)
    cpu = resolve_encoder("auto_"+kind, "ffmpeg.exe")
    assert cpu == EncoderPlan("auto_"+kind, "cpu_"+kind, None, True)
    with pytest.raises(ValueError, match="NVIDIA NVENC"):
        resolve_encoder("nvenc_"+kind, "ffmpeg.exe")


def test_nvenc_probe_runs_two_real_frames_without_user_media(monkeypatch):
    calls = []
    def run(args, **kw):
        calls.append((args, kw))
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(enc.subprocess, "run", run)
    assert probe_nvenc("custom-ffmpeg", "h264_nvenc")
    command, opts = calls[0]
    assert command[0] == "custom-ffmpeg"
    assert command[command.index("-c:v")+1] == "h264_nvenc"
    assert command[command.index("-frames:v")+1] == "2"
    assert "lavfi" in command and "null" in command
    assert "-i" in command
    assert any(str(arg).startswith("color=c=black:") for arg in command)
    assert opts["timeout"] == 15
    assert opts["stderr"] == subprocess.PIPE
    assert opts["check"] is False


def test_nvenc_probe_rejects_missing_gpu_and_hanging_encoder(monkeypatch):
    monkeypatch.setattr(enc.subprocess, "run",
                        lambda args, **kw: subprocess.CompletedProcess(args, 1))
    assert not probe_nvenc("ffmpeg", "hevc_nvenc")
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired(a, kw.get("timeout", 15))
    monkeypatch.setattr(enc.subprocess, "run", timeout)
    assert not probe_nvenc("ffmpeg", "h264_nvenc")
    def missing(*a, **kw):
        raise FileNotFoundError("ffmpeg not found")
    monkeypatch.setattr(enc.subprocess, "run", missing)
    assert not probe_nvenc("ffmpeg", "h264_nvenc")
    with pytest.raises(ValueError):
        probe_nvenc("ffmpeg", "libx264")
