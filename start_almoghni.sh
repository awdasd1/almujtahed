#!/usr/bin/env bash
# ==============================================================================
# منظومة المغني (Almoghni Platform)
# سكربت التشغيل الموحد بنقرة واحدة (Master Startup Script)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "          🌟 تشغيل منظومة المغني | المكتبة الشاملة المضمنة والمكممة       "
echo "========================================================================"
echo "📂 مسار المنظومة: $SCRIPT_DIR"
echo ""

# 1. التحقق من بيئة بايثون وتثبيت المتطلبات إذا لزم الأمر
if ! command -v python3 &> /dev/null; then
    echo "❌ خطأ: لم يتم العثور على python3 في هذا النظام!"
    exit 1
fi

echo "🔍 فحص مكتبات بايثون المطلوبة..."
python3 -c "import fastapi, uvicorn, qdrant_client" 2>/dev/null || {
    echo "⚠️ بعض المكتبات غير مثبتة. جاري التثبيت من requirements.txt..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
}

# 2. فحص وتشغيل خدمة مخزن المتجهات Qdrant
echo "📡 فحص اتصال مخزن المتجهات Qdrant على المنفذ 6333..."
if curl -s http://127.0.0.1:6333/collections > /dev/null 2>&1; then
    echo "✅ خدمة Qdrant قيد التشغيل بالفعل وتستقبل الطلبات!"
else
    echo "⏳ خدمة Qdrant غير مشغلة، جاري تشغيلها الآن..."
    if [ -f "$SCRIPT_DIR/qdrant_service/run_qdrant.sh" ]; then
        chmod +x "$SCRIPT_DIR/qdrant_service/run_qdrant.sh"
        if [ -f "$SCRIPT_DIR/qdrant_service/qdrant" ]; then
            chmod +x "$SCRIPT_DIR/qdrant_service/qdrant"
        fi
        
        # تشغيل كخدمة خلفية
        nohup "$SCRIPT_DIR/qdrant_service/run_qdrant.sh" > "$SCRIPT_DIR/qdrant_service/qdrant.log" 2>&1 &
        QDRANT_PID=$!
        echo "⏳ تم إطلاق Qdrant برقم معرّف: $QDRANT_PID، بانتظار استجابة المنفذ..."
        
        # انتظار حتى يعمل المنفذ
        for i in {1..20}; do
            if curl -s http://127.0.0.1:6333/collections > /dev/null 2>&1; then
                echo "✅ تم تشغيل Qdrant بنجاح!"
                break
            fi
            sleep 1
        done
    else
        echo "⚠️ لم يتم العثور على سكربت تشغيل Qdrant. يرجى التأكد من تشغيله يدوياً."
    fi
fi

# 3. تشغيل خادم تطبيق المغني (Web UI & API Server)
echo ""
echo "🚀 جاري إطلاق خادم منظومة المغني (FastAPI + Uvicorn)..."
echo "🌐 افتح المتصفح على: http://localhost:8085"
echo "📊 لوحة تحكم المتجهات: http://localhost:6333/dashboard"
echo "========================================================================"
echo "اضغط Ctrl+C لإيقاف الخادم في أي وقت."
echo "========================================================================"

cd "$SCRIPT_DIR/web_ui"
exec python3 server.py
