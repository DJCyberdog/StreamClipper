"""Conservative sparse subject and overlay proposals on bounded grayscale frames."""
from __future__ import annotations

import math
from .scene_camera import CameraKeyframe

W,H=96,54


def probable_cut(previous,current):
    """Conservative global discontinuity veto, not a general shot detector.

    Spatial difference and histogram distance must BOTH be large. This avoids
    rejecting ordinary camera motion solely because pixels moved.
    """
    if len(previous)!=W*H or len(current)!=W*H:
        raise ValueError('Ungültiges Trackingbild')
    mad=sum(abs(a-b) for a,b in zip(previous,current))/(W*H)
    if mad<45:
        return False
    a=[0]*16;b=[0]*16
    for x,y in zip(previous,current):
        a[x//16]+=1;b[y//16]+=1
    return sum(abs(x-y) for x,y in zip(a,b))/(2*W*H)>.45


def follow_patch(frames, x, y, *, zoom=1.2):
    """Forward local matching; stop at weak or ambiguous matches, never relock."""
    if not (0<=x<=1 and 0<=y<=1):
        raise ValueError("Ungültiger Subject-Lock-Punkt")
    frames=iter(frames)
    try:
        at,first=next(frames)
    except StopIteration as exc:
        raise ValueError('Keine Trackingbilder') from exc
    if not math.isfinite(at) or at<0 or len(first)!=W*H:
        raise ValueError("Ungültiges Trackingbild")
    cx=max(3,min(W-4,round(x*(W-1))))
    cy=max(3,min(H-4,round(y*(H-1))))
    offsets=[(i,j) for i in range(-3,4) for j in range(-3,4)]
    patch=lambda frame,a,b: tuple(frame[(b+j)*W+a+i] for i,j in offsets)
    target=patch(first,cx,cy)
    if max(target)-min(target)<25:
        raise ValueError("Zu wenig Struktur am gewählten Punkt")
    keys=[CameraKeyframe(at,cx/(W-1),cy/(H-1),zoom)]
    previous=first
    for at,frame in frames:
        if not math.isfinite(at) or not 0 < at-keys[-1].at <= 1.0:
            break  # never bridge long unsampled gaps
        if len(frame)!=W*H:
            raise ValueError("Ungültiges Trackingbild")
        if probable_cut(previous,frame):
            break  # do not follow a matching HUD or logo across a hard cut
        scores=[]
        for a in range(max(3,cx-8),min(W-4,cx+8)+1):
            for b in range(max(3,cy-6),min(H-4,cy+6)+1):
                error=sum(abs(p-q) for p,q in zip(target,patch(frame,a,b)))/len(target)
                scores.append((error,a,b))
        score,a,b=min(scores)
        alternatives=[v for v,u,w in scores if abs(u-a)+abs(w-b)>=4]
        if score>28 or (alternatives and min(alternatives)-score<3):
            break
        cx,cy=a,b
        previous=frame
        keys.append(CameraKeyframe(at,cx/(W-1),cy/(H-1),zoom))
    return tuple(keys)


def edge_candidates(frames):
    """Suggest stable textured edge tiles only, not semantic HUD detection.

    Content may be static gameplay geometry. User confirmation is mandatory.
    """
    frames=list(frames)
    if len(frames)<3 or any(len(frame)!=W*H for _,frame in frames):
        return ()
    found=[]
    tiles=[(x,y,16,9) for y in range(0,H,9) for x in range(0,W,16)
           if y in (0,H-9) or x in (0,W-16)]
    for x,y,w,h in tiles:
        indices=[j*W+i for j in range(y,y+h) for i in range(x,x+w-1)]
        texture=sum(abs(frames[0][1][i]-frames[0][1][i+1]) for i in indices)/len(indices)
        variation=sum(abs(frame[i]-frames[0][1][i]) for _,frame in frames[1:] for i in indices)/((len(frames)-1)*len(indices))
        if texture>=12 and variation<=8:
            found.append((x/W,y/H,w/W,h/H))
    return tuple(found[:12])
