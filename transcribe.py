#!/usr/bin/env python3
"""
transcribe — Simple CLI wrapper around whisply for audio-to-Markdown transcription.

Uses whisply with MLX acceleration on Apple Silicon for fast, on-device
transcription and speaker diarization.

Usage:
    transcribe recording.m4a
    transcribe --speakerid meeting.mp3
    transcribe --speakerid -o notes.md meeting.m4a
    transcribe --turbo recording.m4a
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_whisply_output(output_dir: Path, stem: str) -> Path | None:
    """Find whisply's JSON output file.

    whisply creates: output_dir/<stem>/<stem>.json
    """
    candidate = output_dir / stem / f"{stem}.json"
    if candidate.exists():
        return candidate

    # Search for any json file in the output directory tree
    for f in output_dir.rglob("*.json"):
        return f

    return None


def json_to_markdown_simple(data: dict) -> str:
    """Convert whisply JSON output to simple Markdown (no speaker labels)."""
    lines = ["# Transcript", ""]

    chunks = data.get("chunks", [])
    if chunks:
        paragraph: list[str] = []
        last_end = 0.0
        sentence_count = 0

        for chunk in chunks:
            text = chunk.get("text", "").strip()
            if not text:
                continue

            ts = chunk.get("timestamp", [0.0, 0.0])
            start = ts[0] if ts[0] is not None else last_end
            end = ts[1] if ts[1] is not None else start

            # Count sentences ending in this chunk
            sentence_count += sum(1 for c in text if c in ".?!")

            # Break into new paragraph after ≥1s pause or after ~5 sentences
            if paragraph and (start - last_end > 1.0 or sentence_count >= 5):
                lines.append(" ".join(paragraph))
                lines.append("")
                paragraph = []
                sentence_count = 0

            paragraph.append(text)
            last_end = end

        if paragraph:
            lines.append(" ".join(paragraph))
            lines.append("")
    else:
        # Fallback: use top-level text field
        text = data.get("text", "").strip()
        if text:
            lines.append(text)
            lines.append("")

    return "\n".join(lines)


def json_to_markdown_speakers(data: dict) -> str:
    """Convert whisply annotated JSON output to Markdown with speaker labels."""
    lines = ["# Transcript", ""]

    chunks = data.get("chunks", [])
    if not chunks:
        text = data.get("text", "").strip()
        if text:
            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    # Build speaker-labeled passages by grouping consecutive chunks by speaker
    speaker_map: dict[str, str] = {}
    counter = 1
    passages: list[dict] = []

    for chunk in chunks:
        text = chunk.get("text", "").strip()
        if not text:
            continue

        raw_speaker = chunk.get("speaker", None)

        if raw_speaker and raw_speaker not in speaker_map:
            speaker_map[raw_speaker] = f"Speaker {counter}"
            counter += 1

        label = speaker_map.get(raw_speaker, "Unknown") if raw_speaker else None

        # Merge with previous passage if same speaker
        if passages and passages[-1]["speaker"] == label:
            passages[-1]["text"] += " " + text
        else:
            passages.append({"speaker": label, "text": text})

    if not any(p["speaker"] for p in passages):
        # No speaker info found — fall back to simple format
        return json_to_markdown_simple(data)

    for p in passages:
        label = p["speaker"] or "Unknown"
        lines.append(f"**{label}:** {p['text']}")
        lines.append("")

    return "\n".join(lines)


def run_whisply(
    audio_path: Path,
    output_dir: Path,
    model: str,
    lang: str,
    annotate: bool,
    hf_token: str | None,
) -> Path | None:
    """Run whisply and return the path to its JSON output."""
    venv_bin = Path.home() / ".local" / "share" / "transcribe" / "venv" / "bin"
    whisply_bin = venv_bin / "whisply"

    cmd = [
        str(whisply_bin), "run",
        "-f", str(audio_path),
        "-o", str(output_dir),
        "-d", "mlx",
        "-m", model,
        "-l", lang,
        "-e", "json",
    ]

    if annotate:
        cmd.append("-a")
        if hf_token:
            cmd.extend(["-hf", hf_token])

    print(f"Model: {model}")
    if annotate:
        print("Running transcription with speaker annotation…")
    else:
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
    parser.add_argument("audio_file", help="Path to audio file (.m4a, .mp3, .wav, .flac)")
    parser.add_argument(
        "--speakerid",
        action="store_true",
        help="Label individual speakers (requires HuggingFace token)",
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
        help="Language code, e.g. en, de, fr (default: en; skips auto-detection)",
    )
    parser.add_argument(
        "--hf-token",
        help="HuggingFace access token (for --speakerid; or use hf auth login)",
    )

    args = parser.parse_args()
    audio_path = Path(args.audio_file).expanduser().resolve()

    if not audio_path.exists():
        print(f"Error: file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    supported = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webm"}
    if audio_path.suffix.lower() not in supported:
        print(f"Warning: unexpected format {audio_path.suffix}; trying anyway…", file=sys.stderr)

    output_path = Path(args.output) if args.output else audio_path.with_suffix(".md")
    model = "large-v3-turbo" if args.turbo else "large-v2"

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Copy audio to temp dir with a safe filename so whisply
        # doesn't rename the original (it renames files with spaces)
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
            annotate=args.speakerid,
            hf_token=args.hf_token,
        )

        if not json_path:
            print("Error: could not find whisply output.", file=sys.stderr)
            sys.exit(1)

        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # whisply nests transcription under data["transcription"][lang_code]
        transcription = raw.get("transcription", {})
        # Get the first (and typically only) language key
        lang_key = next(iter(transcription), None)
        if lang_key:
            data = transcription[lang_key]
        else:
            data = raw  # fallback to top-level

        if args.speakerid:
            md = json_to_markdown_speakers(data)
        else:
            md = json_to_markdown_simple(data)

    output_path.write_text(md, encoding="utf-8")
    print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
