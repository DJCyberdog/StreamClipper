"""No remote models: deterministic tests for burned captions and auto-reframing."""
import shutil
import subprocess

import pytest

from streamclipper.captioning import clip_captions, render_ass
from streamclipper.media import (build_export_command, export_clip, probe_video)
from streamclipper.models import TranscriptSegment
from streamclipper.reframe import (FocusPoint, camera_expression, motion_focus,
                                   smooth_focus, smart_crop_filter)


def test_clip_captions_offset_and_unicode():
    segments = [TranscriptSegment(9, 11, "before"),
                TranscriptSegment(12.2, 15.2, "Äh what the heck, das ist doch verrückt!"),
                TranscriptSegment(20, 23, "after")]
    clips = clip_captions(segments, 12, 18)
    assert len(clips) == 1
    assert clips[0][0] == pytest.approx(.2)
    assert clips[0][1] == pytest.approx(3.2)
    assert "verrückt" in clips[0][2]


def test_caption_output_sanitizes_ass_injection_and_wraps_text():
    spans = [TranscriptSegment(10, 15, "Hallo {\\pos(999,999)} wie geht es euch allen da draußen heute denn so?"),
             TranscriptSegment(15, 16, "Na schön")]
    result = render_ass(spans, 10, 16, width=1080, height=1920)
    assert "PlayResX: 1080" in result
    assert "PlayResY: 1920" in result
    assert "Dialogue: 0,0:00:00.00," in result
    assert "{\\pos(" not in result
    assert "｛＼pos(" in result
    assert "\\N" in result or result.count("Dialogue:") > 2
    assert result.count("Dialogue:") >= 2


def test_caption_splits_long_segments_without_dropping_words():
    transcript = [TranscriptSegment(10, 14, "one two three four five six seven eight nine ten eleven")]
    sections = clip_captions(transcript, 10, 14)
    assert len(sections) == 2
    assert sections[0][0] == 0
    assert sections[-1][1] == 4
    assert " ".join(s[2] for s in sections) == transcript[0].text


def test_motion_focus_localized_activity_and_uniform_light_change():
    w, h = 160, 90
    previous = bytes(w * h)
    current = bytearray(w * h)
    for y in range(23, 49):
        for x in range(122, 151):
            current[y*w+x] = 220
    focus = motion_focus(previous, bytes(current))
    assert focus is not None
    assert focus[0] > .7
    assert .25 < focus[1] < .7
    assert motion_focus(previous, bytes([100])*(w*h)) is None


def test_smooth_focus_rate_limited_and_expression_has_timeline():
    samples = [(i * .5, (.8, .5)) for i in range(1, 31)]
    points = smooth_focus(samples)
    assert points[0] == FocusPoint(0, .5, .5)
    assert all(.5 <= point.x <= .87 for point in points)
    assert all(a.at < b.at for a,b in zip(points, points[1:]))
    expr = camera_expression(points, "x")
    assert "lt(t," in expr and "if(" in expr
    assert "crop=" in smart_crop_filter(640, 360, points, zoom=1.18)


def test_smart_command_has_crop_not_fixed_center_or_shell(tmp_path):
    from streamclipper.models import VideoInfo
    video = VideoInfo("capture.mp4", 50, 1920, 1080, 30, True)
    cmd = build_export_command(video, 3, 9, tmp_path / "output.mp4", "smart16",
                               motion_points=[FocusPoint(0,.5,.5), FocusPoint(2,.8,.4)],
                               burned_captions=True)
    filtergraph = cmd[cmd.index("-filter_complex")+1]
    assert "ass=filename=captions.ass" in filtergraph
    assert "if(lt(t," in filtergraph
    assert "crop=1920:1080" in filtergraph
    assert "-filter_complex" in cmd


@pytest.fixture
def short_video(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and FFprobe required")
    source = tmp_path / "Spiel Übung Ö.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=s=320x180:r=12:d=5",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                    "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(source)],
                   check=True, capture_output=True, timeout=45)
    return source, probe_video(source)


@pytest.mark.parametrize("mode,width,height", [
    ("smart16", 640, 360),
    ("smart9", 360, 640),
])
def test_real_ffmpeg_burns_subtitles_and_moves_clip(mode, width, height, short_video, tmp_path):
    source, info = short_video
    original = source.read_bytes()
    transcript = [TranscriptSegment(.4, 1.8, "Hallo zusammen – oh mein Gott!"),
                  TranscriptSegment(2.5, 4.2, "Ich sehe dich jetzt!")]
    dest = tmp_path / ("Clip ö " + mode + ".mp4")
    exported = export_clip(info, 0, 4, dest, mode=mode, width=width, height=height,
                           transcript=transcript, burn_subtitles=True)
    assert exported.is_file()
    actual = probe_video(exported)
    assert (actual.width, actual.height) == (width, height)
    assert source.read_bytes() == original
    assert not list(tmp_path.rglob("*.partial.mp4"))
    assert not list(tmp_path.rglob("captions.ass"))


def test_burn_requires_real_transcript(short_video, tmp_path):
    _, info = short_video
    dest = tmp_path / "no.mp4"
    with pytest.raises(ValueError, match="Whisper-Transkript"):
        export_clip(info, 0, 2, dest, mode="smart16", burn_subtitles=True)
    assert not dest.exists()
