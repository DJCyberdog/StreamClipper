"""Explicit local native long-VOD evidence run, no uploads/downloads.
Never declares independent speech quality or GUI listening accepted.
"""
import argparse
from dataclasses import asdict
from functools import partial
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
from streamclipper.audio_sources import inventory,SpeechSource
from streamclipper.audio_separation import InworldBackend,separate_stream,sha256_file,output_format,RATE
from streamclipper.target_speaker import VoxLockBackend
from streamclipper.reconstructed_speech import select_reconstructed,transcribe_reconstructed
from streamclipper.asr_window_cache import ASRWindowCache
from streamclipper.semantic import transcribe_video
from streamclipper.media import CancelledError,probe_video,tool_path,measure_loudness
from streamclipper.resource_sampling import ResourceSampler
from streamclipper.audio_editor import import_pair,MixOptions
from streamclipper.editor_project import initial_project
from streamclipper.render_contract import RenderRequest,render_request
from streamclipper.render_queue import _snapshot,_rehydrate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",required=True);p.add_argument("--output",required=True)
    p.add_argument("--stream-index",required=True,type=int)
    p.add_argument("--backend",choices=("inworld","voxlock"),required=True)
    p.add_argument("--model",required=True);p.add_argument("--whisper",required=True)
    p.add_argument("--device",choices=("auto","cpu","cuda"),default="auto")
    p.add_argument("--reference");p.add_argument("--authorized-reference",action="store_true")
    p.add_argument("--commit",required=True)
    p.add_argument("--clip-start",type=float,default=0)
    p.add_argument("--short-smoke",action="store_true",help="Test procedure only; never 6h acceptance")
    args=p.parse_args()
    video=probe_video(args.source);snap=inventory(video.path)
    if not args.short_smoke and not 21595<=snap.duration<=21600:
        raise ValueError("Native 6h test expects 5:59:55–6:00:00; use --short-smoke for procedure test")
    if not 0<=args.clip_start<video.duration-.2:raise ValueError("Invalid clip start")
    selection=SpeechSource(snap,args.stream_index,"mix").validate()
    stream=next(s for s in snap.streams if s.index==args.stream_index)
    if args.backend=="voxlock" and (not args.reference or not args.authorized_reference):
        raise ValueError("Explicit authorized reference required for VoxLock")
    root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=False)
    report={"schema_version":1,"commit":args.commit,"platform":platform.platform(),"backend":args.backend,
        "duration_seconds":snap.duration,"input_rate":stream.sample_rate,"channels":stream.channels,
        "evidence_kind":"native_short_procedure" if args.short_smoke else "native_long_vod",
        "gates":{},"quality_acceptance":"NOT_EVALUATED","listening_review":"NOT_EVALUATED"}
    target=root/"native_acceptance.json"
    def save():
        temporary=root/"native_acceptance.tmp"
        temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
        temporary.replace(target)
    def gate(name,status,**detail):
        report["gates"][name]={"status":status,**detail};save()
    save();start=time.monotonic()
    digest=sha256_file(video.path)
    report["source_sha256_before"]=digest
    try:
        with ResourceSampler() as resources:
            if args.backend=="inworld":backend=InworldBackend(args.model,args.device)
            else:backend=VoxLockBackend(args.model,args.reference,consent=args.authorized_reference)
            cuda=None
            if args.backend=="inworld" and backend.metadata["device"]=="cuda":
                import torch
                torch.cuda.reset_peak_memory_stats()
                cuda=torch
                props=torch.cuda.get_device_properties(torch.cuda.current_device())
                report["cuda_device"]={"name":props.name,"total_memory_bytes":props.total_memory}
            report["model"]=backend.metadata
            # Recreate the same source with explicitly cached windows after a
            # controlled interruption. VoxLock resume is segmented, not continuous.
            progress=[]
            def first(value):
                progress.append(value)
            try:
                separate_stream(selection,root,backend=backend,use_cache=True,
                    resume_target=args.backend=="voxlock",progress=first,cancelled=lambda:bool(progress))
            except CancelledError:
                if list(root.glob("separation-*")):raise RuntimeError("Interrupted output published")
            else:raise RuntimeError("Expected cancellation")
            bundle=separate_stream(selection,root,backend=backend,use_cache=True,
                resume_target=args.backend=="voxlock",progress=lambda v:print("Separation",v,flush=True))
            manifest=json.loads((bundle/"provenance.json").read_text(encoding="utf-8"))
            gate("cancel_resume","PASS" if manifest["cache"]["reused_windows"]>0 else "FAIL",
                 **manifest["cache"],processing_mode=manifest["processing_mode"])
            import soundfile as sf
            expected=(round(snap.duration*RATE),RATE,stream.channels,"FLOAT",
                      output_format(round(snap.duration*RATE),stream.channels))
            for filename in ("voice_estimate.wav","residual.wav"):
                info=sf.info(bundle/filename)
                if (info.frames,info.samplerate,info.channels,info.subtype,info.format)!=expected:
                    raise ValueError("Stem geometry mismatch")
                if sha256_file(bundle/filename)!=manifest["outputs"][filename]["sha256"]:
                    raise ValueError("Stem hash mismatch")
            gate("stem_geometry_integrity","PASS",frames=expected[0],container=expected[-1])
            selected=select_reconstructed(snap,bundle/"voice_estimate.wav")
            cache=ASRWindowCache.for_whisper(root/"asr_cache",args.whisper)
            cues=transcribe_reconstructed(video,args.whisper,selected,
                transcriber=partial(transcribe_video,model_cache={}),window_cache=cache,
                progress=lambda v:print("ASR",v,flush=True))
            (root/"transcript.json").write_text(json.dumps([asdict(c) for c in cues],
                ensure_ascii=False,allow_nan=False),encoding="utf-8")
            def forbidden(*a,**kw):raise AssertionError("Unexpected cache miss")
            cached=transcribe_reconstructed(video,args.whisper,selected,transcriber=forbidden,window_cache=cache)
            gate("asr_cache","PASS" if cached==cues and cache.hits>0 else "FAIL",cues=len(cues),hits=cache.hits)
            # Same short output interval across preview, direct and queue
            # serialization. Compare actual decoded AAC, not container bytes.
            project=import_pair(initial_project(video),bundle/"voice_estimate.wav",MixOptions(-3,-6))
            end=min(video.duration,args.clip_start+15)
            req=RenderRequest(video,args.clip_start,end,"crop",width=720,height=1280,project=project)
            queued=_rehydrate(json.loads(json.dumps(_snapshot(req))))
            audio_hashes=[];loudness=[]
            for name,request in (("export",req),("preview",req.preview_excerpt(15)),("queue",queued)):
                path=render_request(request,root/(name+".mp4"))
                audio=subprocess.run([tool_path("ffmpeg"),"-v","error","-nostdin","-i",str(path),
                    "-map","0:a:0","-ar","48000","-ac","2","-f","f32le","pipe:1"],
                    capture_output=True,check=True,timeout=120).stdout
                if not audio:raise ValueError("Rendered audio missing")
                audio_hashes.append(hashlib.sha256(audio).hexdigest())
                loudness.append(measure_loudness(path,duration=end-args.clip_start))
            peak=loudness[0]["true_peak_dbtp"]
            gate("render_aac_parity","PASS" if len(set(audio_hashes))==1 and loudness[0]==loudness[1]==loudness[2] else "FAIL",
                 audio_sha256=audio_hashes,measured_aac=loudness[0])
            gate("aac_peak","BLOCKED" if peak is None else "PASS" if peak<=0 else "FAIL",true_peak_dbtp=peak)
            if cuda is not None:report["torch_peak_reserved_bytes"]=cuda.cuda.max_memory_reserved()
        report["resources"]=resources.report()
        after=sha256_file(video.path);report["source_sha256_after"]=after
        gate("original_integrity","PASS" if after==digest and inventory(video.path)==snap else "FAIL")
        native=(not args.short_smoke and platform.system()=="Windows" and cuda is not None
                and "5060 Ti" in report["cuda_device"]["name"] and report["cuda_device"]["total_memory_bytes"]>=15*1024**3)
        gate("native_rtx_6h","PASS" if native else "BLOCKED",duration=snap.duration,device=report.get("cuda_device"))
        gate("resource_telemetry","PASS" if resources.peak_ram_bytes is not None and
             (resources.peak_vram_bytes is not None or report.get("torch_peak_reserved_bytes") is not None) else "BLOCKED")
    except BaseException as exc:
        gate("execution","FAIL",error=str(exc))
        raise
    finally:
        report["elapsed_seconds"]=time.monotonic()-start
        save()
    print(target)
if __name__=="__main__":main()
