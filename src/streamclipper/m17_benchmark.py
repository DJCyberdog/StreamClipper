"""Independent annotated boundary metrics; do not substitute ranking score for quality."""
import math
from .analyze import _bounds

def compare_boundaries(candidates,story_candidates,moments,duration,clip_seconds=25):
    if not math.isfinite(duration) or duration<=0:raise ValueError("Invalid duration")
    before=[_bounds(c.peak_at,duration,clip_seconds) for c in candidates if c.origin=="auto"]
    after=[(c.start,c.end) for c in story_candidates if c.origin=="auto"]
    def measure(intervals):
        complete=early=late=matched=0;extra=[]
        for m in moments:
            if m.get("uncertain") or m.get("label")=="none":continue
            a,z=float(m["start"]),float(m["end"])
            if not 0<=a<z<=duration:raise ValueError("Invalid annotation")
            overlaps=[(s,e) for s,e in intervals if min(e,z)>max(s,a)]
            if not overlaps:continue
            s,e=max(overlaps,key=lambda p:(min(p[1],z)-max(p[0],a),-(p[1]-p[0])))
            matched+=1;complete+=int(s<=a and e>=z);early+=int(s>a);late+=int(e<z)
            # Outside annotated story, not automatically silence or irrelevant.
            extra.append(max(0,a-s)+max(0,e-z))
        total=sum(not m.get("uncertain") and m.get("label")!="none" for m in moments)
        return {"annotated_events":total,"matched":matched,"fully_contained":complete,
                "complete_fraction":complete/total if total else None,
                "cut_start":early,"cut_end":late,
                "mean_seconds_outside_annotation":sum(extra)/len(extra) if extra else None}
    return {"fixed":measure(before),"story":measure(after),"quality_acceptance":"NOT_EVALUATED",
            "note":"Outside-annotation time is not independently validated idle time."}
