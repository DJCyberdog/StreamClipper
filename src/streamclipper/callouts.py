"""M14 editable callouts, rasterized only for preview/export."""
from dataclasses import dataclass
import re
import math

COLOR=re.compile(r"#[0-9a-fA-F]{6}\Z")
KINDS=("text","bubble","arrow","rectangle","ellipse")


@dataclass(frozen=True)
class Callout:
    kind: str = "text"
    text: str = ""
    foreground: str = "#FFFFFF"
    background: str = "#182036"
    accent: str = "#F5CF52"
    direction: str = "right"
    font_scale: float = 1.
    filled: bool = True

    def validate(self):
        if self.kind not in KINDS or self.direction not in ("left","right","up","down"):
            raise ValueError("Ungültiger Callout-Typ")
        if not isinstance(self.text,str) or len(self.text)>240 or any(ord(c)<32 and c!="\n" for c in self.text):
            raise ValueError("Callout-Text: maximal 240 Zeichen")
        if self.kind in ("text","bubble") and not self.text.strip():
            raise ValueError("Callout benötigt Text")
        if any(not isinstance(v,str) or not COLOR.fullmatch(v) for v in (self.foreground,self.background,self.accent)):
            raise ValueError("Farben benötigen #RRGGBB")
        if type(self.filled) is not bool or type(self.font_scale) not in (int,float) or not math.isfinite(self.font_scale) or not .5<=self.font_scale<=2:
            raise ValueError("Ungültige Callout-Gestaltung")
        return self


def callout_from_dict(value):
    return None if value is None else Callout(**value).validate()


def rasterize(spec,width,height):
    """RGBA overlay in its output box. Font from installed Pillow, no remote assets."""
    spec.validate()
    if not (2<=width<=4096 and 2<=height<=4096 and width*height<=12_000_000):
        raise ValueError("Callout-Auflösung außerhalb der Rendergrenze")
    from PIL import Image, ImageDraw, ImageFont
    image=Image.new("RGBA",(width,height))
    draw=ImageDraw.Draw(image)
    stroke=max(1,round(min(width,height)*.035))
    pad=max(stroke,round(min(width,height)*.06))
    box=(pad,pad,max(pad,width-1-pad),max(pad,height-1-pad))
    fg,bg,accent=spec.foreground,spec.background,spec.accent
    if spec.kind in ("rectangle","ellipse"):
        shape=draw.rectangle if spec.kind=="rectangle" else draw.ellipse
        shape(box,outline=accent,width=stroke,fill=bg if spec.filled else None)
    elif spec.kind=="arrow":
        # Normalized polygon, rotated in normalized space so all directions fit.
        pts=[(.08,.4),(.58,.4),(.58,.12),(.92,.5),(.58,.88),(.58,.6),(.08,.6)]
        transform={"right":lambda x,y:(x,y),"left":lambda x,y:(1-x,y),
                   "up":lambda x,y:(y,1-x),"down":lambda x,y:(1-y,x)}[spec.direction]
        draw.polygon([(round(x*(width-1)),round(y*(height-1))) for x,y in
                      (transform(*p) for p in pts)],fill=accent)
    else:
        bottom=round(height*.78) if spec.kind=="bubble" else box[3]
        text_box=(box[0],box[1],box[2],max(box[1],bottom))
        if spec.filled or spec.kind=="bubble":
            draw.rounded_rectangle(text_box,radius=pad,fill=bg,outline=accent,width=stroke)
        if spec.kind=="bubble":
            draw.polygon([(width*.19,bottom-stroke),(width*.35,bottom-stroke),(width*.19,height*.95)],fill=bg)
        # Fit all text rather than truncate or silently clip. Wrap by glyph width,
        # including long unbroken tokens. Use only bundled Pillow default font.
        available=max(1,text_box[2]-text_box[0]-2*pad)
        available_h=max(1,text_box[3]-text_box[1]-2*pad)
        for size in range(max(6,min(256,round(min(height*.46,width*.24)*spec.font_scale))),5,-1):
            font=ImageFont.load_default(size=size)
            lines=[]
            for paragraph in spec.text.splitlines():
                line=""
                for ch in paragraph:
                    if line and draw.textlength(line+ch,font=font)>available:
                        lines.append(line.strip());line=ch
                    else:line+=ch
                lines.append(line.strip())
            text="\n".join(lines)
            bounds=draw.multiline_textbbox((0,0),text,font=font,spacing=2,align="center")
            tw,th=bounds[2]-bounds[0],bounds[3]-bounds[1]
            if tw<=available and th<=available_h:
                draw.multiline_text(((text_box[0]+text_box[2]-tw)/2-bounds[0],
                    (text_box[1]+text_box[3]-th)/2-bounds[1]),text,font=font,fill=fg,spacing=2,align="center")
                break
        else:raise ValueError("Callout-Text passt nicht in die Bildregion; Box vergrößern oder Text kürzen.")
    return image
