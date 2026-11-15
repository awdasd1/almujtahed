#!/usr/bin/env bash
# إزالة خدمة MCP المغني الدافئة وإيقافها نهائيًا.
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.almoghni.mcp.plist"
launchctl bootout "gui/$(id -u)/com.almoghni.mcp" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "أُزيلت خدمة MCP المغني الدافئة."
