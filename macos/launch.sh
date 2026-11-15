#!/usr/bin/env bash
# يجهّز نسخة سطح المكتب داخل مجلد بيانات المستخدم ثم يشغّل المغني.
set -euo pipefail

APP_CONTENTS="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$APP_CONTENTS/Resources/source"
SUPPORT="$HOME/Library/Application Support/Almoghni"
RUNTIME="$SUPPORT/runtime"
STATUS="$SUPPORT/status.txt"
LOG_DIR="$HOME/Library/Logs/Almoghni"
# نقل بيانات النسخة السابقة إن كان مجلدها ما زال بالاسم القديم.
OLD_SUPPORT="$HOME/Library/Application Support/Al-Mujtahed"
if [ -d "$OLD_SUPPORT" ]; then
  if [ ! -d "$SUPPORT" ]; then
    mv "$OLD_SUPPORT" "$SUPPORT"
  elif [ -d "$OLD_SUPPORT/runtime" ] && [ ! -e "$RUNTIME/.venv" ]; then
    if [ -d "$RUNTIME/shamela_imported" ] && [ ! -e "$OLD_SUPPORT/runtime/shamela_imported" ]; then
      mv "$RUNTIME/shamela_imported" "$OLD_SUPPORT/runtime/shamela_imported"
    fi
    rm -rf "$SUPPORT"
    mv "$OLD_SUPPORT" "$SUPPORT"
  fi
fi
OLD_LOG="$HOME/Library/Logs/Al-Mujtahed"
if [ -d "$OLD_LOG" ] && [ ! -d "$LOG_DIR" ]; then
  mv "$OLD_LOG" "$LOG_DIR"
fi
LOG_FILE="$LOG_DIR/launch.log"

mkdir -p "$SUPPORT" "$LOG_DIR" "$RUNTIME"
printf '%s\n' "جاري تهيئة التطبيق" > "$STATUS"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export ALMOGHNI_STATUS_FILE="$STATUS"
export ALMOGHNI_INIT_PID_FILE="$SUPPORT/init.pid"

if ! command -v rsync >/dev/null 2>&1; then
  printf '%s\n' "تعذر تشغيل التطبيق" > "$STATUS"
  exit 1
fi

rsync -a \
  --exclude '.venv/' \
  --exclude 'models/' \
  --exclude 'shamela4_data/' \
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
