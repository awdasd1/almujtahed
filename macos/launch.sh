#!/usr/bin/env bash
# يجهّز نسخة سطح المكتب داخل مجلد بيانات المستخدم ثم يشغّل المجتهد.
set -euo pipefail

APP_CONTENTS="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$APP_CONTENTS/Resources/source"
SUPPORT="$HOME/Library/Application Support/Al-Mujtahed"
RUNTIME="$SUPPORT/runtime"
STATUS="$SUPPORT/status.txt"
LOG_DIR="$HOME/Library/Logs/Al-Mujtahed"
LOG_FILE="$LOG_DIR/launch.log"

mkdir -p "$SUPPORT" "$LOG_DIR" "$RUNTIME"
printf '%s\n' "جاري تهيئة التطبيق" > "$STATUS"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export ALMUJTAHED_STATUS_FILE="$STATUS"
export ALMUJTAHED_QDRANT_PID_FILE="$SUPPORT/qdrant.pid"
export ALMUJTAHED_INIT_PID_FILE="$SUPPORT/init.pid"

if ! command -v rsync >/dev/null 2>&1; then
  printf '%s\n' "تعذر تشغيل التطبيق" > "$STATUS"
  exit 1
fi

rsync -a \
  --exclude '.venv/' \
  --exclude 'models/' \
  --exclude 'shamela4_data/' \
  --exclude 'qdrant_service/storage/' \
  --exclude 'qdrant_service/snapshots/' \
  --exclude 'qdrant_service/qdrant' \
  --exclude 'qdrant_service/qdrant.log' \
  --exclude '.env' \
  --exclude 'web_ui/uploads/' \
  --exclude 'web_ui/app_memory.db' \
  --exclude 'web_ui/bootstrap_status.json' \
  --exclude 'web_ui/init.log' \
  --exclude '__pycache__/' \
  "$SOURCE/" "$RUNTIME/"

chmod +x "$RUNTIME/start_local.sh" "$RUNTIME/start_local.py" || true
cd "$RUNTIME"
exec >>"$LOG_FILE" 2>&1
exec ./start_local.sh
