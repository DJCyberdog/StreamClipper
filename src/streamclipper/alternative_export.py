"""Alternate short-format export through existing immutable render contract."""
from pathlib import Path
import tempfile
from .media import tool_path,probe_video,_publish_without_overwrite,CancelledError
from .render_contract import render_request
from .montage import run_part

def export_alternative(request,destination,*,progress=None,cancelled=None,notice=None):
    request.validate()
    dest=Path(destination).resolve();suffix=dest.suffix.lower()
    if suffix not in (".gif",".webm"):raise ValueError("GIF oder WebM erforderlich")
    if not 0<request.duration<=(15 if suffix==".gif" else 120):raise ValueError("GIF maximal 15s; WebM maximal 120s")
    if dest==Path(request.video.path).resolve():raise ValueError("Original geschützt")
    with tempfile.TemporaryDirectory(prefix=".sc-alternative-",dir=dest.parent) as temp:
        work=Path(temp)
        source=render_request(request,work/"source.mp4",cancelled=cancelled,encoder_notice=notice,
                              progress=(lambda n:progress(round(n*.75))) if progress else None)
        result=work/("result"+suffix)
        common=[tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error","-n","-i",str(source)]
        if suffix==".gif":
            graph="[0:v]fps=12,scale=480:-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
            cmd=common+["-filter_complex_threads","1","-filter_complex",graph,"-an","-loop","0",str(result)]
        else:cmd=common+["-c:v","libvpx-vp9","-crf","32","-b:v","0","-deadline","good","-cpu-used","4","-c:a","libopus","-b:a","96k",str(result)]
        if notice:notice("Alternative Ausgabe · "+suffix[1:].upper())
        run_part(cmd,work,cancelled)
        actual=probe_video(result)
        if abs(actual.duration-request.duration)>.55 or actual.width<2 or actual.height<2:
            raise ValueError("Alternative Ausgabe: ungültige Zeitbasis")
        if suffix==".gif" and actual.has_audio:raise ValueError("GIF darf keinen Ton enthalten")
        if suffix==".webm" and probe_video(source).has_audio!=actual.has_audio:raise ValueError("WebM-Tonspur fehlt")
        if cancelled and cancelled():raise CancelledError("Export abgebrochen")
        published=_publish_without_overwrite(result,dest)
        if progress:progress(100)
        return published
