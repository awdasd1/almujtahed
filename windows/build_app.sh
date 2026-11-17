#!/usr/bin/env bash
# يبني نسخة المغني لويندوز ويضعها في مجلد التنزيلات.
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
dotnet publish "$ROOT/windows/Almoghni.csproj" -c Release -r win-x64 --self-contained true \
  -p:DebugType=None -o "$BUNDLE"

mkdir -p "$STAGE/source"
git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$STAGE/source"
rm -rf "$STAGE/source/qdrant_service" "$STAGE/source/init_coolify_data.py"
rm -f "$STAGE/source/.env" "$STAGE/source/web_ui/.env"
cp -p "$ROOT/.gitignore" "$ROOT/README.md" "$ROOT/changes.md" "$ROOT/dev.md" \
  "$ROOT/start_local.py" "$ROOT/start_local.sh" "$ROOT/start_local.bat" \
  "$ROOT/local_bundle.py" \
  "$ROOT/requirements-desktop.txt" \
  "$STAGE/source/"
cp -p "$ROOT/web_ui/server.py" "$STAGE/source/web_ui/server.py"
cp -p "$ROOT/web_ui/journey_motion.py" "$STAGE/source/web_ui/journey_motion.py"
mkdir -p "$STAGE/source/web_ui/static/motion/bukhari" "$STAGE/source/web_ui/static/motion/scholars"
cp -p "$ROOT/web_ui/static/motion/bukhari/"*.png "$STAGE/source/web_ui/static/motion/bukhari/"
cp -p "$ROOT/web_ui/static/motion/scholars/"*.png "$STAGE/source/web_ui/static/motion/scholars/"
cp -p "$ROOT/web_ui/design_logo.png" "$STAGE/source/web_ui/design_logo.png"
cp -p "$ROOT/web_ui/shamela_local_mcp.py" "$ROOT/web_ui/almoghni_mcp_server.py" \
  "$ROOT/web_ui/shamela_link.py" "$ROOT/web_ui/shamela_search.py" "$ROOT/web_ui/shamela_bridge_worker.py" \
  "$ROOT/web_ui/library_search.py" "$ROOT/web_ui/build_library_index.py" \
  "$ROOT/web_ui/build_ayah_index.py" "$ROOT/web_ui/build_hadith_gradings.py" "$ROOT/web_ui/quran_uthmani.json" \
  "$ROOT/web_ui/default_agent_groups.json" "$ROOT/web_ui/default_projects.json" "$ROOT/web_ui/default_chats.json" \
  "$STAGE/source/web_ui/"
test -s "$STAGE/source/web_ui/default_chats.json"
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
cp -p "$ROOT/web_ui/static/js/designs.js" "$STAGE/source/web_ui/static/js/designs.js"
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
cp "$ROOT/windows/app.ico" "$BUNDLE/app.ico"
cp "$ROOT/macos/open-board.png" "$BUNDLE/open-board.png"
cp "$ROOT/windows/launch.ps1" "$BUNDLE/launch.ps1"
cp "$ROOT/windows/python_setup.ps1" "$BUNDLE/python_setup.ps1"
cp "$ROOT/web_ui/static/fonts/Almarai-Regular.ttf" "$ROOT/web_ui/static/fonts/Almarai-Bold.ttf" "$BUNDLE/fonts/"
cp -R "$STAGE/source/." "$BUNDLE/source/"

# ——— بذرة الحالة الراهنة (تُولّد وقت البناء فقط ولا تُودع في Git) ———
# قاعدة ذاكرة التطبيق الحية كما هي (وكلاء ٢٠ وبحوث ومشاريع وحزم مخاطر
# وقياسات) معقّمة من الأسرار: مفاتيح المزودين تُفرّغ، وجداول الأعضاء
# الفارغة تُحذف. المشغّل يعتمدها عند غياب قاعدة حية فقط (تثبيت نظيف).
SEED_SRC_DB="${ALMOGHNI_SEED_DB:-$HOME/Library/Application Support/Almoghni/runtime/web_ui/app_memory.db}"
if [ -f "$SEED_SRC_DB" ]; then
  python3 - "$SEED_SRC_DB" "$BUNDLE/source/web_ui/seed_app_memory.db" <<'PY'
import json, sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
con = sqlite3.connect(src)
bak = sqlite3.connect(dst)
con.backup(bak)
con.close()
try:
    row = bak.execute("SELECT payload FROM kv_documents WHERE key LIKE 'providers:%'").fetchall()
    for (payload,) in row:
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                data = {k: "" for k in data}
            bak.execute("UPDATE kv_documents SET payload=? WHERE key LIKE 'providers:%'",
                        (json.dumps(data, ensure_ascii=False),))
        except Exception:
            bak.execute("DELETE FROM kv_documents WHERE key LIKE 'providers:%'")
    for table in ("member_shares", "share_invites"):
        try:
            bak.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    bak.commit()
    bak.execute("VACUUM")
    bak.commit()
finally:
    bak.close()
print("seed db ready")
PY
else
  echo "تنبيه: لا قاعدة حية للبذرة في $SEED_SRC_DB — تُبنى النسخة بلا بذرة ذاكرة" >&2
fi
# ضبط الخطوط والألوان والصور الحالي (من تصدير إعدادات التطبيق المحفوظة).
SEED_SETTINGS="${ALMOGHNI_SEED_SETTINGS:-/tmp/current_settings.json}"
if [ -f "$SEED_SETTINGS" ]; then
  python3 - "$SEED_SETTINGS" "$BUNDLE/source/web_ui/static/default_settings.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
data.pop("providers", None)
json.dump(data, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print("seed settings ready")
PY
fi
# خلفيات الواجهة والطباعة والمخطوطات ومرفقات المشاريع من التشغيل الحالي.
SEED_RT="$(dirname "$SEED_SRC_DB")"
for bg in visual_background print_background ms_background; do
  if [ -d "$SEED_RT/$bg" ]; then
    mkdir -p "$BUNDLE/source/web_ui/seed_backgrounds"
    cp -R "$SEED_RT/$bg" "$BUNDLE/source/web_ui/seed_backgrounds/"
  fi
done
if [ -d "$SEED_RT/uploads" ]; then
  cp -R "$SEED_RT/uploads" "$BUNDLE/source/web_ui/seed_uploads"
fi

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

dotnet publish "$ROOT/windows/AlmoghniSetup.csproj" -c Release -r win-x64 --self-contained true \
  -p:DebugType=None -p:PayloadZip="$STAGE/payload.zip" -o "$STAGE/setup"

EXE="${1:-$HOME/Downloads/almoghni.exe}"
rm -f "$EXE"
cp "$STAGE/setup/AlmoghniSetup.exe" "$EXE"
rm -rf "$HOME/Downloads/المغني-ويندوز"
echo "$EXE"
