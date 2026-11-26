"""M16f: local visual retrieval over bounded, timestamped CLIP samples."""
from pathlib import Path
import math
from .media import sampled_jpeg_frames,CancelledError
from .model_checks import validate_clip_model
from .vision_batch import frame_batches,inference_context
from .vision_device import report_vision_device
from .models import TranscriptSegment

def search_positions(duration,budget,anchors=()):
    if not math.isfinite(duration) or duration<=0 or not 8<=budget<=2000:
        raise ValueError("Invalid visual search budget")
    # Uniform coverage first, supplement with known highlight timestamps.
    uniform=max(1,budget//2)
    positions={round(duration*(i+.5)/uniform,3) for i in range(uniform)}
    for a in anchors:
        if len(positions)>=budget:break
        if math.isfinite(a) and 0<=a<duration:positions.add(round(a,3))
    # Fill remaining budget with a deterministic denser uniform grid.
    for i in range(budget):
        if len(positions)>=budget:break
        positions.add(round(duration*(i+.5)/budget,3))
    return sorted(p for p in positions if 0<=p<duration)

def diverse_hits(scores,limit=20,spacing=5.):
    if not 1<=limit<=100 or not math.isfinite(spacing) or spacing<0:raise ValueError("Invalid review limits")
    chosen=[]
    for score,at in sorted(scores,key=lambda row:(-row[0],row[1])):
        if not math.isfinite(score) or not math.isfinite(at):continue
        if any(abs(at-t)<spacing for _,t in chosen):continue
        chosen.append((score,at))
        if len(chosen)>=limit:break
    return chosen

def visual_search(video,query,model_directory,*,anchors=(),budget=240,limit=20,
                  cancelled=None,progress=None):
    import torch
    from transformers import AutoProcessor,CLIPModel
    if not isinstance(query,str) or not query.strip() or len(query)>500:
        raise ValueError("Enter a visual description (1–500 characters)")
    folder=validate_clip_model(model_directory)
    stamps=search_positions(video.duration,budget,anchors)
    if cancelled and cancelled():raise CancelledError("Bildsuche abgebrochen")
    processor=AutoProcessor.from_pretrained(str(folder),local_files_only=True)
    model=CLIPModel.from_pretrained(str(folder),local_files_only=True)
    device=__import__("streamclipper.hardware_media",fromlist=["torch_device"]).torch_device(torch)
    model.to(device).eval()
    report_vision_device("CLIP-Bildsuche",device)
    # One query versus a fixed neutral prompt: logits rather than softmax over
    # one prompt (which would always give 1). Relative similarity is not truth.
    prompts=[query,"An ordinary screenshot from a video game"]
    scores=[]
    frames=sampled_jpeg_frames(video,timestamps=stamps,max_frames=budget,cancelled=cancelled)
    done=0
    for rows in frame_batches(frames,4 if device=="cuda" else 1,cancelled):
        batch=processor(text=prompts,images=[image for _,image in rows],padding=True,truncation=True,return_tensors="pt")
        batch={k:v.to(device) for k,v in batch.items()}
        with torch.inference_mode():
            logits=model(**batch).logits_per_image.float()
            if not bool(torch.isfinite(logits).all()):raise RuntimeError("Non-finite visual similarity")
            values=(logits[:,0]-logits[:,1]).cpu().tolist()
        scores.extend((float(s),at) for (at,_),s in zip(rows,values,strict=True))
        done+=len(rows)
        if progress:progress(min(99,round(100*done/max(1,len(stamps)))))
    hits=diverse_hits(scores,limit)
    if progress:progress(100)
    return [TranscriptSegment(at,min(video.duration,at+1),
            f"Bildähnlichkeit {score:+.2f} (relativer Score, nicht verifiziert)")
            for score,at in hits]
