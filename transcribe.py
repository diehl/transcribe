#!/usr/bin/env python3
"""
transcribe — CLI tool for audio-to-Markdown transcription on Apple Silicon.

Wraps whisply with MLX acceleration for fast, on-device transcription.

Usage:
    transcribe recording.m4a
    transcribe --turbo meeting.mp3
    transcribe -o notes.md recording.m4a
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WHISPLY_VENV = Path.home() / ".local" / "share" / "transcribe" / "venv" / "bin"
SUPPORTED_FORMATS = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webm"}


def find_whisply_output(output_dir: Path, stem: str) -> Path | None:
    """Find whisply's JSON output file.

    whisply writes to: output_dir/<stem>/<stem>.json
    Falls back to the first .json file found in the output tree.
    """
    candidate = output_dir / stem / f"{stem}.json"
    if candidate.exists():
        return candidate

    for f in output_dir.rglob("*.json"):
        return f

    return None


def extract_transcription(raw: dict) -> dict:
    """Unwrap whisply's nested JSON structure to get transcription data.

    whisply nests output under raw["transcription"][lang_code].
    """
    transcription = raw.get("transcription", {})
    lang_key = next(iter(transcription), None)
    return transcription[lang_key] if lang_key else raw


def json_to_markdown(data: dict, min_words: int = 10) -> str:
    """Convert whisply JSON to Markdown, merging chunks into readable paragraphs."""
    lines = ["# Transcript", ""]

    chunks = data.get("chunks", [])
    if not chunks:
        text = data.get("text", "").strip()
        if text:
            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    segment: list[str] = []
    word_count = 0

    for chunk in chunks:
        text = chunk.get("text", "").strip()
        if not text:
            continue

        segment.append(text)
        word_count += len(text.split())

        if word_count >= min_words:
            lines.append(" ".join(segment))
            lines.append("")
            segment = []
            word_count = 0

    if segment:
        lines.append(" ".join(segment))
        lines.append("")

    return "\n".join(lines)


def run_whisply(
    audio_path: Path,
    output_dir: Path,
    model: str,
    lang: str,
) -> Path | None:
    """Run whisply and return the path to its JSON output."""
    whisply_bin = WHISPLY_VENV / "whisply"

    cmd = [
        str(whisply_bin), "run",
        "-f", str(audio_path),
        "-o", str(output_dir),
        "-d", "mlx",
        "-m", model,
        "-l", lang,
        "-e", "json",
    ]

    print(f"Model: {model}")
    print("Running transcription…")

    env = {**os.environ, "NO_COLOR": "1"}
    result = subprocess.run(cmd, cwd=str(output_dir), env=env)

    if result.returncode != 0:
        print("Error: whisply exited with an error.", file=sys.stderr)
        return None

    return find_whisply_output(output_dir, audio_path.stem)


def main():
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Transcribe audio to Markdown using whisply on Apple Silicon.",
    )
    parser.add_argument(
        "audio_file",
        help="Path to audio file (.m4a, .mp3, .wav, .flac, .ogg, .webm)",
    )
    parser.add_argument(
        "--turbo",
        action="store_true",
        help="Use large-v3-turbo (faster, slightly less accurate)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output .md path (default: <input_name>.md in the same directory)",
    )
    parser.add_argument(
        "--lang",
        default="en",
        help="Language code, e.g. en, de, fr (default: en)",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=10,
        help="Minimum words per paragraph (default: 10)",
    )

    args = parser.parse_args()
    audio_path = Path(args.audio_file).expanduser().resolve()

    if not audio_path.exists():
        print(f"Error: file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
        print(f"Warning: unexpected format {audio_path.suffix}; trying anyway…", file=sys.stderr)

    output_path = Path(args.output) if args.output else audio_path.with_suffix(".md")
    model = "large-v3-turbo" if args.turbo else "large-v2"

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Copy audio to temp dir with a safe filename (whisply renames
        # files containing spaces)
        safe_name = audio_path.name.replace(" ", "_")
        tmp_audio = Path(tmp_dir) / "input" / safe_name
        tmp_audio.parent.mkdir()
        shutil.copy2(audio_path, tmp_audio)

        whisply_output_dir = Path(tmp_dir) / "output"
        whisply_output_dir.mkdir()

        json_path = run_whisply(
            audio_path=tmp_audio,
            output_dir=whisply_output_dir,
            model=model,
            lang=args.lang,
        )

        if not json_path:
            print("Error: could not find whisply output.", file=sys.stderr)
            sys.exit(1)

        with open(json_path, encoding="utf-8") as f:
            raw = json.load(f)

        data = extract_transcription(raw)
        md = json_to_markdown(data, min_words=args.min_words)

    output_path.write_text(md, encoding="utf-8")
    print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
