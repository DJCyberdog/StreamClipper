"""Real local Whisper + VAD + cache smoke, generated TTS, not gaming quality."""
import argparse
import json
import subprocess
import time
from dataclasses import asdict
from functools import partial
from pathlib import Path
import numpy as np
import soundfile as sf
import soxr
from streamclipper.audio_sources import inventory,SpeechSource,transcribe_selected_stream
from streamclipper.asr_window_cache import ASRWindowCache,model_identity
from streamclipper.models import VideoInfo,AnalysisResult
from streamclipper.semantic import transcribe_video
from streamclipper.speech_activity import detect_speech
from streamclipper.speech_timing import propose_timings,apply_proposals
from streamclipper.speech_benchmark import text_errors
from streamclipper.asr_quality import ASROptions,retry_cue,flags
from streamclipper.audio_separation import sha256_file

def main():
    p=argparse.ArgumentParser();p.add_argument("model");p.add_argument("output");args=p.parse_args()
    root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=False)
    model=Path(args.model).resolve(strict=True)
    assert sha256_file(model/"model.bin")=="dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1"
    cases=[]
    for language,voice,text in (("de","de","Heute fahren wir nach Hause. Das war knapp."),
          ("en","en-us","Today we are driving home. That was close.")):
        folder=root/language;folder.mkdir()
        wav=folder/"generated.wav"
        subprocess.run(["espeak-ng","-v",voice,"-s","150","-w",str(wav),text],check=True,timeout=30)
        audio,rate=sf.read(wav,dtype="float32",always_2d=True)
        samples=soxr.resample(audio.mean(axis=1),rate,48000).astype(np.float32)
        samples=np.concatenate((np.zeros(48000,dtype=np.float32),samples,np.zeros(48000*3,dtype=np.float32)))
        source=folder/"speech.wav";sf.write(source,samples,48000,subtype="FLOAT")
        snap=inventory(source);selected=SpeechSource(snap,snap.streams[0].index,"microphone")
        video=VideoInfo(str(source),snap.duration,1,1,1,True)
        cache=ASRWindowCache.for_whisper(folder/"cache",model)
        started=time.monotonic()
        cues=transcribe_selected_stream(video,str(model),selected,transcriber=partial(transcribe_video,model_cache={}),window_cache=cache)
        seconds=time.monotonic()-started
        assert cues and any(c.words for c in cues),"Whisper returned no aligned speech"
        assert all(c.review_origin=="asr" for c in cues)
        def forbidden(*a,**kw):raise AssertionError("Unexpected re-inference")
        cached=transcribe_selected_stream(video,str(model),selected,transcriber=forbidden,window_cache=cache)
        assert cached==cues and cache.hits==1
        spans=detect_speech(selected)
        assert spans and all(0<=a<b<=snap.duration for a,b in spans)
        result=AnalysisResult(video,[],method="smoke"+selected.method_suffix,transcript=cues)
        corrected=apply_proposals(result,propose_timings(cues,spans,duration=video.duration,trim_outer_words=True))
        # Exercise opt-in language and glossary backend, no automatic adoption.
        second=transcribe_video(video,str(model),quality_options=ASROptions(language,"GTA"))
        assert second
        cases.append({"language":language,"duration":snap.duration,"runtime_seconds":seconds,
            "raw_cues":[asdict(c) for c in cues],"vad":spans,"reviewed_proposals":[asdict(c) for c in corrected.transcript],
            "text_metrics":text_errors(text," ".join(c.text for c in cues)),
            "cache_hits":cache.hits,"retry_cues":[asdict(c) for c in second]})
    report={"evidence_kind":"generated_tts_real_asr_smoke","model_files":model_identity(model),
        "technical_contract":"PASS","gaming_quality_acceptance":"NOT_EVALUATED","cases":cases}
    (root/"asr_smoke.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
if __name__=="__main__":main()
