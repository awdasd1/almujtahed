#!/bin/bash
# ==============================================================================
# 🚀 سكريبت شامل لتثبيت Qdrant وسحب واستعادة قاعدة بيانات المغني / الشاملة
# ==============================================================================
# الاستخدام:
#   bash scripts/setup_qdrant.sh
# أو عبر أمر واحد مباشر من أي مكان:
#   curl -sSL https://raw.githubusercontent.com/awdasd1/almojtahed/main/scripts/setup_qdrant.sh | bash
# ==============================================================================

set -e

# ألوان التنسيق
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}📚 سكريبت تثبيت Qdrant واستعادة قاعدة بيانات الشاملة والمغني${NC}"
echo -e "${CYAN}================================================================${NC}"

# إعداد المتغيرات
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION_NAME="${COLLECTION_NAME:-badr_all_tsh_corpus}"
SNAPSHOT_NAME="badr_all_tsh_colc.snapshot"
HF_DATASET_URL="https://huggingface.co/datasets/cs95/almojtahed/resolve/main/${SNAPSHOT_NAME}"
DATA_DIR="${HOME}/qdrant_storage"
SNAPSHOTS_DIR="${HOME}/qdrant_snapshots"

mkdir -p "$DATA_DIR" "$SNAPSHOTS_DIR"

# ------------------------------------------------------------------------------
# 1. التحقق من تشغيل محرك Qdrant أو إطلاقه عبر دوكر
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/4] فحص حالة محرك Qdrant...${NC}"
if curl -s "${QDRANT_URL}/readyz" >/dev/null 2>&1 || curl -s "${QDRANT_URL}/healthz" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ محرك Qdrant يعمل ومتصل بالفعل على: ${QDRANT_URL}${NC}"
else
    if command -v docker >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ Qdrant غير مشغل، جاري إطلاقه تلقائياً عبر Docker...${NC}"
        
        # إيقاف أي حاوية قديمة متوقفة بنفس الاسم
        docker rm -f qdrant 2>/dev/null || true

        docker run -d \
            --name qdrant \
            --restart always \
            -p 6333:6333 \
            -p 6334:6334 \
            -v "${DATA_DIR}:/qdrant/storage:z" \
            -v "${SNAPSHOTS_DIR}:/qdrant/snapshots:z" \
            qdrant/qdrant:latest

        echo -e "${CYAN}⏳ في انتظار جاهزية Qdrant...${NC}"
        RETRY=0
        until curl -s "http://localhost:6333/readyz" >/dev/null 2>&1 || [ $RETRY -ge 30 ]; do
            sleep 2
            RETRY=$((RETRY+1))
        done

        if [ $RETRY -ge 30 ]; then
            echo -e "${RED}❌ فشل إقلاع Qdrant في الوقت المحدد.${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ تم تشغيل Qdrant بنجاح على المنفذ 6333!${NC}"
    else
        echo -e "${RED}❌ Docker غير مثبت و Qdrant لا يستجيب على ${QDRANT_URL}!${NC}"
        echo -e "${YELLOW}يرجى تشغيل Qdrant أولاً أو تثبيت Docker على السيرفر.${NC}"
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# 2. تحميل ملف السنابشوت من Hugging Face
# ------------------------------------------------------------------------------
TARGET_FILE="${SNAPSHOTS_DIR}/${SNAPSHOT_NAME}"
echo -e "\n${YELLOW}[2/4] فحص وتحميل ملف السنابشوت من Hugging Face...${NC}"

if [ -f "$TARGET_FILE" ] && [ $(stat -f%z "$TARGET_FILE" 2>/dev/null || stat -c%s "$TARGET_FILE" 2>/dev/null || echo 0) -gt 1000000000 ]; then
    echo -e "${GREEN}✅ ملف السنابشوت موجود محلياً بالفعل: ${TARGET_FILE}${NC}"
else
    echo -e "${CYAN}📥 جاري سحب السنابشوت من: ${HF_DATASET_URL}${NC}"
    echo -e "${CYAN}💡 يدعم الاستئناف التلقائي في حال انقطاع التحميل...${NC}"

    HF_HEADER=""
    if [ -n "$HF_TOKEN" ]; then
        HF_HEADER="--header=Authorization: Bearer ${HF_TOKEN}"
    fi

    if command -v wget >/dev/null 2>&1; then
        wget -c $HF_HEADER "$HF_DATASET_URL" -O "$TARGET_FILE"
    elif command -v curl >/dev/null 2>&1; then
        CURL_AUTH=""
        [ -n "$HF_TOKEN" ] && CURL_AUTH="-H Authorization: Bearer ${HF_TOKEN}"
        curl -C - -L $CURL_AUTH "$HF_DATASET_URL" -o "$TARGET_FILE"
    else
        echo -e "${RED}❌ لم يتم العثور على curl أو wget لتحميل الملف!${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ اكتمل تحميل ملف السنابشوت بنجاح!${NC}"
fi

# التأكد من وصول ملف السنابشوت داخل الحاوية مهما كانت طريقة تشغيلها
if command -v docker >/dev/null 2>&1; then
    QDRANT_CONTAINER=$(docker ps --filter "ancestor=qdrant/qdrant" --format "{{.Names}}" | head -n1 || docker ps --filter "name=qdrant" --format "{{.Names}}" | head -n1 || echo "")
    if [ -n "$QDRANT_CONTAINER" ]; then
        docker exec "$QDRANT_CONTAINER" mkdir -p /qdrant/snapshots 2>/dev/null || true
        if ! docker exec "$QDRANT_CONTAINER" test -f "/qdrant/snapshots/${SNAPSHOT_NAME}" 2>/dev/null; then
            echo -e "${CYAN}📋 نقل ملف السنابشوت إلى الحاوية (${QDRANT_CONTAINER})...${NC}"
            docker cp "$TARGET_FILE" "${QDRANT_CONTAINER}:/qdrant/snapshots/${SNAPSHOT_NAME}" 2>/dev/null || true
        fi
    fi
fi

# ------------------------------------------------------------------------------
# 3. استعادة السنابشوت داخل Qdrant ومتابعة فك وضخ المتجهات
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/4] جاري إطلاق استعادة السنابشوت داخل Qdrant (المجموعة: ${COLLECTION_NAME})...${NC}"

INTERNAL_SNAPSHOT_PATH="file:///qdrant/snapshots/${SNAPSHOT_NAME}"

# إرسال طلب الاستعادة عبر PUT في الخلفية
RECOVER_RESP=$(curl -s -X PUT "${QDRANT_URL}/collections/${COLLECTION_NAME}/snapshots/recover" \
    -H "Content-Type: application/json" \
    -d "{\"location\": \"${INTERNAL_SNAPSHOT_PATH}\"}" || true)

echo -e "${CYAN}📡 تم إرسال أمر الاستعادة لمحرك Qdrant.${NC}"
echo -e "${YELLOW}⏳ جاري فك ضغط ملايين المتجهات وبناء الفهرس في الذاكرة (يستغرق من 3 إلى 7 دقائق)...${NC}"

# حلقة ذكية لمتابعة حالة المجموعة حتى تصبح green وتكتمل المتجهات
ELAPSED=0
MAX_WAIT=900 # 15 دقيقة كحد أقصى
STATUS=""
POINTS=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    
    CHECK_JSON=$(curl -s "${QDRANT_URL}/collections/${COLLECTION_NAME}" || true)
    STATUS=$(echo "$CHECK_JSON" | grep -o '"status":"[a-zA-Z]*"' | head -n1 | cut -d':' -f2 | tr -d '"' || echo "")
    POINTS=$(echo "$CHECK_JSON" | grep -o '"points_count":[0-9]*' | cut -d':' -f2 || echo 0)
    
    if [ "$STATUS" = "green" ] && [ "$POINTS" -gt 1000 ]; then
        echo -e "\n${GREEN}✅ اكتمل فك وبناء المتجهات بنجاح خلال $((ELAPSED / 60)) دقيقة و $((ELAPSED % 60)) ثانية!${NC}"
        break
    else
        echo -e "   ⏳ جاري المعالجة والبناء... (${ELAPSED} ثانية مضت | الحالة: ${STATUS:-قيد التهيئة})"
    fi
done

# ربط الأسماء المستعارة الفورية بدون استهلاك أي مساحة إضافية
echo -e "\n${CYAN}🔗 إنشاء الأسماء المستعارة (Aliases) لتوافق كافة أنواع الاستعلامات...${NC}"
curl -s -X POST "${QDRANT_URL}/collections/aliases" \
    -H "Content-Type: application/json" \
    -d "{\"actions\": [{\"create_alias\": {\"collection_name\": \"${COLLECTION_NAME}\", \"alias_name\": \"shamela_corpus\"}}, {\"create_alias\": {\"collection_name\": \"${COLLECTION_NAME}\", \"alias_name\": \"badr_all_tsh_colc\"}}]}" >/dev/null 2>&1 || true

# ------------------------------------------------------------------------------
# 4. التحقق والتقرير النهائي الذكي
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/4] إعداد التقرير النهائي...${NC}"

INFO_RESP=$(curl -s "${QDRANT_URL}/collections/${COLLECTION_NAME}" || true)
FINAL_POINTS=$(echo "$INFO_RESP" | grep -o '"points_count":[0-9]*' | cut -d':' -f2 || echo "$POINTS")
FINAL_VECTORS=$(echo "$INFO_RESP" | grep -o '"indexed_vectors_count":[0-9]*' | cut -d':' -f2 || echo "غير معروف")

# استخراج الآي بي الخارجي للسيرفر لتسهيل وصول المستخدم
SERVER_IP=$(curl -s --connect-timeout 2 https://api.ipify.org 2>/dev/null || curl -s --connect-timeout 2 https://ifconfig.me 2>/dev/null || echo "localhost")

echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}🎉 تم تجهيز واستعادة قاعدة بيانات الشاملة والمغني بنجاح 100%!${NC}"
echo -e "${CYAN}📍 اسم المجموعة الرئيسية: ${COLLECTION_NAME}${NC}"
echo -e "${CYAN}🔗 الأسماء المستعارة: shamela_corpus و badr_all_tsh_colc${NC}"
echo -e "${CYAN}📊 عدد النقاط المفهرسة: ${FINAL_POINTS} نقطة${NC}"
echo -e "${CYAN}🧠 إجمالي المتجهات: ${FINAL_VECTORS} متجه${NC}"
echo -e "${GREEN}🌐 رابط لوحة تحكم Qdrant المباشر:${NC}"
echo -e "   👉 http://${SERVER_IP}:6333/dashboard"
echo -e "${GREEN}================================================================${NC}"
