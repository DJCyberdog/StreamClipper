"""M15f reproducible local metrics; no invented holdout or quality claim.
Case input is a manually annotated JSON manifest, not shipped recordings.
"""
from pathlib import Path
import math
import re
import json
import platform
import time
import hashlib
from .audio_separation import sha256_file

def _distance(a,b):
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):
            row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=row
    return previous[-1]

def text_errors(reference,hypothesis):
    def normalize(text):return re.findall(r"\w+",text.casefold())
    a,b=normalize(reference),normalize(hypothesis)
    chars1,chars2=list(" ".join(a)),list(" ".join(b))
    return {"word_errors":_distance(a,b),"reference_words":len(a),
            "wer":_distance(a,b)/len(a) if a else None,
            "char_errors":_distance(chars1,chars2),"reference_chars":len(chars1),
            "cer":_distance(chars1,chars2)/len(chars1) if chars1 else None,
            "unexpected_words":len(b) if not a else None}

def cue_errors(reference,hypothesis):
    """Match only unique overlapping normalized text; unmatched reported."""
    used=set();starts=[];ends=[];tails=[]
    for cue in reference:
        matches=[(i,c) for i,c in enumerate(hypothesis) if i not in used
            and max(c["start"],cue["start"])<min(c["end"],cue["end"])
            and re.findall(r"\w+",c["text"].casefold())==re.findall(r"\w+",cue["text"].casefold())]
        if len(matches)!=1:continue
        i,c=matches[0];used.add(i)
        starts.append(abs(c["start"]-cue["start"]));ends.append(abs(c["end"]-cue["end"]))
        tails.append(max(0.,c["end"]-cue["end"]))
    return {"matched":len(used),"reference_cues":len(reference),"hypothesis_cues":len(hypothesis),
        "start_mae":sum(starts)/len(starts) if starts else None,
        "end_mae":sum(ends)/len(ends) if ends else None,
        "mean_trailing_seconds":sum(tails)/len(tails) if tails else None,
        "trailing_over_250ms":sum(x>.25 for x in tails)}

def signal_metrics(reference,estimate,interferer=None):
    """Aligned PCM sample metrics, float64 accumulated in bounded windows.
    SI-SDR uses zero-mean mono channel projection; no shift optimization.
    Leakage is energy projected onto interferer orthogonal to target.
    """
    import soundfile as sf
    import numpy as np
    from contextlib import ExitStack
    with ExitStack() as stack:
        files=[stack.enter_context(sf.SoundFile(p)) for p in (reference,estimate,*([interferer] if interferer else []))]
        geometry=(files[0].samplerate,files[0].frames)
        if any((f.samplerate,f.frames)!=geometry for f in files):raise ValueError("Benchmarkspuren nicht ausgerichtet")
        sums=np.zeros(len(files));cross=np.zeros((len(files),len(files)));n=0;peak=0.;clips=0
        while True:
            blocks=[f.read(65536,dtype="float64",always_2d=True) for f in files]
            if not len(blocks[0]):break
            if not all(np.isfinite(x).all() for x in blocks):raise ValueError("Nicht endliche Benchmarkdaten")
            peak=max(peak,float(np.max(np.abs(blocks[1]))));clips+=int(np.count_nonzero(np.abs(blocks[1])>=1))
            mat=np.stack([x.mean(axis=1) for x in blocks])
            sums+=mat.sum(axis=1);cross+=mat@mat.T;n+=mat.shape[1]
        if not n:raise ValueError("Leere Benchmarkspur")
        cross-=np.outer(sums,sums)/n
        r,e,rel=float(cross[0,0]),float(cross[1,1]),float(cross[0,1])
        target=rel**2/r if r>1e-15 else 0.
        err=max(0.,e-target)
        si=10*math.log10(target/err) if target>1e-15 and err>1e-15 else None
        leakage=None
        if len(files)==3 and r>1e-15:
            orth=float(cross[2,2]-cross[0,2]**2/r)
            dot=float(cross[1,2]-cross[0,2]*rel/r)
            if orth>1e-15 and e>1e-15:leakage=max(0.,min(1.,dot**2/(orth*e)))
        return {"si_sdr_db":si,"target_energy":r,"estimate_energy":e,"interference_projection_ratio":leakage,
            "sample_peak":peak,"samples_at_or_above_full_scale":clips,"frames":n}

def evaluate_manifest(path):
    """Offline metrics on supplied real or synthetic artifacts. Never labels
    unmeasured metrics as PASS. No inference invoked by this evaluator.
    """
    path=Path(path).resolve(strict=True);doc=json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema_version")!=1 or not doc.get("cases"):raise ValueError("Benchmarkmanifest fehlt")
    def local(value):
        p=(path.parent/value).resolve(strict=True)
        if not p.is_file():raise ValueError("Benchmarkdatei fehlt")
        return p
    rows=[];ids=set();groups={}
    for case in doc["cases"]:
        if case["id"] in ids:raise ValueError("Doppelte Benchmark-ID")
        ids.add(case["id"])
        split=case["split"]
        if split not in ("development","holdout"):raise ValueError("Ungültiger Split")
        group=case["speaker_group"]
        if group in groups and groups[group]!=split:raise ValueError("Sprechergruppe in beiden Splits")
        groups[group]=split
        ref=local(case["reference_voice"]);mix=local(case["mix"]);estimate=local(case["estimate"])
        interference=local(case["interferer"]) if case.get("interferer") else None
        baseline=signal_metrics(ref,mix,interference);variant=signal_metrics(ref,estimate,interference)
        a,b=baseline["si_sdr_db"],variant["si_sdr_db"]
        row={"id":case["id"],"split":split,"language":case["language"],"conditions":case["conditions"],
             "inputs_sha256":{k:sha256_file(v) for k,v in (("reference",ref),("mix",mix),("estimate",estimate))},
             "baseline":baseline,"variant":variant,"si_sdr_improvement_db":b-a if a is not None and b is not None else None}
        for key in ("baseline_cues","variant_cues","timing_proposals_cues"):
            if key in case:
                cues=json.loads(local(case[key]).read_text(encoding="utf-8"))
                row[key]={"text":text_errors(" ".join(c["text"] for c in case["reference_cues"])," ".join(c["text"] for c in cues)),
                          "timing":cue_errors(case["reference_cues"],cues)}
        row["runtime_seconds"]=case.get("runtime_seconds");row["separation_seconds"]=case.get("separation_seconds");row["peak_ram_bytes"]=case.get("peak_ram_bytes");row["peak_vram_bytes"]=case.get("peak_vram_bytes")
        rows.append(row)
    return {"schema_version":1,"manifest_sha256":sha256_file(path),"evidence_kind":doc.get("evidence_kind","unspecified"),
            "model":doc.get("model"),"commit":doc.get("commit"),"platform":platform.platform(),
            "cases":rows,"quality_acceptance":"NOT_EVALUATED"}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("manifest");p.add_argument("output");a=p.parse_args()
    report=evaluate_manifest(a.manifest)
    with Path(a.output).open("x",encoding="utf-8") as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=="__main__":main()
