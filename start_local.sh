#!/usr/bin/env bash
# تشغيل المجتهد محلياً بأمر واحد بعد سحب المستودع على ماك أو لينكس.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

status() {
  printf '%s\n' "$1"
  if [ -n "${ALMUJTAHED_STATUS_FILE:-}" ]; then
    printf '%s\n' "$1" > "$ALMUJTAHED_STATUS_FILE"
  fi
}

case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*)
    WIN_PY="${LOCALAPPDATA:-}/Programs/Python/Python312/python.exe"
    if [ ! -f "$WIN_PY" ]; then
      WIN_PY="$(command -v python || true)"
    fi
    if [ -n "$WIN_PY" ] && [ -f "$WIN_PY" ]; then
      exec "$WIN_PY" -X utf8 -u "$ROOT/start_local.py"
    fi
    status "تعذر تشغيل التطبيق"
    exit 1
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  status "تعذر تشغيل التطبيق"
  exit 1
fi

if [ ! -d .venv ]; then
  status "جاري تثبيت الملفات"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -c "import fastapi, uvicorn, qdrant_client, huggingface_hub, dotenv, llama_cpp" >/dev/null 2>&1 || {
  status "جاري تثبيت الملفات"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

exec python start_local.py
