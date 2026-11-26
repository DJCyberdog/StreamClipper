"""Headless interface for reproducibility, tests, and Codex development."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .portable import configure_portable_environment

configure_portable_environment()

from .analyze import analyze
from .media import export_clip, probe_video
from .models import TranscriptSegment, TranscriptWord
from .semantic import default_models_directory, transcribe_video
from .transcript import save_transcript


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="StreamClipper offline CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    a = commands.add_parser("analyze", help="Offline audio / speech / gameplay evidence into JSON")
    a.add_argument("video")
    a.add_argument("--clip-seconds", type=int, default=25)
    a.add_argument("--max-clips", type=int, default=8)
    a.add_argument("--output")
    a.add_argument("--speech-model", metavar="DIR",
                   help="Lokaler faster-whisper CTranslate2-Modellordner")
    a.add_argument("--vision-model", metavar="DIR",
                   help="Lokaler Transformers-CLIP-Modellordner")
    a.add_argument("--detector-model", metavar="DIR",
                   help="Lokales DETR/RT-DETR-Objekterkennungsmodell; optional")
    a.add_argument("--max-object-frames", type=int, default=90,
                   help="Max. Objekterkennungsbilder (3–300; Standard 90)")
    a.add_argument("--max-visual-frames", type=int, default=180,
                   help="Höchstens so viele Videoframes klassifizieren (Standard: 180)")
    a.add_argument("--story-profile", choices=["short","social","extended"], help="M17 dynamic clip boundaries with M16 evidence")
    a.add_argument("--m16-profile", choices=["generic","open-world"], help="Experimental M16 engine")
    a.add_argument("--m16-hardware", choices=["auto","gpu","cpu","legacy"], default="legacy")
    a.add_argument("--m16-fast-vision", action="store_true", help="Experimental CUDA FP16 and bounded batches")
    a.add_argument("--m16-cache", type=Path, help="Explicit local cache (contains transcript text)")
    a.add_argument("--m16-chat", type=Path, help="Local JSONL chat timestamps")
    t = commands.add_parser("transcribe", help="Whole recording -> local SRT/TXT/VTT subtitles")
    t.add_argument("video")
    t.add_argument("--speech-model", default=str(default_models_directory() / "whisper-small"),
                   metavar="DIR", help="Lokales Whisper-Modell (Standard: data/models/whisper-small)")
    t.add_argument("--output", help="Zielpfad .srt, .vtt oder .txt; Standard: SRT und TXT")
    e = commands.add_parser("export", help="Export one segment with optional dynamic reframing and burned captions")
    e.add_argument("video")
    e.add_argument("--start", type=float, required=True)
    e.add_argument("--end", type=float, required=True)
    e.add_argument("--output", required=True)
    e.add_argument("--mode", choices=["smart16", "smart9", "blur", "crop"], default="smart16")
    e.add_argument("--burn-subtitles", action="store_true",
                   help="Transkripttext fest in die exportierte MP4 einbrennen")
    e.add_argument("--subtitle-offset", type=float, default=0.0,
                   help="Untertitel verschieben (Sekunden, positiv = später, -5 bis +5)")
    e.add_argument("--transcript-json", type=Path,
                   help="JSON-Bericht aus 'analyze' mit Whisper-Transkript")
    args = parser.parse_args(argv)
    if args.command == "analyze":
        engine=analyze
        options={}
        if args.story_profile and not args.m16_profile:parser.error("--story-profile requires --m16-profile")
        if args.m16_profile:
            from .m16_pipeline import analyze_m16
            from .m16_review import read_chat
            engine=analyze_m16
            options={"profile":args.m16_profile,"cache_root":args.m16_cache,"fast_vision":args.m16_fast_vision,"hardware_mode":args.m16_hardware}
            if args.story_profile:
                from .story_clipping import PROFILES,StoryOptions
                options["story_options"]=StoryOptions(*PROFILES[args.story_profile])
            if args.m16_chat:options["chat_messages"]=read_chat(args.m16_chat,probe_video(args.video).duration)
        elif args.m16_cache or args.m16_chat or args.m16_fast_vision or args.m16_hardware!="legacy":
            parser.error("M16 options require --m16-profile")
        result = engine(args.video, args.clip_seconds, args.max_clips,
                         progress=lambda p: print(f"\rAnalyse: {p:3d}%", end="", flush=True),
                         speech_model=args.speech_model, vision_model=args.vision_model,
                         max_visual_frames=args.max_visual_frames,
                         detector_model=args.detector_model,
                         max_object_frames=args.max_object_frames,**options)
        destination = Path(args.output or (str(Path(args.video).with_suffix("")) + ".highlights.json"))
        result.save_json(destination)
        print(f"\n{len(result.candidates)} Kandidaten gespeichert: {destination}")
        for c in result.candidates:
            print(f"  {c.start:.1f}–{c.end:.1f}s | {c.score:02d} | {c.reason}")
    elif args.command == "transcribe":
        video = probe_video(args.video)
        segments = transcribe_video(video, args.speech_model,
            progress=lambda p: print(f"\rTranskript: {p:3d}%", end="", flush=True))
        if args.output:
            destinations = [Path(args.output)]
        else:
            base = Path(args.video).with_suffix("")
            destinations = [Path(f"{base}.transkript.srt"), Path(f"{base}.transkript.txt")]
        for destination in destinations:
            saved = save_transcript(segments, destination)
            print(f"\nTranskript gespeichert ({len(segments)} Abschnitte): {saved}")
    else:
        video = probe_video(args.video)
        transcript = []
        if args.burn_subtitles:
            if not args.transcript_json:
                parser.error("Für --burn-subtitles wird --transcript-json aus Whisper-Analyse benötigt.")
            from .transcript_editor import load_analysis_report
            from .subtitle_translation import export_transcript
            try:
                analysis=load_analysis_report(args.transcript_json,args.video)
                transcript=list(export_transcript(analysis,[(args.start,args.end)],offset=args.subtitle_offset))
            except (OSError,ValueError) as exc:
                parser.error(str(exc))
            if not analysis.transcript:
                parser.error("Keine Transkript-Abschnitte im JSON-Bericht gefunden.")
        path = export_clip(video, args.start, args.end, args.output, args.mode,
                           transcript=transcript, burn_subtitles=args.burn_subtitles and bool(transcript),
                           subtitle_offset=args.subtitle_offset)
        print(f"Export fertig: {path}")


if __name__ == "__main__":
    main()
