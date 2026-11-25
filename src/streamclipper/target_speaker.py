"""Experimental reference-conditioned VoxLock adapter.

Explicit local model directory, explicit reference recording, no auto-enrollment.
Model hashes identify local bytes; they are not publisher authentication.
"""
from pathlib import Path
from importlib.metadata import version
from .audio_separation import sha256_file
from .media import CancelledError

REVISION="2413b292bc2c337bfc19a9802aaf3e011e68e9c4"
FILES=("enroll.onnx","chunk_int8.onnx")
RATE=16000

def load_reference(path,*,consent=False):
    import numpy as np
    import soundfile as sf
    import soxr
    if consent is not True:raise ValueError("Bitte eigene oder ausdrücklich autorisierte Stimmaufnahme bestätigen")
    path=Path(path).resolve(strict=True)
    if path.suffix.lower()!=".wav":raise ValueError("Stimmreferenz muss eine lokale WAV-Datei sein")
    with sf.SoundFile(path) as f:
        if not 8000<=f.samplerate<=192000 or not 1<=f.channels<=2 or not 3<=f.frames/f.samplerate<=30:
            raise ValueError("Stimmreferenz: 3–30 Sekunden, Mono/Stereo, 8–192 kHz")
        audio=f.read(dtype="float32",always_2d=True).mean(axis=1)
        sr=f.samplerate
    if not np.isfinite(audio).all() or np.max(np.abs(audio))<.001:
        raise ValueError("Stimmreferenz leer, stumm oder ungültig")
    ref=soxr.resample(audio,sr,RATE).astype(np.float32) if sr!=RATE else audio
    if len(ref)<3*RATE or not np.isfinite(ref).all():
        raise ValueError("Stimmreferenz ungültig")
    return ref

class VoxLockBackend:
    def __init__(self,model_dir,reference,*,consent=False,cancelled=None):
        import numpy as np
        from importlib.metadata import version
        root=Path(model_dir).resolve(strict=True)
        if not root.is_dir():raise ValueError("Lokaler VoxLock-Modellordner erforderlich")
        hashes={}
        for name in FILES:
            path=root/name
            if not path.is_file() or not 1024<path.stat().st_size<256*1024*1024:
                raise ValueError("VoxLock-Modell unvollständig: "+name)
            hashes[name]=sha256_file(path,cancelled=cancelled)
        if cancelled and cancelled():raise CancelledError("Audiotrennung abgebrochen")
        self.reference=load_reference(reference,consent=consent)
        if version("voxlock")!="1.3.0":raise ValueError("VoxLock 1.3.0 erforderlich")
        from voxlock import VoxLock
        self.model=VoxLock(model_dir=str(root),precision="int8",threads=2)
        self.metadata={"backend":"voxlock","version":"1.3.0","expected_upstream_revision":REVISION,
            "local_file_sha256":hashes,"publisher_hash_verified":False,"device":"CPU/ONNX",
            "speaker_targeted":True,"reference_explicit":True,"reference_duration_seconds":len(self.reference)/RATE,
            "model_sample_rate":RATE,"state":"continuous_stream"}
        # Do not write reference path, audio, embedding, or its fingerprint to the manifest.
    def __call__(self,mono):
        import numpy as np
        import soxr
        source=np.asarray(mono,dtype=np.float32)
        n=len(source)
        # Pad very short final windows and make the 48->16->48k length exact.
        size=max(3*1024,((n+2)//3)*3)
        padded=np.pad(source,(0,size-n))
        low=soxr.resample(padded,48000,RATE).astype(np.float32)
        estimate=np.asarray(self.model.isolate(low,sample=self.reference),dtype=np.float32)
        if estimate.shape!=low.shape or not np.isfinite(estimate).all():
            raise ValueError("VoxLock lieferte ungültige Samples")
        out=soxr.resample(estimate,RATE,48000).astype(np.float32)
        if len(out)!=size:raise ValueError("VoxLock Resampling-Zeitbasis ungültig")
        return out[:n]


    def stream_estimates(self,chunks,count,*,cancelled=None):
        """One enrollment and continuous recurrent state for the entire job.
        Both resamplers are streaming; flush and trim only final padding.
        Yields sequential source-aligned mono 48 kHz samples.
        """
        import numpy as np
        import soxr
        if count<=0:raise ValueError("Leere Zielstimmanalyse")
        down=soxr.ResampleStream(48000,RATE,1,dtype="float32")
        up=soxr.ResampleStream(RATE,48000,1,dtype="float32")
        session=self.model.stream(self.reference)
        padded_count=max(3*1024,((count+2)//3)*3)
        seen=0;emitted=0;actual_output=0;low_input=0;low_output=0
        def check():
            if cancelled and cancelled():raise CancelledError("Audiotrennung abgebrochen")
        for block in chunks:
            check()
            x=np.asarray(block,dtype=np.float32)
            if x.ndim!=1 or not len(x) or not np.isfinite(x).all() or seen+len(x)>count:
                raise ValueError("Ungültiges TSE-Eingabefenster")
            seen+=len(x);last=seen==count
            if last:x=np.pad(x,(0,padded_count-count))
            low=down.resample_chunk(x,last=last)
            low_input+=len(low)
            y=np.asarray(session.push(low),dtype=np.float32)
            if last:y=np.concatenate((y,np.asarray(session.flush(),dtype=np.float32)))
            if y.ndim!=1 or not np.isfinite(y).all():raise ValueError("Ungültige TSE-Modellausgabe")
            low_output+=len(y)
            if low_output>low_input or (last and low_output!=low_input):raise ValueError("TSE-Modellzeitbasis ungültig")
            out=up.resample_chunk(y,last=last)
            actual_output+=len(out)
            if actual_output>padded_count:raise ValueError("TSE-Resampling zu lang")
            n=min(count-emitted,len(out))
            if n>0:
                check()
                emitted+=n
                yield out[:n]
        if seen!=count or emitted!=count or actual_output!=padded_count or low_input!=padded_count//3:
            raise ValueError("TSE-Stream unvollständig oder Zeitbasis ungültig")


    def resume_identity(self,root,source,index):
        """Opt-in byte identity, not a biometric speaker fingerprint.
        A local random cache key scopes HMAC to this cache and recording.
        Only derived cache filenames persist, not reference PCM/path/embedding.
        Anyone with the cache directory AND a candidate recording can test
        exact bytes, so this mode is explicitly opt-in and local only.
        """
        import hmac
        import hashlib
        import os
        import secrets
        import json
        from dataclasses import asdict
        import numpy as np
        root=Path(root);root.mkdir(parents=True,exist_ok=True)
        keyfile=root/"local-cache.key"
        if not keyfile.exists():
            try:
                with os.fdopen(os.open(keyfile,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),"wb") as f:
                    f.write(secrets.token_bytes(32));f.flush();os.fsync(f.fileno())
            except FileExistsError:pass
        if keyfile.stat().st_size!=32:raise ValueError("Lokaler TSE-Cache-Schlüssel ungültig")
        key=keyfile.read_bytes()
        binding=hmac.new(key,digestmod=hashlib.sha256)
        binding.update(b"streamclipper-target-resume-v1\0")
        binding.update(json.dumps({"source":asdict(source),"index":index},sort_keys=True,allow_nan=False).encode())
        binding.update(np.asarray(self.reference,dtype="<f4").tobytes())
        return binding.hexdigest()
