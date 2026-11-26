"""M15f -> M16/M17: speech evidence, never a proof of speaker or highlight."""
from dataclasses import asdict,dataclass
from .asr_quality import flags
from .transcript_editor import validate_segments
import hashlib
import json

@dataclass(frozen=True)
class SpeechEvidence:
    start:float
    end:float
    text:str
    timing_origin:str
    source_kind:str
    quality_flags:tuple[str,...]
    estimated_word_times:bool
    speaker_identity_verified:bool=False

def handoff(result):
    validate_segments(result.transcript,result.video.duration)
    method=result.method
    if "reconstructed=target_voice_estimate" in method:kind="target_voice_estimate"
    elif "reconstructed=foreground_voice_estimate" in method:kind="foreground_voice_estimate"
    elif "|asr:stream=" in method and ",role=microphone," in method:kind="user_designated_microphone"
    else:kind="original_or_unspecified_mix"
    events=[SpeechEvidence(c.start,c.end,c.text,c.review_origin,kind,flags(c),
          not c.words or any(w.origin=="estimated" for w in c.words)) for c in result.transcript]
    payload={"schema_version":1,"source":asdict(result.video),"method":method,
        "events":[asdict(e) for e in events],"limitations":["Speech activity is not a highlight classification.",
        "Speaker attribution and boundaries are uncertain; estimated timestamps are not forced alignment.",
        "M17 must combine speech boundaries with visual event context, not use Whisper segment ends alone."]}
    payload["transcript_sha256"]=hashlib.sha256(json.dumps([asdict(c) for c in result.transcript],
        sort_keys=True,ensure_ascii=False,allow_nan=False).encode("utf-8")).hexdigest()
    return payload
