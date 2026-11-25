"""Reference-based acceptance metrics for temporal video inpainting.

Operate on already aligned RGB8 frames and one byte per mask pixel. This is
a test/benchmark helper, not a reconstruction algorithm. Ground truth must
come from a clean held-out video before synthetic overlays are applied.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RestorationMetrics:
    masked_mae: float
    outside_mae: float
    temporal_error_mae: float
    masked_pixels: int
    temporal_pixels: int


def evaluate_restoration(clean, restored, masks):
    """Mean absolute RGB error and error in inter-frame RGB differences.

    Temporal residual is evaluated only where the same pixel is masked in
    both adjacent frames; scene cuts must be separated by the caller.
    Values are normalized to 0..1 (temporal error can reach 2).
    """
    if not (len(clean)==len(restored)==len(masks) and len(clean)>=2):
        raise ValueError("Mindestens zwei korrespondierende Frames erforderlich")
    size=len(masks[0])
    if size==0:
        raise ValueError("Leere Maske")
    inside=outside=temporal=ni=no=nt=0
    prev_error=None
    prev_mask=None
    for reference, result, mask in zip(clean,restored,masks):
        if (len(mask)!=size or len(reference)!=3*size or len(result)!=3*size
                or not all(isinstance(x,bytes) for x in (reference,result,mask))
                or any(v not in (0,255) for v in mask)):
            raise ValueError("Ungültiges RGB8-/Maskenformat")
        error=[a-b for a,b in zip(result,reference)]
        for i,m in enumerate(mask):
            delta=sum(abs(e) for e in error[3*i:3*i+3])
            if m:
                inside+=delta;ni+=1
                if prev_mask is not None and prev_mask[i]:
                    temporal+=sum(abs(error[j]-prev_error[j]) for j in range(3*i,3*i+3))
                    nt+=1
            else:
                outside+=delta;no+=1
        prev_error=error
        prev_mask=mask
    if not ni or not no or not nt:
        raise ValueError("Benchmark benötigt Masken-, Kontext- und zeitliche Überlappung")
    return RestorationMetrics(inside/(ni*3*255),outside/(no*3*255),
                              temporal/(nt*3*255),ni,nt)
