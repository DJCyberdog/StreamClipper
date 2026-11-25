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

def propose_timings(cues, speech_intervals, *, duration, protected_rows=(), padding=.12, minimum_change=.25, trim_outer_words=False):
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
        if i in protected or cue.review_origin=="manual" or any(w.origin=="manual" for w in cue.words):continue
        if not 0<=cue.start<cue.end<=duration+.1:raise ValueError("Ungültiger Cue")
        hits=[(max(a,cue.start),min(b,cue.end)) for a,b in spans if a<cue.end and b>cue.start]
        if not hits:continue
        # Multiple separated speech islands may belong to different speakers;
        # only trim the external edges, never split or delete their contents.
        a=max(cue.start,hits[0][0]-padding)
        b=min(cue.end,hits[-1][1]+padding)
        # Optional bounded edge estimate: VAD is not forced alignment.
        # Only last/first native word that actually overlaps the adjacent
        # speech island, no interior word edit, no invented exact time.
        words=list(cue.words)
        if trim_outer_words and cue.review_origin in ("asr","vad") and words and all(w.origin=="whisper" for w in words):
            first,last=words[0],words[-1]
            if a-first.start>=minimum_change and first.start<=hits[0][0]<first.end and first.end-a>=.08:
                words[0]=replace(first,start=round(a,3),origin="estimated")
            if last.end-b>=minimum_change and last.start<hits[-1][1]<=last.end and b-last.start>=.08:
                current=words[-1]
                if b-current.start>=.08:words[-1]=replace(current,end=round(b,3),origin="estimated")
        if words:
            a=min(a,min(w.start for w in words))
            b=max(b,max(w.end for w in words))
        a=max(a,cue.start);b=min(b,cue.end)
        if a-cue.start<minimum_change:a=cue.start
        if cue.end-b<minimum_change:b=cue.end
        a,b=round(a,3),round(b,3)
        if b-a<.15 or ((a,b)==(cue.start,cue.end) and tuple(words)==cue.words):continue
        proposals.append(TimingProposal(i,cue,replace(cue,start=a,end=b,words=tuple(words),review_origin="vad" if cue.review_origin!="legacy" else "legacy"),
            "VAD-Randwort geschätzt (kein Alignment)" if tuple(words)!=cue.words else "Sprachintervall begrenzt Vor-/Nachlauf; Wortzeiten unverändert"))
    return tuple(proposals)

def apply_proposals(result, proposals):
    """Explicit commit of reviewed proposals; stale snapshots fail closed."""
    from .transcript_editor import validate_segments
    cues=list(result.transcript)
    seen=set()
    for p in proposals:
        if not 0<=p.row<len(cues) or p.row in seen or cues[p.row]!=p.before:
            raise ValueError("Timingvorschlag ist veraltet oder doppelt")
        if p.before.review_origin=="manual" or any(w.origin=="manual" for w in p.before.words):
            raise ValueError("Manuell korrigierte Zeile geschützt")
        if p.after.text!=p.before.text or not valid_edge_changes(p.before.words,p.after.words) or not p.before.start<=p.after.start<p.after.end<=p.before.end:
            raise ValueError("Timingvorschlag verändert Text, Wörter oder erweitert Grenzen")
        seen.add(p.row);cues[p.row]=p.after
    validate_segments(cues,result.video.duration)
    return replace(result,transcript=cues)


def valid_edge_changes(before,after):
    if len(before)!=len(after):return False
    for i,(old,new) in enumerate(zip(before,after)):
        if old==new:continue
        if old.origin!="whisper" or new.origin!="estimated" or old.text!=new.text or not old.start<=new.start<new.end<=old.end:return False
        if i!=0 and new.start!=old.start:return False
        if i!=len(before)-1 and new.end!=old.end:return False
    return True
