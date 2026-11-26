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
    from bisect import bisect_right,bisect_left
    starts=[a for a,b in spans];ends=[b for a,b in spans]
    protected=set(protected_rows)
    proposals=[]
    for i,cue in enumerate(cues):
        if i in protected or cue.review_origin=="manual" or any(w.origin=="manual" for w in cue.words):continue
        if not 0<=cue.start<cue.end<=duration+.1:raise ValueError("Ungültiger Cue")
        hits=[(max(a,cue.start),min(b,cue.end)) for a,b in spans[bisect_right(ends,cue.start):bisect_left(starts,cue.end)]]
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


@dataclass(frozen=True)
class PauseSplitProposal:
    row:int
    before:TranscriptSegment
    parts:tuple[TranscriptSegment,...]
    reason:str="VAD-Pause zwischen unveränderten Whisper-Wörtern"

def propose_pause_splits(result,speech_intervals,*,padding=.12,minimum_pause=.65):
    """Explicit review proposals only. Both neighboring words must overlap
    separate detected speech islands, and the complete gap must be supported.
    Never split translated, legacy, manually edited or estimated-word cues.
    """
    from bisect import bisect_right,bisect_left
    from .subtitle_translation import cue_key
    from .transcript_editor import validate_segments
    duration=result.video.duration
    if not 0<=padding<=.3 or not .5<=minimum_pause<=3:raise ValueError("Ungültige Pausenparameter")
    spans=tuple(speech_intervals);last=0.
    for a,b in spans:
        if not all(math.isfinite(v) for v in (a,b)) or not last<=a<b<=duration:
            raise ValueError("Ungültige Sprachintervalle")
        last=b
    starts=[a for a,b in spans];ends=[b for a,b in spans]
    translated={t.source_sha256 for t in result.translations}
    validate_segments(result.transcript,duration)
    out=[]
    for row,cue in enumerate(result.transcript):
        words=cue.words
        if cue.review_origin not in ("asr","vad") or len(words)<2 or cue_key(cue) in translated:continue
        if any(w.origin!="whisper" or not cue.start<=w.start<w.end<=cue.end for w in words):continue
        if any(a.end>b.start for a,b in zip(words,words[1:])):continue
        if " ".join(cue.text.split())!=" ".join(w.text for w in words):continue
        breaks=[]
        for i,(left,right) in enumerate(zip(words,words[1:]),1):
            if right.start-left.end<minimum_pause:continue
            li=bisect_left(starts,left.end)-1;ri=bisect_right(ends,right.start)
            if not 0<=li<ri<len(spans) or ri!=li+1:continue
            if ends[li]<=left.start or starts[ri]>=right.end:continue
            if min(right.start,starts[ri])-max(left.end,ends[li])<minimum_pause:continue
            end=round(min(right.start,left.end+padding),3)
            start=round(max(left.end,right.start-padding),3)
            if end>=start:continue
            breaks.append((i,end,start))
        if not breaks:continue
        parts=[];offset=0;start=cue.start
        for i,end,next_start in breaks:
            part=words[offset:i]
            parts.append(TranscriptSegment(start,end," ".join(w.text for w in part),part,"vad"))
            start=next_start;offset=i
        part=words[offset:]
        parts.append(TranscriptSegment(start,cue.end," ".join(w.text for w in part),part,"vad"))
        validate_segments(parts,duration)
        out.append(PauseSplitProposal(row,cue,tuple(parts)))
    return tuple(out)

def apply_pause_splits(result,proposals):
    from .subtitle_translation import cue_key
    from .transcript_editor import validate_segments
    translated={t.source_sha256 for t in result.translations}
    cues=list(result.transcript);seen=set()
    for p in sorted(proposals,key=lambda p:p.row,reverse=True):
        if not 0<=p.row<len(cues) or p.row in seen or cues[p.row]!=p.before or p.before.review_origin not in ("asr","vad") or cue_key(p.before) in translated:
            raise ValueError("Pausenteilung veraltet oder geschützt")
        if any(w.origin!="whisper" for w in p.before.words) or len(p.parts)<2 or tuple(w for c in p.parts for w in c.words)!=p.before.words:
            raise ValueError("Pausenteilung verändert Wortdaten")
        if " ".join(c.text for c in p.parts)!=" ".join(p.before.text.split()) or any(
            c.review_origin!="vad" or c.text!=" ".join(w.text for w in c.words)
            or not p.before.start<=c.start<c.end<=p.before.end or not c.words
            or any(not c.start<=w.start<w.end<=c.end for w in c.words) for c in p.parts):
            raise ValueError("Ungültige Pausenteilung")
        if any(a.end>b.start for a,b in zip(p.parts,p.parts[1:])):raise ValueError("Pausenteilung überlappt")
        validate_segments(p.parts,result.video.duration)
        seen.add(p.row);cues[p.row:p.row+1]=p.parts
    return replace(result,transcript=cues)
