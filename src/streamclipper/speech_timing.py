"""Conservative, reviewable timing proposals from independently measured speech intervals."""
from dataclasses import dataclass,replace
import math
from .models import TranscriptSegment

@dataclass(frozen=True)
class TimingProposal:
    row:int
    before:TranscriptSegment
    after:TranscriptSegment
    reason:str

def propose_timings(cues, speech_intervals, *, duration, protected_rows=(), padding=.12, minimum_change=.25):
    """Only shorten boundaries supported by speech evidence; never infer words.
    Input intervals must originate from a speech detector, not mixed RMS.
    Caller must explicitly protect manually edited cue rows.
    """
    if not all(math.isfinite(v) for v in (duration,padding,minimum_change)) or duration<=0 or not 0<=padding<=.5 or not .05<=minimum_change<=2:
        raise ValueError("Ungültige Timingparameter")
    spans=tuple(speech_intervals)
    last=0.
    for a,b in spans:
        if not all(math.isfinite(v) for v in (a,b)) or not last<=a<b<=duration:
            raise ValueError("Ungültige oder überlappende Sprachintervalle")
        last=b
    protected=set(protected_rows)
    proposals=[]
    for i,cue in enumerate(cues):
        if i in protected or any(w.origin=="manual" for w in cue.words):continue
        if not 0<=cue.start<cue.end<=duration+.1:raise ValueError("Ungültiger Cue")
        hits=[(max(a,cue.start),min(b,cue.end)) for a,b in spans if a<cue.end and b>cue.start]
        if not hits:continue
        # Multiple separated speech islands may belong to different speakers;
        # only trim the external edges, never split or delete their contents.
        a=max(cue.start,hits[0][0]-padding)
        b=min(cue.end,hits[-1][1]+padding)
        # Word timestamps are not independently aligned; preserve their bounds.
        if cue.words:
            a=min(a,min(w.start for w in cue.words))
            b=max(b,max(w.end for w in cue.words))
        a=max(a,cue.start);b=min(b,cue.end)
        if a-cue.start<minimum_change:a=cue.start
        if cue.end-b<minimum_change:b=cue.end
        a,b=round(a,3),round(b,3)
        if b-a<.15 or (a,b)==(cue.start,cue.end):continue
        proposals.append(TimingProposal(i,cue,replace(cue,start=a,end=b),
            "Sprachintervall begrenzt Vor-/Nachlauf; Wortzeiten unverändert"))
    return tuple(proposals)

def apply_proposals(result, proposals):
    """Explicit commit of reviewed proposals; stale snapshots fail closed."""
    from .transcript_editor import validate_segments
    cues=list(result.transcript)
    seen=set()
    for p in proposals:
        if not 0<=p.row<len(cues) or p.row in seen or cues[p.row]!=p.before:
            raise ValueError("Timingvorschlag ist veraltet oder doppelt")
        if p.after.text!=p.before.text or p.after.words!=p.before.words or not p.before.start<=p.after.start<p.after.end<=p.before.end:
            raise ValueError("Timingvorschlag verändert Text, Wörter oder erweitert Grenzen")
        seen.add(p.row);cues[p.row]=p.after
    validate_segments(cues,result.video.duration)
    return replace(result,transcript=cues)
