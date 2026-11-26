"""M16 experimental evidence engine. Scores are heuristic, not probabilities."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from bisect import bisect_left, bisect_right
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from .models import Candidate
from .semantic import EventEvidence

PROFILES = {
    "generic": {"audio": .25, "speech": .75, "motion": .45, "visual": .65, "object": .65, "reaction": .50},
    "open-world": {"audio": .20, "speech": .70, "motion": .42, "visual": .75, "object": .75, "reaction": .50},
}
GROUP = {"audio": "audio", "speech": "speech", "speech_context": "speech", "reaction": "speech",
         "motion": "image", "visual": "image", "object": "image", "chat": "chat"}

def checked_events(events, duration):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid duration")
    return sorted((e for e in events if e.kind in GROUP and math.isfinite(e.at)
                   and 0 <= e.at <= duration and math.isfinite(e.strength) and 0 <= e.strength <= 1),
                  key=lambda e: (e.at, e.kind, e.description))

def adaptive_samples(events, duration, budget=180):
    """Reserve >=20% of center budget for time-stratified quiet controls."""
    if not 5 <= budget <= 2000:
        raise ValueError("Frame budget must be 5–2000")
    valid = checked_events(events, duration)
    centers = max(1, budget // 5)
    controls = max(1, math.ceil(centers * .2))
    picks = []
    spacing = min(6., duration / max(centers * 2, 1))
    def add(t):
        if all(abs(t - p) >= spacing for p in picks):
            picks.append(t)
    # Choose least active position among nine fixed probes per time stratum.
    times = [e.at for e in valid]
    def activity(t):
        l, h = bisect_left(times, t - 3), bisect_right(times, t + 3)
        return sum(e.strength for e in valid[l:h])
    for i in range(controls):
        probes = [duration * (i + (j + .5)/9) / controls for j in range(9)]
        add(min(probes, key=lambda t: (activity(t), abs(t - duration*(i+.5)/controls))))
    hot = [e for e in valid if e.kind not in ("speech_context", "chat")]
    # Distribute high priority anchors across the whole recording.
    for i in range(centers - controls):
        lo = duration*i/max(1,centers-controls)
        hi = duration*(i+1)/max(1,centers-controls)
        options = sorted((e for e in hot if lo <= e.at <= hi), key=lambda e: (-e.strength,e.at))
        for event in options:
            n = len(picks)
            add(event.at)
            if len(picks)>n: break
    for e in sorted(hot, key=lambda e: (-e.strength,e.at)):
        if len(picks)>=centers: break
        add(e.at)
    for i in range(centers):
        if len(picks)>=centers: break
        add(duration*(i+.5)/centers)
    return sorted({round(max(0., min(max(0.,duration-.03), t+o)),3)
                   for t in picks for o in (-2.,-1.,0.,1.,2.)})[:budget]

def rank(events, duration, clip_seconds=25, max_clips=8, profile="generic", preferences=None):
    """Group dependent observations before scoring; never infer an action label."""
    from .analyze import _bounds
    if profile not in PROFILES or clip_seconds < 5 or not 1 <= max_clips <= 1000:
        raise ValueError("Invalid rank configuration")
    weights = PROFILES[profile]
    valid = checked_events(events,duration)
    times = [e.at for e in valid]
    proposals=[]
    for anchor in valid:
        if anchor.kind in ("audio","speech_context","chat"): continue
        nearby=valid[bisect_left(times,anchor.at-5):bisect_right(times,anchor.at+5)]
        best={}
        for e in nearby:
            if e.kind in ("chat","speech_context"): continue
            group=GROUP[e.kind]
            score=e.strength*weights[e.kind]*max(.2,1-abs(e.at-anchor.at)/7)
            if group not in best or score>best[group][0]:
                best[group]=(score,e)
        if not best: continue
        values=sorted((v[0] for v in best.values()),reverse=True)
        score=100*(values[0]+.35*sum(values[1:]))
        if anchor.kind=="motion" and "speech" not in best:
            score*=.7
        if any("Abrupter Bildwechsel" in e.description for e in nearby if e.kind=="motion"):
            score*=.85
        if preferences:
            score+=max(-10,min(10,float(preferences.get(anchor.kind,0))))
        # One observation family can never independently score as several.
        reasons=[f"{e.kind} {e.at:.1f}s ({e.at-anchor.at:+.1f}s): {e.description}"
                 for _,e in sorted(best.values(),key=lambda pair:-pair[0])]
        context=[e.description for e in nearby if e.kind=="speech_context"]
        if context: reasons.append("Kontext (nicht unabhängig): "+context[0])
        if any(e.kind=="chat" for e in nearby): reasons.append("Chat-Aktivität (nur Kontext)")
        if any("Abrupter Bildwechsel" in e.description for e in nearby): reasons.append("Gegenhinweis: Schnitt/Kamera möglich")
        start,end=_bounds(anchor.at,duration,clip_seconds)
        proposals.append(Candidate(start,end,max(0,min(99,round(score))),
                         "Heuristik | "+" | ".join(reasons),round(anchor.at,3)))
    chosen=[]
    for c in sorted(proposals,key=lambda c:(-c.score,c.peak_at,c.reason)):
        if any(c.start<q.end and q.start<c.end for q in chosen): continue
        chosen.append(c)
        if len(chosen)>=max_clips: break
    return chosen

def speech_reaction_hints(levels, duration, *, designated_microphone=False):
    """Acoustic level-change proxy; no laugh/scream/emotion classification."""
    if not designated_microphone: return []
    import statistics
    out=[]
    for i in range(4,len(levels)):
        history=levels[max(0,i-8):i]
        if not all(math.isfinite(v) for v in [levels[i],*history]): continue
        delta=levels[i]-statistics.median(history)
        if levels[i]>-48 and delta>=9:
            out.append(EventEvidence(min(duration,i+.5),"reaction",min(.7,delta/30),
                        "Pegelanstieg auf zugeordneter Sprachspur; Reaktion nicht verifiziert"))
    return checked_events(out,duration)

def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,mode="w",encoding="utf-8",delete=False) as f:
        tmp=Path(f.name)
        try:
            json.dump(value,f,ensure_ascii=False,allow_nan=False,sort_keys=True)
            f.flush();os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True);raise
    try: os.replace(tmp,path)
    finally: tmp.unlink(missing_ok=True)

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def store_evidence(path, key, events, duration):
    payload={"schema_version":1,"identity":key,"duration":duration,
             "events":[asdict(e) for e in checked_events(events,duration)]}
    atomic_json(path,{"payload":payload,"sha256":digest(payload)})

def load_evidence(path,key,duration):
    doc=json.loads(Path(path).read_text(encoding="utf-8"));p=doc["payload"]
    if doc["sha256"]!=digest(p) or p["schema_version"]!=1 or p["identity"]!=key or p["duration"]!=duration:
        raise ValueError("Stale or damaged evidence")
    events=[EventEvidence(**row) for row in p["events"]]
    valid=checked_events(events,duration)
    if len(valid)!=len(events): raise ValueError("Invalid evidence")
    return valid

def feedback_preferences(rows):
    """Explicit local development feedback; never learn from holdout rows."""
    totals={};counts={}
    for r in rows:
        if r.get("split")!="development": continue
        kind=r.get("kind")
        if kind not in ("speech","motion","visual","object","reaction"): continue
        vote=r.get("vote")
        if vote not in (-1,1): raise ValueError("Feedback vote must be -1 or +1")
        totals[kind]=totals.get(kind,0)+vote;counts[kind]=counts.get(kind,0)+1
    return {k:round(8*totals[k]/(counts[k]+4),3) for k in totals}

def chat_hints(messages,duration,window=10):
    """Local relative-time message counts; no identity retention or virality claim."""
    if not math.isfinite(window) or not 1<=window<=60: raise ValueError("Invalid chat window")
    counts={}
    for row in messages:
        t=float(row["at"])
        if math.isfinite(t) and 0<=t<duration:
            bucket=int(t/window);counts[bucket]=counts.get(bucket,0)+1
    if not counts: return []
    import statistics
    baseline=statistics.median(counts.values())
    return [EventEvidence(min(duration,(b+.5)*window),"chat",min(.5,n/max(1,baseline)/10),
                          f"Lokaler Chat: {n} Nachrichten/{window}s (nur Kontext)")
            for b,n in sorted(counts.items()) if n>=max(3,baseline*2)]

def search_transcript(cues,query,limit=50):
    """Literal lexical baseline, NOT semantic embedding search."""
    import re
    terms=set(re.findall(r"\w+",query.casefold()))
    if not terms or not 1<=limit<=1000: return []
    hits=[]
    for cue in cues:
        words=set(re.findall(r"\w+",cue.text.casefold()))
        n=len(terms & words)
        if n: hits.append((n/len(terms),cue))
    return [cue for _,cue in sorted(hits,key=lambda p:(-p[0],p[1].start))[:limit]]
