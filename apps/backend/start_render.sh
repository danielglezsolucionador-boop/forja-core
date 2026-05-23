#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "${SCRIPT_DIR}" && pwd)"

cd "${BACKEND_ROOT}"
export PYTHONPATH="."

echo "FORJA_RENDER_STARTUP_SCRIPT_BEGIN"
echo "FORJA_RENDER_BACKEND_ROOT=${BACKEND_ROOT}"
echo "FORJA_RENDER_PYTHONPATH=${PYTHONPATH}"
echo "FORJA_RENDER_PORT=${PORT:-8100}"
echo "FORJA_RENDER_APP_ENV=${FORJA_APP_ENV:-unset}"
echo "FORJA_RENDER_DB_AUTO_MIGRATE=${FORJA_DB_AUTO_MIGRATE:-unset}"
echo "FORJA_RENDER_DATABASE_URL_CONFIGURED=$([[ -n "${FORJA_DATABASE_URL:-}" ]] && echo true || echo false)"
echo "FORJA_RENDER_JWT_SECRET_CONFIGURED=$([[ -n "${FORJA_JWT_SECRET:-}" ]] && echo true || echo false)"
echo "FORJA_RENDER_ADMIN_PASSWORD_CONFIGURED=$([[ -n "${FORJA_ADMIN_PASSWORD:-}" ]] && echo true || echo false)"
echo "FORJA_RENDER_CORS_ORIGINS=${FORJA_CORS_ORIGINS:-unset}"

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

echo "FORJA_RENDER_PYTHON_BIN=${PYTHON_BIN}"
"${PYTHON_BIN}" --version
echo "FORJA_RENDER_EXEC_UVICORN_BEGIN"
exec "${PYTHON_BIN}" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8100}"
