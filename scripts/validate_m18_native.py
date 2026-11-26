"""Explicit native M18 provider diagnostic. No embedded test media, no account access.
Manifest is local and each entry must attest permission for a single video.
Report excludes raw URLs, media titles and provider exception payloads.
"""
import argparse,hashlib,json,time
from pathlib import Path
from streamclipper.video_sources import parse_source
from streamclipper.video_import import preflight,download
from streamclipper.media import probe_video_local_container
from streamclipper.gaming_intelligence import atomic_json

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest");p.add_argument("directory");p.add_argument("report")
    p.add_argument("--commit",required=True)
    p.add_argument("--authorized",required=True,action="store_true")
    p.add_argument("--preflight-only",action="store_true")
    a=p.parse_args(argv)
    manifest=Path(a.manifest);dest=Path(a.directory).resolve(strict=True);report=Path(a.report)
    if manifest.stat().st_size>128*1024 or report.exists() or not dest.is_dir():
        raise ValueError("Invalid manifest, directory or existing report")
    doc=json.loads(manifest.read_text(encoding="utf-8"))
    rows=doc.get("videos")
    if not isinstance(rows,list) or not 1<=len(rows)<=12:raise ValueError("1–12 authorized entries required")
    validated=[];keys=set()
    for row in rows:
        if row.get("authorized") is not True or not isinstance(row.get("rights"),str) or not row["rights"].strip():
            raise ValueError("Every video requires explicit rights attestation")
        s=parse_source(row["url"])
        key=hashlib.sha256(s.url.encode()).hexdigest()
        if key in keys:raise ValueError("Duplicate test URL")
        keys.add(key)
        max_gib=row.get("max_gib",1)
        if type(max_gib) is not int or not 1<=max_gib<=8:raise ValueError("1–8 GiB cap per test")
        validated.append((s,key,max_gib,row.get("height",720)))
    results=[]
    for s,key,limit,height in validated:
        started=time.monotonic()
        result={"provider":s.provider,"url_sha256":key,"stage":"preflight","status":"FAILED"}
        try:
            m=preflight(s.url,authorized=True)
            result.update(formats=len(m.formats),duration=m.duration,subtitles=len(m.subtitles))
            if not a.preflight_only:
                result["stage"]="download"
                path=download(m,dest,authorized=True,height=height,max_bytes=limit*1024**3)
                v=probe_video_local_container(path)
                result.update(duration=v.duration,width=v.width,height=v.height,has_audio=v.has_audio,bytes=path.stat().st_size)
            result["status"]="PASS"
        except KeyboardInterrupt:
            result["status"]="CANCELLED";results.append(result);break
        except Exception as exc:
            result["error_type"]=type(exc).__name__
        result["elapsed"]=time.monotonic()-started
        results.append(result)
        print(s.provider,result["stage"],result["status"],flush=True)
    passed={r["provider"] for r in results if r["status"]=="PASS"}
    required={"youtube","twitch","twitch-clip","kick","kick-clip"}
    atomic_json(report,{"schema_version":1,"commit":a.commit,"preflight_only":a.preflight_only,
        "results":results,"provider_gaps":sorted(required-passed),
        "native_full_acceptance":"NOT_EVALUATED",
        "note":"Shorts use youtube provider; exact source hashes distinguish entries. Does not certify redirect security, cancellation or platform approval."})
if __name__=="__main__":main()
