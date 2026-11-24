"""M14 persistent, validated caption branding. No Qt or model dependency."""
from dataclasses import dataclass, replace
import re
import math

_COLOR=re.compile(r"#[0-9a-fA-F]{6}\Z")
_FONT=re.compile(r"[\w .-]{1,80}\Z")


@dataclass(frozen=True)
class CaptionStyle:
    mode: str = "legacy"  # legacy, highlight, pop
    font: str = "Arial"
    scale: float = 1.0
    text_color: str = "#FFFFFF"
    accent_color: str = "#F5CF52"
    outline_color: str = "#000000"
    position: str = "scene"  # respect M13 safe zone by default
    group_words: int = 8

    def validate(self):
        if self.mode not in ("legacy","highlight","pop") or self.position not in ("scene","top","bottom"):
            raise ValueError("Ungültiger Untertitelstil")
        if not isinstance(self.font,str) or not _FONT.fullmatch(self.font):
            raise ValueError("Ungültiger Fontname")
        if type(self.scale) not in (float,int) or not math.isfinite(self.scale) or not .5<=self.scale<=2:
            raise ValueError("Ungültige Schriftgröße")
        if type(self.group_words) is not int or not 1<=self.group_words<=8:
            raise ValueError("Ungültige Wortgruppenlänge")
        if any(not isinstance(c,str) or not _COLOR.fullmatch(c)
               for c in (self.text_color,self.accent_color,self.outline_color)):
            raise ValueError("Farben benötigen #RRGGBB")
        return self


def caption_style_from_dict(value):
    if value is None:return CaptionStyle()
    if not isinstance(value,dict):raise ValueError("Ungültiger Untertitelstil")
    return CaptionStyle(**value).validate()


def ass_color(value):
    if not isinstance(value,str) or not _COLOR.fullmatch(value):
        raise ValueError("Ungültige Farbe")
    return "&H00"+value[5:7]+value[3:5]+value[1:3]


PRESETS={
    "Klassisch":CaptionStyle(),
    "Creator Highlight":CaptionStyle(mode="highlight",group_words=4),
    "Neon Pop":CaptionStyle(mode="pop",accent_color="#50E3C2",group_words=3),
}
