#!/usr/bin/env python3
"""
transcribe — CLI tool for audio transcription on Apple Silicon.

Uses mlx-whisper (large-v3) for transcription and pyannote.audio for
speaker diarization. Outputs Markdown.

Usage:
    transcribe recording.m4a
    transcribe --speakerid meeting.mp3
    transcribe --speakerid -o notes.md meeting.m4a
    transcribe --turbo recording.m4a
"""

import argparse
import sys
from pathlib import Path


MODELS = {
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}


def transcribe_audio(audio_path: str, model_key: str = "large-v3", speaker_id: bool = False) -> str:
    """Transcribe an audio file and return Markdown text."""
    import mlx_whisper

    model_repo = MODELS[model_key]
    print(f"Model: {model_repo}")
    print("Running transcription…")

    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=model_repo,
        word_timestamps=speaker_id,
    )

    if speaker_id:
        return _format_diarized(audio_path, result)
    else:
        return _format_simple(result)


# --------------------------------------------------------------------------- #
#  Simple transcript (no speaker labels)
# --------------------------------------------------------------------------- #

def _format_simple(result: dict) -> str:
    lines = ["# Transcript", ""]
    paragraph: list[str] = []
    last_end = 0.0

    for seg in result.get("segments", []):
        text = seg["text"].strip()
        if not text:
            continue

        # Break into a new paragraph after a ≥2-second pause
        if paragraph and seg["start"] - last_end > 2.0:
            lines.append(" ".join(paragraph))
            lines.append("")
            paragraph = []

        paragraph.append(text)
        last_end = seg["end"]

    if paragraph:
        lines.append(" ".join(paragraph))
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  Diarized transcript (speaker labels)
# --------------------------------------------------------------------------- #

def _format_diarized(audio_path: str, result: dict) -> str:
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        print(
            "Error: pyannote.audio is not installed.\n"
            "Run:  ~/.local/share/transcribe/venv/bin/pip install pyannote.audio\n"
            "Then accept the model terms — see install.sh output for details.",
            file=sys.stderr,
        )
        sys.exit(1)

    import torch

    print("Running speaker diarization…")

    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
    except Exception as exc:
        if "token" in str(exc).lower() or "401" in str(exc) or "gated" in str(exc).lower():
            print(
                "Error: HuggingFace authentication required for pyannote models.\n\n"
                "1. Create a token at https://huggingface.co/settings/tokens\n"
                "2. Accept terms at https://huggingface.co/pyannote/speaker-diarization-3.1\n"
                "3. Accept terms at https://huggingface.co/pyannote/segmentation-3.0\n"
                "4. Run:  huggingface-cli login\n",
                file=sys.stderr,
            )
            sys.exit(1)
        raise

    if torch.backends.mps.is_available():
        pipeline.to(torch.device("mps"))

    diarization = pipeline(audio_path)

    # Build speaker timeline
    speaker_segments = [
        {"start": turn.start, "end": turn.end, "speaker": speaker}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]

    # Collect word-level timestamps from whisper result
    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            # mlx-whisper uses "word"; some variants use "text"
            token = w.get("word", w.get("text", "")).strip()
            if token:
                words.append({"start": w["start"], "end": w["end"], "word": token})

    if not words:
        # Fallback: no word-level timestamps — assign whole segments
        return _diarize_segment_level(result, speaker_segments)

    # Map each word to the speaker with the most temporal overlap
    def _find_speaker(w_start: float, w_end: float) -> str:
        best, best_overlap = "Unknown", 0.0
        for ss in speaker_segments:
            overlap = max(0.0, min(w_end, ss["end"]) - max(w_start, ss["start"]))
            if overlap > best_overlap:
                best_overlap = overlap
                best = ss["speaker"]
        return best

    # Group consecutive words by speaker into passages
    passages: list[dict] = []
    cur_speaker = None
    cur_words: list[str] = []

    for w in words:
        spk = _find_speaker(w["start"], w["end"])
        if spk != cur_speaker:
            if cur_words:
                passages.append({"speaker": cur_speaker, "text": " ".join(cur_words)})
            cur_speaker = spk
            cur_words = [w["word"]]
        else:
            cur_words.append(w["word"])

    if cur_words:
        passages.append({"speaker": cur_speaker, "text": " ".join(cur_words)})

    return _render_passages(passages)


def _diarize_segment_level(result: dict, speaker_segments: list[dict]) -> str:
    """Fallback: assign whole whisper segments to speakers (no word timestamps)."""
    passages: list[dict] = []

    for seg in result.get("segments", []):
        text = seg["text"].strip()
        if not text:
            continue
        mid = (seg["start"] + seg["end"]) / 2.0
        best, best_dist = "Unknown", float("inf")
        for ss in speaker_segments:
            if ss["start"] <= mid <= ss["end"]:
                best = ss["speaker"]
                break
            dist = min(abs(mid - ss["start"]), abs(mid - ss["end"]))
            if dist < best_dist:
                best_dist = dist
                best = ss["speaker"]

        # Merge with previous passage if same speaker
        if passages and passages[-1]["speaker"] == best:
            passages[-1]["text"] += " " + text
        else:
            passages.append({"speaker": best, "text": text})

    return _render_passages(passages)


def _render_passages(passages: list[dict]) -> str:
    # Assign friendly names (Speaker 1, Speaker 2, …)
    speaker_map: dict[str, str] = {}
    counter = 1
    for p in passages:
        raw = p["speaker"]
        if raw not in speaker_map and raw != "Unknown":
            speaker_map[raw] = f"Speaker {counter}"
            counter += 1

    lines = ["# Transcript", ""]
    for p in passages:
        label = speaker_map.get(p["speaker"], p["speaker"])
        lines.append(f"**{label}:** {p['text']}")
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio to Markdown using Whisper on Apple Silicon.",
    )
    parser.add_argument("audio_file", help="Path to audio file (.m4a, .mp3, .wav, .flac)")
    parser.add_argument(
        "--speakerid",
        action="store_true",
        help="Label individual speakers (requires pyannote.audio + HuggingFace token)",
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

    args = parser.parse_args()
    audio_path = Path(args.audio_file).expanduser().resolve()

    if not audio_path.exists():
        print(f"Error: file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    supported = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webm"}
    if audio_path.suffix.lower() not in supported:
        print(f"Warning: unexpected format {audio_path.suffix}; trying anyway…", file=sys.stderr)

    output_path = Path(args.output) if args.output else audio_path.with_suffix(".md")
    model_key = "turbo" if args.turbo else "large-v3"

    md = transcribe_audio(str(audio_path), model_key=model_key, speaker_id=args.speakerid)

    output_path.write_text(md, encoding="utf-8")
    print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
