"""Experimental M13d local video inpainting backend. Experimental export integration.

One bounded temporal window, explicit binary masks, lossless compositing.
Only the model-generated pixels inside the mask replace source pixels.
"""
from __future__ import annotations

from pathlib import Path
import json
import math

MODEL_ID = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"
MODEL_REVISION = "ec4d2cb062b548996b179d493fdd05340de702a1"
DIFFUSERS_VERSION = "0.36.0"
FRAME_COUNTS = (9, 17, 33)
PROMPT = ("Continue the existing video game environment naturally behind the "
          "removed overlay, preserving the original scene, colors and motion.")


def validate_window(frames, masks):
    if len(frames) not in FRAME_COUNTS or len(frames) != len(masks):
        raise ValueError("VACE-Testfenster benötigt 9, 17 oder 33 Frames mit Masken")
    w,h=frames[0].size
    if not (64<=w<=832 and 64<=h<=832 and w%16==0 and h%16==0 and w*h<=832*480):
        raise ValueError("Testauflösung: Vielfache von 16, maximal 832×480 Pixel Fläche")
    any_mask=False
    for frame,mask in zip(frames,masks):
        if frame.mode!="RGB" or mask.mode!="L" or frame.size!=(w,h) or mask.size!=(w,h):
            raise ValueError("RGB-Frames und gleich große L-Masken erforderlich")
        histogram=mask.histogram()
        if sum(histogram[1:255]):
            raise ValueError("Maske muss binär sein (0 oder 255)")
        any_mask |= bool(histogram[255])
    if not any_mask:
        raise ValueError("Keine aktiven Masken")
    return w,h


def mask_composite(frames, generated, masks):
    from PIL import Image
    validate_window(frames,masks)
    if len(generated)!=len(frames):
        raise ValueError("Modell hat falsche Frameanzahl geliefert")
    result=[]
    for source,prediction,mask in zip(frames,generated,masks):
        if prediction.size!=source.size:
            raise ValueError("Modell hat falsche Auflösung geliefert")
        result.append(Image.composite(prediction.convert("RGB"),source,mask))
    return result


def restore_window(frames,masks,model_directory,*,seed=42,steps=20,
                   cancelled=None,progress=None,pipeline_factory=None):
    """Opt-in experiment, one temporal inference call, no remote loading.

    pipeline_factory is a test seam. A mock result is not a model quality pass.
    """
    w,h=validate_window(frames,masks)
    if type(seed) is not int or not 0<=seed<2**32 or type(steps) is not int or not 1<=steps<=50:
        raise ValueError("Ungültiger Seed oder Schrittzahl")
    folder=Path(model_directory).expanduser().resolve()
    if not folder.is_dir() or not (folder/"model_index.json").is_file():
        raise FileNotFoundError("Lokaler VACE-Modellordner fehlt")
    config=json.loads((folder/"model_index.json").read_text(encoding="utf-8"))
    if config.get("_class_name")!="WanVACEPipeline":
        raise ValueError("Modell ist keine WanVACEPipeline")
    def check():
        if cancelled and cancelled():
            from .media import CancelledError
            raise CancelledError("Inpainting abgebrochen")
    check()
    factory=pipeline_factory or local_pipeline_factory()
    pipe,generator=factory(folder,seed)
    check()
    def on_step(_pipeline,index,_timestep,kwargs):
        check()
        if progress:
            progress(index+1,steps)
        return kwargs
    # Do not expose the overlay pixels to the model as conditioning.
    from PIL import Image
    conditioned=[Image.composite(Image.new("RGB",f.size,(127,127,127)),f,m)
                 for f,m in zip(frames,masks)]
    output=pipe(prompt=PROMPT,video=conditioned,mask=masks,height=h,width=w,
                num_frames=len(frames),num_inference_steps=steps,guidance_scale=5.,
                generator=generator,output_type="pil",callback_on_step_end=on_step).frames[0]
    check()
    return mask_composite(frames,output,masks)


def local_pipeline_factory():
    """Reuse one local pipeline within one scene, never globally."""
    loaded=None
    location=None
    def factory(folder,seed):
        nonlocal loaded,location
        import torch
        import diffusers
        if diffusers.__version__ != DIFFUSERS_VERSION:
            raise RuntimeError("VACE-Test benötigt Diffusers "+DIFFUSERS_VERSION)
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise RuntimeError("VACE-Test benötigt eine BF16-fähige CUDA-GPU")
        if loaded is None:
            from diffusers import WanVACEPipeline
            loaded=WanVACEPipeline.from_pretrained(str(folder),local_files_only=True,
                                                torch_dtype=torch.bfloat16,use_safetensors=True)
            loaded.enable_model_cpu_offload()
            loaded.vae.enable_tiling()
            location=folder
        elif location!=folder:
            raise ValueError("Modellwechsel innerhalb eines Inpainting-Laufs")
        return loaded,torch.Generator(device="cpu").manual_seed(seed)
    return factory
