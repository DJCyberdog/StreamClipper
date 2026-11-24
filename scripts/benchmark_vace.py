"""Explicit GPU acceptance experiment on a short clean reference sequence.

Usage: python scripts/benchmark_vace.py --clean PATH --model PATH --output PATH
Clean input: 9, 17 or 33 lexically ordered RGB PNG frames at a supported size.
Writes a new directory containing input, masks, baselines, output and metrics.
Never downloads models or edits source frames.
"""
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import time

from streamclipper.portable import configure_portable_environment
from streamclipper.vace_inpainting import (
    restore_window, validate_window, MODEL_ID, MODEL_REVISION, DIFFUSERS_VERSION)
from streamclipper.inpainting_metrics import evaluate_restoration


def make_case(clean, kind):
    from PIL import Image, ImageDraw
    w,h=clean[0].size
    regions={
        "hud": (0, h*3//4, w//4, h),
        "topbar": (0,0,w,h//8),
        "facecam": (w*3//4,0,w,h//3),
        "chat": (w*4//5,h//5,w,h*4//5),
        "alert": (w//4,h//8,w*3//4,h//3),
    }
    region=regions[kind]
    masks=[]; contaminated=[]; black=[]
    for i,frame in enumerate(clean):
        mask=Image.new("L",(w,h),0)
        active=kind!="alert" or len(clean)//3<=i<2*len(clean)//3
        overlay=Image.new("RGB",(w,h),(30,25,80))
        if active:
            mask.paste(255,region)
            draw=ImageDraw.Draw(overlay)
            x,y,right,bottom=region
            for row in range(y+3,bottom-2,8):
                draw.rectangle((x+2,row,min(right-1,x+max(3,(right-x)*3//4)),row+2),
                               fill=(250,180,80))
        masks.append(mask)
        contaminated.append(Image.composite(overlay,frame,mask))
        black.append(Image.composite(Image.new("RGB",(w,h)),frame,mask))
    validate_window(clean,masks)
    return contaminated,masks,black


def metrics(clean,result,masks):
    return asdict(evaluate_restoration(
        [f.tobytes() for f in clean],[f.tobytes() for f in result],
        [m.tobytes() for m in masks]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean",required=True,type=Path)
    parser.add_argument("--model",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--kind",choices=("hud","topbar","facecam","chat","alert"),default="topbar")
    parser.add_argument("--steps",type=int,default=20)
    parser.add_argument("--seed",type=int,default=42)
    args=parser.parse_args()
    configure_portable_environment()
    from PIL import Image
    paths=sorted(args.clean.glob("*.png"))
    if len(paths) not in (9,17,33):
        parser.error("Clean directory must contain exactly 9, 17 or 33 PNG frames")
    clean=[]
    for path in paths:
        with Image.open(path) as image:
            if image.width*image.height>832*480:
                parser.error("Reference frames must already be resized")
            clean.append(image.convert("RGB"))
    dirty,masks,black=make_case(clean,args.kind)
    args.output.mkdir(parents=True,exist_ok=False)
    def save(name,frames):
        folder=args.output/name; folder.mkdir()
        for index,frame in enumerate(frames):
            frame.save(folder/f"{index:04d}.png")
    for name,frames in (("clean",clean),("overlay",dirty),("mask",masks),("black",black)):
        save(name,frames)
    report={"status":"RUNNING","model":MODEL_ID,"expected_model_revision":MODEL_REVISION,
            "model_directory":str(args.model.resolve()),"diffusers":DIFFUSERS_VERSION,
            "kind":args.kind,"seed":args.seed,"steps":args.steps,
            "frames":len(clean),"size":clean[0].size,
            "baselines":{"overlay":metrics(clean,dirty,masks),"black":metrics(clean,black,masks)}}
    target=args.output/"report.json"
    def write():
        target.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    write()
    started=time.monotonic()
    try:
        import torch
        torch.cuda.reset_peak_memory_stats()
        report["gpu"]=torch.cuda.get_device_name(0)
        output=restore_window(dirty,masks,args.model,seed=args.seed,steps=args.steps,
                              progress=lambda i,n:print(f"VACE {i}/{n}",flush=True))
        torch.cuda.synchronize()
        report["peak_allocated_vram_bytes"]=torch.cuda.max_memory_allocated()
        report["peak_reserved_vram_bytes"]=torch.cuda.max_memory_reserved()
        save("restored",output)
        report["restored"]=metrics(clean,output,masks)
        report["status"]="MEASURED_NOT_ACCEPTED"
    except BaseException as exc:
        report["status"]="FAILED"
        report["error"]=str(exc)
        raise
    finally:
        report["elapsed_seconds"]=time.monotonic()-started
        write()


if __name__=="__main__":
    main()
