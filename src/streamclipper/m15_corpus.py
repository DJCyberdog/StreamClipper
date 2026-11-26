"""Freeze local corpus inputs and compare paired M15 results. No automatic quality approval."""
import hashlib
import json
import math
from pathlib import Path
import re
from .audio_separation import sha256_file

REQUIRED_CONDITIONS=("overlapping_speech","game_music","target_absent","quiet_voice","code_switching")

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()

def read(path):
    path=Path(path).resolve(strict=True)
    if path.stat().st_size>32*1024*1024:raise ValueError("Manifest too large")
    return json.loads(path.read_text(encoding="utf-8"))

def freeze_corpus(manifest):
    import soundfile as sf
    path=Path(manifest).resolve(strict=True);doc=read(path)
    if doc.get("schema_version")!=1 or not doc.get("cases"):raise ValueError("Missing cases")
    real=doc.get("evidence_kind")=="real_authorized_gaming_holdout"
    seen=set();groups={};vods={};mixes=set();rows=[]
    for case in doc["cases"]:
        ident=case["id"];split=case["split"];group=case["speaker_group"];vod=case.get("vod_group")
        if not isinstance(ident,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}",ident) or ident in seen:
            raise ValueError("Invalid or duplicate case ID")
        seen.add(ident)
        if split not in ("development","holdout"):raise ValueError("Invalid split")
        if not isinstance(group,str) or not group.strip() or (real and (not isinstance(vod,str) or not vod.strip())):
            raise ValueError("Missing speaker or VOD group")
        for key,mapping in ((group,groups),(vod,vods)):
            if key is None:continue
            if key in mapping and mapping[key]!=split:raise ValueError("Group leakage")
            mapping[key]=split
        conditions=case["conditions"]
        if not isinstance(conditions,list) or not all(isinstance(x,str) for x in conditions):
            raise ValueError("Invalid conditions")
        if case["language"] not in ("de","en","mixed"):raise ValueError("Invalid language")
        files={};geometry={}
        for key in ("mix","reference_voice","reference_wav","interferer"):
            value=case.get(key)
            if not value:
                if key in ("mix","reference_voice") or (real and key=="reference_wav"):raise ValueError("Missing "+key)
                continue
            p=(path.parent/value).resolve(strict=True)
            info=sf.info(p)
            if not 0<info.frames or not 1<=info.channels<=2:raise ValueError("Invalid audio")
            if key=="reference_wav":
                if not 3<=info.duration<=30:raise ValueError("Enrollment duration 3–30 s required")
            elif info.samplerate!=48000 or info.duration>600:
                raise ValueError("Aligned 48 kHz corpus clips <=600 s required")
            files[key]=sha256_file(p);geometry[key]=[info.samplerate,info.frames,info.channels]
        if any(geometry[k][:2]!=geometry["mix"][:2] for k in geometry if k!="reference_wav"):
            raise ValueError("Unaligned corpus audio")
        if files["mix"] in mixes:raise ValueError("Duplicate mix")
        mixes.add(files["mix"])
        cues=case["reference_cues"]
        if not isinstance(cues,list):raise ValueError("Invalid cues")
        last=0.;duration=geometry["mix"][1]/48000
        for cue in cues:
            a,z=cue["start"],cue["end"]
            if not (math.isfinite(a) and math.isfinite(z) and last<=a<z<=duration
                    and isinstance(cue["text"],str) and cue["text"].strip()):
                raise ValueError("Invalid cue")
            last=a
        rows.append({"id":ident,"split":split,"speaker_group":group,"vod_group":vod,
            "language":case["language"],"conditions":conditions,"reference_cues_sha256":digest(cues),
            "audio_sha256":files,"geometry":geometry})
    holdout=[x for x in rows if x["split"]=="holdout"]
    coverage={"holdout_cases":len(holdout),"holdout_speakers":len({x["speaker_group"] for x in holdout}),
        "holdout_vods":len({x["vod_group"] for x in holdout if x["vod_group"] is not None}),
        "languages":sorted({x["language"] for x in holdout}),
        "conditions":sorted({c for x in holdout for c in x["conditions"]})}
    missing=[]
    if not real:missing.append("real_authorized_gaming_holdout")
    if coverage["holdout_speakers"]<2:missing.append("multiple_holdout_speakers")
    if coverage["holdout_vods"]<2:missing.append("multiple_holdout_vods")
    if not any(x["split"]=="development" for x in rows):missing.append("development_split")
    missing.extend("language:"+x for x in ("de","en") if x not in coverage["languages"])
    missing.extend("condition:"+x for x in REQUIRED_CONDITIONS if x not in coverage["conditions"])
    result={"schema_version":1,"evidence_kind":doc.get("evidence_kind","unspecified"),
            "cases":sorted(rows,key=lambda x:x["id"]),"coverage":coverage,"missing_coverage":missing}
    result["corpus_sha256"]=digest(result)
    return result

def verify_corpus(manifest,lock):
    current=freeze_corpus(manifest)
    if current!=read(lock):raise ValueError("Frozen corpus changed")
    return current

def compare_reports(left,right):
    a,b=read(left),read(right)
    for key in ("corpus_sha256","commit","asr_model_sha256"):
        if not a.get(key) or a[key]!=b.get(key):raise ValueError("Incompatible reports: "+key)
    def index(report):
        rows=report["cases"];out={x["id"]:x for x in rows}
        if len(out)!=len(rows):raise ValueError("Duplicate result case")
        return out
    ai,bi=index(a),index(b)
    if ai.keys()!=bi.keys():raise ValueError("Different cases")
    pairs=[]
    for ident,x in ai.items():
        y=bi[ident]
        for key in ("split","language","conditions","frozen_case_sha256"):
            if x.get(key)!=y.get(key):raise ValueError("Different case metadata")
        if not x.get("frozen_case_sha256"):raise ValueError("Missing case hash")
        for key in ("reference","mix","interferer"):
            if x["inputs_sha256"].get(key)!=y["inputs_sha256"].get(key):raise ValueError("Different reference audio")
        if x["split"]=="holdout":pairs.append((x,y))
    if not pairs:raise ValueError("No holdout")
    def summary(rows):
        out={}
        for name,i in (("left",0),("right",1)):
            rr=[p[i] for p in rows]
            def mean(values):
                valid=[v for v in values if isinstance(v,(float,int)) and math.isfinite(v)]
                return {"value":sum(valid)/len(valid) if valid else None,"measured":len(valid)}
            q={"cases":len(rr),"si_sdr_improvement_db":mean([v.get("si_sdr_improvement_db") for v in rr]),
                "leakage_projection_ratio":mean([v["variant"].get("interference_projection_ratio") for v in rr]),
                "runtime_seconds":mean([v.get("runtime_seconds") for v in rr])}
            for k in ("baseline_cues","variant_cues","timing_proposals_cues"):
                texts=[v[k]["text"] for v in rr if k in v];timings=[v[k]["timing"] for v in rr if k in v]
                words=sum(t["reference_words"] for t in texts);errs=sum(t["word_errors"] for t in texts)
                chars=sum(t["reference_chars"] for t in texts);ce=sum(t["char_errors"] for t in texts)
                matched=sum(t["matched"] for t in timings)
                q[k]={"wer":errs/words if words else None,"cer":ce/chars if chars else None,
                      "word_errors":errs,"reference_words":words,"measured_cases":len(texts),
                      "unexpected_words_in_empty_reference":sum(t.get("unexpected_words") or 0 for t in texts),
                      "matched_cues":matched,"reference_cues":sum(t["reference_cues"] for t in timings),
                      "end_mae":sum(t["end_mae"]*t["matched"] for t in timings if t["end_mae"] is not None)/matched if matched else None}
            out[name]=q
        return out
    return {"schema_version":1,"corpus_sha256":a["corpus_sha256"],"commit":a["commit"],
        "left_model":a.get("model"),"right_model":b.get("model"),
        "reports_sha256":[sha256_file(left),sha256_file(right)],"holdout":summary(pairs),
        "by_language":{lang:summary([p for p in pairs if p[0]["language"]==lang])
                       for lang in sorted({p[0]["language"] for p in pairs})},
        "by_condition":{c:summary([p for p in pairs if c in p[0]["conditions"]])
                        for c in sorted({c for p in pairs for c in p[0]["conditions"]})},
        "quality_acceptance":"NOT_EVALUATED"}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="action",required=True)
    f=sub.add_parser("freeze");f.add_argument("manifest");f.add_argument("output")
    c=sub.add_parser("compare");c.add_argument("left");c.add_argument("right");c.add_argument("output")
    a=p.parse_args()
    result=freeze_corpus(a.manifest) if a.action=="freeze" else compare_reports(a.left,a.right)
    with Path(a.output).open("x",encoding="utf-8") as out:json.dump(result,out,indent=2,ensure_ascii=False,allow_nan=False)
if __name__=="__main__":main()
