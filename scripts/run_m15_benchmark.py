"""Opt-in real-model runner on local annotated audio cases.
No model or recording download; no upload. See docs/M15F_ACCEPTANCE.md.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import time
from streamclipper.audio_sources import SpeechSource,inventory
from streamclipper.audio_separation import InworldBackend,separate_stream,sha256_file
from streamclipper.target_speaker import VoxLockBackend
from streamclipper.reconstructed_speech import select_reconstructed,transcribe_reconstructed
from streamclipper.models import VideoInfo,AnalysisResult
from streamclipper.semantic import transcribe_video
from streamclipper.speech_activity import detect_speech
from streamclipper.speech_timing import propose_timings,apply_proposals
from streamclipper.speech_benchmark import evaluate_manifest
from streamclipper.speech_handoff import handoff

def main():
    p=argparse.ArgumentParser()
    p.add_argument("manifest",help="Local annotated cases JSON")
    p.add_argument("output",help="New empty output directory")
    p.add_argument("--backend",choices=("inworld","voxlock"),required=True)
    p.add_argument("--model",required=True,help="Local checkpoint/model directory")
    p.add_argument("--whisper",required=True,help="Local Faster-Whisper model directory")
    p.add_argument("--device",choices=("auto","cpu","cuda"),default="auto")
    p.add_argument("--authorized-references",action="store_true",help="Confirm authorized local reference recordings")
    p.add_argument("--commit",required=True,help="Exact StreamClipper git commit")
    args=p.parse_args()
    manifest=Path(args.manifest).resolve(strict=True)
    doc=json.loads(manifest.read_text(encoding="utf-8"))
    if doc.get("schema_version")!=1 or not doc.get("cases"):raise ValueError("Missing cases")
    # Require explicit consent before TSE, and no automatic enrollment.
    if args.backend=="voxlock" and not args.authorized_references:raise ValueError("Authorized references must be confirmed")
    out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    result={"schema_version":1,"evidence_kind":doc.get("evidence_kind","unspecified"),
        "model":args.backend,"commit":args.commit,"cases":[]}
    groups={};ids=set()
    for case in doc["cases"]:
        key=case["id"]
        if not isinstance(key,str) or not key or not key.replace("-","").replace("_","").isalnum() or key in ids:
            raise ValueError("Invalid/duplicate case ID")
        ids.add(key)
        group=case["speaker_group"];split=case["split"]
        if split not in ("development","holdout") or group in groups and groups[group]!=split:
            raise ValueError("Invalid or leaking split")
        groups[group]=split
    def source(path):return (manifest.parent/path).resolve(strict=True)
    backend=InworldBackend(args.model,args.device) if args.backend=="inworld" else None
    for case in doc["cases"]:
        folder=out/case["id"];folder.mkdir()
        mix=source(case["mix"]);snap=inventory(mix)
        if len(snap.streams)!=1 or snap.duration>600:raise ValueError("Use aligned single-stream 48 kHz cases <=10 minutes")
        selection=SpeechSource(snap,snap.streams[0].index,"mix")
        video=VideoInfo(str(mix),snap.duration,1,1,1,True)
        if args.backend=="voxlock":
            backend=VoxLockBackend(args.model,source(case["reference_wav"]),consent=True)
        started=time.monotonic()
        bundle=separate_stream(selection,folder,backend=backend)
        separation_seconds=time.monotonic()-started
        estimate=select_reconstructed(snap,bundle/"voice_estimate.wav")
        baseline=transcribe_video(video,args.whisper)
        from functools import partial
        variant=transcribe_reconstructed(video,args.whisper,estimate,
            transcriber=partial(transcribe_video,model_cache={}))
        analysis=AnalysisResult(video,[],method="benchmark"+estimate.method_suffix,transcript=variant)
        spans=detect_speech(estimate)
        proposals=propose_timings(variant,spans,duration=video.duration,trim_outer_words=True)
        # Benchmark the deterministic proposals separately from manual review.
        corrected=apply_proposals(analysis,proposals)
        for name,cues in (("baseline",baseline),("variant",variant),("timing_proposals",corrected.transcript)):
            (folder/(name+".json")).write_text(json.dumps([asdict(c) for c in cues],ensure_ascii=False,allow_nan=False),encoding="utf-8")
        (folder/"handoff.json").write_text(json.dumps(handoff(corrected),ensure_ascii=False,allow_nan=False),encoding="utf-8")
        row={k:case[k] for k in ("id","split","speaker_group","language","conditions","reference_cues")}
        row.update({"mix":str(mix),"reference_voice":str(source(case["reference_voice"])),
            "estimate":str(bundle/"voice_estimate.wav"),"baseline_cues":str(folder/"baseline.json"),
            "variant_cues":str(folder/"variant.json"),"timing_proposals_cues":str(folder/"timing_proposals.json"),
            "runtime_seconds":time.monotonic()-started,"separation_seconds":separation_seconds,
            "peak_ram_bytes":None,"peak_vram_bytes":None})
        if case.get("interferer"):row["interferer"]=str(source(case["interferer"]))
        result["cases"].append(row)
    index=out/"evaluated_cases.json"
    index.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    report=evaluate_manifest(index)
    with (out/"metrics.json").open("x",encoding="utf-8") as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(out/"metrics.json")
if __name__=="__main__":main()
