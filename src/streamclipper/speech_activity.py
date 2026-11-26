"""Local speech activity adapter. No model download or mixed-audio RMS fallback."""
from pathlib import Path
from .media import CancelledError
from .audio_sources import inventory,extract_audio_stream
import tempfile

def detect_speech(selection,*,detector=None,cancelled=None,temp_root=None):
    """Run on a user-designated microphone stream, not unspecified mixed audio.
    Default uses the bundled Faster-Whisper Silero VAD at 16 kHz.
    """
    from .reconstructed_speech import ReconstructedSpeech
    if isinstance(selection,ReconstructedSpeech):
        return detect_reconstructed(selection,detector=detector,cancelled=cancelled,temp_root=temp_root)
    selection.validate()
    if selection.role!="microphone":
        raise ValueError("Bitte ausdrücklich eine Mikrofonspur zuordnen; Mix ist keine isolierte Sprache.")
    def check():
        if cancelled and cancelled():raise CancelledError("Spracherkennung abgebrochen")
    check()
    if selection.inventory.duration>21600:
        raise ValueError("VAD: maximal sechs Stunden")
    with tempfile.TemporaryDirectory(prefix="vad-stream-",dir=temp_root) as folder:
        wav=extract_audio_stream(selection.inventory,selection.index,folder,role=selection.role,cancelled=cancelled)
        spans=_detect_windows(wav,selection.inventory.duration,detector=detector,cancelled=cancelled,temp_root=temp_root)
        check()
        if inventory(selection.inventory.source)!=selection.inventory:
            raise ValueError("Originalaufnahme während VAD verändert")
        return spans


def detect_reconstructed(selection,*,detector=None,cancelled=None,temp_root=None):
    """Bounded VAD on a deliberately selected estimate; not speaker truth."""
    selection.validate(cancelled=cancelled)
    result=_detect_windows(selection.path,selection.inventory.duration,detector=detector,cancelled=cancelled,temp_root=temp_root)
    selection.validate(cancelled=cancelled)
    return result


def _detect_windows(path,duration,*,detector=None,cancelled=None,temp_root=None):
    import math
    from contextlib import closing
    from .reconstructed_speech import audio_windows
    if detector is None:
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import get_speech_timestamps,VadOptions
        def detector(path):
            audio=decode_audio(str(path),sampling_rate=16000)
            return [(x["start"]/16000,x["end"]/16000) for x in get_speech_timestamps(
                audio,VadOptions(min_silence_duration_ms=250,speech_pad_ms=0))]
    result=[]
    with closing(audio_windows(path,duration=duration,
            block_seconds=60,context_seconds=1,cancelled=cancelled,temp_root=temp_root)) as windows:
        for file,origin,a,b,duration in windows:
            if cancelled and cancelled():raise CancelledError("Spracherkennung abgebrochen")
            previous=0.
            for start,end in detector(file):
                if not math.isfinite(start) or not math.isfinite(end) or not previous<=start<end<=duration+.001:
                    raise ValueError("Ungültige VAD-Fensterzeiten")
                previous=end
                x,y=max(a,start+origin),min(b,end+origin)
                if y<=x:continue
                if result and x<=result[-1][1]+1e-6:
                    result[-1]=(result[-1][0],max(result[-1][1],y))
                else:result.append((x,y))
    if cancelled and cancelled():raise CancelledError("Spracherkennung abgebrochen")
    return tuple(result)
