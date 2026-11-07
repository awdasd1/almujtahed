#!/usr/bin/env bash
# تثبيت خدمة MCP المجتهد الدافئة: خادم دائم في الخلفية على 127.0.0.1:8765
# ليصل إليه وكلاء خارجيون (Cursor/Claude) حتى والتطبيق مغلق.
set -euo pipefail

RUNTIME="$HOME/Library/Application Support/Al-Mujtahed/runtime"
PY="$RUNTIME/.venv/bin/python"
SERVER="$RUNTIME/web_ui/almujtahed_mcp_server.py"
HERE="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$HERE/com.almujtahed.mcp.plist.template"
PLIST="$HOME/Library/LaunchAgents/com.almujtahed.mcp.plist"
LOG="$HOME/Library/Logs/Al-Mujtahed/mcp_daemon.log"

if [ ! -x "$PY" ] || [ ! -f "$SERVER" ]; then
  echo "افتح تطبيق المجتهد مرة واحدة أولًا ليجهّز بيئته، ثم أعد تشغيل هذا المثبّت."
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$(dirname "$LOG")"
sed -e "s|__PYTHON__|$PY|g" \
    -e "s|__SERVER__|$SERVER|g" \
    -e "s|__WEBUI__|$RUNTIME/web_ui|g" \
    -e "s|__LOG__|$LOG|g" \
    "$TEMPLATE" > "$PLIST"

launchctl bootout "gui/$(id -u)/com.almujtahed.mcp" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "تم تثبيت خدمة MCP المجتهد الدافئة: http://127.0.0.1:8765/mcp"
