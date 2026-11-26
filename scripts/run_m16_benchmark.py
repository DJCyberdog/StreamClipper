"""Run baseline and experimental M16 on the same locked authorized VODs, offline."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from streamclipper.analyze import analyze
from streamclipper.m16_pipeline import analyze_m16,fingerprint_model
from streamclipper.m16_benchmark import freeze,compare,file_hash
from streamclipper.gaming_intelligence import atomic_json,digest
from streamclipper.media import probe_video
from streamclipper.resource_sampling import ResourceSampler

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest");p.add_argument("lock");p.add_argument("output")
    p.add_argument("--commit",required=True)
    p.add_argument("--speech-model");p.add_argument("--vision-model");p.add_argument("--detector-model")
    p.add_argument("--visual-budget",type=int,default=180);p.add_argument("--object-budget",type=int,default=90)
    p.add_argument("--profile",choices=["generic","open-world"],default="generic")
    p.add_argument("--clip-seconds",type=int,default=25)
    args=p.parse_args()
    manifest=Path(args.manifest).resolve(strict=True)
    lock=json.loads(Path(args.lock).read_text(encoding="utf-8"))
    if lock!=freeze(manifest):raise ValueError("Corpus changed")
    sources={v["id"]:manifest.parent/v["path"] for v in json.loads(manifest.read_text(encoding="utf-8"))["vods"]}
    options={"speech_model":args.speech_model,"vision_model":args.vision_model,"detector_model":args.detector_model,
             "max_visual_frames":args.visual_budget,"max_object_frames":args.object_budget}
    models={k:fingerprint_model(v,None) for k,v in options.items() if k.endswith("_model")}
    shared={"schema_version":1,"corpus_sha256":lock["corpus_sha256"],"source_commit":args.commit,
            "model_sha256":digest(models),"settings_sha256":digest({"clip_seconds":args.clip_seconds,
                    "visual_budget":args.visual_budget,"object_budget":args.object_budget,"profile":args.profile}),
            "profile":args.profile,"model_fingerprints":models}
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    reports={name:{**shared,"engine":name,"predictions":{},"resources":{}} for name in ("baseline","m16")}
    for vod in lock["vods"]:
        key=vod["id"];path=sources[key]
        if abs(probe_video(path).duration-vod["duration"])>.1:raise ValueError("Duration differs from corpus")
        if file_hash(path)!=vod["sha256"]:raise ValueError("Source differs from corpus")
        for name,engine in (("baseline",analyze),("m16",analyze_m16)):
            print(key,name,flush=True);started=time.monotonic()
            with ResourceSampler() as resources:
                result=engine(str(path),args.clip_seconds,8,**options,
                    **({"profile":args.profile} if name=="m16" else {}))
            elapsed=time.monotonic()-started
            reports[name]["predictions"][key]=[asdict(c) for c in result.candidates]
            reports[name]["resources"][key]={"elapsed_seconds":elapsed,
                "seconds_per_vod_hour":elapsed/(vod["duration"]/3600),**resources.report()}
    if lock!=freeze(manifest):raise ValueError("Corpus changed during run")
    if models!={k:fingerprint_model(v,None) for k,v in options.items() if k.endswith("_model")}:raise ValueError("Models changed during run")
    for name,report in reports.items():atomic_json(out/(name+".json"),report)
    comparison=compare(lock,reports["baseline"],reports["m16"])
    for row in comparison["holdout"]:
        for name in ("baseline","m16"):
            row[name+"_resources"]=reports[name]["resources"][row["vod"]]
    atomic_json(out/"comparison.json",comparison)
if __name__=="__main__":main()
