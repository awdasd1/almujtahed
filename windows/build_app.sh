#!/usr/bin/env bash
# يبني نسخة المجتهد لويندوز ويضعها في مجلد التنزيلات.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -x "$HOME/.dotnet/dotnet" ]; then
  export DOTNET_ROOT="$HOME/.dotnet"
  export PATH="$HOME/.dotnet:$PATH"
fi
if ! command -v dotnet >/dev/null 2>&1; then
  echo "يلزم .NET 8 SDK لبناء نسخة ويندوز" >&2
  exit 1
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

BUNDLE="$STAGE/app"
dotnet publish "$ROOT/windows/AlMujtahed.csproj" -c Release -r win-x64 --self-contained true \
  -p:DebugType=None -o "$BUNDLE"

mkdir -p "$STAGE/source"
git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$STAGE/source"
cp -p "$ROOT/.gitignore" "$ROOT/README.md" "$ROOT/changes.md" "$ROOT/dev.md" \
  "$ROOT/init_coolify_data.py" "$ROOT/start_local.py" "$ROOT/start_local.sh" "$ROOT/start_local.bat" \
  "$ROOT/local_bundle.py" \
  "$ROOT/requirements-desktop.txt" \
  "$STAGE/source/"
cp -p "$ROOT/web_ui/server.py" "$STAGE/source/web_ui/server.py"
cp -p "$ROOT/web_ui/shamela_local_mcp.py" "$ROOT/web_ui/almujtahed_mcp_server.py" \
  "$ROOT/web_ui/shamela_link.py" "$ROOT/web_ui/shamela_search.py" "$ROOT/web_ui/shamela_bridge_worker.py" \
  "$ROOT/web_ui/library_search.py" "$ROOT/web_ui/build_library_index.py" \
  "$ROOT/web_ui/build_ayah_index.py" "$ROOT/web_ui/build_hadith_gradings.py" "$ROOT/web_ui/quran_uthmani.json" \
  "$ROOT/web_ui/default_agent_groups.json" \
  "$STAGE/source/web_ui/"
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
mkdir -p "$STAGE/source/web_ui/static/css"
cp -p "$ROOT/web_ui/static/css/claude_theme.css" "$STAGE/source/web_ui/static/css/claude_theme.css"
mkdir -p "$STAGE/source/web_ui/static/fonts"
cp -p "$ROOT/web_ui/static/fonts/Almarai-Regular.ttf" "$ROOT/web_ui/static/fonts/Almarai-Bold.ttf" \
  "$STAGE/source/web_ui/static/fonts/"
chmod +x "$STAGE/source/start_local.sh" "$STAGE/source/start_local.py"

mkdir -p "$BUNDLE/fonts" "$BUNDLE/source"
cp "$ROOT/windows/launch.ps1" "$BUNDLE/launch.ps1"
cp "$ROOT/windows/python_setup.ps1" "$BUNDLE/python_setup.ps1"
cp "$ROOT/web_ui/static/fonts/Almarai-Regular.ttf" "$ROOT/web_ui/static/fonts/Almarai-Bold.ttf" "$BUNDLE/fonts/"
cp -R "$STAGE/source/." "$BUNDLE/source/"

python3 - "$BUNDLE" "$STAGE/payload.zip" <<'PY'
import sys, zipfile
from pathlib import Path
root = Path(sys.argv[1])
target = Path(sys.argv[2])
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in root.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(root).as_posix())
PY

dotnet publish "$ROOT/windows/AlMujtahedSetup.csproj" -c Release -r win-x64 --self-contained true \
  -p:DebugType=None -p:PayloadZip="$STAGE/payload.zip" -o "$STAGE/setup"

EXE="${1:-$HOME/Downloads/المجتهد.exe}"
rm -f "$EXE"
cp "$STAGE/setup/AlMujtahedSetup.exe" "$EXE"
rm -rf "$HOME/Downloads/المجتهد-ويندوز"
echo "$EXE"
