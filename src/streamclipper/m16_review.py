"""M16e/f local review utilities. Never modify AnalysisResult or source files."""
from dataclasses import asdict
from pathlib import Path
from io import BytesIO
import json
import math
from .gaming_intelligence import atomic_json,feedback_preferences
from .media import sampled_jpeg_frames,CancelledError

def read_chat(path,duration):
    """Explicit local JSONL with relative VOD seconds; discard all text and identities."""
    if Path(path).suffix.casefold()==".json":
        from .m16_chat_import import parse_chat_export
        return parse_chat_export(path,duration)
    if Path(path).stat().st_size>64*1024*1024:raise ValueError("Chat file too large")
    result=[]
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():continue
            row=json.loads(line);t=float(row["at"])
            if not math.isfinite(t) or not 0<=t<=duration:raise ValueError("Chat outside VOD timebase")
            result.append({"at":t})
            if len(result)>1_000_000:raise ValueError("Chat message limit exceeded")
    return result

def read_feedback(path):
    path=Path(path)
    if not path.exists():return []
    if path.stat().st_size>8*1024*1024:raise ValueError("Feedback file too large")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema_version")!=1 or not isinstance(doc.get("rows"),list):raise ValueError("Invalid feedback")
    return doc["rows"]

def record_feedback(path,source_id,candidate,kind,vote,*,split="personal",corrected=None):
    if candidate.origin!="auto" or kind not in ("speech","motion","visual","object","reaction") or vote not in (-1,1):
        raise ValueError("Select an automatic suggestion and an explicit category/vote")
    if split not in ("personal","development","holdout"):raise ValueError("Invalid split")
    if corrected is not None and (len(corrected)!=2 or not 0<=corrected[0]<corrected[1] or not all(math.isfinite(t) for t in corrected)):
        raise ValueError("Invalid correction")
    rows=read_feedback(path)
    row={"source_id":source_id,"start":candidate.start,"end":candidate.end,"at":candidate.peak_at,
         "kind":kind,"vote":vote,"split":split,"corrected":corrected}
    # Last explicit decision for a given candidate/category wins.
    rows=[x for x in rows if (x["source_id"],x["at"],x["kind"])!=(source_id,candidate.peak_at,kind)]
    rows.append(row)
    atomic_json(path,{"schema_version":1,"rows":rows})

def personal_preferences(path):
    # Personal-use ranking only. The benchmark runner never loads these rows.
    rows=[{**r,"split":"development"} for r in read_feedback(path) if r.get("split")=="personal"]
    return feedback_preferences(rows)

def contact_sheet(video,candidates,destination,cancelled=None):
    from PIL import Image,ImageDraw
    rows=list(candidates)[:24]
    if not rows:raise ValueError("No suggestions")
    stamps=sorted({round(max(0,min(video.duration-.001,c.peak_at)),3) for c in rows})
    stamps=[t for t in stamps if t<video.duration]
    thumbs={}
    for t,raw in sampled_jpeg_frames(video,max_frames=len(stamps),timestamps=stamps,cancelled=cancelled):
        with Image.open(BytesIO(raw)) as src:
            src.thumbnail((300,169));thumbs[t]=src.convert("RGB")
    board=Image.new("RGB",(960,210*math.ceil(len(rows)/3)),(24,24,32));draw=ImageDraw.Draw(board)
    for i,c in enumerate(rows):
        if cancelled and cancelled():raise CancelledError("Kontaktbogen abgebrochen")
        x=(i%3)*320+10;y=(i//3)*210+8
        t=round(max(0,min(video.duration-.001,c.peak_at)),3)
        if t in thumbs:board.paste(thumbs[t],(x,y))
        draw.text((x,y+174),f"#{i+1} | {c.peak_at:.1f}s | {c.score}/99",fill="white")
        draw.text((x,y+190),f"{c.start:.1f} - {c.end:.1f}s",fill="white")
    dest=Path(destination)
    with dest.open("xb") as f:board.save(f,format="PNG")
    return dest

def semantic_transcript_search(cues,query,model_directory,limit=20,cancelled=None):
    """Opt-in local text embedding retrieval. Searches spoken content, not images."""
    import torch
    from transformers import AutoTokenizer,AutoModel
    root=Path(model_directory).resolve(strict=True)
    if not root.is_dir() or not (root/"config.json").is_file():raise ValueError("Local embedding model required")
    if not query.strip() or not 1<=limit<=100:raise ValueError("Invalid search")
    tokenizer=AutoTokenizer.from_pretrained(str(root),local_files_only=True,trust_remote_code=False)
    model=AutoModel.from_pretrained(str(root),local_files_only=True,trust_remote_code=False)
    model.eval()
    def embed(texts):
        batch=tokenizer(texts,padding=True,truncation=True,max_length=256,return_tensors="pt")
        with torch.no_grad():
            hidden=model(**batch).last_hidden_state
            mask=batch["attention_mask"].unsqueeze(-1)
            pooled=(hidden*mask).sum(1)/mask.sum(1).clamp(min=1)
            return torch.nn.functional.normalize(pooled,dim=1)
    q=embed([query]);hits=[]
    for i in range(0,len(cues),32):
        if cancelled and cancelled():raise CancelledError("Suche abgebrochen")
        batch=cues[i:i+32];scores=(embed([c.text for c in batch])@q.T).flatten().tolist()
        hits.extend(zip(scores,batch))
        hits=sorted(hits,key=lambda h:(-h[0],h[1].start))[:limit]
    return hits
