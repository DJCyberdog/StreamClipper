"""Native NVDEC evaluation on an authorized local VOD; no change to default decoder.
Only compares bounded 8-bit NV12-compatible decode, not full-video throughput.
"""
import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import subprocess
import time
from PIL import Image,ImageChops,ImageStat
from streamclipper.media import probe_video,tool_path
from streamclipper.m16_visual_search import search_positions
from streamclipper.gaming_intelligence import atomic_json

def decode(video,at,cuda=False):
    cmd=[tool_path("ffmpeg"),"-hide_banner","-nostdin","-loglevel","error"]
    if cuda:cmd+=["-hwaccel","cuda","-hwaccel_output_format","cuda"]
    filters=("hwdownload,format=nv12," if cuda else "")+"scale=320:-2:flags=fast_bilinear"
    cmd+=["-ss",f"{at:.3f}","-i",video.path,"-map","0:v:0","-an","-sn",
          "-frames:v","1","-vf",filters,"-q:v","6","-f","image2pipe","-vcodec","mjpeg","pipe:1"]
    start=time.monotonic()
    result=subprocess.run(cmd,capture_output=True,timeout=60,check=True)
    elapsed=time.monotonic()-start
    with Image.open(BytesIO(result.stdout)) as f:image=f.convert("RGB")
    return image,elapsed

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video");parser.add_argument("output")
    parser.add_argument("--frames",type=int,default=16)
    args=parser.parse_args()
    if not 8<=args.frames<=120:parser.error("8–120 frames")
    output=Path(args.output)
    if output.exists():raise FileExistsError(output)
    video=probe_video(args.video);stamps=search_positions(video.duration,args.frames)
    rows=[];failure=None
    for i,at in enumerate(stamps):
        cpu,ct=decode(video,at)
        try:gpu,gt=decode(video,at,True)
        except (OSError,subprocess.SubprocessError) as exc:
            failure={"timestamp":at,"error":str(exc),"stderr":str(getattr(exc,"stderr",""))[-1000:]};break
        mae=None
        if cpu.size==gpu.size:
            mae=sum(ImageStat.Stat(ImageChops.difference(cpu,gpu)).mean)/3
        rows.append({"at":at,"cpu_seconds":ct,"nvdec_seconds":gt,"rgb_mae_0_255":mae})
        print(f"{i+1}/{len(stamps)}",flush=True)
    complete=len(rows)==len(stamps) and failure is None
    parity=complete and all(row["rgb_mae_0_255"] is not None and row["rgb_mae_0_255"]<=3 for row in rows)
    ct=sum(r["cpu_seconds"] for r in rows);gt=sum(r["nvdec_seconds"] for r in rows)
    report={"schema_version":1,"duration":video.duration,"requested_frames":len(stamps),"samples":rows,
            "failure":failure,"complete":complete,"parity_rgb_mae_le_3":parity,
            "cpu_seconds":ct,"nvdec_seconds":gt,"speedup":ct/gt if complete and gt>0 else None,
            "recommendation":"consider NVDEC for this source only" if parity and ct>gt*1.1 else "retain CPU seek",
            "note":"This is sparse seeking including process/context creation, not full VOD GPU decode or event quality."}
    atomic_json(output,report)
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
