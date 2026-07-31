#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

npm run dev &
vite_pid=$!

cleanup() {
  kill "$vite_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in {1..40}; do
  if curl --silent --fail http://127.0.0.1:5173 >/dev/null; then
    break
  fi
  sleep 0.25
done

if ! curl --silent --fail http://127.0.0.1:5173 >/dev/null; then
  echo "CYTOLONE prototype did not start on http://127.0.0.1:5173" >&2
  exit 1
fi

npm run simulator
