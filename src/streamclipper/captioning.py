"""Safe, offline ASS captions for FFmpeg burn-in into the rendered MP4.

Only the selected clip's transcript is used. Plain spoken text cannot inject
libass override commands. The intermediary ASS file is ephemeral and internal.
"""
from __future__ import annotations

import math
import re
from typing import Sequence

from .models import TranscriptSegment
from .caption_style import CaptionStyle, ass_color


def _ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"


def _plain_ass_text(text: str, line_length: int) -> str:
    """Escape user transcript; libass `{...}` marks are never allowed."""
    words = re.sub(r"\s+", " ", text).strip().replace("{", "｛").replace("}", "｝")
    words = words.replace("\\", "＼")  # block libass \N, \h and other markup
    lines: list[str] = []
    line = ""
    for word in words.split():
        if line and len(line) + len(word) + 1 > line_length:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return r"\N".join(lines[:2])


def clip_captions(segments: Sequence[TranscriptSegment], start: float, end: float,
                  *, max_words: int = 8, offset_seconds: float = 0.0) -> list[tuple[float, float, str]]:
    """Re-time Whisper segments to this export and split lengthy utterances.

    Segment-level Whisper timestamps do not align individual words precisely.
    These are proportional estimates, never claimed to be word-level alignment.
    """
    if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end:
        raise ValueError("Ungültiges Clip-Zeitfenster")
    if not math.isfinite(offset_seconds) or abs(offset_seconds) > 5:
        raise ValueError("Untertitelversatz muss zwischen -5 und +5 Sekunden liegen")
    if max_words <= 0:
        raise ValueError("max_words muss positiv sein")
    cues: list[tuple[float, float, str]] = []
    for segment in segments:
        if not all(math.isfinite(v) for v in (segment.start, segment.end)):
            continue
        if (segment.end + offset_seconds <= start or
                segment.start + offset_seconds >= end or
                segment.end <= segment.start):
            continue
        if segment.words:
            # Exact per-word speech timings: successive cues reveal each
            # word within its current group (max_words), not a guessed split.
            # Keep pauses blank, so words do not appear before they're spoken.
            for j, word in enumerate(segment.words):
                if word.end <= word.start or not word.text.strip():
                    continue
                group = j // max_words * max_words
                a = max(start, word.start + offset_seconds) - start
                b = min(end, word.end + offset_seconds) - start
                if b <= a + .005:
                    continue
                prefix = ' '.join(w.text for w in segment.words[group:j+1])
                cues.append((a, b, prefix))
            continue
        words = segment.text.strip().split()
        if not words:
            continue
        # Legacy segment-only timestamps: time-proportional ESTIMATES.
        for j in range(0, len(words), max_words):
            fraction_start = j / len(words)
            fraction_end = min(1., (j + max_words) / len(words))
            a = segment.start + (segment.end - segment.start) * fraction_start + offset_seconds
            b = segment.start + (segment.end - segment.start) * fraction_end + offset_seconds
            local_start = max(start, a) - start
            local_end = min(end, b) - start
            if local_end <= local_start + .06:
                continue
            cues.append((local_start, local_end, " ".join(words[j:j+max_words])))
    return sorted(cues, key=lambda item: (item[0], item[1]))


def render_ass(segments: Sequence[TranscriptSegment], start: float, end: float,
               *, width: int = 1920, height: int = 1080,
               offset_seconds: float = 0.0, safe_position: str = 'bottom',
               caption_style: CaptionStyle = CaptionStyle()) -> str:
    """Create a self-contained subtitle track meant to be burned by libass."""
    caption_style.validate()
    if caption_style.position != 'scene':
        safe_position = caption_style.position
    if safe_position not in ('bottom', 'top'):
        raise ValueError('Ungültige Untertitelposition')
    if width <= 0 or height <= 0:
        raise ValueError("Ungültige Exportauflösung")
    # Scale font with canvas width, while accounting for a narrow portrait view.
    font_size = round((53 if width >= height else 46)*caption_style.scale)
    side_margin = round(width * .07)
    bottom_margin = round(height * (.11 if width >= height else .17))
    alignment = 8 if safe_position == 'top' else 2
    style = (
        f"Style: Main,{caption_style.font},{font_size},{ass_color(caption_style.text_color)},"
        f"{ass_color(caption_style.accent_color)},{ass_color(caption_style.outline_color)},&H96000000,"
        f"-1,0,0,0,100,100,0,0,1,3,1,{alignment},{side_margin},{side_margin},{bottom_margin},1"
    )
    output = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}",
        f"PlayResY: {height}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        style, "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if caption_style.mode != 'legacy':
        output.extend(_styled_word_events(segments,start,end,offset_seconds,caption_style))
        return '\n'.join(output) + '\n'
    for a, b, text in clip_captions(
            segments, start, end, offset_seconds=offset_seconds, max_words=caption_style.group_words):
        safe = _plain_ass_text(text, 36 if width >= height else 22)
        if safe:
            output.append(
                f"Dialogue: 0,{_ass_timestamp(a)},{_ass_timestamp(b)},Main,,0,0,0,,{safe}"
            )
    return "\n".join(output) + "\n"


def subtitle_text_at_time(segments: Sequence[TranscriptSegment], position: float,
                          offset_seconds: float = 0.0,
                          max_words: int = 8) -> str | None:
    """Determine exactly which caption text is burned at a recording time."""
    if not math.isfinite(position) or not math.isfinite(offset_seconds):
        return None
    for segment in segments:
        if segment.start + offset_seconds > position or segment.end + offset_seconds <= position:
            continue
        # Render only the small active segment; avoid regenerating captions
        # for a whole six-hour recording on every player position update.
        for a, b, text in clip_captions([segment], segment.start, segment.end,
                                        max_words=max_words, offset_seconds=0):
            if a + segment.start + offset_seconds <= position < b + segment.start + offset_seconds:
                return text
    return None


def _styled_word_events(segments,start,end,offset,style):
    """Highlight current word; pop adds a short scale animation.
    Untimed legacy segments keep ordinary cues, not fictitious word timing.
    Only generated ASS tags are trusted; all user words are escaped first.
    """
    for seg in segments:
        if not seg.words:
            for a,b,text in clip_captions([seg],start,end,offset_seconds=offset,max_words=style.group_words):
                safe=_plain_ass_text(text,36)
                yield f"Dialogue: 0,{_ass_timestamp(a)},{_ass_timestamp(b)},Main,,0,0,0,,{safe}"
            continue
        for j,word in enumerate(seg.words):
            a=max(start,word.start+offset)-start
            b=min(end,word.end+offset)-start
            if b<=a+.005:continue
            first=j//style.group_words*style.group_words
            group=seg.words[first:first+style.group_words]
            pieces=[]
            for index,token in enumerate(group,first):
                safe=_plain_ass_text(token.text,200)
                if index==j:
                    color=ass_color(style.accent_color)[2:]
                    tags=r"{\1c&H"+color+"&"
                    if style.mode=="pop":
                        tags+=r"\fscx115\fscy115\t(0,120,\fscx100\fscy100)"
                    safe=tags+"}"+safe+r"{\r}"
                pieces.append(safe)
            yield f"Dialogue: 0,{_ass_timestamp(a)},{_ass_timestamp(b)},Main,,0,0,0,,{' '.join(pieces)}"
