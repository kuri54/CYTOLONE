#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/cytolone/current"
BIN_WRAPPER="${HOME}/.local/bin/cytolone"

rm -f "$BIN_WRAPPER"
rm -rf "$INSTALL_DIR"

echo "CYTOLONE uninstalled."
echo "uv, uv-managed Python, uv cache, and shell startup files were not modified."
