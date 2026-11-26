"""Owner native M16 media/analysis acceptance. Only local authorized input.
Produces diagnostic results, not annotated highlight-quality evidence.
"""
import argparse
from dataclasses import asdict
from pathlib import Path
import time
from streamclipper.media import probe_video,tool_path
from streamclipper.hardware_media import test_decode,phase_notice
from streamclipper.encoders import probe_nvenc
from streamclipper.resource_sampling import ResourceSampler
from streamclipper.m16_pipeline import analyze_m16
from streamclipper.gaming_intelligence import atomic_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("video");p.add_argument("report")
    p.add_argument("--speech-model");p.add_argument("--vision-model");p.add_argument("--detector-model")
    p.add_argument("--commit",required=True)
    p.add_argument("--profile",choices=["generic","open-world"],default="open-world")
    p.add_argument("--compare-cpu",action="store_true")
    args=p.parse_args()
    dest=Path(args.report)
    if dest.exists():raise FileExistsError(dest)
    info=probe_video(args.video)
    ffmpeg=tool_path("ffmpeg")
    report={"schema_version":1,"commit":args.commit,"duration_seconds":info.duration,
            "six_hour_input":info.duration>=21600,
            "nvdec_scale_cuda_probe":test_decode(ffmpeg,info.path),
            "h264_nvenc_probe":probe_nvenc(ffmpeg,"h264_nvenc"),
            "hevc_nvenc_probe":probe_nvenc(ffmpeg,"hevc_nvenc"),
            "runs":[],"quality_acceptance":"NOT_EVALUATED"}
    for policy in (["cpu","gpu"] if args.compare_cpu else ["gpu"]):
        notices=[]
        def notice(value):
            if not notices or notices[-1]!=value:
                notices.append(value)
        token=phase_notice.set(notice)
        started=time.monotonic()
        try:
            with ResourceSampler() as resources:
                result=analyze_m16(info.path,profile=args.profile,hardware_mode=policy,
                      fast_vision=policy=="gpu",speech_model=args.speech_model,
                      vision_model=args.vision_model,detector_model=args.detector_model,
                      progress=lambda n:print(f"\r{policy} {n:3d}%",end="",flush=True))
            elapsed=time.monotonic()-started
            report["runs"].append({"hardware_requested":policy,"elapsed_seconds":elapsed,
                "seconds_per_vod_hour":elapsed/(info.duration/3600),
                "phase_notices":notices,"resources":resources.report(),
                "candidate_bounds":[{"start":c.start,"end":c.end,"score":c.score,
                                      "peak_at":c.peak_at} for c in result.candidates],
                "transcript_segments":len(result.transcript),"status":"COMPLETED"})
        except Exception as exc:
            report["runs"].append({"hardware_requested":policy,"status":"FAILED",
                       "error_type":type(exc).__name__,"phase_notices":notices})
            atomic_json(dest,report)
            raise
        finally:phase_notice.reset(token)
    atomic_json(dest,report)
    print(f"\nReport: {dest}")
if __name__=="__main__":main()
