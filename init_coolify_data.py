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
import urllib.error
import urllib.parse
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
SNAPSHOT_EXPECTED_BYTES = 172 * (1024 ** 3)

def local_mode():
    return os.getenv("ALMUJTAHED_LOCAL", "").strip() == "1"

def qdrant_root():
    if local_mode():
        return ROOT_DIR / "qdrant_service"
    return DATA_DIR / "qdrant"

def bootstrap_status_path():
    if local_mode():
        return ROOT_DIR / "web_ui" / "bootstrap_status.json"
    return DATA_DIR / "web" / "bootstrap_status.json"

# روابط Hugging Face
SNAPSHOT_REPO = "cs95/shamela-full-7m-qdrant"
SNAPSHOT_FILENAME = "shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot"
SHAMELA_DB_REPO = "AuthenticIlm/Shamela4_Full_DB"
EMBEDDING_MODEL_REPO = "cs95/almojtahed-qwen3-8b"

def write_bootstrap_status(phase, message, received_bytes=0, needs_reinstall=False):
    """ملف صغير تقرأه واجهة الصحة. لا يُقاس الحجم عند كل طلب حتى لا يُثقل القرص."""
    try:
        status_path = bootstrap_status_path()
        status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "phase": phase,
            "message": message,
            "received_bytes": int(received_bytes or 0),
            "expected_bytes": SNAPSHOT_EXPECTED_BYTES,
            "needs_reinstall": bool(needs_reinstall),
            "updated_at": time.time(),
        }
        temporary = status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(status_path)
    except Exception as ex:
        print(f"⚠️ تعذر تحديث حالة السحب: {ex}")

def qdrant_bytes_on_disk():
    target = qdrant_root() / "storage" if local_mode() else qdrant_root()
    if not target.exists():
        return 0
    if sys.platform == "win32":
        total = 0
        for root, _dirs, files in os.walk(target):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        return total
    try:
        if sys.platform == "darwin":
            output = subprocess.check_output(["du", "-sk", str(target)], text=True, timeout=60)
            return int(output.split()[0]) * 1024
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

    def stop(self):
        self.finish("snapshot", "جاري سحب سنابشوت المتجهات وتركيبه في Qdrant")

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

def failure_needs_reinstall(ex, archive):
    blob = f"{type(ex).__name__} {ex}".lower()
    markers = ("checksum", "etag", "consistency", "corrupt", "unexpected eof", "bad magic")
    return any(marker in blob for marker in markers)


def snapshot_recovery_client():
    """تركيب ١٧٢ جيجا يستغرق ساعات. مهلة العميل القصيرة كانت تُظهر التلف والملف سليم."""
    from qdrant_client import QdrantClient
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        timeout=24 * 60 * 60,
        check_compatibility=False,
    )

def snapshot_archive_path():
    folder = qdrant_root() / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / SNAPSHOT_FILENAME

def snapshot_bytes_received(folder):
    best = 0
    partial = folder / f"{SNAPSHOT_FILENAME}.partial"
    final = folder / SNAPSHOT_FILENAME
    for path in (partial, final):
        if path.is_file():
            try:
                best = max(best, path.stat().st_size)
            except OSError:
                pass
    cache = folder / ".cache" / "huggingface" / "download"
    if cache.is_dir():
        for item in cache.glob("*.incomplete"):
            try:
                best = max(best, item.stat().st_size)
            except OSError:
                pass
    return best

def adopt_largest_incomplete(folder, partial):
    """ينقل أكبر جزء محفوظ إلى ملف واحد حتى لا يبدأ التحميل من الصفر."""
    cache = folder / ".cache" / "huggingface" / "download"
    best = None
    best_size = partial.stat().st_size if partial.is_file() else 0
    if cache.is_dir():
        for item in cache.glob("*.incomplete"):
            try:
                size = item.stat().st_size
            except OSError:
                continue
            if size > best_size:
                best = item
                best_size = size
    if best is not None:
        partial.parent.mkdir(parents=True, exist_ok=True)
        if partial.exists():
            partial.unlink()
        best.replace(partial)
    if cache.is_dir():
        for item in cache.glob("*.incomplete"):
            try:
                item.unlink()
            except OSError:
                pass

def _snapshot_total(response, start):
    content_range = response.headers.get("Content-Range") or ""
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[-1]
        if total.isdigit():
            return int(total)
    length = response.headers.get("Content-Length")
    if length and str(length).isdigit():
        status = getattr(response, "status", 200)
        return start + int(length) if status == 206 else int(length)
    return 0

def download_snapshot_resume(url, partial, token):
    partial.parent.mkdir(parents=True, exist_ok=True)
    current_url = url
    while True:
        start = partial.stat().st_size if partial.is_file() else 0
        headers = {"User-Agent": "almujtahed-local"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if start:
            headers["Range"] = f"bytes={start}-"
        request = urllib.request.Request(current_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status = getattr(response, "status", 200)
                if start and status == 200:
                    redirected = response.geturl()
                    if redirected != current_url:
                        current_url = redirected
                        continue
                    raise RuntimeError("الخادم تجاهل استئناف التحميل")
                total = _snapshot_total(response, start)
                with partial.open("ab" if status == 206 else "wb") as handle:
                    while True:
                        chunk = response.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        handle.flush()
                size = partial.stat().st_size
                if total and size >= total:
                    return
                if not total and status == 200 and size > start:
                    return
        except urllib.error.HTTPError as ex:
            if ex.code == 416 and start > 0:
                return
            if ex.code in (408, 429, 500, 502, 503, 504):
                time.sleep(5)
                continue
            raise
        except (TimeoutError, urllib.error.URLError, ConnectionError, OSError):
            time.sleep(5)

class _FileProgress:
    """يكتب حجم الملف الناقص كل ١٠ ثوان حتى تستأنف الواجهة من آخر جزء وصل."""

    def __init__(self, folder, phase, message):
        self.folder = folder
        self.phase = phase
        self.message = message
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        write_bootstrap_status(self.phase, self.message, snapshot_bytes_received(self.folder))
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.wait(10):
            write_bootstrap_status(self.phase, self.message, snapshot_bytes_received(self.folder))

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

def download_snapshot_archive():
    archive = snapshot_archive_path()
    free = shutil.disk_usage(archive.parent).free
    need = SNAPSHOT_EXPECTED_BYTES * 2 + 5 * (1024 ** 3)
    if free < need:
        print(f"⚠️ المساحة الحرة {free / (1024 ** 3):.0f} GiB أقل من نحو 350 GiB اللازمة للملف والقاعدة معاً.")
    token = os.getenv("HF_TOKEN") or None
    partial = archive.with_name(archive.name + ".partial")
    adopt_largest_incomplete(archive.parent, partial)
    progress = _FileProgress(archive.parent, "download", "جاري سحب قاعدة البيانات")
    progress.start()
    try:
        if not (archive.is_file() and archive.stat().st_size > 1024 ** 3):
            url = "https://huggingface.co/datasets/" + SNAPSHOT_REPO + "/resolve/main/" + urllib.parse.quote(SNAPSHOT_FILENAME)
            download_snapshot_resume(url, partial, token)
            if partial.is_file():
                partial.replace(archive)
        if not (archive.is_file() and archive.stat().st_size > 1024 ** 3):
            raise RuntimeError("وصل ملف أصغر من السنابشوت المتوقع")
    finally:
        progress.stop()
    return archive

def install_resumable_snapshot(client):
    archive = download_snapshot_archive()
    print("📦 اكتمل ملف السنابشوت. جاري تركيبه في Qdrant، ثم يُحذف الملف.")
    stop = threading.Event()

    def watch():
        while not stop.wait(20):
            write_bootstrap_status("install", "جاري تركيب قاعدة البيانات ... فضلا انتظر حتى تكتمل ويتوقف العداد", qdrant_bytes_on_disk())

    write_bootstrap_status("install", "جاري تركيب قاعدة البيانات ... فضلا انتظر حتى تكتمل ويتوقف العداد", 0)
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    try:
        snapshot_recovery_client().recover_snapshot(
            collection_name=COLLECTION_NAME,
            location=f"file://{archive.resolve()}",
            priority="snapshot",
            wait=True,
        )
    finally:
        stop.set()
        thread.join(timeout=2)
    try:
        archive.unlink()
    except OSError:
        pass
    write_bootstrap_status("ready", "اكتمل تركيب قاعدة البيانات", qdrant_bytes_on_disk())
    print("✅ تم تركيب قاعدة البيانات وحُذف ملف السنابشوت.")

def init_qdrant_snapshot(client):
    """فحص واستعادة لقطة المتجهات في Qdrant"""
    print_banner("1. فحص مخزن متجهات الشاملة (Qdrant Vector Database)")
    if not client:
        print("⏭️ تم تخطي فحص Qdrant لعدم توفر الاتصال حالياً.")
        return

    on_disk = qdrant_root() / "storage" / "collections" / COLLECTION_NAME
    if local_mode():
        if on_disk.is_dir() and any(on_disk.iterdir()):
            print("✅ ملفات قاعدة البيانات موجودة على القرص. لن يُعاد التحميل.")
            write_bootstrap_status("ready", "مخزن المتجهات جاهز", 0)
            return
        archive = snapshot_archive_path()
        archive_ready = False
        try:
            archive_ready = archive.is_file() and archive.stat().st_size > 1024 ** 3
        except OSError:
            archive_ready = False
        try:
            points = 0
            names = [c.name for c in client.get_collections().collections]
            if COLLECTION_NAME in names:
                info = client.get_collection(COLLECTION_NAME)
                points = int(info.points_count or 0)
            if points > 1000:
                print(f"✅ مجموعة الشاملة جاهزة ({points:,} متجهاً). لن يُعاد التحميل.")
                write_bootstrap_status("ready", "مخزن المتجهات جاهز", 0)
                return
            if archive_ready:
                print("✅ ملف قاعدة البيانات موجود. سيُركّب من القرص دون إعادة سحب.")
            install_resumable_snapshot(client)
        except Exception as ex:
            print(f"❌ توقف تنصيب قاعدة البيانات: {ex}")
            archive = snapshot_archive_path()
            damaged = failure_needs_reinstall(ex, archive)
            phase = "install" if archive.is_file() and archive.stat().st_size > 1024 ** 3 else "download"
            message = "توقفت الملفات بسبب تلف أو انقطاع حرج" if damaged else "سيُستأنف التنصيب من الجزء الذي وصل"
            write_bootstrap_status(phase, message, snapshot_bytes_received(archive.parent), needs_reinstall=damaged)
        return

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
            snapshot_recovery_client().recover_snapshot(
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
                snapshot_recovery_client().recover_snapshot(
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
        write_bootstrap_status("error", "توقفت استعادة سنابشوت المتجهات", qdrant_bytes_on_disk(), needs_reinstall=True)

def _repair_lfs_pointer_books(shamela_dir: Path):
    """بعض الكتب الكبيرة تصل كمؤشرات Git LFS وهمية لا كنصوص. تُستكمل ملفاتها الحقيقية هنا."""
    stubs = []
    for pages_file in shamela_dir.glob("*/*/pages.jsonl"):
        try:
            if pages_file.stat().st_size > 512:
                continue
            with open(pages_file, "rb") as handle:
                if handle.read(64).startswith(b"version https://git-lfs"):
                    stubs.append(pages_file)
        except OSError:
            continue
    if not stubs:
        return
    print(f"📥 جاري استكمال نصوص {len(stubs)} كتاباً وصلت ناقصة...")
    token = os.getenv("HF_TOKEN", "").strip() or None
    try:
        from huggingface_hub import hf_hub_download
    except Exception as ex:
        print(f"⚠️ تعذر استكمال الكتب الناقصة: {ex}")
        return
    done = 0
    for pages_file in stubs:
        rel = pages_file.relative_to(shamela_dir).as_posix()
        try:
            src = hf_hub_download(
                repo_id=SHAMELA_DB_REPO,
                repo_type="dataset",
                filename=rel,
                token=token,
            )
            shutil.copyfile(src, pages_file)
            done += 1
            if done % 50 == 0:
                print(f"📥 تم استكمال {done} من {len(stubs)} كتاباً...")
        except Exception as ex:
            print(f"⚠️ تعذر استكمال {rel}: {ex}")
    print(f"✅ تم استكمال {done} من {len(stubs)} كتاباً ناقصاً.")


def init_shamela_databases():
    """فحص وسحب قاعدة نصوص الشاملة الكاملة عبر git clone السريع جداً وتفادي قيود API"""
    print_banner("2. فحص نصوص كتب الشاملة الكاملة (Shamela4 Full DBs)")
    shamela_dir = ROOT_DIR / "shamela4_data"
    shamela_dir.mkdir(parents=True, exist_ok=True)

    # فحص هل المجلد يحتوي على كتب الشاملة
    existing_items = list(shamela_dir.glob("*/*"))
    if len(existing_items) > 100:
        print(f"✅ مكتبة الشاملة مثبتة وموجودة بالفعل! ({len(existing_items)} مجلد كتاب).")
        _repair_lfs_pointer_books(shamela_dir)
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
        _repair_lfs_pointer_books(shamela_dir)
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

    # على السحابة يُحذف الريرانكر لتوفير المساحة. الجهاز المحلي يُبقي ملفاته.
    rerank_gguf_path = gguf_dir / "almojtahed-reranker-8b-Q4_K_M.gguf"
    if rerank_gguf_path.exists() and not local_mode():
        try:
            rerank_gguf_path.unlink()
            print("🧹 تم حذف نموذج الريرانكر لتوفير 4.4 جيجابايت من مساحة القرص.")
        except Exception:
            pass

def main(skip_models=False, only_models=False, snapshot_only=False, texts_only=False):
    global QDRANT_HOST
    if local_mode():
        QDRANT_HOST = "127.0.0.1"
    print("\n" + "=" * 75)
    title = "الجهاز المحلي" if local_mode() else "Coolify"
    print(f"🌟 بدء فحص وتهيئة بيانات منصة المجتهد ({title})")
    print("=" * 75)

    if texts_only:
        # وضع النصوص فقط (Qdrant موقوف بقرار المنتج): لا انتظار محرك ولا سنابشوت.
        init_shamela_databases()
    elif only_models:
        init_ai_models()
    else:
        client = wait_for_qdrant(timeout=45)
        init_qdrant_snapshot(client)
        if not snapshot_only:
            init_shamela_databases()
            if not skip_models:
                init_ai_models()

    print("\n" + "=" * 75)
    print("🎉 اكتمل فحص البيانات بنجاح، جاري بدء تشغيل واجهة المجتهد...")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="تهيئة بيانات المجتهد من Hugging Face")
    parser.add_argument("--local", action="store_true", help="ضع الملفات داخل مجلد المشروع على الجهاز")
    parser.add_argument("--skip-models", action="store_true", help="تخطَّ نموذج التضمين")
    parser.add_argument("--only-models", action="store_true", help="اسحب نموذج التضمين فقط")
    parser.add_argument("--snapshot-only", action="store_true", help="ركّب ملف القاعدة المحلي فقط، بلا سحب جديد")
    parser.add_argument("--texts-only", action="store_true", help="نصوص الشاملة فقط، بلا Qdrant ولا سنابشوت ولا نماذج")
    args = parser.parse_args()
    if args.local:
        os.environ["ALMUJTAHED_LOCAL"] = "1"
        os.environ["QDRANT_HOST"] = "127.0.0.1"
    main(skip_models=args.skip_models, only_models=args.only_models, snapshot_only=args.snapshot_only, texts_only=args.texts_only)
