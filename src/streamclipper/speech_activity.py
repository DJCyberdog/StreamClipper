"""Local speech activity adapter. No model download or mixed-audio RMS fallback."""
from pathlib import Path
from .media import CancelledError
from .audio_sources import inventory,extract_audio_stream
import tempfile

def detect_speech(selection,*,detector=None,cancelled=None,temp_root=None):
    """Run on a user-designated microphone stream, not unspecified mixed audio.
    Default uses the bundled Faster-Whisper Silero VAD at 16 kHz.
    """
    selection.validate()
    if selection.role!="microphone":
        raise ValueError("Bitte ausdrücklich eine Mikrofonspur zuordnen; Mix ist keine isolierte Sprache.")
    def check():
        if cancelled and cancelled():raise CancelledError("Spracherkennung abgebrochen")
    check()
    if selection.inventory.duration>600:
        raise ValueError('VAD-Prototyp: maximal 10 Minuten; Chunk-Verarbeitung folgt.')
    with tempfile.TemporaryDirectory(prefix="vad-stream-",dir=temp_root) as folder:
        wav=extract_audio_stream(selection.inventory,selection.index,folder,role=selection.role,cancelled=cancelled)
        if detector is None:
            from faster_whisper.audio import decode_audio
            from faster_whisper.vad import get_speech_timestamps,VadOptions
            def detector(path):
                # Faster-Whisper decodes into memory; cap this initial adapter.
                audio=decode_audio(str(path),sampling_rate=16000)
                check()
                return [(x["start"]/16000,x["end"]/16000) for x in get_speech_timestamps(
                    audio,VadOptions(min_silence_duration_ms=250,speech_pad_ms=0))]
        check()
        spans=tuple(detector(wav))
        check()
        if inventory(selection.inventory.source)!=selection.inventory:
            raise ValueError("Originalaufnahme während VAD verändert")
        return spans
