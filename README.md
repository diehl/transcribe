# transcribe

A command-line tool for transcribing audio files to Markdown on Apple Silicon Macs. Built on [whisply](https://github.com/tsmdt/whisply), which provides MLX-accelerated Whisper transcription and speaker diarization via [pyannote.audio](https://github.com/pyannote/pyannote-audio).

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.10+
- [Homebrew](https://brew.sh) (the installer uses it to install ffmpeg if needed)

## Installation

```bash
./install.sh
```

The installer handles everything automatically:

- Checks for Python 3.10+ and installs ffmpeg via Homebrew if missing
- Creates an isolated virtual environment at `~/.local/share/transcribe/`
- Installs [whisply](https://github.com/tsmdt/whisply) with MLX support and all dependencies into that venv
- Places a shell wrapper at `~/.local/bin/transcribe` so the command works globally — no conda or venv activation needed
- Adds `~/.local/bin` to your PATH in `~/.zshrc` if it isn't there already

### Reinstalling

Just run `./install.sh` again. It removes the previous venv and rebuilds cleanly.

### Uninstalling

```bash
./uninstall.sh
```

This removes the venv, the shell wrapper, and the PATH entry from `~/.zshrc`. Model weights cached by HuggingFace in `~/.cache/huggingface/hub/` are left in place — the script prints a command to remove those too if you want a full cleanup.

## Usage

### Basic transcription

```bash
transcribe recording.m4a
```

Transcribes the audio using the large-v3 model (the most accurate available) with MLX acceleration and writes the output to `recording.md` in the same directory as the input file. Defaults to English; use `--lang` to specify another language.

### Speaker diarization

```bash
transcribe --speakerid meeting.mp3
```

Produces a transcript with individual speakers labeled (`Speaker 1`, `Speaker 2`, etc.) and their text grouped into passages. Requires one-time setup — see below.

### Options

| Flag | Description |
|---|---|
| `--speakerid` | Identify and label individual speakers |
| `--turbo` | Use large-v3-turbo (faster, slightly less accurate) |
| `--lang CODE` | Language code (default: `en`). Skips auto-detection. |
| `-o PATH` | Set a custom output path (default: `<input_name>.md`) |
| `--hf-token TOKEN` | Pass HuggingFace token directly (alternative to `hf auth login`) |

### Examples

```bash
# Basic transcript
transcribe interview.m4a

# Speaker-labeled transcript
transcribe --speakerid interview.m4a

# Faster transcription with custom output path
transcribe --turbo -o ~/notes/call-notes.md call.mp3

# Transcribe non-English audio
transcribe --lang de german-interview.m4a
```

### Supported formats

m4a, mp3, wav, flac, ogg, webm

## Speaker diarization setup (one-time)

The `--speakerid` feature uses pyannote.audio's pretrained models, which are gated on HuggingFace. You need a free account and must accept the model license terms.

1. Create a HuggingFace account at [huggingface.co](https://huggingface.co)
2. Accept the terms for both models:
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
3. Create an access token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
4. Log in from the terminal:

```bash
~/.local/share/transcribe/venv/bin/hf auth login
```

This only needs to be done once. Basic transcription (without `--speakerid`) works immediately with no token.

## Output format

### Basic mode

Produces clean prose paragraphs broken at natural pauses (≥2 seconds of silence):

```markdown
# Transcript

So the main thing we're looking at here is the watershed boundary
and how it connects to the acequia system downstream.

If you look at the elevation data you can see there's a natural
collection point right about here.
```

### Speaker ID mode

Labels each passage with the detected speaker:

```markdown
# Transcript

**Speaker 1:** So the main thing we're looking at here is the watershed
boundary and how it connects to the acequia system downstream.

**Speaker 2:** Right, and if you look at the elevation data you can see
there's a natural collection point right about here.
```

## How it works

`transcribe` is a thin wrapper around [whisply](https://github.com/tsmdt/whisply). It translates a simple CLI interface into whisply commands, runs the transcription with MLX acceleration, and converts whisply's JSON output into clean Markdown.

Under the hood, whisply uses [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) for Apple Silicon-optimized transcription, [whisperX](https://github.com/m-bain/whisperX) for word-level alignment, and [pyannote.audio](https://github.com/pyannote/pyannote-audio) for speaker diarization.

## Architecture

```
~/.local/share/transcribe/
├── venv/              # isolated Python virtual environment (whisply + deps)
└── transcribe.py      # wrapper script

~/.local/bin/
└── transcribe         # shell wrapper (calls venv python directly)
```

The shell wrapper is a one-liner that invokes the venv's Python interpreter directly, so the tool works from any directory without activation.

## Models

| Model | Flag | Notes |
|---|---|---|
| large-v3 (default) | *(none)* | Most accurate; ~3 GB download on first run |
| large-v3-turbo | `--turbo` | Faster, slightly less accurate |

Model weights are cached by HuggingFace in `~/.cache/huggingface/hub/` and reused across runs. Run `whisply list` from within the venv to see all available models.

## License

[MIT](LICENSE)
