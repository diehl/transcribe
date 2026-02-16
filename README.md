# transcribe

A CLI tool for transcribing audio files to Markdown on Apple Silicon. Wraps [whisply](https://github.com/tsmdt/whisply) with MLX acceleration for fast, fully on-device transcription.

## Features

- On-device transcription using OpenAI Whisper via MLX — no data leaves your machine
- Outputs clean Markdown with readable paragraph segmentation
- Handles filenames with spaces and various audio formats
- Configurable paragraph length via `--min-words`

## Requirements

- Apple Silicon Mac (M1 or later)
- Python 3.10+
- [ffmpeg](https://formulae.brew.sh/formula/ffmpeg) (`brew install ffmpeg`)
- whisply installed in a dedicated venv at `~/.local/share/transcribe/venv`

## Installation

```bash
mkdir -p ~/.local/share/transcribe
python3 -m venv ~/.local/share/transcribe/venv
~/.local/share/transcribe/venv/bin/pip install whisply
```

Place `transcribe.py` somewhere on your `$PATH` (or create an alias):

```bash
cp transcribe.py ~/.local/bin/transcribe
chmod +x ~/.local/bin/transcribe
```

## Usage

```bash
# Basic transcription (uses large-v2 model)
transcribe recording.m4a

# Faster transcription with large-v3-turbo
transcribe --turbo meeting.mp3

# Specify output path
transcribe -o notes.md recording.m4a

# Adjust paragraph length (default: 10 words minimum)
transcribe --min-words 20 recording.m4a

# Non-English audio
transcribe --lang de interview.mp3
```

## Options

| Flag | Description |
|------|-------------|
| `--turbo` | Use `large-v3-turbo` instead of the default `large-v2` |
| `-o`, `--output` | Output path (default: `<input_name>.md`) |
| `--lang` | Language code (default: `en`) |
| `--min-words` | Minimum words per paragraph (default: `10`) |

## Supported Formats

`.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.webm`

Other formats will be attempted but are not guaranteed to work.

## Models

The default model is `large-v2`, which provides a good balance of accuracy and reliability. The `--turbo` flag switches to `large-v3-turbo` for faster transcription at a slight accuracy tradeoff.

Note: `large-v3` is not offered as an option due to known issues with repetition and hallucination in its output.
