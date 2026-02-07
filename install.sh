#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------------------------------------- #
#  transcribe — installer
#  Installs into ~/.local/share/transcribe with a wrapper in ~/.local/bin
# --------------------------------------------------------------------------- #

INSTALL_DIR="$HOME/.local/share/transcribe"
BIN_DIR="$HOME/.local/bin"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            transcribe — installer for macOS ARM              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Preflight checks ──────────────────────────────────────────────────────── #

# Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install Python 3.10+ first."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "Error: Python 3.10+ required (found $PY_VERSION)."
    exit 1
fi
echo "✓ Python $PY_VERSION"

# ffmpeg (required by whisper for m4a/mp3 decoding)
if ! command -v ffmpeg &>/dev/null; then
    echo ""
    echo "ffmpeg not found — installing via Homebrew…"
    brew install ffmpeg
    echo ""
fi
echo "✓ ffmpeg"

# ── Create isolated venv ──────────────────────────────────────────────────── #

echo ""
echo "Installing to: $INSTALL_DIR"

if [ -d "$INSTALL_DIR/venv" ]; then
    echo "  Removing previous installation…"
    rm -rf "$INSTALL_DIR/venv"
fi

mkdir -p "$INSTALL_DIR"
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

echo "  Upgrading pip…"
pip install --upgrade pip --quiet

# ── Install whisply with MLX support ──────────────────────────────────────── #

echo ""
echo "Installing whisply with MLX support…"
pip install whisply --quiet
pip install "whisply[mlx]" --quiet

# huggingface-cli for token management
pip install huggingface_hub[cli] --quiet

deactivate

# ── Copy the script ───────────────────────────────────────────────────────── #

cp "$SCRIPT_DIR/transcribe.py" "$INSTALL_DIR/transcribe.py"

# ── Create shell wrapper ──────────────────────────────────────────────────── #

mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/transcribe" << 'WRAPPER'
#!/usr/bin/env bash
exec "$HOME/.local/share/transcribe/venv/bin/python" "$HOME/.local/share/transcribe/transcribe.py" "$@"
WRAPPER

chmod +x "$BIN_DIR/transcribe"

echo ""
echo "✓ Installed:  $BIN_DIR/transcribe"

# ── PATH setup ─────────────────────────────────────────────────────────────── #

ZSHRC="$HOME/.zshrc"
if ! grep -qF '/.local/bin' "$ZSHRC" 2>/dev/null; then
    echo "" >> "$ZSHRC"
    echo '# Added by transcribe installer' >> "$ZSHRC"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$ZSHRC"
    echo "✓ Added ~/.local/bin to PATH in ~/.zshrc"
fi

# ── Speaker annotation setup reminder ─────────────────────────────────────── #

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SETUP FOR --speakerid  (one-time, skip if you don't need it)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Speaker annotation uses pyannote.audio, which requires a"
echo "  free HuggingFace account and token:"
echo ""
echo "  1. Create an account at https://huggingface.co"
echo "  2. Accept the model terms:"
echo "     → https://huggingface.co/pyannote/speaker-diarization-3.1"
echo "     → https://huggingface.co/pyannote/segmentation-3.0"
echo "  3. Create an access token:"
echo "     → https://huggingface.co/settings/tokens"
echo "  4. Run:"
echo "     $INSTALL_DIR/venv/bin/hf auth login"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Usage:"
echo "  transcribe recording.m4a              # basic transcript"
echo "  transcribe --speakerid meeting.mp3    # with speaker labels"
echo "  transcribe --turbo recording.m4a      # faster, slightly less accurate"
echo "  transcribe -o notes.md recording.m4a  # custom output path"
echo ""
echo "Done! 🎙️"
echo ""
echo "If this is a fresh install, run this or open a new terminal:"
echo ""
echo "  source ~/.zshrc"
