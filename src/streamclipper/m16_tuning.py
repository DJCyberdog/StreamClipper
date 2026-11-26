"""Development-only weight selection. Holdout annotations are never consulted."""
from dataclasses import asdict
from .gaming_intelligence import PROFILES,rank,digest
from .m16_benchmark import evaluate

def tune_weights(lock,development_evidence,profile="generic",clip_seconds=25):
    if profile not in PROFILES:raise ValueError("Unknown profile")
    dev=[v for v in lock["vods"] if v["split"]=="development"]
    if not dev or set(development_evidence)!={v["id"] for v in dev}:
        raise ValueError("Exactly the frozen development VOD IDs are required")
    if not any(m["label"]!="none" and not m["uncertain"] for v in dev for m in v["moments"]):
        raise ValueError("Development positives required")
    original=dict(PROFILES[profile]);variants=[original]
    # Small preregistered grid, deterministic. Do not optimize dozens of
    # parameters on a tiny corpus or call the heuristic calibrated.
    for kind in sorted(original):
        for delta in (-.15,.15):
            w=dict(original);w[kind]=round(max(0,min(1,w[kind]+delta)),3);variants.append(w)
    results=[]
    for w in variants:
        measurements=[]
        for v in dev:
            preds=rank(development_evidence[v["id"]],v["duration"],clip_seconds,8,profile,weights_override=w)
            measurements.append(evaluate(v,[asdict(c) for c in preds]))
        tp=sum(m["hits"] for m in measurements)
        positives=sum(m["positives"] for m in measurements)
        # Unreviewed predictions are conservatively not credited, not
        # relabelled negative. This objective is a tuning utility only.
        reviewed_hits=sum(m["top8_hits"] for m in measurements)
        precision=reviewed_hits/(8*len(dev))
        recall=tp/max(1,positives)
        objective=2*precision*recall/(precision+recall) if precision+recall else 0.
        results.append({"weights":w,"objective":objective,"recall":recall,
                        "top8_conservative_utility":precision})
    selected=max(enumerate(results),key=lambda x:(x[1]["objective"],-x[0]))[1]
    return {"schema_version":1,"profile":profile,"development_ids":sorted(development_evidence),
            "corpus_sha256":lock["corpus_sha256"],"selection":selected,"trials":results,
            "calibration":"heuristic_not_probability"}
