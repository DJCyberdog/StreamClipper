"""Optional, local acoustic reaction evidence; no speaker or emotion identification."""
from pathlib import Path
import math
from .semantic import EventEvidence
from .media import CancelledError

LABELS={"laughter":"Lachen","laugh":"Lachen","giggle":"Kichern","chuckle, chortle":"Lachen",
        "screaming":"Schreien","scream":"Schreien","shout":"Rufen","shouting":"Rufen","yell":"Rufen"}

def reaction_labels(labels):
    return {int(k):LABELS[str(v).strip().casefold()] for k,v in labels.items()
            if str(v).strip().casefold() in LABELS}

def pitch_hz(samples,rate):
    """Conservative autocorrelation pitch proxy, not a voice/identity classifier."""
    import numpy as np
    x=np.asarray(samples,dtype=np.float32)
    if len(x)<rate//30:return None
    x=x-x.mean()
    if float(np.sqrt(np.mean(x*x)))<.015:return None
    low=max(1,rate//500);high=min(len(x)//3,rate//75)
    if high<=low+2:return None
    fft_size=1<<(2*len(x)-1).bit_length()
    power=np.abs(np.fft.rfft(x,n=fft_size))**2
    ac=np.fft.irfft(power,n=fft_size)[:high+2]
    if ac[0]<=0:return None
    ac=ac/ac[0]
    peaks=[i for i in range(low,high+1) if ac[i]>=ac[i-1] and ac[i]>ac[i+1] and ac[i]>=.55]
    if not peaks:return None
    strongest=max(ac[i] for i in peaks)
    lag=next(i for i in peaks if ac[i]>=.9*strongest)
    return rate/lag

def analyze_reactions(wav, duration, model_directory=None, *, anchors=(), budget=180,
                      cancelled=None, progress=None):
    """Read bounded windows from a user-designated original mic only.
    Optional HF audio classifier must provide named laugh/shout classes.
    The label scores are model outputs, not calibrated event probabilities.
    """
    import numpy as np
    import soundfile as sf
    from .gaming_intelligence import adaptive_samples
    if not 5<=budget<=600:raise ValueError("Invalid acoustic budget")
    positions=adaptive_samples(anchors,duration,budget)
    # Use every fifth point as a window center; avoid nearly identical samples.
    centers=[]
    for t in positions:
        if not centers or t-centers[-1]>=2:centers.append(t)
    model=extractor=None;labels={}
    if model_directory:
        import torch
        from transformers import AutoFeatureExtractor,AutoModelForAudioClassification
        folder=Path(model_directory).resolve(strict=True)
        extractor=AutoFeatureExtractor.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
        model=AutoModelForAudioClassification.from_pretrained(str(folder),local_files_only=True,trust_remote_code=False)
        labels=reaction_labels(model.config.id2label)
        if not labels:raise ValueError("Local audio model has no named laugh/shout classes")
        device="cuda" if torch.cuda.is_available() else "cpu"
        model.to(device).eval()
        from .vision_device import report_vision_device
        report_vision_device("Akustisches Reaktionsmodell",device)
    result=[]
    with sf.SoundFile(str(wav)) as f:
        rate=f.samplerate
        if not 8000<=rate<=192000:raise ValueError("Unsupported microphone rate")
        for i,t in enumerate(centers):
            if cancelled and cancelled():raise CancelledError("Reaktionsanalyse abgebrochen")
            start=max(0,t-2.0);end=min(duration,t+2.0)
            f.seek(min(f.frames,round(start*rate)))
            raw=f.read(max(1,round((end-start)*rate)),dtype="float32",always_2d=True)
            if len(raw)<rate//10:continue
            samples=raw.mean(axis=1)
            # Compare adjacent voiced 40 ms pitch estimates in the same window.
            step=max(1,round(.04*rate))
            pitches=[pitch_hz(samples[j:j+step],rate) for j in range(0,len(samples)-step+1,step)]
            first=[p for p in pitches[:len(pitches)//2] if p]
            second=[p for p in pitches[len(pitches)//2:] if p]
            if len(first)>=4 and len(second)>=4:
                shift=abs(12*math.log2(float(np.median(second))/float(np.median(first))))
                if shift>=4:
                    result.append(EventEvidence(round(t,3),"reaction",min(.55,.25+shift/40),
                       "Stimmlagenänderung auf zugeordneter Sprachspur (akustischer Hinweis)"))
            if model is not None:
                target=int(extractor.sampling_rate)
                if target!=rate:
                    import soxr
                    samples=soxr.resample(samples,rate,target)
                batch=extractor(samples,sampling_rate=target,return_tensors="pt")
                batch={k:v.to(device) for k,v in batch.items()}
                with torch.inference_mode():
                    logits=model(**batch).logits[0].float()
                    if not bool(torch.isfinite(logits).all()):raise RuntimeError("Non-finite audio classifier output")
                    # AudioSet models may be multi-label; use configured loss type.
                    scores=(logits.sigmoid() if model.config.problem_type=="multi_label_classification"
                            else logits.softmax(dim=-1)).cpu().tolist()
                key=max(labels,key=lambda j:scores[j])
                if scores[key]>=.5:
                    result.append(EventEvidence(round(t,3),"reaction",min(.75,.3+scores[key]*.45),
                        f"Akustische Modellähnlichkeit: {labels[key]} (nicht verifiziert)"))
            if progress:progress(min(99,round(100*(i+1)/max(1,len(centers)))))
    if progress:progress(100)
    return result
