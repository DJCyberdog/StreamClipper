"""Bounded image batches and opt-in CUDA mixed precision for M16."""
from contextlib import nullcontext
from io import BytesIO

def frame_batches(frames, size, cancelled=None):
    from PIL import Image
    from .media import CancelledError
    if not 1 <= size <= 8:
        raise ValueError("Batch size must be 1–8")
    rows=[]
    for at, encoded in frames:
        if cancelled and cancelled():raise CancelledError("Bildanalyse abgebrochen")
        with Image.open(BytesIO(encoded)) as src:
            rows.append((at,src.convert("RGB")))
        if len(rows)==size:
            yield rows
            rows=[]
    if rows:yield rows

def inference_context(torch, device, mixed_precision):
    if mixed_precision and str(device).startswith("cuda"):
        return torch.autocast(device_type="cuda",dtype=torch.float16)
    return nullcontext()

def vision_batch_size(device, requested, default_cuda=4):
    if requested is not None:
        if type(requested) is not int or not 1<=requested<=8:raise ValueError("Invalid vision batch size")
        return requested
    return default_cuda if str(device).startswith("cuda") else 1
