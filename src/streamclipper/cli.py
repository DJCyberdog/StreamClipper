"""Headless interface for reproducibility, tests, and Codex development."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .portable import configure_portable_environment

configure_portable_environment()

from .analyze import analyze
from .media import export_clip, probe_video
from .models import TranscriptSegment
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
    a.add_argument("--max-visual-frames", type=int, default=180,
                   help="Höchstens so viele Videoframes klassifizieren (Standard: 180)")
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
    e.add_argument("--transcript-json", type=Path,
                   help="JSON-Bericht aus 'analyze' mit Whisper-Transkript")
    args = parser.parse_args(argv)
    if args.command == "analyze":
        result = analyze(args.video, args.clip_seconds, args.max_clips,
                         progress=lambda p: print(f"\rAnalyse: {p:3d}%", end="", flush=True),
                         speech_model=args.speech_model, vision_model=args.vision_model,
                         max_visual_frames=args.max_visual_frames)
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
            data = json.loads(args.transcript_json.read_text(encoding="utf-8"))
            if Path(data.get("video", {}).get("path", "")).resolve() != Path(args.video).resolve():
                parser.error("Transkript gehört nicht zum angegebenen Video.")
            transcript = [TranscriptSegment(float(x["start"]), float(x["end"]), str(x["text"]))
                          for x in data.get("transcript", [])]
            if not transcript:
                parser.error("Keine Transkript-Abschnitte im JSON-Bericht gefunden.")
        path = export_clip(video, args.start, args.end, args.output, args.mode,
                           transcript=transcript, burn_subtitles=args.burn_subtitles)
        print(f"Export fertig: {path}")


if __name__ == "__main__":
    main()
