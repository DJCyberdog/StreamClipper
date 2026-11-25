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
            "model_sample_rate":RATE,"state":"reset_per_overlap_window"}
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
