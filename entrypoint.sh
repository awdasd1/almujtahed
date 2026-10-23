#!/usr/bin/env bash
# ==============================================================================
# منظومة المجتهد - سكربت بدء التشغيل والتهيئة السحابية للحاوية
# ==============================================================================

set -e

echo "=========================================================="
echo "🌟 بدء تشغيل منصة المجتهد على Coolify / Docker"
echo "=========================================================="

# القرص الثابت يبقى بعد حذف الحاوية وإعادة بنائها.
# في Coolify أضف Persistent Storage وجهته /data
DATA_DIR="${ALMUJTAHED_DATA_DIR:-/data}"
export ALMUJTAHED_DATA_DIR="$DATA_DIR"
mkdir -p \
  "$DATA_DIR/qdrant/storage" \
  "$DATA_DIR/qdrant/snapshots" \
  "$DATA_DIR/shamela4_data" \
  "$DATA_DIR/models/gguf" \
  "$DATA_DIR/web/uploads" \
  "$DATA_DIR/web/backups"

bind_dir() {
  local persistent="$1"
  local link="$2"
  mkdir -p "$persistent"
  if [ -d "$link" ] && [ ! -L "$link" ]; then
    if [ -z "$(ls -A "$persistent" 2>/dev/null)" ]; then
      cp -a "$link"/. "$persistent"/ 2>/dev/null || true
    fi
    rm -rf "$link"
  fi
  ln -sfn "$persistent" "$link"
}

bind_file() {
  local persistent="$1"
  local link="$2"
  local starter="${3:-}"
  mkdir -p "$(dirname "$persistent")"
  if [ -e "$link" ] && [ ! -L "$link" ] && [ ! -e "$persistent" ]; then
    mv "$link" "$persistent"
  fi
  if [ ! -e "$persistent" ]; then
    if [ -n "$starter" ] && [ -f "$starter" ]; then
      cp "$starter" "$persistent"
    else
      : > "$persistent"
    fi
  fi
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    rm -f "$link"
  fi
  ln -sfn "$persistent" "$link"
}

bind_dir "$DATA_DIR/qdrant/storage" /app/qdrant_service/storage
bind_dir "$DATA_DIR/qdrant/snapshots" /app/qdrant_service/snapshots
bind_dir "$DATA_DIR/shamela4_data" /app/shamela4_data
bind_dir "$DATA_DIR/models" /app/models
bind_dir "$DATA_DIR/web/uploads" /app/web_ui/uploads
bind_dir "$DATA_DIR/web/backups" /app/web_ui/backups
bind_file "$DATA_DIR/web/app_memory.db" /app/web_ui/app_memory.db
bind_file "$DATA_DIR/web/members.json" /app/web_ui/members.json
if [ -f /app/shamela_index.db ] && [ ! -L /app/shamela_index.db ] && [ ! -f "$DATA_DIR/web/shamela_index.db" ]; then
  mv /app/shamela_index.db "$DATA_DIR/web/shamela_index.db"
fi
if [ -e /app/shamela_index.db ] && [ ! -L /app/shamela_index.db ]; then
  rm -f /app/shamela_index.db
fi
ln -sfn "$DATA_DIR/web/shamela_index.db" /app/shamela_index.db
bind_file "$DATA_DIR/web/app.env" /app/.env /app/.env.example

if [ ! -s "$DATA_DIR/web/members.json" ]; then
  printf '%s\n' '{"invites":[],"accounts":[]}' > "$DATA_DIR/web/members.json"
fi

echo "💾 البيانات الثابتة على: $DATA_DIR"

# 2. Qdrant عملية مستقلة. nohup يبقيها بعد انطلاق واجهة المجتهد.
echo "📡 التحقق من جاهزية محرك Qdrant..."
if ! curl -sf --max-time 2 http://127.0.0.1:6333/collections >/dev/null 2>&1; then
    if [ -f /app/qdrant_service/qdrant ]; then
        echo "⚡ جاري تشغيل محرك Qdrant المدمج داخل الحاوية..."
        mkdir -p /app/qdrant_service/storage /app/qdrant_service/snapshots /app/qdrant_service/config
        cd /app/qdrant_service
        nohup ./qdrant --config-path /app/qdrant_service/config/config.yaml >> /app/qdrant_service/qdrant.log 2>&1 &
        cd /app
    fi
fi
qdrant_ready=0
for _try in $(seq 1 45); do
    if curl -sf --max-time 2 http://127.0.0.1:6333/collections >/dev/null 2>&1; then
        qdrant_ready=1
        echo "✅ Qdrant يستمع على المنفذ 6333"
        break
    fi
    sleep 2
done
if [ "$qdrant_ready" -ne 1 ]; then
    echo "⚠️ Qdrant لم يرد بعد. الواجهة ستعيد المحاولة، وآخر السجل:"
    tail -n 20 /app/qdrant_service/qdrant.log 2>/dev/null || true
fi

# 3. جلب البيانات في الخلفية حتى تفتح الواجهة وتعرض شريط التقدم أثناء السحب
echo "🔄 فحص جاهزية مخازن الشاملة والمتجهات والموديلات من Hugging Face..."
nohup python3 /app/init_coolify_data.py >> "$DATA_DIR/web/init.log" 2>&1 &
echo "📥 جلب البيانات يعمل في الخلفية. شريط التقدم يظهر في نافذة صحة الخادم."

# 3. إطلاق خادم التطبيق
echo "🚀 تشغيل خادم المجتهد (FastAPI)..."
cd /app/web_ui
exec python3 server.py
