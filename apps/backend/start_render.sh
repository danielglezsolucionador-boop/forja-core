#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "${SCRIPT_DIR}" && pwd)"

cd "${BACKEND_ROOT}"
export PYTHONPATH="."

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python.exe >/dev/null 2>&1; then
  PYTHON_BIN="python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "FORJA Render startup failed: python executable not found" >&2
  exit 127
fi

exec "${PYTHON_BIN}" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8100}"
