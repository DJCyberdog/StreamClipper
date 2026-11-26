"""M18 offline and real local-media integration checks; no external downloads."""
import json,socket,subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from streamclipper.video_sources import parse_source
from streamclipper.video_import import sanitize_metadata,choose_formats
from streamclipper.network_gate import public_addresses,guarded_proxy
from streamclipper.media import CancelledError,probe_video,tool_path
from streamclipper.models import VideoInfo

@pytest.mark.parametrize("url,provider,ident",[
    ("https://youtu.be/abcdefghijk?list=bad","youtube","abcdefghijk"),
    ("https://www.youtube.com/shorts/abcdefghijk","youtube","abcdefghijk"),
    ("https://www.youtube.com/watch?v=abcdefghijk&list=foo","youtube","abcdefghijk"),
    ("https://twitch.tv/videos/123","twitch","123"),
    ("https://clips.twitch.tv/InterestingClip","twitch-clip","InterestingClip"),
    ("https://kick.com/a/videos/12345678-abcd-1234-abcd-123456789012","kick","12345678-abcd-1234-abcd-123456789012"),
    ("https://kick.com/a?clip=clip_abcdefghijk","kick-clip",None),
    ("https://vimeo.com/123","vimeo","123"),
    ("https://example.org/a.mp4","direct",None)])
def test_single_video_parser(url,provider,ident):
    s=parse_source(url);assert (s.provider,s.expected_id)==(provider,ident)
    assert "list=" not in s.url

@pytest.mark.parametrize("url",["http://example.org/a.mp4","file:///a.mp4","https://127.0.0.1/a.mp4",
    "https://[::1]/a.mp4","https://youtube.com/playlist?list=abc","https://kick.com/a",
    "https://user:pass@example.org/a.mp4","https://example.org:8443/a.mp4",
    "https://example.org/a.mp4?token=secret","https://youtube.com.evil.org/watch?v=abcdefghijk"])
def test_bad_import_urls(url):
    with pytest.raises(ValueError):parse_source(url)

@pytest.mark.parametrize("ip",["127.0.0.1","10.0.0.1","192.168.1.1","169.254.169.254","100.64.0.1","::1","::ffff:127.0.0.1","fc00::1","224.0.0.1"])
def test_dns_guard_blocks_nonpublic(ip):
    with pytest.raises(ValueError):public_addresses("example.org",resolver=lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,"",(ip,443))])

def test_dns_mixed_answers_block():
    rows=[(socket.AF_INET,socket.SOCK_STREAM,6,"",(ip,443)) for ip in ("8.8.8.8","127.0.0.1")]
    with pytest.raises(ValueError):public_addresses("example.org",resolver=lambda *a,**k:rows)

def test_real_connect_gate_blocks_loopback():
    with guarded_proxy(1024) as (_,gate):
        with socket.create_connection(gate.server_address,timeout=2) as conn:
            conn.sendall(b"CONNECT 127.0.0.1:443 HTTP/1.1\r\nHost: 127.0.0.1:443\r\n\r\n")
            assert b"403" in conn.recv(256)

def info():
    return {"id":"123","title":"Title","duration":2,"availability":"public","formats":[
        {"format_id":"low","height":720,"vcodec":"h264","acodec":"aac","ext":"mp4","protocol":"https","filesize":100},
        {"format_id":"hi","height":1080,"vcodec":"h264","acodec":"none","ext":"mp4","protocol":"https"},
        {"format_id":"audio","vcodec":"none","acodec":"aac","ext":"m4a","protocol":"https","language":"en"},
        {"format_id":"drm","vcodec":"h264","acodec":"aac","height":2160,"ext":"mp4","protocol":"https","has_drm":True}],
        "subtitles":{"en":[{"url":"https://secret"}]}}

def test_preflight_sanitizes_and_selects():
    s=parse_source("https://twitch.tv/videos/123");meta=sanitize_metadata(s,info())
    assert [f.id for f in choose_formats(meta)]==["hi","audio"]
    assert [f.id for f in choose_formats(meta,720)]==["low"]
    assert meta.subtitles==("en",) and "secret" not in repr(meta)
    for bad in ({"_type":"playlist","entries":[]},{"is_live":True},{"availability":"private"},{"id":"124"},{"has_drm":True},{"age_limit":18}):
        with pytest.raises(ValueError):sanitize_metadata(s,{**info(),**bad})

def test_import_requires_explicit_consent(monkeypatch):
    from streamclipper import video_import as vi
    monkeypatch.setattr(vi,"run_worker",lambda *a,**k:pytest.fail("Network not authorized"))
    with pytest.raises(ValueError):vi.preflight("https://twitch.tv/videos/123")

def test_real_media_publication_with_fake_downloader(tmp_path,monkeypatch):
    from streamclipper import video_import as vi
    src=parse_source("https://twitch.tv/videos/123")
    meta=sanitize_metadata(src,info())
    monkeypatch.setattr(vi,"preflight",lambda *a,**k:meta)
    monkeypatch.setattr(vi.shutil,"disk_usage",lambda p:SimpleNamespace(free=100*1024**3))
    # Simulate only the external provider. Actual FFmpeg and publication are real.
    def worker(source,args,**kw):
        assert "--no-overwrites" in args and "--continue" in args and "--break-match-filters" in args
        target=Path(kw["cwd"])/"video.mp4"
        subprocess.run([tool_path("ffmpeg"),"-v","error","-y","-f","lavfi","-i","testsrc2=s=96x54:r=30:d=2",
                        "-c:v","libx264","-pix_fmt","yuv420p",str(target)],check=True)
        kw["on_line"]('SC_PROGRESS:{"downloaded_bytes":500,"total_bytes":1000,"speed":100}')
        kw["on_line"]("SC_DONE:"+str(target))
    monkeypatch.setattr(vi,"run_worker",worker)
    previous=tmp_path/"twitch_123.mp4";previous.write_bytes(b"original")
    events=[]
    p=vi.download(meta,tmp_path,authorized=True,height=720,max_bytes=1024**2,progress=events.append)
    assert p!=previous and previous.read_bytes()==b"original"
    assert not probe_video(p).has_audio
    d=json.loads(p.with_name(p.name+".import.json").read_text())
    assert d["id"]=="123" and events[-1]["stage"]=="complete"

def test_cancel_preserves_part(tmp_path,monkeypatch):
    from streamclipper import video_import as vi
    meta=sanitize_metadata(parse_source("https://twitch.tv/videos/123"),info())
    monkeypatch.setattr(vi,"preflight",lambda *a,**k:meta)
    monkeypatch.setattr(vi.shutil,"disk_usage",lambda p:SimpleNamespace(free=100*1024**3))
    def worker(source,args,**kw):
        (Path(kw["cwd"])/"video.mp4.part").write_bytes(b"partial")
        raise CancelledError("cancelled")
    monkeypatch.setattr(vi,"run_worker",worker)
    with pytest.raises(CancelledError):vi.download(meta,tmp_path,authorized=True,max_bytes=1024**2)
    assert len(list(tmp_path.glob(".sc-import-*/video.mp4.part")))==1
    assert not list(tmp_path.glob("*.mp4"))

def test_channel_first_scan_and_dedup(tmp_path,monkeypatch):
    from streamclipper import channel_ingestion as ci
    c=ci.Channel("https://www.twitch.tv/demo/videos","twitch",str(tmp_path),15,1,1024**2,paused=False)
    found={"123":"https://www.twitch.tv/videos/123"}
    monkeypatch.setattr(ci,"discover",lambda *a,**k:dict(found))
    calls=[];states=[]
    monkeypatch.setattr(ci,"preflight",lambda url,**k:url)
    monkeypatch.setattr(ci,"download",lambda meta,*a,**k:calls.append(meta))
    c=ci.poll(c,persist=states.append,now=100)
    assert c.initialized and c.seen==("123",) and not calls
    found["124"]="https://www.twitch.tv/videos/124";found["125"]="https://www.twitch.tv/videos/125"
    c=ci.poll(c,persist=states.append,now=1000)
    assert len(calls)==1 and "124" in c.seen
    assert ci.poll(c,persist=states.append,now=1001)==c

def test_local_markers_spool_and_stable_watch(tmp_path):
    from streamclipper.local_integrations import post_command,take_commands,record_marker,markers,WatchFolder
    spool=tmp_path/"commands"
    post_command("marker",spool);assert take_commands(spool)==["marker"]
    assert take_commands(spool)==[]
    record_marker("obs",5,"obs-record",tmp_path/"markers")
    assert markers("obs","obs-record",tmp_path/"markers")==[5]
    watch=WatchFolder(tmp_path);f=tmp_path/"recording.mp4";f.write_bytes(b"x")
    assert watch.scan(0)==[];f.write_bytes(b"xx");assert watch.scan(10)==[]
    assert watch.scan(25)==[f] and watch.scan(50)==[]

def test_nle_and_subtitle_roundtrip(tmp_path):
    from streamclipper.nle_export import edl,fcpxml
    from streamclipper.subtitle_import import load_subtitles
    import xml.etree.ElementTree as ET
    video=VideoInfo(str(tmp_path/"A&B.mp4"),20,1920,1080,30,True)
    out=edl(video,[(10,12),(0,1)])
    assert "00:00:10:00 00:00:12:00 00:00:00:00 00:00:02:00" in out
    xml=ET.fromstring(fcpxml(video,[(10,12),(0,1)]))
    assert [x.get("start") for x in xml.findall(".//asset-clip")]==["10s","0s"]
    p=tmp_path/"test.vtt";p.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nHello\n",encoding="utf-8")
    rows=load_subtitles(p,20);assert rows[0].start==1 and rows[0].end==2.5 and not rows[0].words

def test_pkce_and_callback_state():
    from streamclipper.publish_prepare import pkce,callback_code,authorize_youtube,PublishAdapter,Token
    verifier,challenge=pkce();assert len(verifier)>=43 and len(challenge)==43
    assert callback_code("/callback?state=abc&code=def","abc")=="def"
    with pytest.raises(ValueError):callback_code("/callback?state=wrong&code=def","abc")
    with pytest.raises(ValueError):authorize_youtube("client","secret")
    assert "secret" not in repr(Token("secret"))
    with pytest.raises(NotImplementedError):PublishAdapter().publish()
