"""M15a: enumerate actual container audio streams, then explicitly extract one.

No role inference or AI separation. Decoded PCM is synchronized to container
time zero (same source seek origin as the editor), with leading/trailing
padding, and never replaces the source. All generated files are local.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
import os
import shutil
import subprocess
import tempfile
import time

from .media import tool_path, CancelledError, _stop_process

ROLES=("unspecified","mix","microphone","game","music","other")


@dataclass(frozen=True)
class AudioStream:
    index:int  # absolute FFprobe stream index, not audio ordinal
    codec:str
    sample_rate:int
    channels:int
    layout:str
    language:str
    title:str
    start_time:float | None
    duration:float | None
    default:bool


@dataclass(frozen=True)
class AudioInventory:
    source:str
    duration:float
    start_time:float | None
    size:int
    mtime_ns:int
    streams:tuple[AudioStream,...]


def _number(value):
    try:
        v=float(value)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None


def inventory(path):
    source=Path(path).resolve(strict=True)
    if not source.is_file():raise ValueError("Audioquelle ist keine Datei")
    stat=source.stat()
    proc=subprocess.run([tool_path("ffprobe"),"-v","error","-select_streams","a",
        "-show_entries","format=duration,start_time:stream=index,codec_name,sample_rate,channels,channel_layout,start_time,duration:stream_tags=language,title:stream_disposition=default",
        "-of","json",str(source)],capture_output=True,check=True,text=True,timeout=40)
    doc=json.loads(proc.stdout)
    fmt=doc.get("format",{})
    duration=_number(fmt.get("duration"))
    if duration is None or not 0<duration<=86400:
        raise ValueError("Ungültige Aufnahmedauer (maximal 24 h)")
    streams=[]
    for s in doc.get("streams",[]):
        tags=s.get("tags",{})
        streams.append(AudioStream(int(s["index"]),str(s.get("codec_name") or "unknown"),
            int(s.get("sample_rate") or 0),int(s.get("channels") or 0),
            str(s.get("channel_layout") or ""),str(tags.get("language") or ""),
            str(tags.get("title") or ""),_number(s.get("start_time")),
            _number(s.get("duration")),bool(s.get("disposition",{}).get("default",0))))
    if len(streams)>128 or len({s.index for s in streams})!=len(streams):
        raise ValueError("Ungültige Anzahl oder Index der Audiospuren")
    return AudioInventory(str(source),duration,_number(fmt.get("start_time")),
                          stat.st_size,stat.st_mtime_ns,tuple(streams))


def extract_audio_stream(snapshot,index,folder,*,role="unspecified",cancelled=None):
    """Create a unique bundle with PCM WAV and explicit source metadata.

    Uses original channel count and sample rate. FFmpeg timestamp compensation
    may insert/drop samples to preserve the container timeline; this is not
    packet-bit-identical demuxing. No source role is asserted by the program.
    """
    if role not in ROLES:raise ValueError("Unbekannte Audio-Rolle")
    def check():
        if cancelled and cancelled():raise CancelledError("Audioextraktion abgebrochen")
    check()
    current=inventory(snapshot.source)
    if current!=snapshot:raise ValueError("Audioquelle wurde seit Inventarisierung verändert")
    stream=next((s for s in current.streams if s.index==index),None)
    if stream is None:raise ValueError("Audiospur nicht gefunden")
    if not 8000<=stream.sample_rate<=192000 or not 1<=stream.channels<=8:
        raise ValueError("Nicht unterstützte Sample-Rate oder Kanalzahl")
    count=round(current.duration*stream.sample_rate)
    output=Path(folder).resolve()
    output.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(output).free < count*stream.channels*4+64*1024*1024:
        raise OSError("Nicht genügend Speicherplatz für PCM-Audiospur")
    bundle=Path(tempfile.mkdtemp(prefix=f"audio-stream-{index}-",dir=output))
    stage=bundle/"audio.partial.wav";target=bundle/"audio.wav"
    try:
        cmd=[tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error","-n",
             "-copyts","-start_at_zero","-i",current.source,"-map",f"0:{index}","-vn","-sn","-dn",
             "-af",f"aresample=async=1:first_pts=0,apad,atrim=end_sample={count}",
             "-ar",str(stream.sample_rate),"-ac",str(stream.channels),
             "-c:a","pcm_f32le","-rf64","auto",str(stage)]
        with tempfile.TemporaryFile() as errors:
            proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors)
            deadline=time.monotonic()+max(120,current.duration*2+60)
            try:
                while proc.poll() is None:
                    check()
                    if time.monotonic()>deadline:raise RuntimeError("Audioextraktion: Zeitlimit")
                    time.sleep(.1)
                if proc.returncode:
                    errors.seek(max(0,errors.seek(0,os.SEEK_END)-2000))
                    raise RuntimeError("FFmpeg: "+errors.read().decode("utf-8","replace"))
            finally:_stop_process(proc)
        check()
        actual=inventory(stage)
        if (len(actual.streams)!=1 or actual.streams[0].sample_rate!=stream.sample_rate
                or actual.streams[0].channels!=stream.channels
                or abs(actual.duration-count/stream.sample_rate)>.002):
            raise ValueError("Extrahierte Audiospur hat unerwartete Zeitbasis oder Kanäle")
        if inventory(snapshot.source)!=snapshot:
            raise ValueError("Originalaufnahme während Extraktion verändert")
        manifest={"schema_version":1,"kind":"decoded_container_stream",
            "role_user_selected":role,"source":asdict(snapshot),"selected_stream":asdict(stream),
            "output":{"file":"audio.wav","sample_format":"float32","samples_per_channel":count,
                      "timeline_origin":"container_start","duration":count/stream.sample_rate,
                      "timestamp_compensation":True}}
        (bundle/"provenance.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,
             allow_nan=False),encoding="utf-8")
        check()
        stage.rename(target)
        return target
    except BaseException:
        shutil.rmtree(bundle,ignore_errors=True)
        raise
