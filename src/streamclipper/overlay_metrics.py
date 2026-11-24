"""Independent, labeled-region evaluation for M13c overlay proposals."""
from dataclasses import dataclass
import math

from .smart_director import overlap, OverlayZone


def spatial_iou(a,b):
    shared=overlap(a.region,b.region)
    return shared/(a.region[2]*a.region[3]+b.region[2]*b.region[3]-shared)


def temporal_iou(a,b,start,end):
    def interval(z):
        return (start,end) if z.start is None else (max(start,z.start),min(end,z.end))
    x,y=interval(a);u,v=interval(b)
    shared=max(0.,min(y,v)-max(x,u))
    union=max(0.,y-x)+max(0.,v-u)-shared
    return shared/union if union else 0.


@dataclass(frozen=True)
class OverlayMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None


def evaluate_zones(predicted,truth,start,end,*,spatial=.5,temporal=.5):
    """Maximum-cardinality one-to-one matching; disabled proposals count.

    Ground truth must be annotated before running the model. Disabled is a
    safety flag, not an evaluation filter. Duplicate proposals are penalized.
    """
    predicted,truth=tuple(predicted),tuple(truth)
    if (not all(math.isfinite(v) for v in (start,end,spatial,temporal))
            or not 0<=start<end or not 0<spatial<=1 or not 0<temporal<=1):
        raise ValueError("Ungültige Benchmarkparameter")
    if len(predicted)>200 or len(truth)>200:
        raise ValueError("Zu viele Benchmarkzonen")
    for z in (*predicted,*truth):
        z.validate()
        if z.start is not None and not start<=z.start<z.end<=end:
            raise ValueError("Benchmarkzone außerhalb des Prüfintervalls")
    edges=[]
    for p in predicted:
        matches=[]
        for i,t in enumerate(truth):
            if p.kind!=t.kind:
                continue
            s=spatial_iou(p,t);v=temporal_iou(p,t,start,end)
            if s>=spatial and v>=temporal:
                matches.append((s*v,i))
        edges.append([i for _,i in sorted(matches,key=lambda q:(-q[0],q[1]))])
    assigned={}
    def augment(i,seen):
        for j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in assigned or augment(assigned[j],seen):
                assigned[j]=i
                return True
        return False
    for i in range(len(predicted)):
        augment(i,set())
    tp=len(assigned);fp=len(predicted)-tp;fn=len(truth)-tp
    return OverlayMetrics(tp,fp,fn,tp/len(predicted) if predicted else None,
                          tp/len(truth) if truth else None)
