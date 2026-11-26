"""Compare fixed and story boundaries using one frozen authorized corpus."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from streamclipper.m16_benchmark import freeze
from streamclipper.m16_pipeline import analyze_m16
from streamclipper.story_clipping import StoryOptions,PROFILES,refine_result
from streamclipper.m17_benchmark import compare_boundaries
from streamclipper.gaming_intelligence import atomic_json
from streamclipper.media import probe_video

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest");p.add_argument("lock");p.add_argument("output")
    p.add_argument("--commit",required=True)
    p.add_argument("--story-profile",choices=PROFILES,default="social")
    p.add_argument("--speech-model");p.add_argument("--vision-model");p.add_argument("--detector-model")
    a=p.parse_args();manifest=Path(a.manifest).resolve();lock=json.loads(Path(a.lock).read_text(encoding="utf-8"))
    output=Path(a.output)
    if output.exists():raise FileExistsError(output)
    if freeze(manifest)!=lock:raise ValueError("Frozen corpus changed")
    paths={v["id"]:manifest.parent/v["path"] for v in json.loads(manifest.read_text(encoding="utf-8"))["vods"]}
    rows=[];options=StoryOptions(*PROFILES[a.story_profile])
    for v in lock["vods"]:
        if v["split"]!="holdout":continue
        source=paths[v["id"]]
        if abs(probe_video(source).duration-v["duration"])>.1:raise ValueError("Duration mismatch")
        evidence=[]
        baseline=analyze_m16(str(source),speech_model=a.speech_model,vision_model=a.vision_model,
                             detector_model=a.detector_model,evidence_sink=evidence.extend)
        story=refine_result(baseline,evidence,options)
        rows.append({"vod":v["id"],"game":v["game"],"language":v["language"],
            "metrics":compare_boundaries(baseline.candidates,story.candidates,v["moments"],v["duration"])})
    if freeze(manifest)!=lock:raise ValueError("Corpus changed during benchmark")
    atomic_json(output,{"schema_version":1,"commit":a.commit,"corpus_sha256":lock["corpus_sha256"],
        "settings":asdict(options),"holdout":rows,"gaps":lock["gaps"],"quality_acceptance":"NOT_EVALUATED"})
if __name__=="__main__":main()
