"""Run existing local CLIP on pre-annotated, held-out video scenes.

python scripts/benchmark_overlays.py --manifest cases.json --model data/models/clip-vit-base-patch32 --output report.json
Manifest is a list of {"video": "local.mp4", "start": 0, "end": 5,
"zones": [{"kind":"hud","region":[0,0,.2,.2]}]}. Empty zones are negative controls.
Paths relative to manifest. No downloads, no output overwrite.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from streamclipper.media import probe_video
from streamclipper.overlay_recognition import recognize_overlays
from streamclipper.overlay_metrics import evaluate_zones
from streamclipper.smart_director import OverlayZone


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--model",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    raw=args.manifest.read_bytes()
    if len(raw)>2_000_000:
        parser.error("Manifest too large")
    cases=json.loads(raw)
    if not isinstance(cases,list) or not 1<=len(cases)<=100:
        parser.error("Expected 1–100 pre-annotated cases")
    if not any(not case["zones"] for case in cases) or not any(case["zones"] for case in cases):
        parser.error("Include positive and negative controls")
    report={"status":"RUNNING","manifest_sha256":hashlib.sha256(raw).hexdigest(),
            "model_directory":str(args.model.resolve()),"spatial_iou":.5,"temporal_iou":.5,
            "cases":[]}
    totals=[0,0,0]
    started=time.monotonic()
    # Reserve the report before model execution. Preserve failure evidence.
    with args.output.open("x",encoding="utf-8") as stream:
        try:
            for case in cases:
                path=(args.manifest.parent/case["video"]).resolve(strict=True)
                video=probe_video(path)
                start,end=float(case["start"]),float(case["end"])
                truth=tuple(OverlayZone(**{**z,"region":tuple(z["region"])}) for z in case["zones"])
                evaluate_zones((),truth,start,end)
                if not 0<=start<end<=video.duration+.1:
                    raise ValueError("Case outside source duration")
                at=time.monotonic()
                proposed=recognize_overlays(video,str(args.model.resolve()),start,end)
                score=evaluate_zones(proposed,truth,start,end)
                report["cases"].append({"video":str(path),"start":start,"end":end,
                    "truth":[asdict(z) for z in truth],"proposals":[asdict(z) for z in proposed],
                    "metrics":asdict(score),"seconds":time.monotonic()-at})
                for i,value in enumerate((score.true_positives,score.false_positives,score.false_negatives)):
                    totals[i]+=value
            tp,fp,fn=totals
            report["aggregate"]={"tp":tp,"fp":fp,"fn":fn,
                "precision":tp/(tp+fp) if tp+fp else None,
                "recall":tp/(tp+fn) if tp+fn else None}
            report["status"]="MEASURED_NOT_ACCEPTED"
        except BaseException as exc:
            report["status"]="FAILED"
            report["error"]=str(exc)
            raise
        finally:
            report["elapsed_seconds"]=time.monotonic()-started
            json.dump(report,stream,indent=2,allow_nan=False)


if __name__=="__main__":
    main()
