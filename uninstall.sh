#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.local/share/transcribe"
BIN_DIR="$HOME/.local/bin"
WRAPPER="$BIN_DIR/transcribe"
ZSHRC="$HOME/.zshrc"

echo "Uninstalling transcribe…"
echo ""

# Remove venv and script directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "✓ Removed $INSTALL_DIR"
else
    echo "  (not found: $INSTALL_DIR)"
fi

# Remove shell wrapper
if [ -f "$WRAPPER" ]; then
    rm "$WRAPPER"
    echo "✓ Removed $WRAPPER"
else
    echo "  (not found: $WRAPPER)"
fi

# Remove PATH entry from .zshrc
if [ -f "$ZSHRC" ] && grep -qF '# Added by transcribe installer' "$ZSHRC" 2>/dev/null; then
    sed -i '' '/# Added by transcribe installer/d' "$ZSHRC"
    sed -i '' '/export PATH="\$HOME\/.local\/bin:\$PATH"/d' "$ZSHRC"
    echo "✓ Removed PATH entry from ~/.zshrc"
else
    echo "  (no PATH entry found in ~/.zshrc)"
fi

echo ""
echo "Note: Model weights cached by HuggingFace remain in ~/.cache/huggingface/hub/"
echo "To remove them as well:  rm -rf ~/.cache/huggingface/hub/models--mlx-community--whisper-*"
echo ""
echo "Done."
