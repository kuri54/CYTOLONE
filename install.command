#!/usr/bin/env bash
set -euo pipefail

APP_NAME="CYTOLONE"
INSTALL_ROOT="${HOME}/.local/share/cytolone"
INSTALL_DIR="${INSTALL_ROOT}/current"
BIN_DIR="${HOME}/.local/bin"
WRAPPER="${BIN_DIR}/cytolone"
TMP_DIR=""

cleanup() {
    if [ -n "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}

pause_before_exit() {
    local status="$?"

    cleanup

    if [ -t 0 ]; then
        echo ""
        read -r -p "Press Enter to close this window..." _
    fi

    exit "$status"
}
trap pause_before_exit EXIT

fail() {
    echo "Error: $*" >&2
    exit 1
}

append_path_if_needed() {
    local rc_file="$1"
    local path_line='export PATH="$HOME/.local/bin:$PATH"'

    if [ ! -f "$rc_file" ]; then
        touch "$rc_file"
    fi

    if ! grep -Fq "$path_line" "$rc_file"; then
        {
            echo ""
            echo "# Added by CYTOLONE installer"
            echo "$path_line"
        } >> "$rc_file"
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ "$(uname -s)" = "Darwin" ] || fail "${APP_NAME} supports macOS only."
[ "$(uname -m)" = "arm64" ] || fail "${APP_NAME} supports Apple Silicon Macs only."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found. Installing uv with the official installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
fi

command -v uv >/dev/null 2>&1 || fail "uv installation failed. Add ~/.local/bin to PATH and retry."

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"

TMP_DIR="$(mktemp -d "${INSTALL_ROOT}/.install.XXXXXX")"

rsync -a --delete \
    --exclude ".git/" \
    --exclude ".venv/" \
    --exclude "venv/" \
    --exclude "dist/" \
    --exclude "debug_images/" \
    --exclude "mlx_models/" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude ".DS_Store" \
    "${SCRIPT_DIR}/" "${TMP_DIR}/"

rm -rf "$INSTALL_DIR"
mv "$TMP_DIR" "$INSTALL_DIR"
TMP_DIR=""

cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_DIR"
exec uv run cytolone "\$@"
EOF
chmod +x "$WRAPPER"

append_path_if_needed "${HOME}/.zshrc"
append_path_if_needed "${HOME}/.bashrc"

echo "${APP_NAME} installed."
echo "Run: cytolone"
echo "If your current shell cannot find cytolone, restart Terminal or run:"
echo '  export PATH="$HOME/.local/bin:$PATH"'
