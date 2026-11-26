"""M17: deterministic, non-destructive story-aware clip boundaries."""
from dataclasses import dataclass,replace
from bisect import bisect_left,bisect_right
import math
from .models import Candidate,AnalysisResult

PROFILES={"short":(10.,30.),"social":(15.,60.),"extended":(20.,120.)}
@dataclass(frozen=True)
class StoryOptions:
    minimum:float=15.
    maximum:float=60.
    context:float=5.
    reaction:float=8.
    def validate(self):
        if not all(math.isfinite(x) for x in (self.minimum,self.maximum,self.context,self.reaction)):
            raise ValueError("Ungültiges Längenbudget")
        if not 5<=self.minimum<=self.maximum<=180 or not 0<=self.context<=20 or not 0<=self.reaction<=30:
            raise ValueError("Ungültiges Längenbudget")
        return self

def speech_spans(transcript,duration):
    """Prefer real/manual word timing over ASR segments with trailing silence."""
    rows=[]
    for cue in transcript:
        words=[w for w in cue.words if w.origin in ("whisper","manual") and 0<=w.start<w.end<=duration]
        a,z=(min(w.start for w in words),max(w.end for w in words)) if words else (cue.start,cue.end)
        if math.isfinite(a) and math.isfinite(z) and 0<=a<z<=duration:
            rows.append((a,z))
    merged=[]
    for a,z in sorted(rows):
        if merged and a<=merged[-1][1]+.15:
            merged[-1]=(merged[-1][0],max(z,merged[-1][1]))
        else:merged.append((a,z))
    return merged

def story_bounds(candidate,duration,transcript=(),events=(),options=StoryOptions()):
    options.validate()
    if candidate.origin!="auto":return candidate
    if not math.isfinite(duration) or not 0<=candidate.start<=candidate.peak_at<=candidate.end<=duration or candidate.start>=candidate.end:
        raise ValueError("Ungültiger Kandidat")
    t=candidate.peak_at
    budget=min(duration,options.maximum)
    minimum=min(duration,options.minimum)
    start=max(0,t-options.context);end=min(duration,t+options.reaction)
    # Attach only nearby related cues, not arbitrary distant loudness/chat.
    beats=sorted(e.at for e in events if e.kind in ("motion","object","visual","speech","reaction") and
                 math.isfinite(e.at) and math.isfinite(e.strength) and e.strength>=.4 and 0<=e.at<=duration
                 and t-options.context-6<=e.at<=t+options.reaction+12)
    for at in beats:
        if start-4<=at<=end+4:
            a,z=min(start,max(0,at-2)),max(end,min(duration,at+3))
            if z-a<=budget:start,end=a,z
    spans=speech_spans(transcript,duration)
    # A nearby complete utterance is a useful context/reaction boundary.
    for a,z in spans:
        if a<=start<z or (start-3<=a<=t and z>=start):
            if end-a<=budget:start=min(start,a)
        if a<=end<z or (end<=a<=end+2 and a<=t+options.reaction+5):
            if z-start<=budget:end=max(end,z)
    # Cut cues are weak boundary hints, never proof of a scene ending.
    cuts=sorted(e.at for e in events if e.kind=="motion" and "Abrupter Bildwechsel" in e.description
                and math.isfinite(e.at) and 0<=e.at<=duration)
    safe=lambda v:not any(a<v<z for a,z in spans)
    if cuts:
        before=[v for v in cuts if start-2<=v<=start and end-v<=budget and safe(v)]
        after=[v for v in cuts if end<=v<=end+2 and v-start<=budget and safe(v)]
        if before:start=max(before)
        if after:end=min(after)
    if end-start>budget:
        start=max(0,min(t-min(options.context,budget/3),duration-budget))
        end=start+budget
    if end-start<minimum:
        start=max(0,min(start-(minimum-(end-start))/2,duration-minimum))
        end=min(duration,start+minimum)
    # Prefer outward speech snapping if budget permits; report unavoidable cuts.
    for a,z in spans:
        if a<start<z and end-a<=budget:start=a
        if a<end<z and z-start<=budget:end=z
    warnings=[]
    if not safe(start) or not safe(end):warnings.append("Sprachgrenze im Längenbudget nicht sicher")
    reason=candidate.reason+" | Story-Vorschlag: Kontext/Ereignis/Reaktion (Heuristik)"
    if warnings:reason+=" | "+ "; ".join(warnings)
    return replace(candidate,start=max(0,round(start,3)),end=min(duration,round(end,3)),reason=reason)

def refine_result(result,events=(),options=StoryOptions()):
    """Rank stays fixed; merge overlapping automatic suggestions only when budget permits."""
    options.validate()
    manual=[c for c in result.candidates if c.origin!="auto"]
    autos=[]
    for c in result.candidates:
        if c.origin!="auto":continue
        new=story_bounds(c,result.video.duration,result.transcript,events,options)
        duplicates=[i for i,p in enumerate(autos) if min(p.end,new.end)>max(p.start,new.start)]
        if duplicates:
            i=duplicates[0];p=autos[i]
            a,z=min(p.start,new.start),max(p.end,new.end)
            if z-a<=options.maximum and abs(p.peak_at-new.peak_at)<=12:
                combined=replace(p,start=a,end=z,reason=p.reason+" | Nahe Storybeats zusammengeführt")
                if not any(j!=i and min(q.end,z)>max(q.start,a) for j,q in enumerate(autos)):
                    autos[i]=combined
            continue
        autos.append(new)
    return replace(result,candidates=autos+manual,method=result.method+"|m17-story-v1")

def length_variants(candidate,duration,transcript=()):
    """Exact 15/30/60 second budgets where possible, prioritizing complete speech."""
    rows=[]
    for seconds in (15,30,60):
        # Manual intervals remain untouched; variants are distinct proposals.
        copy=replace(candidate,origin="auto")
        c=story_bounds(copy,duration,transcript,(),StoryOptions(seconds,seconds,seconds*.3,seconds*.4))
        rows.append((f"{seconds}s",c))
    return rows

def hook_candidates(candidate,transcript=(),events=()):
    """Suggest timestamped openings, never invent speech or move the stored clip."""
    points=[(candidate.start,"Originaler Einstieg")]
    if candidate.start<=candidate.peak_at<candidate.end:
        points.append((candidate.peak_at,"Ereignismoment"))
    for a,z in speech_spans(transcript,candidate.end):
        if candidate.start<=a<min(candidate.end,candidate.peak_at+2):
            points.append((a,"Beginn eines Sprachabschnitts"))
    for e in events:
        if e.kind in ("visual","motion","reaction") and candidate.start<=e.at<candidate.end:
            points.append((e.at,"Evidenz-Hinweis: "+e.kind))
    seen=set();out=[]
    for t,label in points:
        key=round(t,3)
        if key not in seen:
            seen.add(key);out.append((key,label))
    return out[:12]

def chapters(duration,candidates,transcript=(),*,gap=90.,maximum=600.):
    """Coarse review segments, not inferred mission titles."""
    if not math.isfinite(duration) or duration<=0 or not 10<=gap<=maximum<=1800:raise ValueError("Ungültige Kapitelparameter")
    starts=[0.];anchors=sorted(c.peak_at for c in candidates if 0<=c.peak_at<duration)
    for a in anchors:
        if a-starts[-1]>=gap:starts.append(a)
    starts.append(duration);out=[]
    for a,z in zip(starts,starts[1:]):
        while z-a>maximum:
            out.append((a,a+maximum,"Aufnahmeabschnitt"));a+=maximum
        if z>a:out.append((a,z,"Aufnahmeabschnitt"))
    return out
