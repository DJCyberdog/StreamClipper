"""M16a: freeze authorized annotated VODs and evaluate paired predictions locally."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from .gaming_intelligence import atomic_json,digest

LABELS={"crash","chase","combat","success","surprise","laugh","story","other","none"}
NEGATIVES={"camera","menu","hud","loud_audio","ordinary_driving","conversation"}

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def freeze(manifest):
    p=Path(manifest);doc=json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema_version")!=1 or doc.get("authorized") is not True:
        raise ValueError("Explicit authorized versioned corpus required")
    groups={}; seen=set(); hashes=set(); rows=[]
    for v in doc["vods"]:
        vid=v["id"];group=v["creator_group"];split=v["split"]
        if not isinstance(vid,str) or not vid or vid in seen or not group or split not in ("development","holdout"):
            raise ValueError("Invalid VOD ID or split")
        if group in groups and groups[group]!=split: raise ValueError("Creator leakage")
        groups[group]=split;seen.add(vid)
        duration=float(v["duration"])
        if not math.isfinite(duration) or duration<=0: raise ValueError("Invalid duration")
        sha=file_hash(p.parent/v["path"])
        if sha in hashes: raise ValueError("Duplicate source bytes")
        hashes.add(sha)
        moments=[]; ids=set()
        for m in v["moments"]:
            mid=m["id"];a=float(m["start"]);z=float(m["end"]);label=m["label"]
            if not mid or mid in ids or not 0<=a<z<=duration or label not in LABELS:
                raise ValueError("Invalid annotation")
            ids.add(mid)
            uncertain=m.get("uncertain",False)
            if type(uncertain) is not bool: raise ValueError("Invalid uncertainty")
            moments.append(dict(id=mid,start=a,end=z,label=label,uncertain=uncertain,
                                negative_type=m.get("negative_type",""),reviewed=m.get("reviewed",False)))
        rows.append(dict(id=vid,creator_group=group,split=split,duration=duration,sha256=sha,
                         game=v["game"],language=v["language"],moments=moments))
    rows.sort(key=lambda x:x["id"])
    hold=[v for v in rows if v["split"]=="holdout"]
    all_m=[m for v in rows for m in v["moments"]]
    hm=[m for v in hold for m in v["moments"] if not m["uncertain"]]
    gaps=[]
    if len(all_m)<100: gaps.append("100 annotated moments")
    if len(hold)<2 or len({v["creator_group"] for v in hold})<2: gaps.append("independent holdout")
    if not any(v["split"]=="development" for v in rows): gaps.append("development split")
    if not any(m["label"]!="none" for m in hm): gaps.append("positive holdout")
    missing=NEGATIVES-{m["negative_type"] for m in hm if m["label"]=="none"}
    gaps.extend("negative:"+x for x in sorted(missing))
    if any(m["uncertain"] and not m["reviewed"] for m in all_m): gaps.append("second review for uncertain moments")
    payload={"schema_version":1,"vods":rows,"gaps":gaps}
    payload["corpus_sha256"]=digest(payload)
    return payload

def evaluate(vod,predictions,tolerance=3.):
    if not math.isfinite(tolerance) or not 0<=tolerance<=30: raise ValueError("Invalid tolerance")
    # Uncertain annotations excluded; unannotated predictions cannot be called false positives.
    # Full coverage must be independently declared; otherwise report unknown counts.
    positives=[m for m in vod["moments"] if m["label"]!="none" and not m["uncertain"]]
    negatives=[m for m in vod["moments"] if m["label"]=="none" and not m["uncertain"]]
    matched=set();hits=0;fp=0;unknown=0;duplicates=0;starts=[];ends=[]
    top_hits=top_reviewed=0
    for i,c in enumerate(predictions):
        a,z,t=(float(c[k]) for k in ("start","end","peak_at"))
        if not 0<=a<=t<=z<=vod["duration"] or a==z: raise ValueError("Invalid prediction")
        options=[m for m in positives if m["start"]-tolerance<=t<=m["end"]+tolerance]
        fresh=[m for m in options if m["id"] not in matched]
        reviewed=True
        if fresh:
            m=min(fresh,key=lambda m:abs(t-(m["start"]+m["end"])/2))
            matched.add(m["id"]);hits+=1
            starts.append(abs(a-m["start"]));ends.append(abs(z-m["end"]))
            if i<8:top_hits+=1
        elif options: duplicates+=1
        elif any(m["start"]<=t<=m["end"] for m in negatives): fp+=1
        else: unknown+=1;reviewed=False
        if i<8 and reviewed:top_reviewed+=1
    reviewed_seconds=0.;end=0.
    for a,z in sorted((m["start"],m["end"]) for m in negatives):
        reviewed_seconds+=max(0,z-max(a,end));end=max(end,z)
    return {"top8_hits":top_hits,"top8_reviewed":top_reviewed,"top8_predictions":min(8,len(predictions)),
            "precision_at_8_reviewed":top_hits/top_reviewed if top_reviewed else None,
            "recall":hits/len(positives) if positives else None,"hits":hits,"positives":len(positives),
            "known_false_positives":fp,"unknown_predictions":unknown,"duplicates":duplicates,
            "false_positives_per_reviewed_negative_hour":fp/(reviewed_seconds/3600) if reviewed_seconds else None,
            "negative_reviewed_seconds":reviewed_seconds,
            "start_mae":sum(starts)/len(starts) if starts else None,"end_mae":sum(ends)/len(ends) if ends else None}

def compare(lock,baseline,variant,tolerance=3.):
    check=dict(lock);stamp=check.pop("corpus_sha256")
    if digest(check)!=stamp: raise ValueError("Corpus lock integrity")
    for report in (baseline,variant):
        if report.get("corpus_sha256")!=stamp: raise ValueError("Wrong corpus")
    for key in ("model_sha256","settings_sha256","source_commit"):
        if not baseline.get(key) or baseline[key]!=variant.get(key):raise ValueError("Mismatched "+key)
    ids={v["id"] for v in lock["vods"]}
    if set(baseline["predictions"])!=ids or set(variant["predictions"])!=ids: raise ValueError("Different VOD coverage")
    rows=[]
    for v in lock["vods"]:
        if v["split"]!="holdout":continue
        rows.append({"vod":v["id"],"game":v["game"],"language":v["language"],
                     "baseline":evaluate(v,baseline["predictions"][v["id"]],tolerance),
                     "variant":evaluate(v,variant["predictions"][v["id"]],tolerance)})
    return {"schema_version":1,"corpus_sha256":stamp,"gaps":lock["gaps"],"tolerance_seconds":tolerance,
            "holdout":rows,"quality_acceptance":"NOT_EVALUATED"}

def main():
    import argparse
    p=argparse.ArgumentParser();s=p.add_subparsers(dest="command",required=True)
    f=s.add_parser("freeze");f.add_argument("manifest");f.add_argument("output")
    c=s.add_parser("compare")
    for a in ("lock","baseline","variant","output"):c.add_argument(a)
    a=p.parse_args()
    def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))
    result=freeze(a.manifest) if a.command=="freeze" else compare(read(a.lock),read(a.baseline),read(a.variant))
    if Path(a.output).exists():raise FileExistsError(a.output)
    atomic_json(a.output,result)
if __name__=="__main__":main()
