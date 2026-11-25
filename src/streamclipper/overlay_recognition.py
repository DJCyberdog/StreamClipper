"""Local CLIP overlay proposals for M13c. No downloads or automatic activation.

Classification is relative prompt similarity, not a calibrated detection score.
Use bounded, predefined crop proposals; genuine localized detection remains a
separate validation target. Temporal intervals are sampled estimates.
"""
from dataclasses import dataclass
from io import BytesIO
import math

from .smart_director import OverlayZone, overlap, valid_rect

LABELS = (
    ("hud", "video game heads-up display, minimap, health bar or ammunition counter over gameplay"),
    ("topbar", "streaming overlay banner with channel branding and follower or subscriber counters"),
    ("chat", "livestream chat overlay with multiple usernames and chat messages"),
    ("facecam", "small webcam video inset showing a streamer in front of a camera"),
    ("alert", "temporary livestream follower subscriber or donation notification graphic"),
    ("graphic", "stream broadcast logo watermark or decorative overlay graphic"),
    ("gameplay", "ordinary uninterrupted video game scene without any superimposed interface"),
    ("menu", "in-game menu or cinematic scene, not a livestream broadcast overlay"),
)
REGIONS = (
    (0.,0.,1.,.14), (0.,.86,1.,.14),
    (0.,0.,.25,.30), (.75,0.,.25,.30),
    (0.,.70,.25,.30), (.75,.70,.25,.30),
    (0.,.20,.25,.60), (.75,.20,.25,.60),
    (.25,.15,.50,.35),
)
POSITIVE = frozenset(k for k,_ in LABELS[:6])
MAX_EVIDENCE_GAP = 2.5


@dataclass(frozen=True)
class OverlayHit:
    at: float
    region: tuple
    kind: str
    similarity: float


def classify(scores, at, region):
    if not math.isfinite(at) or at<0 or not valid_rect(region):
        return None
    if set(scores) != {k for k,_ in LABELS} or any(
            not math.isfinite(v) or not 0 <= v <= 1 for v in scores.values()):
        return None
    ranked=sorted(scores,key=scores.get,reverse=True)
    winner=ranked[0]
    value=scores[winner]
    if winner not in POSITIVE or value<.30 or value-scores[ranked[1]]<.08:
        return None
    return OverlayHit(at,region,winner,value)


def proposals(hits, timestamps, start, end, *, limit=24):
    """Require repeated non-alert evidence, keep transient alerts bounded.

    All proposals are disabled and unmasked until explicitly approved.
    """
    if type(limit) is not int or not 1<=limit<=24:
        raise ValueError('Ungültiges Vorschlagslimit')
    stamps=tuple(sorted(set(timestamps)))
    if not stamps:
        return ()
    index={t:i for i,t in enumerate(stamps)}
    groups={}
    for h in hits:
        if h.at in index:
            groups.setdefault((h.kind,h.region),{})[index[h.at]]=h
    ranked=[]
    for (kind,region), group in groups.items():
        runs=[]
        for i in sorted(group):
            if (runs and i==runs[-1][-1]+1
                    and stamps[i]-stamps[runs[-1][-1]]<=MAX_EVIDENCE_GAP):
                runs[-1].append(i)
            else:
                runs.append([i])
        for run in runs:
            if kind!="alert" and len(run)<2:
                continue
            a,b=run[0],run[-1]
            static=(kind!="alert" and len(run)==len(stamps)
                    and stamps[0]-start<=MAX_EVIDENCE_GAP/2
                    and end-stamps[-1]<=MAX_EVIDENCE_GAP/2)
            left=None if static else max(start, stamps[a] if a==0 else (stamps[a-1]+stamps[a])/2)
            right=None if static else min(end, end if b==len(stamps)-1 else (stamps[b]+stamps[b+1])/2)
            if not static:
                left=max(left,stamps[a]-MAX_EVIDENCE_GAP/2)
                right=min(right,stamps[b]+MAX_EVIDENCE_GAP/2)
            if not static and right<=left:
                continue
            zone=OverlayZone(kind,region,left,right,enabled=False,mask=False)
            zone.validate()
            ranked.append((sum(group[i].similarity for i in run)/len(run),len(run),zone))
    ranked.sort(key=lambda v:(-v[0],-v[1],v[2].kind,v[2].region))
    # Suppress nearly identical same-type proposals only when time supports
    # the same interval. Nested detections are not independent evidence.
    accepted=[]
    for _,_,zone in ranked:
        if any(zone.kind==prior.kind and (zone.start,zone.end)==(prior.start,prior.end)
               and overlap(zone.region,prior.region)/
                   (zone.region[2]*zone.region[3]+prior.region[2]*prior.region[3]
                    -overlap(zone.region,prior.region))>=.75 for prior in accepted):
            continue
        accepted.append(zone)
        if len(accepted)>=limit:
            break
    return tuple(accepted)


def recognize_overlays(video, model_directory, start, end, *, cancelled=None):
    from .media import sampled_jpeg_frames, CancelledError
    from .model_checks import validate_clip_model
    folder=validate_clip_model(model_directory)
    if not 0<=start<end<=video.duration+.1:
        raise ValueError("Ungültige Szenenzeit")
    try:
        import torch
        from PIL import Image
        from transformers import AutoProcessor, CLIPModel
    except ImportError as exc:
        raise RuntimeError('CLIP benötigt die vorhandene Python-Umgebung mit .[vision]') from exc
    processor=AutoProcessor.from_pretrained(str(folder),local_files_only=True)
    model=CLIPModel.from_pretrained(str(folder),local_files_only=True)
    device="cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()
    count=min(8,max(3,math.ceil(end-start)))
    right=min(end,video.duration)
    stamps=sorted(set(round(start+(right-start)*(i+.5)/count,3) for i in range(count)))
    stamps=[s for s in stamps if start<=s<right]
    hits=[]
    seen=[]
    for at,jpeg in sampled_jpeg_frames(video,max_frames=8,timestamps=stamps,cancelled=cancelled):
        seen.append(at)
        with Image.open(BytesIO(jpeg)) as raw:
            frame=raw.convert("RGB")
        w,h=frame.size
        for region in REGIONS:
            if cancelled and cancelled():
                raise CancelledError("Overlay-Analyse abgebrochen")
            x,y,rw,rh=region
            crop=frame.crop((int(x*w),int(y*h),math.ceil((x+rw)*w),math.ceil((y+rh)*h)))
            inputs=processor(text=[p for _,p in LABELS],images=crop,return_tensors="pt",padding=True)
            inputs={k:v.to(device) for k,v in inputs.items()}
            with torch.inference_mode():
                values=model(**inputs).logits_per_image.softmax(dim=1)[0].tolist()
            hit=classify(dict(zip((k for k,_ in LABELS),values)),at,region)
            if hit:
                hits.append(hit)
    return proposals(hits,seen,start,end)
