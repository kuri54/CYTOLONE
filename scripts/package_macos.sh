#!/usr/bin/env bash
set -euo pipefail

fail() {
    echo "Error: $*" >&2
    exit 1
}

VERSION="${1:-}"
[ -n "$VERSION" ] || fail "Usage: bash scripts/package_macos.sh v0.1.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
PACKAGE_NAME="CYTOLONE-${VERSION}-mac-arm64"
STAGING_DIR="${DIST_DIR}/${PACKAGE_NAME}"
ARCHIVE_PATH="${DIST_DIR}/${PACKAGE_NAME}.tar.gz"

required_paths=(
    "CYTOLONE"
    "pyproject.toml"
    "uv.lock"
    "install.command"
    "uninstall.command"
)

optional_paths=(
    "README.md"
    "README_JA.md"
    "LICENSE"
)

for path in "${required_paths[@]}"; do
    [ -e "${ROOT_DIR}/${path}" ] || fail "Required path not found: ${path}"
done

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

for path in "${required_paths[@]}"; do
    rsync -a \
        --exclude "__pycache__/" \
        --exclude "*.pyc" \
        --exclude ".DS_Store" \
        "${ROOT_DIR}/${path}" "$STAGING_DIR/"
done

for path in "${optional_paths[@]}"; do
    if [ -e "${ROOT_DIR}/${path}" ]; then
        rsync -a \
            --exclude "__pycache__/" \
            --exclude "*.pyc" \
            --exclude ".DS_Store" \
            "${ROOT_DIR}/${path}" "$STAGING_DIR/"
    fi
done

chmod +x "${STAGING_DIR}/install.command" "${STAGING_DIR}/uninstall.command"

tar -C "$DIST_DIR" -czf "$ARCHIVE_PATH" "$PACKAGE_NAME"
rm -rf "$STAGING_DIR"

echo "Created ${ARCHIVE_PATH}"
