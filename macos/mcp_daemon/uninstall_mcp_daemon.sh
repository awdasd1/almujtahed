#!/usr/bin/env bash
# إزالة خدمة MCP المجتهد الدافئة وإيقافها نهائيًا.
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.almujtahed.mcp.plist"
launchctl bootout "gui/$(id -u)/com.almujtahed.mcp" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "أُزيلت خدمة MCP المجتهد الدافئة."
