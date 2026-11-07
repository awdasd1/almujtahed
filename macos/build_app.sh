#!/usr/bin/env bash
# يبني تطبيق المجتهد لماك ويضعه في مجلد التنزيلات.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$HOME/Downloads/المجتهد.app}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

swiftc -O -target arm64-apple-macosx13.0 -framework Cocoa -framework WebKit \
  -o "$STAGE/AlMujtahed" "$ROOT/macos/AlMujtahedLauncher.swift"

mkdir -p "$STAGE/source"
git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$STAGE/source"
cp -p "$ROOT/.gitignore" "$ROOT/README.md" "$ROOT/changes.md" "$ROOT/dev.md" \
  "$ROOT/init_coolify_data.py" "$ROOT/start_local.py" "$ROOT/start_local.sh" "$ROOT/start_local.bat" \
  "$ROOT/local_bundle.py" \
  "$STAGE/source/"
cp -p "$ROOT/web_ui/server.py" "$STAGE/source/web_ui/server.py"
cp -p "$ROOT/web_ui/shamela_local_mcp.py" "$ROOT/web_ui/almujtahed_mcp_server.py" \
  "$ROOT/web_ui/shamela_link.py" "$ROOT/web_ui/shamela_search.py" "$ROOT/web_ui/shamela_bridge_worker.py" \
  "$ROOT/web_ui/library_search.py" "$ROOT/web_ui/build_library_index.py" \
  "$ROOT/web_ui/build_ayah_index.py" "$ROOT/web_ui/build_hadith_gradings.py" "$ROOT/web_ui/quran_uthmani.json" \
  "$STAGE/source/web_ui/"
cp -p "$ROOT/web_ui/default_agent_groups.json" "$STAGE/source/web_ui/default_agent_groups.json"
cp -p "$ROOT/web_ui/anchor_table.json" "$STAGE/source/web_ui/anchor_table.json"
cp -p "$ROOT/web_ui/madhhab_authority.json" "$STAGE/source/web_ui/madhhab_authority.json"
cp -p "$ROOT/web_ui/discipline_books.json" "$STAGE/source/web_ui/discipline_books.json"
cp -p "$ROOT/web_ui/templates/auth.html" "$ROOT/web_ui/templates/index.html" \
  "$STAGE/source/web_ui/templates/"
cp -p "$ROOT/web_ui/static/js/projects.js" "$STAGE/source/web_ui/static/js/projects.js"
cp -p "$ROOT/web_ui/static/js/reader.js" "$STAGE/source/web_ui/static/js/reader.js"
cp -p "$ROOT/web_ui/static/js/search.js" "$STAGE/source/web_ui/static/js/search.js"
cp -p "$ROOT/web_ui/static/js/chat.js" "$STAGE/source/web_ui/static/js/chat.js"
cp -p "$ROOT/web_ui/static/js/agents.js" "$STAGE/source/web_ui/static/js/agents.js"
cp -p "$ROOT/web_ui/static/js/share.js" "$STAGE/source/web_ui/static/js/share.js"
cp -p "$ROOT/web_ui/static/js/tools.js" "$STAGE/source/web_ui/static/js/tools.js"
cp -p "$ROOT/web_ui/static/js/shamela_link.js" "$STAGE/source/web_ui/static/js/shamela_link.js"
cp -p "$ROOT/web_ui/static/js/app.js" "$STAGE/source/web_ui/static/js/app.js"
cp -p "$ROOT/web_ui/static/js/force3d.js" "$STAGE/source/web_ui/static/js/force3d.js"
cp -p "$ROOT/web_ui/static/js/echarts.min.js" "$STAGE/source/web_ui/static/js/echarts.min.js"
cp -p "$ROOT/web_ui/static/js/g6.min.js" "$STAGE/source/web_ui/static/js/g6.min.js"
cp -p "$ROOT/web_ui/static/js/g2.min.js" "$STAGE/source/web_ui/static/js/g2.min.js"
mkdir -p "$STAGE/source/web_ui/static/geo"
cp -p "$ROOT/web_ui/static/geo/world.json" "$STAGE/source/web_ui/static/geo/world.json"
mkdir -p "$STAGE/source/web_ui/static/geo/examples"
cp -p "$ROOT/web_ui/static/geo/places.json" "$STAGE/source/web_ui/static/geo/places.json"
cp -p "$ROOT/web_ui/static/geo/examples/"*.js "$STAGE/source/web_ui/static/geo/examples/"
cp -p "$ROOT/web_ui/static/css/claude_theme.css" "$STAGE/source/web_ui/static/css/claude_theme.css"
chmod +x "$STAGE/source/start_local.sh" "$STAGE/source/start_local.py"

rm -rf "$DEST"
mkdir -p "$DEST/Contents/MacOS" "$DEST/Contents/Resources/fonts"
cp "$STAGE/AlMujtahed" "$DEST/Contents/MacOS/AlMujtahed"
cp "$ROOT/macos/launch.sh" "$DEST/Contents/Resources/launch.sh"
mkdir -p "$DEST/Contents/Resources/mcp_daemon"
cp "$ROOT/macos/mcp_daemon/com.almujtahed.mcp.plist.template" "$ROOT/macos/mcp_daemon/install_mcp_daemon.sh" "$ROOT/macos/mcp_daemon/uninstall_mcp_daemon.sh" "$DEST/Contents/Resources/mcp_daemon/"
chmod +x "$DEST/Contents/Resources/mcp_daemon/install_mcp_daemon.sh" "$DEST/Contents/Resources/mcp_daemon/uninstall_mcp_daemon.sh"
cp "$ROOT/macos/Info.plist" "$DEST/Contents/Info.plist"
cp "$ROOT/web_ui/static/fonts/Almarai-Regular.ttf" "$ROOT/web_ui/static/fonts/Almarai-Bold.ttf" "$DEST/Contents/Resources/fonts/"
chmod +x "$DEST/Contents/MacOS/AlMujtahed" "$DEST/Contents/Resources/launch.sh"
rsync -a "$STAGE/source/" "$DEST/Contents/Resources/source/"
xattr -cr "$DEST" || true
echo "$DEST"
