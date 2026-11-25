"""M15a real multistream fixtures: original mix vs explicit microphone."""
from array import array
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import sys
from dataclasses import replace
import pytest

from streamclipper.audio_sources import inventory,extract_audio_stream
from streamclipper.media import CancelledError

pytestmark=pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                              reason="FFmpeg/FFprobe unavailable")


def run(*args):
    return subprocess.run(["ffmpeg","-hide_banner","-nostdin","-loglevel","error",*map(str,args)],
                          check=True,capture_output=True,timeout=90).stdout


@pytest.fixture
def source(tmp_path):
    path=tmp_path/"multi.mkv"
    run("-f","lavfi","-i","color=black:s=160x128:r=20:d=3",
        "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=3",
        "-itsoffset",.75,"-f","lavfi","-i","sine=frequency=880:sample_rate=48000:duration=1",
        "-map","0:v:0","-map","1:a:0","-map","2:a:0","-c:v","libx264","-pix_fmt","yuv420p",
        "-c:a","pcm_s16le","-metadata:s:a:0","title=Mix","-metadata:s:a:1","title=Mic",
        "-metadata:s:a:1","language=deu",path)
    return path


def rms_and_frequency(path,at,frequency):
    data=run("-ss",at,"-i",path,"-t",.2,"-map","0:a:0","-ac",1,"-ar",8000,
             "-c:a","pcm_f32le","-f","f32le","pipe:1")
    v=array("f");v.frombytes(data)
    if sys.byteorder!="little":v.byteswap()
    assert len(v)>=1500
    rms=math.sqrt(sum(x*x for x in v)/len(v))
    a=sum(x*math.sin(2*math.pi*frequency*i/8000) for i,x in enumerate(v))
    b=sum(x*math.cos(2*math.pi*frequency*i/8000) for i,x in enumerate(v))
    return rms,2*math.hypot(a,b)/len(v)


def test_inventory_and_aligned_extraction(source,tmp_path):
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    snap=inventory(source)
    assert [s.index for s in snap.streams]==[1,2]
    assert all(s.sample_rate==48000 and s.channels==1 for s in snap.streams)
    assert abs(snap.duration-3)<.1
    assert abs(snap.streams[1].start_time-.75)<.04
    out=extract_audio_stream(snap,2,tmp_path/"exports",role="microphone")
    manifest=json.loads((out.parent/"provenance.json").read_text(encoding="utf-8"))
    assert manifest["role_user_selected"]=="microphone"
    assert manifest["kind"]=="decoded_container_stream"
    assert manifest["selected_stream"]["index"]==2
    assert abs(inventory(out).duration-snap.duration)<.002
    assert rms_and_frequency(out,.1,880)[0]<.001
    assert rms_and_frequency(out,1.,880)[1]>.08
    assert rms_and_frequency(out,1.,440)[1]<.005
    assert rms_and_frequency(out,2.2,880)[0]<.001
    mix=extract_audio_stream(snap,1,tmp_path/"exports",role="mix")
    assert mix!=out and rms_and_frequency(mix,1.,440)[1]>.08
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    assert not list((tmp_path/"exports").rglob("*.partial.wav"))


def test_reject_unknown_index_changed_source_and_cancel(source,tmp_path):
    snap=inventory(source);folder=tmp_path/"exports"
    with pytest.raises(ValueError,match="nicht gefunden"):
        extract_audio_stream(snap,0,folder)
    with pytest.raises(ValueError,match="verändert"):
        extract_audio_stream(replace(snap,size=snap.size+1),1,folder)
    with pytest.raises(CancelledError):
        extract_audio_stream(snap,1,folder,cancelled=lambda:True)
    assert not folder.exists()


def test_one_stream_is_not_separation(tmp_path):
    path=tmp_path/"single.wav"
    run("-f","lavfi","-i","sine=frequency=440:sample_rate=44100:duration=1","-c:a","pcm_s16le",path)
    snap=inventory(path)
    assert len(snap.streams)==1
    wav=extract_audio_stream(snap,snap.streams[0].index,tmp_path/"out")
    manifest=json.loads((wav.parent/"provenance.json").read_text(encoding="utf-8"))
    assert manifest["role_user_selected"]=="unspecified"
    assert manifest["kind"]=="decoded_container_stream"
    assert inventory(wav).streams[0].sample_rate==44100
