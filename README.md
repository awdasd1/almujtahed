# 🌟 منظومة المجتهد الشاملة والمستقلة (Al-Mujtahed Standalone Platform)

> **المكتبة الشاملة المضمنة والمكممة - بحث دلالي عميق، استوديو مشاريع، قارئ شاملة، ووكلاء مساعدون**  
> نسخة محمولة ذاتياً (Self-Contained & Fully Portable) مهيأة للنقل والتشغيل على أي جهاز أو سيرفر جديد بنسبة **100% دون أي فقد في البيانات أو النماذج**.

---

## 📦 محتويات حزمة «المجتهد» المستقلة (`almujtahed/`)

تحتوي هذه الحزمة على كافة الملفات التشغيلية والمخازن المتجهة والنماذج وقواعد البيانات في مكان واحد:

```
almujtahed/
├── 🚀 start_almujtahed.sh          # سكربت التشغيل الموحد بنقرة واحدة (Qdrant + FastAPI Web Server)
├── 📄 requirements.txt            # كافة اعتماديات ومكتبات بايثون المطلوبة
├── 📚 books.csv                   # الفهرس الببليوغرافي الشامل (8,589 كتاباً ومؤلفاً)
├── 🗄️ shamela_index.db            # قاعدة بيانات SQLite لفهارس الكتب والتصنيفات (8,589 كتاباً)
│
├── ⚙️ web_ui/                      # خادم المنظومة الكامل والواجهة التفاعلية (FastAPI)
│   ├── server.py                  # خادم الـ Backend المحدث بمسارات محمولة ذاتية
│   ├── shamela_local_mcp.py       # خادم MCP المحلي لربط الشاملة بأدوات الذكاء
│   ├── astronomy_engine.py        # محرك التحقق الفلكي ومطابقة التقاويم الهجرية والميلادية
│   ├── agent_groups_data.json     # قاعدة بيانات مجموعات الوكلاء الشرعيين المساعدين
│   ├── projects_data.json         # قاعدة بيانات استوديو المشاريع البحثية والجولات
│   ├── tools_data.json            # مركز الأدوات البرمجية والبصرية والـ Sandbox
│   ├── providers_data.json        # مفاتيح API ونماذج الاستدلال
│   ├── static/                    # التصميم ونظام الألوان claude_theme.css ومكتبات العرض
│   ├── templates/                 # صفحات الواجهة (index.html, mindmap.html)
│   └── uploads/                   # مجلد الحفظ المركزي (Bucket) لملفات وصور المستخدم
│
├── 🧠 models/                      # نماذج التضمين الدلالي الشرعي المكممة
│   └── gguf/
│       └── almojtahed-embedding-8b-Q4_K_M.gguf  # نموذج التضمين الدلالي 8B (4.4 GB)
│
├── 🗄️ qdrant_service/             # محرك وقاعدة بيانات المتجهات Qdrant الجاهزة للعمل
│   ├── qdrant                     # الملف التنفيذي لمحرك Qdrant
│   ├── run_qdrant.sh              # سكربت تشغيل خدمة Qdrant على المنفذ 6333
│   ├── config/config.yaml         # إعدادات الخدمة والتخزين
│   ├── storage/collections/
│   │   └── shamela_almojtahed_8b_dense/  # مخزن المتجهات الحي والمفعل فوراً (8.15M مقطع - 172 GB)
│   └── snapshots/
│       └── shamela_almojtahed_8b_dense.snapshot # ملف اللقطة الاحتياطية الكاملة (171 GB)
│
├── 📖 shamela4_data/              # نصوص الشاملة الكاملة للقارئ التراثي (40 تصنيفاً - 19 GB)
└── 🔬 inference_models/           # محرك الاستدلال والفحص المحلي (inference_engine.py)
```

---

## 🚚 طريقة نقل المنظومة إلى جهاز جديد بنسبة 100%

### الخطوة 1: نسخ المجلد إلى الجهاز الجديد
قم بنسخ مجلد `almujtahed` بالكامل عبر قرص تخزين خارجي (External SSD) أو عبر الشبكة:
```bash
# على سبيل المثال، نسخ المجلد كاملاً إلى مسارك المفضل في الجهاز الجديد
cp -R /path/to/almujtahed /home/username/almujtahed
```

---

### الخطوة 2: تثبيت بيئة بايثون والاعتماديات
في الجهاز الجديد، افتح الطرفية (Terminal) داخل مجلد `almujtahed` وشغل:
```bash
cd almujtahed

# يُفضل إنشاء بيئة وهمية معزولة
python3 -m venv .venv
source .venv/bin/activate

# تثبيت متطلبات التشغيل
pip install -r requirements.txt
```

> **ملاحظة لنماذج GGUF على ماك (Metal) أو لينكس (CUDA):**
> لتفعيل تسريع المعالج الرسومي (Metal على Mac Apple Silicon):
> ```bash
> CMAKE_ARGS="-DGGML_METAL=on" pip install --upgrade --force-reinstall llama-cpp-python
> ```
> أو على سيرفرات لينكس ذات كروت Nvidia (CUDA):
> ```bash
> CMAKE_ARGS="-DGGML_CUDA=on" pip install --upgrade --force-reinstall llama-cpp-python
> ```

---

### الخطوة 3: تشغيل المنظومة بنقرة واحدة 🚀

فقط قم بتشغيل السكربت الموحد:
```bash
./start_almujtahed.sh
```

يقوم هذا السكربت تلقائياً بالآتي:
1. فحص بيئة بايثون وتوافر الحزم.
2. تشغيل خدمة مخزن المتجهات **Qdrant** على المنفذ `6333` بالبيانات الحية المفهرسة مسبقاً (8.15 مليون مقطع).
3. إطلاق خادم الويب **FastAPI** على المنفذ `8085`.
4. فتح المنظومة في المتصفح عبر الرابط:
   - **الواجهة الرئيسية**: `http://localhost:8085`
   - **لوحة تحكم المتجهات Qdrant**: `http://localhost:6333/dashboard`

---

## 🐳 خيار بديل: تشغيل Qdrant عبر دوكر (Docker)
إذا كنت تنتقل إلى نظام تشغيل مختلف (مثل Ubuntu Linux) وترغب في تشغيل Qdrant عبر Docker مع استخدام نفس مجلد البيانات المنسوخ دون إعادة فهرسة:
```bash
cd almujtahed/qdrant_service
docker run -d -p 6333:6333 -p 6334:6334 \
  -v "$(pwd)/storage:/qdrant/storage" \
  qdrant/qdrant
```
ثم شغل خادم التطبيق مباشرة:
```bash
cd ../web_ui
python3 server.py
```
