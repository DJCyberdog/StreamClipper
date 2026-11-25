"""Actual neural inference smoke on generated TTS; never a gaming holdout."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import numpy as np
import soundfile as sf
import soxr
from streamclipper.audio_sources import inventory,SpeechSource
from streamclipper.audio_separation import InworldBackend,separate_stream
from streamclipper.target_speaker import VoxLockBackend
from streamclipper.speech_benchmark import signal_metrics

def main():
    p=argparse.ArgumentParser()
    p.add_argument("kind",choices=("inworld","voxlock"));p.add_argument("model");p.add_argument("output")
    args=p.parse_args();root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=False)
    def tts(name,voice,text):
        wav=root/(name+".source.wav")
        subprocess.run(["espeak-ng","-v",voice,"-s","155","-w",str(wav),text],check=True,timeout=30)
        audio,rate=sf.read(wav,dtype="float32",always_2d=True)
        data=soxr.resample(audio.mean(axis=1),rate,48000).astype(np.float32)
        data=data/max(.01,float(np.max(np.abs(data))))*.22
        return data
    enrollment=tts("reference","de+m3","Dies ist eine saubere Beispielaufnahme der Teststimme. Sie liest einen anderen Satz.")
    target=tts("target","de+m3","Jetzt fahren wir nach links und haben das Ziel erreicht. Das war knapp!")
    other=tts("interferer","en-us+f3","The radio is talking over the player. We have reached the other side of the street.")
    count=48000*12
    def pad(data,offset):
        x=np.zeros(count,dtype=np.float32);n=min(len(data),count-offset);x[offset:offset+n]=data[:n];return x
    target=pad(target,48000//2);other=pad(other,48000*2)
    noise=np.random.default_rng(153).normal(0,.008,count).astype(np.float32)
    sf.write(root/"reference.wav",enrollment[:48000*10],48000,subtype="FLOAT")
    sf.write(root/"target.wav",target,48000,subtype="FLOAT")
    sf.write(root/"interferer.wav",other,48000,subtype="FLOAT")
    if args.kind=="voxlock":backend=VoxLockBackend(args.model,root/"reference.wav",consent=True)
    else:backend=InworldBackend(args.model,"cpu")
    rows=[]
    for label,mix in (("target_present",target+other+noise),("target_absent",other+noise)):
        path=root/(label+".wav");sf.write(path,mix,48000,subtype="FLOAT")
        snap=inventory(path);start=time.monotonic()
        bundle=separate_stream(SpeechSource(snap,snap.streams[0].index,"mix"),root,backend=backend)
        voice,sr=sf.read(bundle/"voice_estimate.wav",dtype="float32")
        residual,_=sf.read(bundle/"residual.wav",dtype="float32")
        assert sr==48000 and voice.shape==mix.shape and np.isfinite(voice).all()
        assert np.isfinite(residual).all()
        np.testing.assert_allclose(voice+residual,mix,atol=2e-6,rtol=1e-5)
        if label=="target_present":assert float(np.max(np.abs(voice)))>1e-6,"No speech output"
        row={"case":label,"runtime_seconds":time.monotonic()-start,
             "voice_rms":float(np.sqrt(np.mean(voice.astype(np.float64)**2))),
             "mix_rms":float(np.sqrt(np.mean(mix.astype(np.float64)**2))),
             "reconstruction_max_error":float(np.max(np.abs(voice+residual-mix)))}
        if label=="target_present":
            row["baseline"]=signal_metrics(root/"target.wav",path,root/"interferer.wav")
            row["estimate"]=signal_metrics(root/"target.wav",bundle/"voice_estimate.wav",root/"interferer.wav")
        rows.append(row)
    report={"evidence_kind":"generated_tts_neural_smoke","model":backend.metadata,"cases":rows,
            "technical_contract":"PASS","gaming_quality_acceptance":"NOT_EVALUATED"}
    (root/"smoke.json").write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))
if __name__=="__main__":main()
