#!/usr/bin/env python3
"""ربط مكتبة الشاملة المحلية (تطبيق الشاملة الجديد) بالمجتهد.

الفكرة: أغلب الباحثين لديهم تطبيق الشاملة أصلًا. بدل تنزيل المكتبة كاملة:
1) كشف: نعثر على بيانات التطبيق ونقرأ كتالوجه `master.db` ونعدّ الكتب
   المنزّلة فعلًا (التطبيق ينزّل النصوص عند الطلب، فالكتالوج وحده لا يكفي).
2) استيراد: نصوص الكتب المنزّلة محفوظة عندهم داخل فهرس Lucene؛ نقرؤه
   بأدواتهم المدمجة نفسها (JRE + حزم Lucene داخل التطبيق، عبر JPype)
   ونحوّل كل كتاب مرة واحدة إلى صيغة المجتهد الداخلية (`pages.jsonl`
   ورفيقاتها) تحت مجلد استيراد خاص. بعد التحويل لا يعتمد المجتهد على
   بنيتهم الداخلية في شيء: المستورَد كتاب أصلي عندنا يُفهرس ويُبحث
   ويُتحقق منه كسائر المكتبة.

تنبيه هوية مثبت بالفحص: ترقيم كتب الشاملة الجديد مختلف كليًا عن ترقيم
الشاملة 4 عندنا (كتابهم 1458 ليس البخاري). فالمستورَد يأخذ عندنا رقمًا
جديدًا من نطاق خاص (900000+) ويحتفظ برقمهم في `shamela_id`، والمطابقة
مع مكتبتنا تكون بالعنوان والمؤلف لا بالرقم.

الاستعمال اليدوي:
  python3 shamela_link.py status
  python3 shamela_link.py import [--books 1458,6494] [--force] [--out DIR]
"""
import glob
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
from pathlib import Path

# أقفال لكل كتاب على حدة (1.10.270): استخراجان متزامنان للكتاب نفسه (مُسخِّن
# المجلس + لمس كسول من وكيل) كانا يكتبان الملفات نفسها معًا فيفسدانها،
# وقارئ أثناء الكتابة يرى صفحات ناقصة فيُسقط الشواهد.
_BOOK_LOCKS: dict = {}
_BOOK_LOCKS_GUARD = threading.Lock()


def _book_lock(tid: int) -> threading.Lock:
    with _BOOK_LOCKS_GUARD:
        lk = _BOOK_LOCKS.get(int(tid))
        if lk is None:
            lk = threading.Lock()
            _BOOK_LOCKS[int(tid)] = lk
        return lk


def _atomic_write(path: Path, text: str):
    tmp = path.with_name(f"{path.name}.tmp{threading.get_ident()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
NEW_ID_BASE = 900000  # نطاق أرقام الكتب المستوردة عندنا (لا يصادم أي ترقيم)

# ---------------------------------------------------------------- كشف المواضع

def _candidate_shamela_roots():
    home = Path.home()
    roots = []
    env = os.getenv("SHAMELA_APP_DIR", "").strip()
    if env:
        roots.append(Path(env).expanduser())
    roots += [
        home / "Library" / "Application Support" / "Shamela",          # macOS
        Path(os.getenv("APPDATA", "")) / "Shamela" if os.getenv("APPDATA") else None,
        Path(os.getenv("LOCALAPPDATA", "")) / "Shamela" if os.getenv("LOCALAPPDATA") else None,
        home / "AppData" / "Roaming" / "Shamela",                      # Windows احتياطي
    ]
    return [r for r in roots if r]


def find_shamela_root():
    """مجلد تطبيق الشاملة الذي فيه قاعدة البيانات، أو None."""
    for root in _candidate_shamela_roots():
        if (root / "database" / "master.db").exists():
            return root
    return None


def import_dir() -> Path:
    """مجلد الكتب المستوردة من الشاملة (قابل للكتابة دائمًا، خارج الحزمة)."""
    env = os.getenv("ALMUJTAHED_SHAMELA_IMPORT_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Al-Mujtahed" / "runtime" / "shamela_imported"
    if os.getenv("APPDATA"):
        return Path(os.getenv("APPDATA")) / "Al-Mujtahed" / "runtime" / "shamela_imported"
    return home / ".almujtahed" / "shamela_imported"


def mirror_dir() -> Path:
    """مرآة قاعدة الشاملة داخل تطبيقنا (الخطة الثانية، 1.10.270): نسخة من
    مجلد database وحده (الفهرس + قواعد الكتب) تُزامَن تفاضليًا، فيقرأ الجسر
    والاستخراج منها لا من تثبيت الشاملة — استقلال عن موضعه وتغيّراته."""
    env = os.getenv("ALMUJTAHED_SHAMELA_MIRROR_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    return import_dir().parent / "shamela_mirror"


def mirror_ready() -> bool:
    if os.getenv("ALMUJTAHED_MIRROR", "").strip().lower() == "off":
        return False
    md = mirror_dir()
    return (md / ".mirror_ok").exists() and (md / "database" / "store" / "page").exists()


def data_database_dir():
    """مجلد قاعدة بيانات الشاملة الحاكم للقراءة: مرآتنا إن اكتملت، وإلا الأصل."""
    if mirror_ready():
        return mirror_dir() / "database"
    root = find_shamela_root()
    return (root / "database") if root else None


_MIRROR_SYNC_LOCK = threading.Lock()


def sync_mirror(progress=lambda m: None) -> dict:
    """مزامنة تفاضلية لقاعدة الشاملة إلى مرآتنا: الجديد والمتغير فقط،
    وملفات segments_* أخيرًا حتى لا يشير فهرس المرآة إلى مقاطع لم تصل.
    اكتمالها يرفع علم .mirror_ok فتتحول القراءة إليها من أول بحث تالٍ."""
    root = find_shamela_root()
    if not root:
        return {"ok": False, "message": "لم يُعثر على الشاملة"}
    if not _MIRROR_SYNC_LOCK.acquire(blocking=False):
        return {"ok": False, "message": "مزامنة جارية"}
    try:
        src = root / "database"
        dst = mirror_dir() / "database"
        dst.mkdir(parents=True, exist_ok=True)
        copied = deleted = scanned = 0
        segments = []

        def _stale(s: Path, d: Path) -> bool:
            try:
                if not d.exists():
                    return True
                ss, dd = s.stat(), d.stat()
                return ss.st_size != dd.st_size or int(ss.st_mtime) != int(dd.st_mtime)
            except Exception:
                return True

        for dirpath, _dirs, files in os.walk(src):
            rel_dir = Path(dirpath).relative_to(src)
            for name in files:
                scanned += 1
                s, d = Path(dirpath) / name, dst / rel_dir / name
                if name.startswith("segments"):
                    segments.append((s, d))
                    continue
                if _stale(s, d):
                    try:
                        d.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(s, d)
                        copied += 1
                    except Exception:
                        pass
        for s, d in segments:
            if _stale(s, d):
                try:
                    d.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(s, d)
                    copied += 1
                except Exception:
                    pass
        store_src, store_dst = src / "store" / "page", dst / "store" / "page"
        if store_src.exists() and store_dst.exists():
            src_names = set(os.listdir(store_src))
            for name in os.listdir(store_dst):
                if name not in src_names:
                    try:
                        (store_dst / name).unlink()
                        deleted += 1
                    except Exception:
                        pass
        (mirror_dir() / ".mirror_ok").write_text(str(int(time.time())), encoding="utf-8")
        msg = f"🪞 [Mirror] مزامنة قاعدة الشاملة: فُحص {scanned} ملفًا، نُسخ {copied}، حُذف {deleted}"
        progress(msg)
        return {"ok": True, "copied": copied, "deleted": deleted, "scanned": scanned}
    finally:
        _MIRROR_SYNC_LOCK.release()


def _catalog_path() -> Path:
    for cand in (_ROOT / "shamela_index.db", _HERE / "shamela_index.db"):
        if cand.exists():
            return cand
    return _ROOT / "shamela_index.db"


def _our_catalog() -> dict:
    """{book_id: {rel_path, title, author}} من كتالوج المجتهد."""
    p = _catalog_path()
    out = {}
    if not p.exists():
        return out
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        for bid, rel, title, author in con.execute(
                "SELECT book_id, rel_path, title_ar, main_author_name_ar FROM books"):
            out[int(bid)] = {"rel_path": str(rel or ""), "title": str(title or ""),
                             "author": str(author or "")}
        con.close()
    except Exception:
        pass
    return out


def _their_catalog(db_dir: Path) -> dict:
    """{their_id: {title, author, author_id, death, category, category_id}} من master.db."""
    out = {}
    con = sqlite3.connect(f"file:{db_dir / 'master.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    authors = {int(r["author_id"]): dict(r) for r in con.execute("SELECT * FROM author")}
    cats = {int(r["category_id"]): str(r["category_name"]) for r in con.execute("SELECT * FROM category")}
    for r in con.execute("SELECT * FROM book"):
        bid = int(r["book_id"])
        au = authors.get(int(r["main_author"] or 0), {})
        out[bid] = {
            "title": str(r["book_name"] or ""),
            "author": str(au.get("author_name") or r["authors"] or ""),
            "author_id": int(r["main_author"] or 0),
            "death": au.get("death_number"),
            "death_text": str(au.get("death_text") or ""),
            "category": cats.get(int(r["book_category"] or 0), "كتب عامة"),
            "category_id": int(r["book_category"] or 0),
            "book_type": int(r["book_type"] or 1),
        }
    con.close()
    return out


def _downloaded_ids(db_dir: Path):
    """أرقام كتب الشاملة التي لها قاعدة صفحات محلية (منزّلة عندهم)."""
    ids = set()
    for f in glob.glob(str(db_dir / "book" / "*" / "*.db")):
        m = re.fullmatch(r"(\d+)\.db", os.path.basename(f))
        if m:
            ids.add(int(m.group(1)))
    return ids


# ------------------------------------------------------- مطابقة الهوية عندنا

def _norm(text: str) -> str:
    try:
        sys.path.insert(0, str(_HERE))
        from shamela_local_mcp import clean_arabic_text
        t = clean_arabic_text(text or "")
    except Exception:
        t = str(text or "")
    t = re.sub(r"^(كتاب|شرح|مختصر|متن)\s+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _our_title_index(ours: dict) -> dict:
    """{عنوان مطبّع: book_id} لمكتبتنا — أساس مطابقة المستورَد."""
    idx = {}
    for bid, row in ours.items():
        key = _norm(row.get("title", ""))
        if key:
            idx.setdefault(key, bid)
    return idx


def _match_ours(meta: dict, title_index: dict):
    """رقم الكتاب عندنا إن طابق العنوان المطبّع تمامًا، وإلا None.
    محافظ عمدًا: طبعة مختلفة عندهم تُستورد نسخةً موازية ولا تُحجب."""
    return title_index.get(_norm(meta.get("title", "")))


def _our_book_on_disk(our_id, ours: dict) -> bool:
    """هل ملفات هذا الكتاب موجودة عندنا فعلًا (لا مجرد سطر في الكتالوج)؟
    فمن لم تنزل مكتبتنا عنده بعد يجب أن يستورد ولو طابق العنوان."""
    row = ours.get(our_id) or {}
    if not row.get("rel_path"):
        return False
    try:
        sys.path.insert(0, str(_HERE))
        import shamela_local_mcp
        return shamela_local_mcp._dir_for_rel(row["rel_path"]) is not None
    except Exception:
        return False


def _imported_pairs(out_dir: Path) -> dict:
    """{their_id: our_id} من بيانات الكتب المستوردة."""
    pairs = {}
    if out_dir.exists():
        for f in glob.glob(str(out_dir / "*" / "*" / "book_metadata.json")):
            try:
                meta = json.loads(Path(f).read_text(encoding="utf-8"))
                if meta.get("shamela_id") and meta.get("book_id"):
                    pairs[int(meta["shamela_id"])] = int(meta["book_id"])
            except Exception:
                continue
    return pairs


def _allocate_ids(their_ids, ours: dict, existing_pairs: dict) -> dict:
    """تخصيص أرقام عندنا للكتب المستوردة (ثابتة عبر التشغيلات)."""
    used = set(ours) | set(existing_pairs.values())
    nxt = NEW_ID_BASE
    out = {}
    for tid in sorted(their_ids):
        if tid in existing_pairs:
            out[tid] = existing_pairs[tid]
            continue
        while nxt in used:
            nxt += 1
        out[tid] = nxt
        used.add(nxt)
    return out


def library_source() -> str:
    """مصدر المكتبة الحاكم الآن: shamela (المستوردة أولًا) أو hf (المدمجة).
    مفتاح واحد في ملف بجانب الكتالوج — قلبه يعزل مصدرًا ويحيي الآخر."""
    try:
        v = (_ROOT / "library_source.txt").read_text(encoding="utf-8").strip().lower()
        return "shamela" if v == "shamela" else "hf"
    except OSError:
        return "hf"


def set_library_source(src: str) -> str:
    src = "shamela" if str(src).strip().lower() == "shamela" else "hf"
    (_ROOT / "library_source.txt").write_text(src + "\n", encoding="utf-8")
    return src


def _id_map_file() -> Path:
    return import_dir() / "shamela_id_map.json"


def load_id_map() -> dict:
    try:
        return {str(k): int(v) for k, v in
                json.loads(_id_map_file().read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def save_id_map(m: dict) -> None:
    try:
        _id_map_file().parent.mkdir(parents=True, exist_ok=True)
        _id_map_file().write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def ensure_id_map() -> dict:
    """{our_id: their_id} كاملة: من مطابقة العناوين + أزواج الاستيراد.
    تُبنى مرة وتُحفظ؛ تُدمج فيها كل عملية تحويل ما تعلمته."""
    root = find_shamela_root()
    if not root:
        return load_id_map()
    m = load_id_map()
    _dbd = data_database_dir() or (root / "database")
    downloaded = _downloaded_ids(_dbd)
    if len(m) >= int(len(downloaded) * 0.9) and m:
        return m
    theirs = _their_catalog(_dbd)
    ours = _our_catalog()
    tidx = _our_title_index(ours)
    for tid in downloaded:
        mid = _match_ours(theirs.get(tid, {}), tidx)
        if mid:
            m[str(mid)] = tid
    for tid, oid in _imported_pairs(import_dir()).items():
        m[str(oid)] = tid
    save_id_map(m)
    return m


def census() -> dict:
    """حالة الربط كاملة: كشف + عدّ + فجوات. بلا JVM (SQLite وملفات فقط)."""
    st = {"found": False}
    root = find_shamela_root()
    if not root:
        st["message"] = "لم يُعثر على تطبيق المكتبة الشاملة الجديد على هذا الجهاز."
        return st
    db_dir = data_database_dir() or (root / "database")
    st.update({"found": True, "shamela_root": str(root)})
    try:
        theirs = _their_catalog(db_dir)
    except Exception as exc:
        st["message"] = f"تعذّرت قراءة كتالوج الشاملة: {exc}"
        return st
    ours = _our_catalog()
    title_index = _our_title_index(ours)
    downloaded = _downloaded_ids(db_dir)
    imported = _imported_pairs(import_dir())
    # المسجَّل بلا ملفات بعد (المسار الكسول) محسوب «عندنا» أيضًا
    for _oid, _tid in load_id_map().items():
        if int(_oid) >= NEW_ID_BASE:
            imported[_tid] = int(_oid)
    st["library_source"] = library_source()
    in_ours = set()
    for b in downloaded:
        mid = _match_ours(theirs.get(b, {}), title_index)
        if mid and _our_book_on_disk(mid, ours):
            in_ours.add(b)
    importable = sorted((downloaded - in_ours) - set(imported))
    st.update({
        "catalog_total": len(theirs),
        "our_total": len(ours),
        "downloaded": len(downloaded),
        "downloaded_in_our_library": len(in_ours),
        "importable_new": len(importable),
        "imported": len(imported),
        "import_dir": str(import_dir()),
        "missing_from_shamela_downloads": max(0, len(theirs) - len(downloaded)),
    })
    if not downloaded:
        st["advice"] = "تطبيق الشاملة مثبّت لكن لا كتب منزّلة فيه بعد؛ نزّل كتبك فيه ثم ارجع للاستيراد، أو اعتمد مكتبة المجتهد المدمجة."
    elif importable:
        st["advice"] = (f"عندك {len(importable)} كتابًا منزّلًا في الشاملة لا يطابق عنوانُه كتابًا عندنا — "
                        "استيراده يضيفه فورًا بلا تنزيل كامل.")
    else:
        st["advice"] = "كل كتب الشاملة المنزّلة عندك موجودة أصلًا في مكتبة المجتهد أو مستوردة."
    return st


# ------------------------------------------------------------------ الاستيراد

def _find_jvm_and_jars(root: Path):
    jvms = sorted(glob.glob(str(root / "app" / "mac" / "*" / "jre" / "*" / "lib" / "server" / "libjvm.dylib")))
    jvms += sorted(glob.glob(str(root / "app" / "*" / "jre" / "*" / "lib" / "server" / "libjvm.dylib")))
    jvms += sorted(glob.glob(str(root / "app" / "**" / "jvm.dll"), recursive=True))
    jars = sorted(glob.glob(str(root / "app" / "lucene" / "*" / "*.jar")))
    if not jars:
        jars = sorted(glob.glob(str(root / "app" / "**" / "lucene-core-*.jar"), recursive=True))
    return (jvms[0] if jvms else None), jars


_TITLE_SPAN = re.compile(r"<span[^>]*data-type=['\"]title['\"][^>]*id=toc-(\d+)[^>]*>(.*?)</span>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _clean_title(html: str) -> str:
    return " ".join(_TAG.sub(" ", html or "").split())


def _safe_name(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", " ", str(text or "")).strip() or "كتب عامة"


def _docs_for_books(reader, jpype, tids):
    """مواضع وثائق كتب بعينها بقفزة بادئة في قاموس id — للاستخراج الكسول."""
    docs = {}
    BytesRef = jpype.JClass("org.apache.lucene.util.BytesRef")
    JByte = jpype.JByte
    JArray = jpype.JArray
    for leaf_ctx in reader.leaves():
        leaf = leaf_ctx.reader()
        terms = leaf.terms("id")
        if terms is None:
            continue
        it = terms.iterator()
        base = int(leaf_ctx.docBase)
        for tid in tids:
            prefix = f"{tid}-"
            target = BytesRef(JArray(JByte)(prefix.encode("utf-8")))
            it.seekCeil(target)
            term = it.term()
            while term is not None:
                s = term.utf8ToString()
                if not s.startswith(prefix):
                    break
                try:
                    seq = int(s[len(prefix):])
                except ValueError:
                    term = it.next()
                    continue
                postings = it.postings(None)
                while True:
                    d = int(postings.nextDoc())
                    if d == 2147483647:
                        break
                    docs.setdefault(tid, []).append((seq, base + d))
                term = it.next()
    return docs


def extract_book(their_id: int, progress=lambda m: None) -> dict:
    """تحويل كتاب واحد عند أول لمس له (المسار الكسول)."""
    return convert(book_ids=[int(their_id)], as_primary=True, progress=progress)


def register_new_books() -> int:
    """تسجيل كتب الشاملة المنزّلة غير المعروفة عندنا في الكتالوج والخريطة
    بلا تحويل نصوص — تُستخرج كسولًا عند أول لمس. هذا عمل الإقلاع الخفيف."""
    root = find_shamela_root()
    if not root:
        return 0
    _dbd = data_database_dir() or (root / "database")
    theirs = _their_catalog(_dbd)
    ours = _our_catalog()
    title_index = _our_title_index(ours)
    downloaded = _downloaded_ids(_dbd)
    id_map = ensure_id_map()
    known_theirs = set(id_map.values()) | set(_imported_pairs(import_dir()))
    used_ours = set(ours) | {int(k) for k in id_map}
    cat = _catalog_path()
    added = 0
    con = sqlite3.connect(str(cat)) if cat.exists() else None
    try:
        nxt = NEW_ID_BASE
        for tid in sorted(downloaded):
            if tid in known_theirs:
                continue
            meta = theirs.get(tid, {})
            if _match_ours(meta, title_index):
                continue  # توأم: خريطته من المطابقة ولا يحتاج سطرًا
            while nxt in used_ours:
                nxt += 1
            our_id = nxt
            used_ours.add(our_id)
            id_map[str(our_id)] = tid
            known_theirs.add(tid)
            if con is not None:
                rel = (f"shamela4_data/{_safe_name(meta.get('category'))}/"
                       f"{our_id}__{_safe_name(meta.get('title'))}")
                con.execute(
                    "INSERT OR IGNORE INTO books (book_id, shamela_id, title_ar, category_id, category_name_ar,"
                    " main_author_id, main_author_name_ar, main_author_death_hijri, rel_path) VALUES (?,?,?,?,?,?,?,?,?)",
                    (our_id, tid, meta.get("title") or str(tid), meta.get("category_id"),
                     meta.get("category"), meta.get("author_id"), meta.get("author"),
                     meta.get("death"), rel))
            added += 1
        if con is not None:
            con.commit()
    finally:
        if con is not None:
            con.close()
    save_id_map(id_map)
    return added


def convert(book_ids=None, force: bool = False, out_dir: Path = None, progress=print,
            as_primary: bool = False) -> dict:
    """تحويل كتب الشاملة المنزّلة إلى صيغة المجتهد. يرجع تقريرًا.
    book_ids هنا أرقام الشاملة (نطاقهم)، لا أرقامنا.
    as_primary (وضع الهجرة): التوأم المطابق عنوانًا عندنا يُكتب برقمنا
    ومسارنا داخل مجلد الاستيراد، فتصير النسخة المستوردة هي نسخة الكتاب
    نفسه لا كتابًا موازيًا — والمصدر الحاكم يختار أيّ النسختين تُقرأ."""
    root = find_shamela_root()
    if not root:
        return {"ok": False, "message": "لم يُعثر على تطبيق الشاملة."}
    db_dir = data_database_dir() or (root / "database")
    store = db_dir / "store" / "page"
    if not store.exists():
        return {"ok": False, "message": "لم يُعثر على مخزن نصوص الشاملة (لا كتب منزّلة؟)."}
    out_dir = Path(out_dir) if out_dir else import_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    theirs = _their_catalog(db_dir)
    ours = _our_catalog()
    title_index = _our_title_index(ours)
    downloaded = _downloaded_ids(db_dir)
    # الأزواج المعروفة: من ملفات المستوردة + خريطة الهوية (تسجيلات بلا ملفات بعد)
    existing_pairs = {tid: oid for oid, tid in
                      ((int(k), v) for k, v in load_id_map().items())}
    existing_pairs.update(_imported_pairs(out_dir))
    wanted = sorted(set(book_ids) & downloaded) if book_ids else sorted(downloaded)
    if progress is print:
        progress = lambda m: print(m, flush=True)  # noqa: E731
    targets, skipped_have, skipped_imported = [], 0, 0
    twin_of = {}   # their_id -> our book_id (وضع الهجرة)
    for tid in wanted:
        if as_primary:
            mid = _match_ours(theirs.get(tid, {}), title_index)
            if mid:
                twin_of[tid] = mid
                rel_t = ours[mid]["rel_path"].replace("shamela4_data/", "").strip("/")
                if (out_dir / rel_t / "manifest.json").exists():
                    skipped_imported += 1
                    continue
            elif tid in existing_pairs:
                meta_f = next(iter(glob.glob(str(out_dir / "*" / f"{existing_pairs[tid]}__*" / "manifest.json"))), None)
                if meta_f:
                    skipped_imported += 1
                    continue
            targets.append(tid)
            continue
        if not force:
            mid = _match_ours(theirs.get(tid, {}), title_index)
            if mid and _our_book_on_disk(mid, ours):
                skipped_have += 1
                continue
            if tid in existing_pairs:
                skipped_imported += 1
                continue
        elif tid in existing_pairs:
            # استئناف آمن عند القسر: كتاب اكتمل سابقًا (بياناته موجودة) لا يُعاد
            meta_f = next(iter(glob.glob(str(out_dir / "*" / f"{existing_pairs[tid]}__*" / "manifest.json"))), None)
            if meta_f:
                skipped_imported += 1
                continue
        targets.append(tid)
    id_map = _allocate_ids([t for t in targets if t not in twin_of], ours, existing_pairs)
    id_map.update(twin_of)
    progress(json.dumps({"stage": "plan", "targets": len(targets),
                         "skipped_have": skipped_have, "skipped_imported": skipped_imported}, ensure_ascii=False))

    # --- JVM بأدواتهم المدمجة
    try:
        import jpype  # type: ignore
    except ImportError:
        progress(json.dumps({"stage": "install_jpype"}, ensure_ascii=False))
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "jpype1"])
        import jpype  # type: ignore
    jvm, jars = _find_jvm_and_jars(root)
    if not jvm or not jars:
        return {"ok": False, "message": "لم يُعثر على JRE/Lucene داخل تطبيق الشاملة."}
    if not jpype.isJVMStarted():
        jpype.startJVM(jvm, classpath=jars, convertStrings=True)
    Paths = jpype.JClass("java.nio.file.Paths")
    FSDirectory = jpype.JClass("org.apache.lucene.store.FSDirectory")
    DirectoryReader = jpype.JClass("org.apache.lucene.index.DirectoryReader")
    reader = DirectoryReader.open(FSDirectory.open(Paths.get(str(store))))
    sf = reader.storedFields()

    # مروران: فهرسة مواضع الوثائق لكل كتاب، ثم التحويل كتابًا كتابًا.
    # عند تحديد كتب بعينها (استخراج كسول) نقفز بمصطلحات بادئة رقم الكتاب
    # مباشرة — ثوانٍ بدل مسح الفهرس كله.
    docs_by_book = {}
    _target_set = set(targets)
    total_docs = int(reader.maxDoc())
    if book_ids:
        docs_by_book = _docs_for_books(reader, jpype, targets)
        progress(json.dumps({"stage": "indexed", "docs": total_docs,
                             "books_with_text": len(docs_by_book)}, ensure_ascii=False))
        scanned = total_docs  # تخطَّى المسح الكامل إلى كتابة الكتب مباشرة
    else:
        scanned = 0
    try:
        for leaf_ctx in (reader.leaves() if not book_ids else []):
            leaf = leaf_ctx.reader()
            terms = leaf.terms("id")
            if terms is None:
                raise RuntimeError("no id terms")
            it = terms.iterator()
            base = int(leaf_ctx.docBase)
            while True:
                term = it.next()
                if term is None:
                    break
                s = term.utf8ToString()
                if "-" not in s:
                    continue
                bid_s, seq_s = s.rsplit("-", 1)
                try:
                    tid, seq = int(bid_s), int(seq_s)
                except ValueError:
                    continue
                if tid not in _target_set:
                    continue
                postings = it.postings(None)
                while True:
                    d = int(postings.nextDoc())
                    if d == 2147483647:  # NO_MORE_DOCS
                        break
                    docs_by_book.setdefault(tid, []).append((seq, base + d))
            scanned += int(leaf.maxDoc())
            progress(json.dumps({"stage": "scan", "i": scanned, "of": total_docs}, ensure_ascii=False))
    except Exception:
        docs_by_book = {}
        _id_only = jpype.JClass("java.util.Collections").singleton("id")
        for i in range(total_docs):
            doc = sf.document(i, _id_only)
            idv = doc.get("id")
            if not idv or "-" not in str(idv):
                continue
            bid_s, seq_s = str(idv).rsplit("-", 1)
            try:
                tid, seq = int(bid_s), int(seq_s)
            except ValueError:
                continue
            if tid in _target_set:
                docs_by_book.setdefault(tid, []).append((seq, i))
            if i % 200000 == 0:
                progress(json.dumps({"stage": "scan", "i": i, "of": total_docs}, ensure_ascii=False))
    progress(json.dumps({"stage": "indexed", "docs": total_docs,
                         "books_with_text": len(docs_by_book)}, ensure_ascii=False))

    report = {"ok": True, "converted": [], "pages": 0, "failed": []}
    for n, tid in enumerate(targets, 1):
        _lk = _book_lock(tid)
        _lk.acquire()
        try:
            meta = theirs.get(tid, {"title": str(tid), "author": "", "category": "كتب عامة", "category_id": 0})
            our_id = id_map[tid]
            if as_primary and tid in twin_of:
                rel = ours[our_id]["rel_path"].replace("shamela4_data/", "").strip("/")
            else:
                rel = f"{_safe_name(meta.get('category'))}/{our_id}__{_safe_name(meta.get('title'))}"
            bdir = out_dir / rel
            bdir.mkdir(parents=True, exist_ok=True)
            book_db = next(iter(glob.glob(str(db_dir / "book" / "*" / f"{tid}.db"))), None)
            page_meta, title_parent = {}, {}
            if book_db:
                con = sqlite3.connect(f"file:{book_db}?mode=ro", uri=True)
                for pid, part, pnum in con.execute("SELECT id, part, page FROM page"):
                    page_meta[int(pid)] = (str(part or ""), int(pnum or 0))
                try:
                    for ttid, tpage, parent in con.execute("SELECT id, page, parent FROM title"):
                        title_parent[int(ttid)] = (int(tpage or 0), int(parent or 0))
                except sqlite3.Error:
                    pass
                con.close()
            rows = sorted(docs_by_book.get(tid, []))
            toc_found = {}
            part_counter = {}
            npages = 0
            with open(bdir / f"pages.jsonl.tmp{threading.get_ident()}", "w", encoding="utf-8") as fh:
                for seq, doc_i in rows:
                    doc = sf.document(doc_i)
                    body = str(doc.get("body") or "")
                    foot = doc.get("foot")
                    part, pnum = page_meta.get(seq, ("", 0))
                    part_counter[part] = part_counter.get(part, 0) + 1
                    fh.write(json.dumps({
                        "page_id": our_id * 1000000 + seq,
                        "book_id": our_id,
                        "shamela_page_id": seq,
                        "part": part,
                        "page_num": pnum,
                        "sequence_num": part_counter[part],
                        "body": body,
                        "footnotes": (str(foot) if foot else None),
                        "hints": None,
                        "services_raw": None,
                    }, ensure_ascii=False) + "\n")
                    npages += 1
                    for m in _TITLE_SPAN.finditer(body):
                        toc_found[int(m.group(1))] = (_clean_title(m.group(2)), seq)
            os.replace(bdir / f"pages.jsonl.tmp{threading.get_ident()}", bdir / "pages.jsonl")
            our_tid = {}
            with open(bdir / f"toc.jsonl.tmp{threading.get_ident()}", "w", encoding="utf-8") as fh:
                for i, (their_tid, (text, seq)) in enumerate(
                        sorted(toc_found.items(), key=lambda kv: kv[1][1]), 1):
                    our_tid[their_tid] = i
                    parent_theirs = title_parent.get(their_tid, (0, 0))[1]
                    fh.write(json.dumps({
                        "title_id": i, "book_id": our_id, "page_id": our_id * 1000000 + seq,
                        "parent_id": our_tid.get(parent_theirs),
                        "shamela_title_id": their_tid, "title_text": text,
                    }, ensure_ascii=False) + "\n")
            os.replace(bdir / f"toc.jsonl.tmp{threading.get_ident()}", bdir / "toc.jsonl")
            meta_out = {
                "book_id": our_id, "shamela_id": tid, "title_ar": meta.get("title") or str(tid),
                "book_type": meta.get("book_type", 1), "book_type_label": "كتاب",
                "category_id": meta.get("category_id"), "category_name_ar": meta.get("category"),
                "main_author_id": meta.get("author_id"), "main_author_name_ar": meta.get("author"),
                "main_author_death_hijri": meta.get("death"), "main_author_death_hijri_text": meta.get("death_text") or "",
                "source": "shamela-app-import",
            }
            _atomic_write(bdir / "book_metadata.json", json.dumps(meta_out, ensure_ascii=False, indent=1))
            _atomic_write(bdir / "manifest.json", json.dumps(
                {**meta_out, "page_count": npages, "toc_count": len(toc_found)},
                ensure_ascii=False, indent=1))
            report["converted"].append(tid)
            report["pages"] += npages
            progress(json.dumps({"stage": "book", "i": n, "of": len(targets), "book_id": tid,
                                 "our_id": our_id, "title": meta.get("title"), "pages": npages}, ensure_ascii=False))
        except Exception as exc:  # كتاب فاسد لا يوقف البقية
            report["failed"].append({"book_id": tid, "error": str(exc)[:200]})
            progress(json.dumps({"stage": "fail", "book_id": tid, "error": str(exc)[:200]}, ensure_ascii=False))
        finally:
            _lk.release()
    try:
        reader.close()
    except Exception:
        pass
    report.update({"targets": len(targets), "skipped_have": skipped_have, "skipped_imported": skipped_imported})
    (out_dir / ".import_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    try:  # خريطة الهوية تتغذى من كل تحويل (توائم ومخصصات)
        _m = load_id_map()
        for _tid in targets:
            _m[str(id_map[_tid])] = _tid
        save_id_map(_m)
    except Exception:
        pass
    return report


def register_imported_catalog(out_dir: Path = None) -> int:
    """إدخال الكتب المستوردة الجديدة في كتالوج المجتهد بأرقامها.
    كتاب عندنا ملفاته أصلًا لا يُسجَّل ثانية (لا مكررات بالعنوان)."""
    out_dir = Path(out_dir) if out_dir else import_dir()
    cat = _catalog_path()
    if not cat.exists():
        return 0
    ours = _our_catalog()
    title_index = _our_title_index(ours)
    added = 0
    con = sqlite3.connect(str(cat))
    try:
        have = {int(r[0]) for r in con.execute("SELECT book_id FROM books")}
        for meta_file in glob.glob(str(out_dir / "*" / "*" / "book_metadata.json")):
            try:
                meta = json.loads(Path(meta_file).read_text(encoding="utf-8"))
            except Exception:
                continue
            our_id = int(meta.get("book_id") or 0)
            if not our_id or our_id in have:
                continue
            twin = title_index.get(_norm(meta.get("title_ar", "")))
            if twin and _our_book_on_disk(twin, ours):
                continue
            rel = "shamela4_data/" + str(Path(meta_file).parent.relative_to(out_dir)).replace(os.sep, "/")
            con.execute(
                "INSERT OR IGNORE INTO books (book_id, shamela_id, title_ar, category_id, category_name_ar,"
                " main_author_id, main_author_name_ar, main_author_death_hijri, rel_path) VALUES (?,?,?,?,?,?,?,?,?)",
                (our_id, meta.get("shamela_id"), meta.get("title_ar") or str(our_id),
                 meta.get("category_id"), meta.get("category_name_ar"), meta.get("main_author_id"),
                 meta.get("main_author_name_ar"), meta.get("main_author_death_hijri"), rel))
            have.add(our_id)
            added += 1
        con.commit()
    finally:
        con.close()
    return added


def _fts_dir() -> Path:
    env = os.getenv("ALMUJTAHED_FTS_DIR", "").strip()
    if env:
        return Path(env)
    for cand in (_ROOT / "library_fts", _ROOT / "exp_fts" / "full",
                 Path.home() / "Library" / "Application Support" / "Al-Mujtahed" / "runtime" / "library_fts"):
        if glob.glob(str(cand / "shard*.db")):
            return cand
    return _ROOT / "library_fts"


def build_import_fts(out_dir: Path = None, fts_dir_override: Path = None) -> dict:
    """شظية FTS للكتب المستوردة الجديدة فقط (أرقامها من نطاق الاستيراد):
    التوائم المكتوبة بأرقامنا أصلًا في الفهرس الرئيسي/فهرس الشاملة الكامل،
    وإعادة فهرستها هنا تصنع أشباحًا مكررة في حوض النتائج."""
    out_dir = Path(out_dir) if out_dir else import_dir()
    fts_dir = Path(fts_dir_override) if fts_dir_override else _fts_dir()
    if not fts_dir.exists():
        return {"ok": False, "message": "مجلد فهارس البحث غير موجود بعد."}
    sys.path.insert(0, str(_HERE))
    from library_search import _normalize
    shard = fts_dir / "shard_import.db"
    if shard.exists():
        shard.unlink()
    con = sqlite3.connect(str(shard))
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("CREATE VIRTUAL TABLE pages_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, part UNINDEXED, page_num UNINDEXED, seq UNINDEXED, tokenize='unicode61')")
    con.execute("CREATE VIRTUAL TABLE headings_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, tokenize='unicode61')")
    npages = 0
    for pages_file in glob.glob(str(out_dir / "*" / "*" / "pages.jsonl")):
        bdir = Path(pages_file).parent
        batch, hb = [], []
        with open(pages_file, encoding="utf-8") as fh:
            for line in fh:
                pg = json.loads(line)
                if int(pg.get("book_id") or 0) < NEW_ID_BASE:
                    batch = None  # توأم بأرقامنا: مفهرس في موضعه الأصلي
                    break
                txt = _normalize(pg.get("body") or "")
                if txt:
                    batch.append((txt, pg["book_id"], pg["page_id"], pg.get("part") or "", pg.get("page_num") or 0, pg.get("sequence_num") or 0))
        if batch is None:
            continue
        toc_file = bdir / "toc.jsonl"
        if toc_file.exists():
            with open(toc_file, encoding="utf-8") as fh:
                for line in fh:
                    tc = json.loads(line)
                    txt = _normalize(tc.get("title_text") or "")
                    if txt:
                        hb.append((txt, tc["book_id"], tc["page_id"]))
        con.executemany("INSERT INTO pages_fts VALUES (?,?,?,?,?,?)", batch)
        con.executemany("INSERT INTO headings_fts VALUES (?,?,?)", hb)
        npages += len(batch)
    con.commit()
    con.execute("INSERT INTO pages_fts(pages_fts) VALUES('optimize')")
    con.execute("INSERT INTO headings_fts(headings_fts) VALUES('optimize')")
    con.commit()
    con.close()
    return {"ok": True, "pages": npages, "shard": str(shard)}


def open_shamela_app() -> dict:
    """فتح تطبيق الشاملة ليكمل المستخدم تنزيل ما يحتاجه هناك (تنزيل رسمي)."""
    import subprocess
    if sys.platform == "darwin":
        for args in (["open", "-b", "com.raha.shamela"],
                     ["open", "-a", "المكتبة الشاملة ٢"],
                     ["open", "-a", "المكتبة الشاملة"]):
            try:
                if subprocess.run(args, capture_output=True, timeout=10).returncode == 0:
                    return {"ok": True, "message": "فُتح تطبيق الشاملة — نزّل الكتب الناقصة هناك وستُستورد هنا تلقائيًا."}
            except Exception:
                continue
        return {"ok": False, "message": "تعذّر فتح تطبيق الشاملة — افتحه يدويًا ونزّل ما تحتاجه ثم عُد."}
    return {"ok": False, "message": "افتح تطبيق الشاملة ونزّل الكتب الناقصة، وستُستورد هنا تلقائيًا عند رصدها."}


def build_shamela_fts(out_dir: Path = None) -> dict:
    """فهرس بحث كامل من الكتب المستوردة وحدها (مصدر الشاملة بعد الهجرة)."""
    out = Path(out_dir) if out_dir else import_dir()
    fts_out = _ROOT / "library_fts_shamela"
    sys.path.insert(0, str(_HERE))
    os.environ["ALMUJTAHED_FTS_SOURCE_ROOT"] = str(out)
    import build_library_index
    _ours = _our_catalog()
    _tidx = _our_title_index(_ours)
    books = [{"book_id": bid, "rel_path": row["rel_path"]}
             for bid, row in _ours.items()]
    known = {b["book_id"] for b in books}
    for meta_file in glob.glob(str(out / "*" / "*" / "book_metadata.json")):
        try:
            meta = json.loads(Path(meta_file).read_text(encoding="utf-8"))
        except Exception:
            continue
        bid = int(meta.get("book_id") or 0)
        if not bid or bid in known:
            continue
        if _tidx.get(_norm(meta.get("title_ar", ""))):
            continue  # توأم قديم برقم مستورد: نسخته برقمنا هي المعتمدة
        rel = "shamela4_data/" + str(Path(meta_file).parent.relative_to(out)).replace(os.sep, "/")
        books.append({"book_id": bid, "rel_path": rel})
        known.add(bid)
    return build_library_index.build(out_dir=str(fts_out), books=books)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "import", "source", "build-fts"])
    ap.add_argument("--books", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--as-primary", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--set", default="")
    a = ap.parse_args()
    if a.cmd == "build-fts":
        print(json.dumps(build_shamela_fts(), ensure_ascii=False, indent=1))
    elif a.cmd == "source":
        if a.set:
            print("library_source =", set_library_source(a.set))
        else:
            print("library_source =", library_source())
    elif a.cmd == "status":
        print(json.dumps(census(), ensure_ascii=False, indent=1))
    else:
        ids = [int(x) for x in a.books.split(",") if x.strip()] or None
        rep = convert(book_ids=ids, force=a.force, as_primary=a.as_primary,
                      out_dir=Path(a.out) if a.out else None)
        reg = register_imported_catalog(Path(a.out) if a.out else None)
        if rep.get("converted"):
            if library_source() == "shamela":
                # داخل فهرس الشاملة الحاكم: شظية صغيرة للجديد فقط بجانب شظاياه
                fts = build_import_fts(Path(a.out) if a.out else None,
                                       fts_dir_override=_ROOT / "library_fts_shamela")
            else:
                fts = build_import_fts(Path(a.out) if a.out else None)
        else:
            fts = {}
        print(json.dumps({"report": rep, "catalog_added": rep and reg, "fts": fts}, ensure_ascii=False, indent=1))
