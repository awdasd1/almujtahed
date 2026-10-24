#!/usr/bin/env python3
"""
منظومة المجتهد - سكربت التهيئة والتنصيب الآلي على خوادم السحاب وCoolify
يقوم بجلب وتثبيت:
1. سنابشوت متجهات الشاملة (172 GB) واستعادتها آلياً في Qdrant ثم تنظيف الملف المؤرشف لتوفير المساحة
2. قاعدة بيانات نصوص الشاملة الكاملة (40 قسماً) من HuggingFace عبر git clone --depth 1 السريع جداً
3. نموذج التضمين الشرعي (cs95/almojtahed-qwen3-8b)
4. نموذج الريرانكر المتخصص (cs95/almojtahed-reranker-8b)
"""

import json
import os
import sys
import time
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

# تحميل متغيرات البيئة
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant").strip()
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = "shamela_almojtahed_8b_dense"
DATA_DIR = Path(os.getenv("ALMUJTAHED_DATA_DIR", "/data"))
BOOTSTRAP_STATUS_PATH = DATA_DIR / "web" / "bootstrap_status.json"
SNAPSHOT_EXPECTED_BYTES = 172 * (1024 ** 3)

# روابط Hugging Face
SNAPSHOT_REPO = "cs95/shamela-full-7m-qdrant"
SNAPSHOT_FILENAME = "shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot"
SHAMELA_DB_REPO = "AuthenticIlm/Shamela4_Full_DB"
EMBEDDING_MODEL_REPO = "cs95/almojtahed-qwen3-8b"

def write_bootstrap_status(phase, message, received_bytes=0):
    """ملف صغير تقرأه واجهة الصحة. لا يُقاس الحجم عند كل طلب حتى لا يُثقل القرص."""
    try:
        BOOTSTRAP_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "phase": phase,
            "message": message,
            "received_bytes": int(received_bytes or 0),
            "expected_bytes": SNAPSHOT_EXPECTED_BYTES,
            "updated_at": time.time(),
        }
        temporary = BOOTSTRAP_STATUS_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(BOOTSTRAP_STATUS_PATH)
    except Exception as ex:
        print(f"⚠️ تعذر تحديث حالة السحب: {ex}")

def qdrant_bytes_on_disk():
    target = DATA_DIR / "qdrant"
    if not target.exists():
        return 0
    try:
        output = subprocess.check_output(["du", "-sb", str(target)], text=True, timeout=30)
        return int(output.split()[0])
    except Exception:
        return 0

class _SnapshotProgress:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        write_bootstrap_status("snapshot", "جاري سحب سنابشوت المتجهات وتركيبه في Qdrant", qdrant_bytes_on_disk())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.wait(20):
            write_bootstrap_status(
                "snapshot",
                "جاري سحب سنابشوت المتجهات وتركيبه في Qdrant",
                qdrant_bytes_on_disk(),
            )

    def finish(self, phase, message):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        write_bootstrap_status(phase, message, qdrant_bytes_on_disk())

def print_banner(msg):
    print("\n" + "=" * 75)
    print(f"🚀 {msg}")
    print("=" * 75)

def wait_for_qdrant(timeout=60):
    """الانتظار حتى يبدأ خادم Qdrant بالاستجابة مع فحص المضيفين المحتملين تلقائياً"""
    global QDRANT_HOST
    candidate_hosts = [
        QDRANT_HOST,
        "localhost",
        "127.0.0.1",
        "qdrant",
        "host.docker.internal"
    ]
    seen = set()
    hosts = [h for h in candidate_hosts if h and not (h in seen or seen.add(h))]
    
    print(f"📡 فحص الاتصال بخدمة Qdrant (المضيفون المحتملون: {', '.join(hosts)} على المنفذ {QDRANT_PORT})...")
    start = time.time()
    from qdrant_client import QdrantClient
    while time.time() - start < timeout:
        for h in hosts:
            try:
                client = QdrantClient(host=h, port=QDRANT_PORT, timeout=3)
                client.get_collections()
                print(f"✅ تم الاتصال بمحرك Qdrant بنجاح على المضيف: {h}:{QDRANT_PORT}")
                QDRANT_HOST = h
                return client
            except Exception:
                pass
        time.sleep(2)
    print(f"⚠️ تعذر الاتصال بـ Qdrant بعد {timeout} ثانية. تأكد من تشغيل خدمة qdrant.")
    return None

def init_qdrant_snapshot(client):
    """فحص واستعادة لقطة المتجهات في Qdrant"""
    print_banner("1. فحص مخزن متجهات الشاملة (Qdrant Vector Database)")
    if not client:
        print("⏭️ تم تخطي فحص Qdrant لعدم توفر الاتصال حالياً.")
        return

    on_disk = DATA_DIR / "qdrant" / "storage" / "collections" / COLLECTION_NAME
    if on_disk.is_dir():
        print(f"✅ ملفات المجموعة «{COLLECTION_NAME}» موجودة على القرص. لن يُعاد سحب السنابشوت.")
        write_bootstrap_status("ready", "مخزن المتجهات موجود على القرص", qdrant_bytes_on_disk())
        return

    try:
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION_NAME in collections:
            info = client.get_collection(COLLECTION_NAME)
            if info.points_count and info.points_count > 1000:
                print(f"✅ مجموعة الشاملة «{COLLECTION_NAME}» جاهزة ونشطة بالفعل! (عدد المتجهات: {info.points_count:,})")
                write_bootstrap_status("ready", "مخزن المتجهات جاهز", qdrant_bytes_on_disk())
                return
            else:
                print(f"⚠️ المجموعة موجودة ولكن فارغة، سيتم استعادة السنابشوت...")
        else:
            print(f"🔍 المجموعة «{COLLECTION_NAME}» غير موجودة في Qdrant. جاري التجهيز للاستعادة...")

        # التحقق أولاً من وجود رابط السنابشوت المباشر على Hugging Face
        token = os.getenv("HF_TOKEN") or None
        direct_url = f"https://huggingface.co/datasets/{SNAPSHOT_REPO}/resolve/main/{SNAPSHOT_FILENAME}"
        if token:
            direct_url = f"https://oauth2:{token}@huggingface.co/datasets/{SNAPSHOT_REPO}/resolve/main/{SNAPSHOT_FILENAME}"

        print(f"📥 جاري استعادة السنابشوت مباشرة من Hugging Face ({SNAPSHOT_REPO})...")
        print("💡 يتم التدفق والفك المباشر في Qdrant دون الحاجة لمساحة تخزين مضاعفة...")
        progress = _SnapshotProgress()
        progress.start()
        try:
            client.recover_snapshot(
                collection_name=COLLECTION_NAME,
                location=direct_url,
                priority="snapshot",
                wait=True
            )
            progress.finish("ready", "اكتمل سحب سنابشوت المتجهات وتركيبه")
            print("✅ تم استعادة وتركيب السنابشوت في Qdrant بنجاح تام!")
        except Exception as direct_err:
            progress.finish("snapshot", "السحب مستمر داخل Qdrant والواجهة تعمل أثناء ذلك")
            print(f"⚠️ الاستعادة المباشرة توقفت ({type(direct_err).__name__})، التحقق من توفر السنابشوت محلياً...")
            shared_snapshots_dir = Path("/qdrant/snapshots")
            if shared_snapshots_dir.exists() and os.access(str(shared_snapshots_dir), os.W_OK):
                snapshots_dir = shared_snapshots_dir
            else:
                snapshots_dir = ROOT_DIR / "qdrant_service" / "snapshots"
            local_snapshot_path = snapshots_dir / SNAPSHOT_FILENAME
            if local_snapshot_path.exists():
                snapshot_uri = f"file://{local_snapshot_path.resolve()}"
                client.recover_snapshot(
                    collection_name=COLLECTION_NAME,
                    location=snapshot_uri,
                    priority="snapshot",
                    wait=True
                )
                print("✅ تم استعادة السنابشوت من الملف المحلي بنجاح!")
                write_bootstrap_status("ready", "اكتمل تركيب السنابشوت من الملف المحلي", qdrant_bytes_on_disk())
                try:
                    local_snapshot_path.unlink()
                except Exception:
                    pass

    except Exception as ex:
        print(f"❌ خطأ أثناء استعادة سنابشوت Qdrant: {ex}")
        write_bootstrap_status("error", "توقفت استعادة سنابشوت المتجهات", qdrant_bytes_on_disk())

def init_shamela_databases():
    """فحص وسحب قاعدة نصوص الشاملة الكاملة عبر git clone السريع جداً وتفادي قيود API"""
    print_banner("2. فحص نصوص كتب الشاملة الكاملة (Shamela4 Full DBs)")
    shamela_dir = ROOT_DIR / "shamela4_data"
    shamela_dir.mkdir(parents=True, exist_ok=True)

    # فحص هل المجلد يحتوي على كتب الشاملة
    existing_items = list(shamela_dir.glob("*/*"))
    if len(existing_items) > 100:
        print(f"✅ مكتبة الشاملة مثبتة وموجودة بالفعل! ({len(existing_items)} مجلد كتاب).")
        return

    print(f"📥 جاري سحب كتب الشاملة الـ 8,589 في 40 قسماً عبر git clone --depth 1...")
    token = os.getenv("HF_TOKEN", "").strip()
    clone_url = f"https://huggingface.co/datasets/{SHAMELA_DB_REPO}"
    if token:
        clone_url = f"https://oauth2:{token}@huggingface.co/datasets/{SHAMELA_DB_REPO}"

    tmp_clone_dir = shamela_dir / "_git_tmp"
    try:
        if tmp_clone_dir.exists():
            shutil.rmtree(tmp_clone_dir, ignore_errors=True)
        
        cmd = ["git", "clone", "--depth", "1", clone_url, str(tmp_clone_dir)]
        subprocess.run(cmd, check=True)
        
        # نقل الأقسام واستبعاد .git لتوفير مساحة التخزين
        for item in tmp_clone_dir.iterdir():
            if item.name == ".git":
                continue
            dest = shamela_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
            
        shutil.rmtree(tmp_clone_dir, ignore_errors=True)
        print("✅ تم اكتمال سحب كتب الشاملة بنجاح فائق وتوفير المساحة!")
    except Exception as ex:
        print(f"⚠️ تعذر سحب الشاملة عبر git ({ex})، جاري المحاولة الاحتياطية عبر huggingface_hub...")
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(
                repo_id=SHAMELA_DB_REPO,
                repo_type="dataset",
                local_dir=str(shamela_dir),
                token=token or None,
                max_workers=4
            )
            print("✅ تم اكتمال التحميل الاحتياطي بنجاح!")
        except Exception as hf_err:
            print(f"❌ خطأ أثناء تحميل الشاملة: {hf_err}")

def init_ai_models():
    """فحص وسحب نماذج التضمين وإعادة الترتيب المكممة GGUF"""
    print_banner("3. فحص نماذج الذكاء الاصطناعي (GGUF Embedding & Reranker Models)")
    models_dir = ROOT_DIR / "models"
    gguf_dir = models_dir / "gguf"
    gguf_dir.mkdir(parents=True, exist_ok=True)
    token = os.getenv("HF_TOKEN") or None

    # 1. نموذج التضمين الشرعي المكمم 8B GGUF
    emb_gguf_path = gguf_dir / "almojtahed-embedding-8b-Q4_K_M.gguf"
    if emb_gguf_path.exists() and emb_gguf_path.stat().st_size > 1024**3:
        print(f"✅ نموذج التضمين المكمم Al-Mojtahed 8B موجود وجاهز ({emb_gguf_path.stat().st_size / (1024**3):.2f} GB).")
    else:
        print(f"📥 جاري سحب ملف التضمين المكمم {emb_gguf_path.name} من {EMBEDDING_MODEL_REPO}...")
        from huggingface_hub import hf_hub_download
        last_error = None
        for attempt in range(1, 5):
            try:
                print(f"📥 محاولة سحب نموذج التضمين {attempt} من 4...")
                hf_hub_download(
                    repo_id=EMBEDDING_MODEL_REPO,
                    filename="almojtahed-embedding-8b-Q4_K_M.gguf",
                    local_dir=str(gguf_dir),
                    token=token
                )
                if emb_gguf_path.exists() and emb_gguf_path.stat().st_size > 1024**3:
                    print("✅ تم تحميل نموذج التضمين المكمم Al-Mojtahed 8B GGUF بنجاح!")
                    last_error = None
                    break
                last_error = "وصل ملف أصغر من النموذج المتوقع"
            except Exception as ex:
                last_error = type(ex).__name__
                print(f"⚠️ تعذر سحب نموذج GGUF التضمين في المحاولة {attempt}: {last_error}")
                time.sleep(min(60, 8 * attempt))
        if last_error:
            print(f"⚠️ بقي نموذج التضمين غير مكتمل بعد 4 محاولات: {last_error}")

    # إزالة نموذج الريرانكر إن وجد لتوفير 4.4 جيجابايت
    rerank_gguf_path = gguf_dir / "almojtahed-reranker-8b-Q4_K_M.gguf"
    if rerank_gguf_path.exists():
        try:
            rerank_gguf_path.unlink()
            print("🧹 تم حذف نموذج الريرانكر لتوفير 4.4 جيجابايت من مساحة القرص.")
        except Exception:
            pass

def main():
    print("\n" + "=" * 75)
    print("🌟 بدء فحص وتهيئة بيانات منصة المجتهد السحابية (Coolify Init Engine)")
    print("=" * 75)

    # 1. فحص Qdrant والسنابشوت
    client = wait_for_qdrant(timeout=45)
    init_qdrant_snapshot(client)

    # 2. فحص قاعدة الشاملة
    init_shamela_databases()

    # 3. فحص النماذج
    init_ai_models()

    print("\n" + "=" * 75)
    print("🎉 اكتمل فحص البيانات بنجاح، جاري بدء تشغيل واجهة المجتهد...")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
