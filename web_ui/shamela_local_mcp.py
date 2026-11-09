#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
shamela_local_mcp.py - خادم بروتوكول MCP الداخلي لمنظومة المجتهد
=============================================================================
الوظيفة: توفير أدوات التحقيق والمطالعة الموضعية لنصوص الشاملة التراثية الأصلية:
  1. get_page_range: تقليب وقراءة صفحات متسلسلة كاملة بنصها وهوامشها وتخريجها.
  2. get_book_toc: استخراج شجرة الأبواب وفهرس المحتويات للكتاب.
  3. verify_quote: مطابقة نص الاقتباس الحرفي داخل صفحات الكتاب بدقة تامة.
  4. search_in_book: بحث حرفي سريع ومحصور داخل نطاق كتاب واحد.
=============================================================================
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

SYSTEM_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = SYSTEM_ROOT.parent

# تحديد مسار نصوص الشاملة الكاملة
if (SYSTEM_ROOT / "shamela4_data").exists():
    SHAMELA_DATA_DIR = SYSTEM_ROOT / "shamela4_data"
else:
    SHAMELA_DATA_DIR = Path(os.getenv("SHAMELA4_DATA_DIR", str(WORKSPACE_ROOT / "shamela4_data")))

# ذاكرة تخزين مؤقت لفهارس صفحات الكتب لتسريع التصفح المتكرر
_BOOK_INDEX_CACHE: Dict[str, Dict[str, Any]] = {}

def clean_arabic_text(text: str) -> str:
    """إزالة وسوم HTML والتشكيل لتسهيل البحث والمطابقة"""
    if not text:
        return ""
    # إزالة وسوم HTML
    t = re.sub(r"<[^>]+>", " ", text)
    # إزالة حركات التشكيل والتطويل
    t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)
    # توحيد الهمزات والألف والياء
    t = re.sub(r"[إأآا]", "ا", t)
    t = re.sub(r"[ىي]", "ي", t)
    t = re.sub(r"ة", "ه", t)
    return " ".join(t.split())

import sqlite3

# مسار قاعدة بيانات الفهرس المحلي المدمج
if (SYSTEM_ROOT / "shamela_index.db").exists():
    DB_PATH = SYSTEM_ROOT / "shamela_index.db"
elif (Path(__file__).resolve().parent / "shamela_index.db").exists():
    DB_PATH = Path(__file__).resolve().parent / "shamela_index.db"
else:
    DB_PATH = SYSTEM_ROOT / "shamela_index.db"

def _library_source() -> str:
    """المصدر الحاكم: shamela = المستوردة من تطبيق الشاملة أولًا، hf = المدمجة.
    يُقرأ كل مرة (ملف صغير) فيسري القلب فورًا بلا إعادة بناء أي شيء."""
    try:
        v = (SYSTEM_ROOT / "library_source.txt").read_text(encoding="utf-8").strip().lower()
        return "shamela" if v == "shamela" else "hf"
    except OSError:
        return "hf"


def _data_roots() -> List[Path]:
    """جذور مكتبة الشاملة المحتملة، بترتيب الأولوية (يحكمه المصدر المفعّل)"""
    roots = [SHAMELA_DATA_DIR]
    for raw in (os.environ.get("SHAMELA4_DATA_DIR") or "",):
        if raw:
            roots.insert(0, Path(raw).expanduser())
    home = Path.home()
    _imp = os.environ.get("ALMUJTAHED_SHAMELA_IMPORT_DIR", "")
    if _imp:
        _imp_path = Path(_imp).expanduser()
    else:
        try:
            import shamela_link as _SLL
            _imp_path = _SLL.import_dir()
        except Exception:
            _imp_path = home / "Library" / "Application Support" / "Al-Mujtahed" / "runtime" / "shamela_imported"
    if _library_source() == "shamela":
        roots.insert(0, _imp_path)
    else:
        roots.append(_imp_path)  # الجديد المستورد وحده هناك يُقرأ، والتوائم من المدمجة
    for candidate in (
        home / "Library" / "Application Support" / "Al-Mujtahed" / "runtime" / "shamela4_data",
        SYSTEM_ROOT / "shamela4_data",
    ):
        if candidate not in roots:
            roots.append(candidate)
    return [r for r in roots if str(r)]


def _valid_book_dir(path: Optional[Path]) -> Optional[Path]:
    """مجلد كتاب صالح فقط إن كان ملف صفحاته حقيقياً لا مؤشر Git LFS"""
    if not path or not path.exists():
        return None
    pages = path / "pages.jsonl"
    if not pages.exists():
        return None
    try:
        with open(pages, "rb") as f:
            head = f.read(64)
        if head.startswith(b"version https://git-lfs"):
            return None
    except Exception:
        return None
    return path


def _dir_for_rel(rel_path: str) -> Optional[Path]:
    clean_rel = str(rel_path).replace("shamela4_data/", "").strip("/")
    for root in _data_roots():
        found = _valid_book_dir(root / clean_rel)
        if found:
            return found
    return None


def resolve_book_files(book_id_or_title: Any) -> Optional[Path]:
    """العثور على مجلد الكتاب بدقة متناهية عبر SQLite وفهارس الشاملة"""
    if not SHAMELA_DATA_DIR.exists() and not any(r.exists() for r in _data_roots()):
        return None

    str_val = str(book_id_or_title).strip()
    
    # 1. فحص قاعدة بيانات SQLite الرسمية
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # بحث برقم الشاملة إذا كان المدخل رقماً فقط، لا أول رقم يظهر داخل العنوان
            if re.fullmatch(r"#?\s*\d{1,5}", str_val):
                clean_id = re.sub(r"\D", "", str_val)
                cursor.execute("SELECT rel_path FROM books WHERE book_id = ? LIMIT 1", (clean_id,))
                row = cursor.fetchone()
                if row and row["rel_path"]:
                    p = _dir_for_rel(row["rel_path"])
                    if p:
                        conn.close()
                        return p

            q_clean = re.sub(r"^(?:كتاب|شرح|مختصر|متن|كتاب\s+شرح)\s+", "", str_val).strip()
            cursor.execute("SELECT rel_path FROM books WHERE title_ar = ? LIMIT 1", (str_val,))
            row = cursor.fetchone()
            if not row and q_clean != str_val:
                cursor.execute("SELECT rel_path FROM books WHERE title_ar = ? LIMIT 1", (q_clean,))
                row = cursor.fetchone()
            if not row:
                best = _best_book_row(cursor, str_val)
                if best and best.get("rel_path"):
                    p = _dir_for_rel(best["rel_path"])
                    if p:
                        conn.close()
                        return p
            if not row and len(q_clean) >= 8:
                cursor.execute(
                    "SELECT rel_path FROM books WHERE title_ar LIKE ? || '%' ORDER BY LENGTH(title_ar) ASC LIMIT 1",
                    (q_clean,),
                )
                row = cursor.fetchone()

            if row and row["rel_path"]:
                p = _dir_for_rel(row["rel_path"])
                if p:
                    conn.close()
                    return p
            conn.close()
        except Exception:
            pass

    # المسار الكسول: كتاب معروف في الكتالوج ولا ملفات له بعدُ على القرص،
    # والمصدر الحاكم هو الشاملة — يُستخرج من تطبيقها عند أول لمس ثم يُعاد.
    if _library_source() == "shamela":
        try:
            return _lazy_extract_and_resolve(book_id_or_title)
        except Exception:
            pass
    return None


_LAZY_FAILED = set()
_LAZY_LOCK = __import__("threading").Lock()
_LAZY_DIAG = {"our_id": None, "their_id": None, "error": ""}


def _lazy_extract_and_resolve(book_id_or_title) -> Optional[Path]:
    """استخراج كتاب واحد من الشاملة المثبتة ثم حلّ مجلده (مرة لكل كتاب)."""
    str_val = str(book_id_or_title).strip()
    our_id = None
    m = re.fullmatch(r"#?\s*(\d{1,7})", str_val)
    if m:
        our_id = int(m.group(1))
    else:
        m2 = re.search(r"/(\d{1,7})__", str_val.replace("\\", "/"))
        if m2:
            our_id = int(m2.group(1))
    if our_id is None and DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            row = conn.execute("SELECT book_id FROM books WHERE title_ar = ? LIMIT 1", (str_val,)).fetchone()
            conn.close()
            if row:
                our_id = int(row[0])
        except Exception:
            pass
    if our_id is None:
        _LAZY_DIAG.update({"our_id": None, "error": "رقم الكتاب غير معروف في الكتالوج"})
        return None
    with _LAZY_LOCK:
        if our_id in _LAZY_FAILED:
            _LAZY_DIAG.update({"our_id": our_id, "error": "فشل استخراج سابق لهذا الكتاب في هذه الجلسة"})
            return None
    import shamela_link as SL
    their_id = SL.ensure_id_map().get(str(our_id))
    _LAZY_DIAG.update({"our_id": our_id, "their_id": their_id, "error": ""})
    if not their_id:
        with _LAZY_LOCK:
            _LAZY_FAILED.add(our_id)
        _LAZY_DIAG.update({"error": "لا خريطة هوية لهذا الكتاب إلى رقم الشاملة"})
        return None
    # قفل الكتاب نفسه داخل convert يجعل اللمسات المتزامنة تنتظر الاستخراج
    # الجاري ثم تجد الملفات جاهزة، بدل إقلاع فوري بصفحات ناقصة (1.10.270).
    print(f"📥 [Lazy] استخراج كتاب {our_id} (شاملة {their_id}) عند أول لمس…", flush=True)
    try:
        _ext = SL.extract_book(int(their_id))
        if isinstance(_ext, dict) and _ext.get("ok") is False:
            _LAZY_DIAG.update({"error": f"الاستخراج أرجع فشلًا: {_ext.get('message') or _ext}"})
    except Exception as _exc:
        _LAZY_DIAG.update({"error": f"استثناء أثناء الاستخراج: {type(_exc).__name__}: {_exc}"[:300]})
        with _LAZY_LOCK:
            _LAZY_FAILED.add(our_id)
        return None
    # بعد الاستخراج: حلّ جديد عبر الكتالوج
    found = None
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=5)
            row = conn.execute("SELECT rel_path FROM books WHERE book_id = ? LIMIT 1", (our_id,)).fetchone()
            conn.close()
            if row and row[0]:
                found = _dir_for_rel(row[0])
        except Exception:
            pass
    if found is None:
        with _LAZY_LOCK:
            _LAZY_FAILED.add(our_id)
    return found


def get_book_index(book_dir: Path) -> Dict[str, Any]:
    """بناء أو جلب فهرس أوفست الصفحات للكتاب لقراءته لحظياً عبر seek"""
    cache_key = str(book_dir)
    if cache_key in _BOOK_INDEX_CACHE:
        return _BOOK_INDEX_CACHE[cache_key]

    pages_file = book_dir / "pages.jsonl"
    if not pages_file.exists():
        return {"entries": [], "meta": {}}
    try:
        with open(pages_file, "rb") as probe:
            if probe.read(64).startswith(b"version https://git-lfs"):
                return {"entries": [], "meta": {}}
    except OSError:
        return {"entries": [], "meta": {}}

    entries = []
    meta = {}
    meta_file = book_dir / "book_metadata.json"
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass

    try:
        with open(pages_file, "rb") as f:
            offset = 0
            seq = 1
            for line in f:
                try:
                    d = json.loads(line.decode("utf-8"))
                    part = str(d.get("volume") or d.get("part") or "").strip()
                    p_num = d.get("page_num")
                    page_id = d.get("page_id")
                    entries.append({
                        "seq": seq,
                        "part": part,
                        "page_num": p_num,
                        "page_id": page_id,
                        "offset": offset
                    })
                    seq += 1
                except Exception:
                    pass
                offset += len(line)
    except Exception as e:
        print(f"Error indexing pages for {book_dir.name}: {e}")

    result = {"entries": entries, "meta": meta, "book_dir": book_dir}
    _BOOK_INDEX_CACHE[cache_key] = result
    return result

# =============================================================================
# أدوات MCP المعيارية (MCP Tool Handlers)
# =============================================================================

def get_page_range(book: Any, start_page: int, end_page: int, part: Optional[str] = None) -> Dict[str, Any]:
    """
    أداة 1: تقليب وقراءة صفحات متسلسلة كاملة بنصها وهوامشها.
    """
    b_dir = resolve_book_files(book)
    if not b_dir:
        return {"error": f"تعذر العثور على ملفات الكتاب: {book}"}

    idx = get_book_index(b_dir)
    entries = idx["entries"]
    if not entries:
        return {"error": "الكتاب لا يحتوي على صفحات صالحة للقراءة."}

    # تصفية الصفحات حسب الجزء ورقم الصفحة
    p_str = str(part).strip() if part and str(part).strip() != "None" else None
    matched_entries = []
    for e in entries:
        if p_str and e["part"] != p_str:
            continue
        p_num = e.get("page_num")
        if p_num is not None:
            try:
                p_int = int(p_num)
                if start_page <= p_int <= end_page:
                    matched_entries.append(e)
            except Exception:
                pass

    if not matched_entries:
        # إذا لم يُعثر عليها برقم الصفحة المطبوعة، نعتمد التسلسل (Seq)
        matched_entries = [e for e in entries if start_page <= e["seq"] <= end_page]

    pages_file = b_dir / "pages.jsonl"
    pages_data = []

    try:
        with open(pages_file, "rb") as f:
            for entry in matched_entries[:50]:  # سقف أقصى 50 صفحة في الطلب الواحد
                f.seek(entry["offset"])
                line = f.readline()
                if line:
                    data = json.loads(line.decode("utf-8"))
                    raw_body = data.get("body", "")
                    clean_b = re.sub(r"<[^>]+>", "", raw_body).strip()
                    footnotes = data.get("footnotes") or ""
                    if footnotes:
                        footnotes = re.sub(r"<[^>]+>", "", footnotes).strip()

                    pages_data.append({
                        "part": entry["part"],
                        "page_num": entry["page_num"],
                        "seq": entry["seq"],
                        "body": clean_b,
                        "footnotes": footnotes
                    })
    except Exception as e:
        return {"error": f"خطأ أثناء قراءة صفحات الكتاب: {e}"}

    distinct_parts = []
    for e in matched_entries:
        pt = str(e.get("part") or "").strip()
        if pt and pt not in distinct_parts:
            distinct_parts.append(pt)

    return {
        "status": "ok",
        "book_title": idx["meta"].get("title_ar") or b_dir.name.split("__")[-1].replace("-", " "),
        "author": idx["meta"].get("main_author_name_ar") or "من أئمة التراث",
        "start_page": start_page,
        "end_page": end_page,
        "part": p_str or (distinct_parts[0] if distinct_parts else "1"),
        "available_parts": distinct_parts,
        "pages_count": len(pages_data),
        "pages": pages_data
    }

def get_book_toc(book: Any) -> Dict[str, Any]:
    """
    أداة 2: استخراج شجرة الأبواب وفهرس المحتويات للكتاب.
    """
    b_dir = resolve_book_files(book)
    if not b_dir:
        return {"error": f"تعذر العثور على ملفات الكتاب: {book}"}

    toc_file = b_dir / "toc.jsonl"
    if not toc_file.exists():
        return {"status": "ok", "message": "لا يتوفر ملف فهرس أبواب منفصل لهذا الكتاب.", "toc": []}

    toc_items = []
    try:
        with open(toc_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    toc_items.append({
                        "title": item.get("title_text", ""),
                        "page_id": item.get("page_id"),
                        "shamela_title_id": item.get("shamela_title_id")
                    })
    except Exception as e:
        return {"error": f"فشل قراءة فهرس الكتاب: {e}"}

    meta_file = b_dir / "book_metadata.json"
    title = b_dir.name.split("__")[-1].replace("-", " ")
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                m = json.load(f)
                title = m.get("title_ar") or title
        except Exception:
            pass

    return {
        "status": "ok",
        "book_title": title,
        "total_headings": len(toc_items),
        "toc": toc_items[:400]  # إرجاع أول 400 عنوان وباب رئيسي
    }

def verify_quote(book: Any, quote_text: str, part: Optional[str] = None, page_hint: Optional[int] = None) -> Dict[str, Any]:
    """
    أداة 3: مطابقة نص الاقتباس الحرفي داخل صفحات الكتاب بدقة 100%.
    """
    b_dir = resolve_book_files(book)
    if not b_dir:
        return {"error": f"تعذر العثور على ملفات الكتاب: {book}"}

    idx = get_book_index(b_dir)
    entries = idx["entries"]
    clean_target = clean_arabic_text(quote_text)
    if len(clean_target) < 6:
        return {"error": "النص المراد التحقق منه قصير جداً."}

    def _strip_parens(s: str) -> str:
        # كتب الشروح تدرج المتن بين قوسين؛ النقل الطبيعي يحذفهما فلا يفشل التطابق
        s = re.sub(r"[()\[\]{}（）【】]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    clean_target_np = _strip_parens(clean_target)

    _MARKER_CHARS = set("﵀﵁﵂﵃﵄﵅﵆﵇﵈﵉﵊﵋﵌﵍﵎﵏ﷺﷻ﴿﴾¬")

    _PUNCT = "،؛:.-–—()[]{}\u00ab\u00bb\u201c\u201d\"'!؟?/\\|"

    def _words(s: str):
        out = []
        for w in _strip_parens(s).split():
            w = w.strip(_PUNCT)
            if not w:
                continue
            if all(ch in _MARKER_CHARS or ch.isdigit() or ch in "٠١٢٣٤٥٦٧٨٩" for ch in w):
                continue  # رموز ترحم وأرقام حواشٍ وعلامات أقواس ليست من المتن
            w = w.replace("ئ", "ي").replace("ؤ", "و").replace("ى", "ي")
            if w.endswith("ءا") and len(w) > 2:
                w = w[:-1]  # ألف التنوين بعد الهمزة رسمٌ لا حرف زائد: قرءا = قرء
            out.append(w)
        return out

    def _seq_match(page_words, target_words):
        """تتابع كلمات النقل داخل كلمات الصفحة مع تسامح إدخالات قصيرة (حواشٍ/شروح بينية)."""
        if not target_words or not page_words:
            return False
        max_gap = 8
        max_ins = max(6, (len(target_words) * 3) // 4)
        first = target_words[0]
        # مواضع البدء: تطابق مباشر، أو كلمتا صفحة مدمجتان تساويان كلمة النقل الأولى (رسم «ما لا» في الطبعة = «مالا» في النقل)
        starts = []
        for i, w in enumerate(page_words):
            if w == first:
                starts.append(i)
            elif i + 1 < len(page_words) and w + page_words[i + 1] == first:
                starts.append(i + 1)
        for st in starts:
            pi, ins = st, 0
            ok = True
            for tw in target_words[1:]:
                found = -1
                for k in range(pi + 1, min(len(page_words), pi + 2 + max_gap)):
                    if page_words[k] == tw:
                        found = k
                        break
                    if k + 1 < len(page_words) and page_words[k] + page_words[k + 1] == tw:
                        found = k + 1
                        break
                if found < 0:
                    ok = False
                    break
                ins += found - pi - 1
                if ins > max_ins:
                    ok = False
                    break
                pi = found
            if ok:
                return True
        return False

    target_words = _words(clean_target)

    pages_file = b_dir / "pages.jsonl"
    
    # تحديد نطاق الفحص: إذا وجد رقم صفحة تقريبي نفحص الصفحات المحيطة أولاً
    scan_entries = entries
    if page_hint is not None:
        near = [e for e in entries if e.get("page_num") and abs(int(e["page_num"]) - page_hint) <= 8]
        if near:
            scan_entries = near + [e for e in entries if e not in near]

    # تسريع بالفهرس: صفحات مرشحة من FTS داخل الكتاب نفسه (± صفحة للامتداد)،
    # تُفحص أولًا؛ فإن لم يُعثر فيها على مطابقة تابعنا المسح الكامل — الدقة لا تتغير
    cand_phase = 0
    try:
        card = resolve_book(book)
        bid = card.get("book_id") if card.get("status") == "ok" else None
        if bid:
            import library_search
            li = library_search.get_index()
            r = li.search(quote_text, mode="words", book_ids=[int(bid)], limit=16)
            pos_by_pid = {e.get("page_id"): i for i, e in enumerate(entries)}
            seen_off, cand = set(), []
            for h in r.get("results", []):
                i = pos_by_pid.get(h.get("page_id"))
                if i is None:
                    continue
                for j in (i - 1, i, i + 1):
                    if 0 <= j < len(entries) and entries[j]["offset"] not in seen_off:
                        seen_off.add(entries[j]["offset"])
                        cand.append(entries[j])
            if cand:
                scan_entries = cand + [e for e in scan_entries if e["offset"] not in seen_off]
                cand_phase = len(cand)
    except Exception:
        cand_phase = 0

    matches = []
    q_words = set(w for w in clean_target.split() if len(w) >= 3)
    best = None
    try:
        with open(pages_file, "rb") as f:
            for ci, entry in enumerate(scan_entries):
                f.seek(entry["offset"])
                line = f.readline()
                if line:
                    data = json.loads(line.decode("utf-8"))
                    body = data.get("body", "")
                    clean_b = clean_arabic_text(body)
                    plain = re.sub(r"<[^>]+>", " ", body)
                    plain = re.sub(r"\s+", " ", plain).strip()
                    if q_words:
                        overlap = len(q_words & set(clean_b.split())) / len(q_words)
                        if best is None or overlap > best["score"]:
                            best = {"score": round(overlap, 3), "part": entry["part"], "page_num": entry["page_num"], "snippet": plain[:400]}

                    if clean_target in clean_b or clean_target_np in _strip_parens(clean_b) or _seq_match(_words(clean_b), target_words):
                        pos = clean_b.find(clean_target)
                        exact = quote_text.strip() in plain
                        matches.append({
                            "verified": True,
                            "match_status": "MATCH_EXACT" if exact else "MATCH_NORMALIZED",
                            "part": entry["part"],
                            "page_num": entry["page_num"],
                            "seq": entry["seq"],
                            "snippet": plain[:400],
                            "continuation": plain[max(0, pos):pos + len(clean_target) + 300] if pos >= 0 else plain[:300]
                        })
                        if len(matches) >= 3:
                            break
                if cand_phase and ci + 1 >= cand_phase and matches:
                    break  # وُجدت المطابقة في صفحات الفهرس المرشحة؛ لا حاجة لمسح بقية الكتاب
    except Exception as e:
        return {"error": f"خطأ أثناء التحقق من الاقتباس: {e}"}

    if not matches and len(entries) > 1:
        # نقل يمتد عبر صفحتين متتاليتين: افحص أزواج الصفحات المتجاورة بالترتيب الطبيعي
        try:
            hot = set()
            if best and best.get("score", 0) >= 0.4:
                hot = {e["offset"] for e in entries
                       if q_words and e.get("offset") is not None}
            prev = None
            with open(pages_file, "rb") as f:
                for entry in entries:
                    f.seek(entry["offset"])
                    line = f.readline()
                    if not line:
                        prev = None
                        continue
                    data = json.loads(line.decode("utf-8"))
                    clean_b = clean_arabic_text(data.get("body", ""))
                    cur = (entry, clean_b)
                    if prev is not None:
                        pe, pc = prev
                        same_part = str(pe.get("part")) == str(entry.get("part"))
                        tw_set = set(target_words)
                        ov = (len(tw_set & set(_words(pc)) | (tw_set & set(_words(clean_b)))) / len(tw_set)) if tw_set else 0
                        if ov >= 0.5:
                            joined = pc + " " + clean_b
                            if clean_target in joined or clean_target_np in _strip_parens(joined) or _seq_match(_words(joined), target_words):
                                plain = re.sub(r"<[^>]+>", " ", data.get("body", ""))
                                plain = re.sub(r"\s+", " ", plain).strip()
                                matches.append({
                                    "verified": True,
                                    "match_status": "MATCH_NORMALIZED",
                                    "part": pe["part"],
                                    "page_num": pe["page_num"],
                                    "seq": pe["seq"],
                                    "spans_pages": True,
                                    "snippet": plain[:400],
                                    "continuation": "النقل يبدأ في هذه الصفحة ويمتد إلى الصفحة التالية" + ("" if same_part else " من الجزء نفسه"),
                                })
                                break
                    prev = cur
        except Exception:
            pass

    meta_file = b_dir / "book_metadata.json"
    title = b_dir.name.split("__")[-1].replace("-", " ")
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as mf:
                m = json.load(mf)
                title = m.get("title_ar") or title
        except Exception:
            pass

    try:
        clean_rel = str(b_dir.relative_to(SHAMELA_DATA_DIR))
    except ValueError:
        # الكتاب وُجد في جذر بيانات آخر (لقطة/نسخة دعم): المسار المطلق صالح للعرض
        clean_rel = str(b_dir)
    found = len(matches) > 0
    return {
        "status": "ok",
        "book_title": title,
        "rel_path": clean_rel,
        "verified": found,
        "match_status": matches[0]["match_status"] if found else "NOT_FOUND",
        "matches_count": len(matches),
        "matches": matches,
        "closest": None if found else best,
        "quote_checked": quote_text,
        "note": "لا يُنقل اقتباس حالته NOT_FOUND." if not found else "المطابقة على نص الصفحة من الملف، بعد توحيد الرسم والتشكيل عند الحاجة."
    }


def _edition_siblings(book: Any) -> List[Dict[str, Any]]:
    """طبعات أخرى للعمل نفسه (نفس جذع العنوان والمؤلف) من فهرس الشاملة."""
    card = resolve_book(book)
    if card.get("status") != "ok" or not card.get("title"):
        return []
    stem = re.split(r"\s+-\s+|، ت|، ط|\s+ط\s+", card["title"])[0].strip()
    out = []
    try:
        db = WORKSPACE_ROOT / "shamela_index.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        for r in conn.execute(
                "SELECT book_id, title_ar, main_author_name_ar FROM books WHERE title_ar LIKE ? AND book_id != ? LIMIT 8",
                (stem + "%", int(card["book_id"]))):
            if (r["main_author_name_ar"] or "")[:10] == (card.get("author") or "")[:10]:
                out.append({"book_id": r["book_id"], "title": r["title_ar"]})
        conn.close()
    except Exception:
        pass
    return out[:3]


def verify_batch(citations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """مطابقة حتى 40 نقلًا دفعة واحدة (سجل مطابقة)، مع إعادة تحديد الموضع في
    طبعات أخرى للعمل عند الفشل في الطبعة المحددة."""
    def _one(c):
        book, quote = c.get("book"), c.get("quote_text") or c.get("quote") or ""
        r = verify_quote(book=book, quote_text=quote, part=c.get("part"),
                         page_hint=c.get("page_hint") or c.get("page_num"))
        status = r.get("match_status") or "NOT_FOUND"
        entry = {"book": book, "quote_checked": quote, "match_status": status,
                 "matches": r.get("matches"), "book_title": r.get("book_title")}
        if status == "NOT_FOUND":
            for sib in _edition_siblings(book):
                r2 = verify_quote(book=str(sib["book_id"]), quote_text=quote)
                if r2.get("match_status") in ("MATCH_EXACT", "MATCH_NORMALIZED"):
                    entry.update({"match_status": "RELOCATED", "relocated_to": {
                        "book_id": sib["book_id"], "title": sib["title"],
                        "matches": r2.get("matches")}})
                    status = "RELOCATED"
                    break
        entry["match_status"] = status
        return entry

    cites = list(citations or [])[:40]
    items = []
    if cites:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=6) as ex:
            items = list(ex.map(_one, cites))
    counts = {"MATCH_EXACT": 0, "MATCH_NORMALIZED": 0, "RELOCATED": 0, "NOT_FOUND": 0}
    for e in items:
        counts[e["match_status"]] = counts.get(e["match_status"], 0) + 1
    return {"status": "ok", "ledger": counts, "items": items,
            "note": "سجل مطابقة: لا يُعتمد في الجواب إلا MATCH_EXACT/MATCH_NORMALIZED/RELOCATED بعد قراءة صفحته."}


def get_book_coverage(book: Any) -> Dict[str, Any]:
    """بطاقة تغطية: خريطة أجزاء الكتاب وعدد صفحات كل جزء وعدّاد فهرسه، مع
    تحذير بتر إن نقصت الأجزاء المسجلة عن مجلدات الطبعة المعلنة."""
    b_dir = resolve_book_files(book)
    if not b_dir:
        return {"error": f"تعذر العثور على ملفات الكتاب: {book}"}
    idx = get_book_index(b_dir)
    entries = idx["entries"]
    card = resolve_book(book)
    parts: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        p = parts.setdefault(str(e["part"]), {"pages": 0, "first_page": e["page_num"], "last_page": e["page_num"]})
        p["pages"] += 1
        p["last_page"] = e["page_num"]
    toc_count = 0
    toc_file = b_dir / "toc.jsonl"
    if toc_file.exists():
        try:
            toc_count = sum(1 for _ in open(toc_file, encoding="utf-8"))
        except Exception:
            pass
    declared_volumes = card.get("volumes")
    warnings = []
    if declared_volumes and len(parts) < int(declared_volumes):
        warnings.append(f"تحذير تغطية: الطبعة معلنة {declared_volumes} مجلدًا والنص المسجل {len(parts)} أجزاء فقط — قد يكون النص مبتورًا في آخره؛ وثّق ذلك ولا تستدل بغياب.")
    return {"status": "ok", "book_id": card.get("book_id"), "title": card.get("title"),
            "author": card.get("author"), "death_year": card.get("death_year"),
            "category": card.get("category"), "total_pages": len(entries),
            "parts": parts, "toc_entries": toc_count,
            "declared_volumes": declared_volumes, "warnings": warnings}

_ERAS = [("حتى 400هـ", 0, 400), ("401–700هـ", 401, 700), ("701–1100هـ", 701, 1100), ("بعد 1100هـ", 1101, 99998)]
_AYAH_TEXT_CACHE: Dict[Any, str] = {}


def _ayah_text(surah: int, ayah: int) -> str:
    key = (int(surah), int(ayah))
    if key not in _AYAH_TEXT_CACHE:
        try:
            d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "quran_uthmani.json"), encoding="utf-8"))
            for r in (d.get("quran") or d):
                _AYAH_TEXT_CACHE[(int(r["chapter"]), int(r["verse"]))] = clean_arabic_text(r["text"])
        except Exception:
            pass
    return _AYAH_TEXT_CACHE.get(key, "")


def _excerpt_around(body: str, anchor_norm: str, span: int = 950) -> str:
    """مقتطف معاينة حول مرساة: بحث في النص الأصلي ثم تقدير موضعي بالنص المطبّع."""
    if not body:
        return ""
    pos = body.find("﴿")
    if pos < 0 and anchor_norm:
        norm_body = clean_arabic_text(body)
        words = anchor_norm.split()
        pos_n = -1
        for i in range(max(0, len(words) - 3)):
            pos_n = norm_body.find(" ".join(words[i:i + 4]))
            if pos_n >= 0:
                break
        if pos_n >= 0 and norm_body:
            pos = int(pos_n / len(norm_body) * len(body))
    if pos < 0:
        pos = 0
    start = max(0, pos - 120)
    return body[start:start + span].strip()


_SAYER_RE = re.compile(r"(?:عن|وقال|وقالت|وذكر|حدثنا[^،:]{0,40}عن)\s+([^\s،:؛.()]{2,22}(?:\s+(?:بن|ابن|أبي|أبو|أم|آل)\s+[^\s،:؛.()]{2,22})?)")


def _full_text_around(body: str, anchor_norm: str, budget: int = 2400) -> str:
    """نص الموضع كاملًا بميزانية أحرف: يبدأ قبل المرساة بقليل ويمتد بقدر الميزانية."""
    if not body:
        return ""
    pos = body.find("﴿")
    if pos < 0 and anchor_norm:
        norm_body = clean_arabic_text(body)
        words = anchor_norm.split()
        for i in range(max(0, len(words) - 3)):
            p = norm_body.find(" ".join(words[i:i + 4]))
            if p >= 0:
                pos = int(p / max(1, len(norm_body)) * len(body))
                break
    if pos < 0:
        pos = 0
    start = max(0, pos - 150)
    return body[start:start + int(budget or 2400)].strip()


def ayah_dossier(surah: int, ayah: int, per_era: int = 5, per_source_chars: int = 2400, brief: bool = False) -> Dict[str, Any]:
    """ملف آية طبقي: مواضعها في التفاسير مطوية بحسب الكتاب، موزعة على أربع طبقات
    عصر، مع مقتطف معاينة من صفحة كل مصدر واستخراج آلي أولي لقائلي السلف.
    brief: مخرجات نحيفة للاستكشاف السريع (مقتطفات أقصر)."""
    if brief:
        per_source_chars = min(int(per_source_chars or 2400), 900)
    import library_search
    idx = library_search.get_index()
    loc = idx.ayah_loci(int(surah), int(ayah), kind="tafsir", limit=400)
    if loc.get("status") != "ok":
        return loc
    books: List[Dict[str, Any]] = []
    seen_books = set()
    for h in loc["loci"]:
        if h["book_id"] in seen_books:
            continue
        seen_books.add(h["book_id"])
        books.append(h)
    anchor = _ayah_text(surah, ayah)
    layers: Dict[str, List[Dict[str, Any]]] = {}
    sayers: Dict[str, int] = {}
    for era_name, lo, hi in _ERAS:
        picked = []
        for h in books:
            d = h["author_death_hijri"] if h["author_death_hijri"] and h["author_death_hijri"] != 99999 else 99998
            if not (lo <= d <= hi) or len(picked) >= int(per_era or 5):
                continue
            gp = get_page(h["book_id"], h["page_num"], h["part"]) if h.get("page_num") else {}
            page = gp.get("page") or {}
            body = (page.get("body") or "") + "\n" + (page.get("footnotes") or "")
            if era_name == "حتى 400هـ":
                for m in _SAYER_RE.finditer(clean_arabic_text(body)):
                    nm = m.group(1).strip()
                    if len(nm) >= 4 and not any(w in nm for w in ("الله", "رسول", "النبي", "قال", "ابن", "ابيه", "عبد")):
                        sayers[nm] = sayers.get(nm, 0) + 1
            full = _full_text_around(body, anchor, per_source_chars)
            entry = {**h, "text": full, "excerpt": full[:300],
                     "text_note": "نص الموضع من صفحة الكتاب بميزانية أحرف؛ ما زاد يُقرأ بـget_page_range."}
            if era_name == "حتى 400هـ":
                # أقوال القائلين أنفسهم: جمل «قال/عن فلان» من متن الصفحة، لا أسماءهم فقط
                quotes = []
                for sent in re.split(r"[.\n]", body):
                    s = sent.strip()
                    m = _SAYER_RE.search(clean_arabic_text(s))
                    if m and 25 <= len(s) <= 300 and "﴿" not in s[:12]:
                        quotes.append({"sayer": m.group(1).strip(), "quote": s})
                    if len(quotes) >= 3:
                        break
                if quotes:
                    entry["salaf_quotes"] = quotes
            picked.append(entry)
        layers[era_name] = picked
    top_sayers = sorted(sayers.items(), key=lambda kv: -kv[1])[:14]
    _res = {"status": "ok", "surah": int(surah), "ayah": int(ayah),
            "ayah_text": _ayah_text(surah, ayah), "layers": layers,
            "salaf_sayers_auto": [{"name": n, "mentions": c} for n, c in top_sayers],
            "coverage": {**loc.get("coverage", {}), "tafsir_books_deduped": len(books)},
            "note": "ملف طبقي من فهرسنا: المواضع مطوية بحسب الكتاب وموزعة بالوفيات؛ قائلو السلف استخراج آلي من صفحات الطبقة الأولى يُتحقق منه بالقراءة، والمقتطفات للمعاينة لا للنقل."}
    _attach_quotes(_res, [w for w in re.split(r"\s+", re.sub(r"[﴿﴾]", " ", anchor or "")) if len(w) >= 3][:6])
    return _res


_GRADING_RE = re.compile(r"(صحّحه|صححه|حسّنه|حسنه|ضعّفه|ضعفه|إسناده\s+(?:صحيح|حسن|ضعيف|قوي|جيد)|رجاله\s+(?:ثقات|رجال الصحيح|موثقون)|حديث\s+(?:صحيح|حسن|ضعيف)(?:\s+الإسناد)?|قال\s+(?:الترمذي|الحاكم|الدارقطني|ابن حجر|الذهبي|النووي)[^.:؛]{0,70})")
_GRADER_NAMES = ("الألباني|الحاكم|الذهبي|الترمذي|ابن حجر|النووي|الدارقطني|ابن خزيمة|ابن حبان|ابن القطان|"
                 "المنذري|الهيثمي|البوصيري|ابن الملقن|شعيب الأرنؤوط|الأرنؤوط|أحمد شاكر|ابن باز|ابن عثيمين|"
                 "الوادعي|ابن حزم|البيهقي|الخطابي|ابن عبد البر|العراقي|الشوكاني|الصنعاني|ابن تيمية|ابن القيم|"
                 "ابن كثير|السيوطي|المناوي|العجلوني|السخاوي|ابن الجوزي|البخاري|مسلم|أبو داود|النسائي|ابن ماجه|أحمد")
_GRADER_RE = re.compile(r"(?:صحّحه|صححه|حسّنه|حسنه|ضعّفه|ضعفه|وثّقه|وثقه|قال|وقاله|ذكر)\s+(?:الشيخ\s+|الإمام\s+|الحافظ\s+)?(" + _GRADER_NAMES + r")")
_VERDICT_RES = [("موضوع", r"موضوع|مكذوب"), ("ضعيف", r"ضعيف|منكر|لا يصح|ليس بصحيح|واه"),
                ("صحيح", r"صحيح|على شرط الشيخين|على شرط مسلم"), ("حسن", r"حسن"),
                ("رجاله ثقات", r"رجاله ثقات|رجاله موثقون|رجال الصحيح")]


_TITLE_EDITOR_RE = re.compile(r"(?:تخريج|تحقيق|تعليق|حاشية|شرح)\s+([^،\-–—(]{3,32})")


def _grader_of(sentence: str, book_author: str = "", book_title: str = "") -> Dict[str, str]:
    m = _GRADER_RE.search(sentence or "")
    verdict = ""
    for name, pat in _VERDICT_RES:
        if re.search(pat, sentence or ""):
            verdict = name
            break
    if m:
        return {"grader": m.group(1), "grader_source": "مسمّى في النص", "verdict": verdict}
    te = _TITLE_EDITOR_RE.search(book_title or "")
    if te:
        return {"grader": te.group(1).strip(), "grader_source": "محقق/شارح الكتاب من عنوانه", "verdict": verdict}
    if book_author:
        return {"grader": book_author, "grader_source": "مؤلف الكتاب الحامل (قد ينقل الحكم عن غيره)", "verdict": verdict}
    return {"grader": "", "grader_source": "غير مسمّى", "verdict": verdict}


def hadith_dossier(text: str, limit: int = 8, brief: bool = False) -> Dict[str, Any]:
    """ملف حديث: مواضع المتن مجمعة (أصول/شروح/تخريج) + أحكام مستخرجة آليًا من
    صفحات كتب التخريج والشروح عندنا، موسومة بأنها آلية تُقرأ في سياقها."""
    import library_search
    idx = library_search.get_index()
    loci = idx.hadith_loci(text, limit=int(limit or 8))
    cats = ["التخريج والأطراف", "شروح الحديث", "العلل والسؤالات الحديثية", "كتب السنة", "علوم الحديث"]
    cand = idx.search(text, mode="words", categories=cats, limit=24)
    # صفحات مرشحة: نتائج البحث + مواضع الأصول والشروح والتخريج
    page_meta: Dict[int, Dict[str, Any]] = {}
    for h in cand.get("results", []):
        page_meta.setdefault(h["page_id"], h)
    for grp in (loci.get("groups") or {}).values():
        for h in grp:
            if h["page_id"] not in page_meta:
                m = idx.meta.get(h["book_id"], {})
                page_meta[h["page_id"]] = {**h, "author": m.get("author")}
    gradings: List[Dict[str, Any]] = []
    seen_sent = set()
    gdb = os.path.join(idx.fts_dir, "hadith_gradings.db")
    if os.path.exists(gdb) and page_meta:
        try:
            con = sqlite3.connect(f"file:{gdb}?mode=ro", uri=True)
            # الصفحات المرشحة وجوارها (±3) في الكتاب نفسه: الحكم قد يجلس في صفحة مجاورة لموضع المتن
            cand_pairs = {(h.get("book_id"), pid) for pid, h in page_meta.items() if h.get("book_id")}
            rows_g = []
            for bid, pid in list(cand_pairs)[:40]:
                rows_g.extend(con.execute(
                    "SELECT book_id, page_id, part, page_num, sentence FROM page_gradings WHERE book_id=? AND page_id BETWEEN ? AND ?",
                    (bid, pid - 3, pid + 3)))
            book_meta = {}
            for h in page_meta.values():
                if h.get("book_id"):
                    book_meta.setdefault(h["book_id"], h)
            for bid, pid, gpart, gpnum, sent in rows_g:
                if len(gradings) >= 12:
                    break
                key = clean_arabic_text(sent)[:80]
                if key in seen_sent:
                    continue
                seen_sent.add(key)
                h = page_meta.get(pid) or book_meta.get(bid, {})
                gradings.append({"grading_excerpt": sent,
                                 **_grader_of(sent, h.get("author") or "", h.get("title") or ""),
                                 "book_id": bid, "title": h.get("title"),
                                 "author_death_hijri": h.get("author_death_hijri"),
                                 "part": gpart, "page_num": gpnum, "page_id": pid})
            con.close()
        except Exception:
            gradings = []
    if not gradings:
        # احتياط: تعدين مباشر من الصفحات الأصلية إن غاب الفهرس الخامل
        seen_books: Dict[int, int] = {}
        for h in cand.get("results", []):
            if len(gradings) >= 10:
                break
            if seen_books.get(h["book_id"], 0) >= 1 or not h.get("page_num"):
                continue
            seen_books[h["book_id"]] = 1
            gp = get_page(h["book_id"], h["page_num"], h["part"])
            page = gp.get("page") or {}
            body = (page.get("body") or "") + "\n" + (page.get("footnotes") or "")
            for sent in re.split(r"[.\n؛]", body):
                s = sent.strip()
                if 12 <= len(s) <= 240 and _GRADING_RE.search(s):
                    key = clean_arabic_text(s)[:80]
                    if key in seen_sent:
                        continue
                    seen_sent.add(key)
                    gradings.append({"grading_excerpt": s, **_grader_of(s, h.get("author") or "", h.get("title") or ""),
                                     "book_id": h["book_id"], "title": h["title"],
                                     "author_death_hijri": h["author_death_hijri"],
                                     "part": h["part"], "page_num": h["page_num"], "page_id": h["page_id"]})
                    break
    # إرفاق نص الأصل: متن الحديث يُنقل من كتابه (السنن/المسند) لا من كتب الفقه،
    # فنرفق نص صفحات أوائل مواضع «أصول» و«تخريج» ليُنقل المتن والحكم من مصدريهما
    attached = 0
    groups = loci.get("groups", {})

    def _usul_rank(h):
        t = h.get("title") or ""
        if "صحيح البخاري" in t:
            return 0
        if "صحيح مسلم" in t:
            return 1
        return 2

    def _work_stem(h):
        # جذع العمل لطيّ الطبعات: طبعتان لمسند واحد لا تحجزان موضعين
        return re.split(r"\s+-\s+|\s+ت\s+|\s+ط\s+", h.get("title") or "")[0].strip()

    _plans = (("أصول", 700, 2), ("تخريج", 600, 1)) if brief else (("أصول", 1700, 4), ("تخريج", 1400, 2))
    _cap_att = 3 if brief else 6
    for label, budget, topn in _plans:
        rows = list(groups.get(label, []))
        if label == "أصول":
            rows.sort(key=_usul_rank)  # الصحيحان أولًا عند وجودهما فلا يُعلن «تعذر الأصل» وهما في المتن
        seen_books = set()
        for h in rows:
            if attached >= _cap_att or len(seen_books) >= topn:
                break
            if _work_stem(h) in seen_books or not h.get("page_num"):
                continue
            seen_books.add(_work_stem(h))
            gp = get_page(h["book_id"], h["page_num"], h["part"])
            page = gp.get("page") or {}
            body = (page.get("body") or "").strip()
            if body:
                h["text"] = _full_text_around(body, clean_arabic_text(text), budget)
                h["text_from_original"] = True
                attached += 1
    _res = {"status": "ok", "text": text, "loci_groups": groups,
            "original_texts_attached": attached,
            "gradings_auto": gradings,
            "gradings_index": "hadith_gradings.db" if os.path.exists(gdb) else "unavailable (تعدين مباشر)",
            "note": "انقل متن الحديث من نصوص مجموعة «أصول» المرفقة (أو get_page على مواضعها) ومن كتابه الأصلي بعزو جزئه وصفحته، والحكم من كتب التخريج؛ ولا تنقل متن حديث من كتاب فقه إلا عند تعذر بلوغ الأصل مع التصريح بذلك في جوابك. الأحكام الآلية قد تخص حديثًا جارًا في الصفحة؛ لا يُعتمد حكم حتى يُقرأ في سياقه من كتابه."}
    _attach_quotes(_res, [w for w in re.split(r"\s+", clean_arabic_text(text)) if len(w) >= 4][:6])
    return _res


def _attach_texts(node: Any, budget: int, cap: List[int]) -> None:
    """إرفاق نص الصفحة الأصلي بأول مواضع البنية (كتب/صفحات) حتى سقف عدد."""
    if cap[0] <= 0:
        return
    if isinstance(node, dict):
        if node.get("book_id") and node.get("page_num") and "text" not in node:
            gp = get_page(node["book_id"], node["page_num"], node.get("part"))
            page = gp.get("page") or {}
            body = (page.get("body") or "").strip()
            if body:
                node["text"] = body[:budget]
                cap[0] -= 1
        for v in node.values():
            _attach_texts(v, budget, cap)
    elif isinstance(node, list):
        for v in node:
            _attach_texts(v, budget, cap)


def _collect_text_rows(node: Any, out: list) -> None:
    if isinstance(node, dict):
        if node.get("book_id") and node.get("text"):
            out.append(node)
        for v in node.values():
            _collect_text_rows(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_text_rows(v, out)


def _quote_candidates(text: str, terms: list, per_row: int = 2) -> list:
    t = re.sub(r"<[^>]+>", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    sents = [s.strip() for s in re.split(r"(?<=[.؛؟!])\s+|\n+", t) if s.strip()]
    nterms = [clean_arabic_text(x) for x in (terms or []) if x and len(str(x).strip()) >= 2]
    scored = []
    for s in sents:
        if not (35 <= len(s) <= 340):
            continue
        cs = clean_arabic_text(s)
        scored.append((sum(1 for x in nterms if x in cs), s))
    scored.sort(key=lambda x: -x[0])
    picked = [s for sc, s in scored if sc > 0][:per_row]
    if not picked and scored:
        picked = [scored[0][1]]
    out = []
    for s in picked:
        if len(s) > 320:
            s = s[:320].rsplit(" ", 1)[0]
        out.append(s)
    return out


def _attach_quotes(result: Dict[str, Any], terms: list, max_total: int = 12) -> None:
    """اقتباسات جاهزة موثقة: جمل مفتاحية من نصوص الملف تُطابَق داخل الخادم نفسه،
    فينقل الوكيل حرفيًا منها ولا يحتاج دفعات تحقق منفصلة (الطبقة الأولى)."""
    rows: list = []
    _collect_text_rows(result, rows)
    cands, seen = [], set()
    for row in rows[:15]:
        for cand in _quote_candidates(row.get("text") or "", terms, per_row=1):
            key = (row.get("book_id"), cand[:60])
            if key in seen:
                continue
            seen.add(key)
            cands.append((row, cand))
    cands = cands[:14]

    def _check(rc):
        row, cand = rc
        try:
            v = verify_quote(row["book_id"], cand, page_hint=row.get("page_num"))
        except Exception:
            return None
        if not v.get("verified"):
            return None
        m0 = (v.get("matches") or [{}])[0]
        return {
            "book_id": row.get("book_id"), "title": row.get("title"),
            "author": row.get("author"),
            "part": m0.get("part") or row.get("part"),
            "page_num": m0.get("page_num") or row.get("page_num"),
            "quote": cand, "match_status": v.get("match_status"),
        }

    quotes = []
    if cands:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=6) as ex:
            for item in ex.map(_check, cands):
                if item:
                    quotes.append(item)
                if len(quotes) >= max_total:
                    break
    quotes = quotes[:max_total]
    result["quotes"] = quotes
    result["quotes_note"] = ("اقتباسات مستخرجة من نصوص هذا الملف ومتحقق منها آليًا داخل الخادم؛ "
                             "النقل الحرفي المعتمد من هذه القائمة، وما عداها يُقرأ في صفحته قبل النقل.")


from collections import OrderedDict as _OrderedDict
import uuid as _uuid

_PACKS: "_OrderedDict[str, Dict[str, Any]]" = _OrderedDict()
_PACK_CAP = 24


def _store_pack(result: Dict[str, Any]) -> str:
    pid = _uuid.uuid4().hex[:10]
    result["pack_id"] = pid
    _PACKS[pid] = result
    while len(_PACKS) > _PACK_CAP:
        _PACKS.popitem(last=False)
    return pid


def get_pack_slice(pack_id: str, field: str = None, offset: int = 0, limit: int = 5) -> Dict[str, Any]:
    """شريحة من حزمة ملف محفوظة عند الخادم: الحالة الوسيطة هنا لا في سياق الوكيل."""
    pack = _PACKS.get(str(pack_id or ""))
    if pack is None:
        return _error("PACK_NOT_FOUND", f"لا حزمة بهذا الرقم (قديمة أو من خادم آخر): {pack_id}")
    if not field:
        return {"status": "ok", "pack_id": str(pack_id), "fields": list(pack.keys())}
    val = pack.get(field)
    off, lim = max(0, int(offset or 0)), max(1, int(limit or 5))
    if isinstance(val, list):
        return {"status": "ok", "pack_id": str(pack_id), "field": field,
                "total": len(val), "offset": off, "items": val[off:off + lim]}
    if isinstance(val, str):
        return {"status": "ok", "pack_id": str(pack_id), "field": field,
                "total_chars": len(val), "offset": off, "text": val[off:off + lim * 800]}
    return {"status": "ok", "pack_id": str(pack_id), "field": field, "value": val}


def word_dossier(word: str, limit: int = 12, brief: bool = False) -> Dict[str, Any]:
    """ملف لفظ: مواد المعاجم وكتب الغريب بالوفيات مع نص مادة كل مصدر من صفحته."""
    import library_search
    idx = library_search.get_index()
    d = idx.lugha_search(word, limit=int(limit or 12))
    cap = [4 if brief else int(limit or 12)]
    _attach_texts(d.get("passages_by_death", []), 900 if brief else 1800, cap)
    _attach_quotes(d, [word])
    d["note"] = (d.get("note") or "") + " النصوص مرفقة من صفحات المصادر للقراءة المباشرة؛ النقل المعتمد من الصفحة كاملة."
    return d


def fiqh_dossier(topic: str, per_cell: int = 2, death_max: int = None, brief: bool = False) -> Dict[str, Any]:
    """ملف موضوع فقهي بالنصوص: ملف الموضوع الطبقي مع نص صفحة مداخل الموسوعات
    وأول موضع من كل خلية ممتلئة، للقراءة المباشرة قبل الحفر العميق.
    brief: مخرجات نحيفة (نصوص أقل وأقصر) للاستكشاف السريع."""
    import library_search
    idx = library_search.get_index()
    d = idx.dossier_topic(topic, per_cell=int(per_cell or 2), death_max=death_max)
    cap = [8 if brief else 20]
    _enc_b = 900 if brief else 2000
    _attach_texts(d.get("encyclopedia_entries", []), _enc_b, cap)
    # إرفاق موزع على الطبقات: نص مضمون من كل طبقة أولًا حتى لا تنحصر النصوص
    # في المتقدمين وتُهمل الوسطى والمتأخرون، ثم جولات استيفاء على الخلايا
    layers = d.get("layers") or []
    _cell_b = 900 if brief else 1800
    for layer in layers:
        for cell in (layer.get("cells") or {}).values():
            hits = cell.get("hits") or []
            if hits:
                _attach_texts([hits[0]], _cell_b, cap)
                break
    for rnd in range(int(per_cell or 2)):
        for layer in layers:
            for cell in (layer.get("cells") or {}).values():
                hits = cell.get("hits") or []
                if rnd < len(hits):
                    _attach_texts([hits[rnd]], _cell_b, cap)
    d["texts_attached"] = (8 if brief else 20) - cap[0]
    if brief:
        # تقليم الحقول: النحيف يبقي مفاتيح الاستدلال والنص فقط
        keep = ("book_id", "title", "author", "author_death_hijri", "part", "page_num", "page_id", "text", "mode", "heading", "snippet")
        def _trim(rows):
            return [{k: h[k] for k in keep if k in h} for h in (rows or [])]
        d["encyclopedia_entries"] = _trim(d.get("encyclopedia_entries"))
        d["headings"] = _trim(d.get("headings"))
        for layer in layers:
            for cell in (layer.get("cells") or {}).values():
                cell["hits"] = _trim(cell.get("hits"))
    _attach_quotes(d, [w for w in re.split(r"\s+", topic or "") if len(w) >= 3])
    d["note"] = (d.get("note") or "") + " أُرفق نص أول موضع من الموسوعات والخلايا موزعًا على الطبقات الزمنية كلها للقراءة المباشرة؛ بقية المواضع تُقرأ بـget_page. مثّل في جوابك طبقات كل مذهب (متقدمًا ومتوسطًا ومتأخرًا) ما وجدت نصوصها."
    return d


def search_in_book(book: Any, query: str, limit: int = 10) -> Dict[str, Any]:
    """
    أداة 4: بحث حرفي سريع ومحصور داخل نطاق كتاب واحد.
    """
    b_dir = resolve_book_files(book)
    if not b_dir:
        return {"error": f"تعذر العثور على ملفات الكتاب: {book}"}

    idx = get_book_index(b_dir)
    entries = idx["entries"]
    clean_q = clean_arabic_text(query)
    q_words = clean_q.split()

    pages_file = b_dir / "pages.jsonl"
    hits = []

    try:
        with open(pages_file, "rb") as f:
            for entry in entries:
                f.seek(entry["offset"])
                line = f.readline()
                if line:
                    data = json.loads(line.decode("utf-8"))
                    body = data.get("body", "")
                    clean_b = clean_arabic_text(body)

                    if clean_q in clean_b or (len(q_words) > 1 and all(w in clean_b for w in q_words)):
                        clean_plain = re.sub(r"<[^>]+>", " ", body)
                        clean_plain = re.sub(r"\s+", " ", clean_plain).strip()
                        # مقتطف متمركز حول أول مطابقة (بتجاوز التشكيل) لا من أول الصفحة
                        snippet = clean_plain[:350]
                        if q_words:
                            flex = "".join(re.escape(ch) + r"[ـً-ٰ]*" for ch in q_words[0] if not ch.isspace())
                            m = re.search(flex, clean_plain)
                            if m:
                                snippet = clean_plain[max(0, m.start() - 130): m.start() + 240]
                        hits.append({
                            "part": entry["part"],
                            "page_num": entry["page_num"],
                            "seq": entry["seq"],
                            "snippet": snippet
                        })
                        if len(hits) >= limit:
                            break
    except Exception as e:
        return {"error": f"فشل البحث داخل الكتاب: {e}"}

    return {
        "status": "ok",
        "book_title": idx["meta"].get("title_ar") or b_dir.name.split("__")[-1].replace("-", " "),
        "query": query,
        "results_count": len(hits),
        "results": hits
    }

# =============================================================================
# مواصفات أدوات MCP لتمريرها للنماذج الذكية (MCP Tools Catalog Schema)
# =============================================================================

SHAMELA_MCP_TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_page_range",
            "description": "قراءة وتقليب صفحات متتالية كاملة من أي كتاب في الشاملة بنصها الأصلي وهوامش التحقيق (تستعمل عند الحاجة لقراءة سياق المسألة كاملاً أو باب بأكمله).",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "اسم الكتاب أو رقمه في الشاملة (مثال: '2437' أو 'المغني لابن قدامة')"},
                    "start_page": {"type": "integer", "description": "رقم بداية الصفحة"},
                    "end_page": {"type": "integer", "description": "رقم نهاية الصفحة"},
                    "part": {"type": "string", "description": "رقم أو اسم الجزء (اختياري، مثال: '3')"}
                },
                "required": ["book", "start_page", "end_page"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_book_toc",
            "description": "استعراض شجرة الأبواب وفهرس المحتويات للكتاب لمعرفة مواضع الأبواب والفصول وتوزيع المسائل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "اسم الكتاب أو رقمه المعياري في الشاملة"}
                },
                "required": ["book"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_quote",
            "description": "مطابقة نص الاقتباس الحرفي داخل صفحات الكتاب والتأكد من وروده بنصه دون أي تصرف أو اختلاق من النموذج.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "اسم الكتاب أو رقمه"},
                    "quote_text": {"type": "string", "description": "النص التراثي المراد التحقق من وجوده حرفياً"},
                    "page_hint": {"type": "integer", "description": "رقم الصفحة التقريبي إن وجد لتسريع التحقق"}
                },
                "required": ["book", "quote_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_book",
            "description": "بحث حرفي سريع ومحصور داخل نطاق كتاب واحد محدد فقط للوقوف على كلمة أو عبارة معينة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "اسم الكتاب أو رقمه"},
                    "query": {"type": "string", "description": "الكلمة أو العبارة المراد البحث عنها داخل هذا الكتاب"},
                    "limit": {"type": "integer", "description": "أقصى عدد للنتائج (افتراضياً 10)"}
                },
                "required": ["book", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_surrounding_context",
            "description": "تقليب الصفحات السابقة واللاحقة (استيفاء السياق المحيط) لصفحة معينة في كتاب لكشف رأس الحولية التاريخية أو مطلع المسألة الفقهية الحاكمة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "اسم الكتاب أو رقمه"},
                    "page_num": {"type": "integer", "description": "رقم الصفحة المراد استيفاء سياقها"},
                    "part": {"type": "string", "description": "رقم الجزء إن وجد"},
                    "before_pages": {"type": "integer", "description": "عدد الصفحات السابقة (افتراضياً 2)"},
                    "after_pages": {"type": "integer", "description": "عدد الصفحات اللاحقة (افتراضياً 2)"}
                },
                "required": ["book", "page_num"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_book",
            "description": "حلّ كتاب إلى رقمه المعياري في الشاملة ومؤلفه وتصنيفه ومساره. الرقم هو المفتاح الوحيد لبقية الأدوات.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "رقم الكتاب أو عنوانه أو اسم شهرته"}
                },
                "required": ["book"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_book_card",
            "description": "بطاقة الكتاب الببليوغرافية من قاعدة الكتب: المحقق والطبعة والناشر ومدينة النشر وسنة الطبع.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "رقم الكتاب أو عنوانه"}
                },
                "required": ["book"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_page",
            "description": "قراءة صفحة واحدة بعينها بنصها وهوامشها من ملف الكتاب. هي وحدها مصدر النقل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "رقم الكتاب أو عنوانه"},
                    "page_num": {"type": "integer", "description": "رقم الصفحة"},
                    "part": {"type": "string", "description": "رقم الجزء إن وجد"}
                },
                "required": ["book", "page_num"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_issue_heading",
            "description": "عنوان الباب أو المسألة الحاكم لصفحة، من فهرس الكتاب.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "رقم الكتاب أو عنوانه"},
                    "page_num": {"type": "integer", "description": "رقم الصفحة"},
                    "part": {"type": "string", "description": "رقم الجزء إن وجد"}
                },
                "required": ["book", "page_num"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_books_scoped",
            "description": "بحث لفظي داخل قائمة أرقام كتب مغلقة. القائمة إلزامية ولا يخرج البحث عنها. النتائج مرشحات غير قابلة للنقل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "العبارة أو الألفاظ المميزة"},
                    "book_ids": {"type": "array", "items": {"type": "string"}, "description": "أرقام كتب النطاق المغلق"},
                    "limit_per_book": {"type": "integer", "description": "أقصى نتائج من كل كتاب"},
                    "limit": {"type": "integer", "description": "أقصى عدد كلي"}
                },
                "required": ["query", "book_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "anchor_lookup",
            "description": "جدول المراسي التراثية: يطابق مسألة معاصرة (باروكة، عملات رقمية، نقل أعضاء...) بعبارات من لسان التراث قبل 1000هـ مع شاهد موثق لكل عبارة (كتاب/جزء/صفحة). ابدأ بها في المسائل المعاصرة قبل أي بحث.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "سؤال المستخدم أو مسألته المعاصرة"},
                    "limit_entries": {"type": "integer", "description": "أقصى مداخل مطابقة"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "anchor_search",
            "description": "بحث الطبقات بالمراسي: يطابق الجدول ثم يبحث لفظيا بعباراته في كتب التراث ويعيد نصوص الصفحات. مرر book_ids لإغلاق النطاق عليها. النتائج مرشحات تقرأ وتطابق قبل النقل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "سؤال المستخدم أو مسألته"},
                    "book_ids": {"type": "array", "items": {"type": "string"}, "description": "اختياري: إغلاق النطاق على هذه الكتب"},
                    "limit": {"type": "integer", "description": "أقصى شواهد"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trace_hadith",
            "description": "تتبع ألفاظ حديث في كتب الحديث وحدها: أصول وشروح وتخريج. لا ينقل لفظاً من كتاب فقه. التصنيف آلي ترشيحي.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "ألفاظ مميزة من متن الحديث"},
                    "limit_books": {"type": "integer", "description": "أقصى كتب تُفحص"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_library",
            "description": "بحث فوري في نصوص المكتبة كلها (٨٥٨٩ كتابًا) عبر الفهرس في أجزاء الثانية. mode: phrase عبارة حرفية متتابعة (الأقوى للشواهد)، words كل الكلمات في صفحة واحدة، any أي كلمة، boolean منطقي (AND/OR/NOT). death_max سقف وفاة المؤلف بالهجري يختاره الباحث (٥٠٠ أو ١٠٠٠ أو ١٣٠٠...) وبدونه لا سقف. categories لتصنيفات بعينها، book_ids لإغلاق النطاق على كتب وكيل. النتائج مرشحات بمقتطفات: اقرأ الصفحة كاملة بـget_page وطابق بـverify_quote قبل النقل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "عبارة البحث بصياغة تراثية"},
                    "mode": {"type": "string", "enum": ["phrase", "words", "any", "boolean"], "description": "نمط المطابقة"},
                    "death_max": {"type": "integer", "description": "سقف وفاة المؤلف هجريًا (اختياري)"},
                    "death_min": {"type": "integer", "description": "حد أدنى لوفاة المؤلف (اختياري)"},
                    "categories": {"type": "array", "items": {"type": "string"}, "description": "تصنيفات بعينها"},
                    "book_ids": {"type": "array", "items": {"type": "integer"}, "description": "إغلاق النطاق على كتب بعينها"},
                    "include_alive": {"type": "boolean", "description": "شمول الأحياء والمجهولين عند وضع سقف وفاة"},
                    "limit": {"type": "integer", "description": "أقصى نتائج"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_headings",
            "description": "بحث في عناوين الأبواب والفصول (٤ ملايين عنوان) للوصول إلى فصل المسألة قبل قراءة المتون. يقدّم صيغ الأبواب التراثية (باب/فصل/مسألة/حكم) ويؤخّر معاجم البلدان واللغة. مرر death_max/categories/book_ids بنفس مرشحات search_library.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "اسم المسألة أو الباب"},
                    "mode": {"type": "string", "enum": ["phrase", "words", "any"]},
                    "death_max": {"type": "integer"},
                    "categories": {"type": "array", "items": {"type": "string"}},
                    "book_ids": {"type": "array", "items": {"type": "integer"}},
                    "limit": {"type": "integer"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_batch",
            "description": "حتى ٢٤ بحثًا في استدعاء واحد بنفس المرشحات (سقف وفاة/تصنيفات/كتب)، مدموجة ومنزوعة التكرار. مثالية لبحث مراسي اللجنة الخمس دفعة واحدة بدل خمس جولات متتابعة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {"type": "array", "items": {"type": "string"}, "description": "قائمة العبارات التراثية"},
                    "mode": {"type": "string", "enum": ["phrase", "words", "any"]},
                    "death_max": {"type": "integer"},
                    "categories": {"type": "array", "items": {"type": "string"}},
                    "book_ids": {"type": "array", "items": {"type": "integer"}},
                    "limit_per_query": {"type": "integer"}
                },
                "required": ["queries"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "survey_topic",
            "description": "مسح إحصائي قبل الحفر: عدد الصفحات الحاوية للمصطلح موزعة بحسب التصنيف والقرن الهجري وأغزر الكتب، ليعرف الباحث أين يتركز موضوعه وأي قرن ازدهر فيه قبل البحث العميق.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "المصطلح أو اللفظ المراد مسحه"},
                    "death_max": {"type": "integer"},
                    "categories": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dossier_topic",
            "description": "ملف موضوع فقهي مركّب قبل الحفر: مداخل الموسوعات الفقهية (الكويتية والتويجري) وعناوين أبواب وقائمة قراءة بأربع طبقات زمنية مضروبة في مذاهب أهل السنة (حنفي/مالكي/شافعي/حنبلي/ظاهري)، موضعان لكل خلية من الفهرس وسطر تغطية يوثق الخلايا الصفرية. ابدأ به في مسائل الفقه المقارن، ثم اقرأ بـget_page وطابق بـverify_quote.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "اسم المسألة بصياغتها التراثية (مثال: بيع العينة)"},
                    "per_cell": {"type": "integer", "description": "مواضع لكل خلية طبقة×مذهب (1-4)"},
                    "death_max": {"type": "integer", "description": "سقف وفاة الباحث يقص الطبقات عنده"}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ayah_dossier",
            "description": "ملف آية طبقي: مواضعها في التفاسير مطوية بحسب الكتاب وموزعة على أربع طبقات عصر، مع مقتطف معاينة من صفحة كل مصدر واستخراج آلي أولي لقائلي السلف من الطبقة الأولى. لأسئلة تفسير آية ومقارنة المفسرين عبر القرون.",
            "parameters": {
                "type": "object",
                "properties": {
                    "surah": {"type": "integer"},
                    "ayah": {"type": "integer"},
                    "per_era": {"type": "integer"},
                    "brief": {"type": "boolean", "description": "مقتطفات أقصر للاستكشاف السريع"}
                },
                "required": ["surah", "ayah"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "word_dossier",
            "description": "ملف لفظ لغوي بالنصوص: مواد المعاجم وكتب الغريب مرتبة بالوفيات مع نص مادة كل مصدر من صفحته الأصلية للقراءة المباشرة. brief لنصوص أقل وأقصر.",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "limit": {"type": "integer"},
                    "brief": {"type": "boolean"}
                },
                "required": ["word"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fiqh_dossier",
            "description": "ملف موضوع فقهي بالنصوص: طبقات العصر × المذاهب مع نص صفحة مداخل الموسوعات وأول موضع من كل خلية، للقراءة المباشرة ثم الحفر بـget_page والمطابقة بـverify_batch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "per_cell": {"type": "integer"},
                    "death_max": {"type": "integer"},
                    "brief": {"type": "boolean", "description": "مخرجات نحيفة للاستكشاف السريع: نصوص مرفقة أقل وأقصر"}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hadith_dossier",
            "description": "ملف حديث: مواضع المتن مجمعة (أصول/شروح/تخريج وعلل) مع نصوص مرفقة من الأصول والتخريج وأحكام مستخرجة آليًا تُقرأ في سياقها قبل اعتمادها. brief لمخرجات نحيفة سريعة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "limit": {"type": "integer"},
                    "brief": {"type": "boolean"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pack_slice",
            "description": "شريحة من حزمة ملف محفوظة عند الخادم برقم pack_id (يأتي مع نتائج ayah/word/fiqh/hadith_dossier): بلا field تُعاد أسماء الحقول، وبـfield قائمة تُعاد عناصرها مجزأة بـoffset/limit. الحالة الكاملة عند الخادم، فاجلب ما تحتاجه فقط ولا تحمل الملف كله في سياقك. النقل الحرفي من حقل quotes الموثق داخل الملف نفسه.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pack_id": {"type": "string", "description": "رقم الحزمة من نتيجة الملف"},
                    "field": {"type": "string", "description": "اسم الحقل المطلوب (quotes/texts/layers...)"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"}
                },
                "required": ["pack_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_batch",
            "description": "سجل مطابقة مجمّع: حتى 40 نقلًا دفعة واحدة تُطابَق على صفحات كتبها (MATCH_EXACT/MATCH_NORMALIZED)، وما فشل يُعاد تحديد موضعه في طبعات أخرى للعمل (RELOCATED). استعمله قبل تسليم أي جواب فيه نقول بين «».",
            "parameters": {
                "type": "object",
                "properties": {
                    "citations": {"type": "array", "items": {"type": "object"}, "description": "عناصر {book, quote_text, page_hint?, part?}"}
                },
                "required": ["citations"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_book_coverage",
            "description": "بطاقة تغطية كتاب: خريطة أجزائه وعدد صفحات كل جزء وعدّاد فهرسه، مع تحذير صريح إن كان النص المسجل أنقص من مجلدات الطبعة المعلنة (بتر صامت). استعمله قبل الاستدلال بغياب مسألة من كتاب.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book": {"type": "string", "description": "اسم الكتاب أو رقمه"}
                },
                "required": ["book"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ayah_loci",
            "description": "مواضع آية (سورة/رقم) في التفاسير مرتبة بوفاة المفسر من فهرس مراسي ﴿﴾ المبني على المكتبة، مع استشهادات الآية في سائر الكتب وسطر تغطية بعدد التفاسير ذات الموضع.",
            "parameters": {
                "type": "object",
                "properties": {
                    "surah": {"type": "integer"},
                    "ayah": {"type": "integer"},
                    "kind": {"type": "string", "enum": ["all", "tafsir", "citation"]},
                    "limit": {"type": "integer"}
                },
                "required": ["surah", "ayah"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "attestations",
            "description": "نسب عبارة قصيرة ثابتة: أقدم قائليها بترتيب وفيات المؤلفين مع طي طبعات العمل وتوزيع القرون — لمن قال أولًا وهل سُبق إليه.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phrases": {"type": "array", "items": {"type": "string"}},
                    "limit_works": {"type": "integer"}
                },
                "required": ["phrases"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hadith_loci",
            "description": "مواضع متن حديث في كتب السنة وشروحها وكتب التخريج والعلل من الفهرس مباشرة، مرتبة بالوفيات داخل كل صنف. أسرع من trace_hadith للمواضع الأولية.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "qawaid_search",
            "description": "قاعدة فقهية أو أصولية: عناوين كتب القواعد والأشباه والفروق والأصول الحاملة لها مع أقدم شاهد على صياغتها بالوفيات.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creed_search",
            "description": "مسألة عقدية: عناوين ومواضع في كتب العقيدة والفرق والردود بنصوص أصحابها، لاستخراج مقالات المدارس من كتبها لا من نقل خصومها.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fiqh_topics",
            "description": "شجرة موضوعات الفقه المنسّقة: موضوعات الأبواب وعدد مواضع كل موضوع عند كل مذهب سني. ابدأ بها لاكتشاف الموضوع المفهرس.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fiqh_topic_locations",
            "description": "مواضع موضوع فقهي موسومة بالمذهب من عناوين أبواب كتب المذاهب نفسها، بعناوين حقيقية تُقرأ صفحاتها وتُطابق.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "madhhab": {"type": "string"},
                    "per_madhhab": {"type": "integer"}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creed_issue",
            "description": "مسألة عقدية مفهرسة: أقسام المسألة من كتب كل مدرسة سنية (أهل الحديث والأثر/الأشاعرة/الماتريدية/الظاهرية) وكتب المقالات ناقلة عنها، من بذرة مسائل منسّقة تنمو. إن لم تُفهرس المسألة أُعيدت قائمتها مع بحث عام.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "per_school": {"type": "integer"}
                },
                "required": ["issue"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lugha_search",
            "description": "لفظ لغوي: مواد المعاجم وكتب الغريب والمعاني مرتبة بوفيات أصحابها لتعريف اللفظ وتاريخ استعماله.",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["word"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tarikh_search",
            "description": "حدث أو علم تاريخي: عناوين كتب التاريخ والسير والتراجم وروايات مرتبة بوفاة المؤرخ لتتبع طبقات النقل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "madhhab_authorities",
            "description": "فهرس ضبط المذهب: الكتب المعتمدة الحاسمة بطبقاتها وعلماء كل طبقة وقاموس اصطلاحي موزون وقواعد الترجيح داخل المذهب، باقتباسات موثّقة. استعمله قبل وصف قول بأنه «المذهب» أو «المقرر».",
            "parameters": {
                "type": "object",
                "properties": {
                    "madhhab": {"type": "string"}
                },
                "required": ["madhhab"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "authority_books",
            "description": "فهارس ضبط: كتب الإجماع الناقلة له، وكتب أسباب الخلاف، وكتب الخلاف العالي بين المذاهب — طبقاتها وأدوارها ومبادئ موثّقة من مقدماتها. قبل ادعاء إجماع راجع kind=ijma، وعند تعليل خلاف راجع kind=asbab، وللمقارنة العالية راجع kind=khilaf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string"}
                },
                "required": ["kind"]
            }
        }
    }
]

def get_surrounding_context(book: Any, page_num: int, part: Optional[str] = None, before_pages: int = 2, after_pages: int = 2) -> Dict[str, Any]:
    """تقليب واستيفاء الصفحات السابقة واللاحقة لكشف سياق المسألة أو الحولية"""
    p_int = max(1, int(page_num or 1))
    b_int = max(0, min(int(before_pages or 2), 5))
    a_int = max(0, min(int(after_pages or 2), 5))
    start_p = max(1, p_int - b_int)
    end_p = p_int + a_int
    return get_page_range(book=book, start_page=start_p, end_page=end_p, part=part)

def _error(code: str, message: str) -> Dict[str, Any]:
    return {"status": "error", "code": code, "error": message}


def _books_conn() -> Optional[sqlite3.Connection]:
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _tok_stems(s: Any) -> List[str]:
    s = re.sub(r"[ً-ٰٟ]", "", str(s or ""))
    s = s.translate(str.maketrans({"إ": "ا", "أ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"}))
    s = re.sub(r"[^\w\s]", " ", s)
    raw = []
    for t in s.split():
        if len(t) > 3:
            t = re.sub(r"^(?:ال|لل|ل)", "", t)
        if t in ("ابي", "ابا"):
            t = "ابو"
        if t:
            raw.append(t)
    # دمج مركّبات «عبد» (عبد الكافي، عبد البر) رمزًا واحدًا حتى لا تُسرق
    # أسماء الشهرة (الكافي) من أجزاء أسماء الأعلام.
    stems = []
    i = 0
    while i < len(raw):
        if raw[i] == "عبد" and i + 1 < len(raw):
            stems.append("عبد" + raw[i + 1])
            i += 2
        else:
            stems.append(raw[i])
            i += 1
    return stems


def _best_book_row(cur, text: str) -> Optional[Dict[str, Any]]:
    """مطابقة رمزية موزونة عند فشل التطابق الحرفي: درجة التطابق أولًا
    (رموز العنوان ×2 + المؤلف + مكافأة الاحتواء الكامل لرموز السؤال)،
    ثم بادئة العنوان، ثم عدد المجلدات كاسرًا للتعادل بين الأعمال المختلفة،
    ثم قصر العنوان ورقم الكتاب. تُرفق بالمختار قائمة منافسين (_rivals)
    لكشف التباس الأسماء المشتركة بدل إخفائه.

    تحلّ أسماء الشهرة القصيرة («الصحاح») والأسماء المقيدة بالمؤلف («غريب الحديث
    لأبي عبيد») وأسماء الشهرة ذات العنوان الببليوغرافي المختلف («دقائق أولي النهى»
    = «شرح منتهى الإرادات للبهوتي»)، ولا تسرقها بادئة عنوان كتاب آخر أقل تطابقًا."""
    q = _tok_stems(re.sub(r"^(?:كتاب|شرح|مختصر|متن)\s+", "", str(text or "").strip()))
    if not q:
        return None
    try:
        cur.execute("SELECT * FROM books")
        rows = cur.fetchall()
    except Exception:
        return None
    scored = []
    for r in rows:
        d = dict(r)
        tt = _tok_stems(d.get("title_ar"))
        if not tt:
            continue
        th = sum(1 for t in q if t in tt)
        if th == 0:
            continue
        au = _tok_stems(d.get("main_author_name_ar"))
        ah = sum(1 for t in q if t in au)
        score = 2 * th + ah
        if all(t in tt for t in q):
            score += 3
        elif all(t in tt or t in au for t in q):
            score += 2
        # العنوان بعينه صدرُ السؤال وبقيّته مؤلف («غريب الحديث» + «لأبي عبيد»):
        # الكتاب الأصل لا شرحه ولا إصلاح غلطه.
        if len(tt) >= 2 and tt == q[:len(tt)]:
            score += 6
        # جزاء رموز السؤال التي لم تجد لها موضعًا في العنوان ولا المؤلف:
        # يمنع إحلال عناوين مصطنعة على كتب حقيقية بمجرد اشتراك كلمتين.
        score -= 2 * max(0, len(q) - th - ah)
        prefix_run = 0
        for a, b in zip(q, tt):
            if a == b:
                prefix_run += 1
            else:
                break
        vols = int(d.get("volume_count_observed") or 0)
        death = int(d.get("main_author_death_hijri") or 0)
        era = 0 if 0 < death <= 1300 else 1
        vols_tier = 1 if vols >= 10 else 0
        key = (score, prefix_run, ah, -era, vols_tier, -(len(tt) - th), vols,
               -len(str(d.get("title_ar") or "")), -(d.get("book_id") or 0))
        scored.append((key, d, score))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    best, best_score = scored[0][1], scored[0][2]
    if best_score < 5:
        return None
    rivals = []
    for _key, d, sc in scored[1:]:
        if sc >= best_score - 2:
            rivals.append({"book_id": d.get("book_id"), "title": d.get("title_ar") or "",
                           "author": d.get("main_author_name_ar") or "",
                           "death_year": d.get("main_author_death_hijri"),
                           "volumes": d.get("volume_count_observed"), "score": sc})
        if len(rivals) >= 5:
            break
    best["_rivals"] = rivals
    best["_score"] = best_score
    return best


def _book_row(book: Any) -> Optional[Dict[str, Any]]:
    conn = _books_conn()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        text = str(book or "").strip()
        row = None
        if re.fullmatch(r"#?\s*\d{1,5}", text):
            cur.execute("SELECT * FROM books WHERE book_id = ? LIMIT 1", (re.sub(r"\D", "", text),))
            row = cur.fetchone()
        if row is None and text:
            cur.execute("SELECT * FROM books WHERE title_ar = ? LIMIT 1", (text,))
            row = cur.fetchone()
        if row is None and text and " " not in text.strip() and len(text.strip()) >= 4:
            # اسم شهرة من كلمة واحدة («المحلى»، «المغني»): الكتاب الذي يبدأ
            # عنوانه به أولى من كتاب يضم في عنوانه لفظًا مشابهًا لمؤلف آخر
            # («المحلى» لابن حزم لا «شرح الورقات للمحلي» الجلال).
            _q = text.strip().replace("%", "").replace("_", "")
            cur.execute("SELECT * FROM books WHERE title_ar LIKE ? || '%' ORDER BY volume_count_observed DESC, LENGTH(title_ar) ASC LIMIT 1", (_q,))
            row = cur.fetchone()
        if row is None and text:
            best = _best_book_row(cur, text)
            if best:
                return best
        if row is None and len(text) >= 8:
            cur.execute("SELECT * FROM books WHERE title_ar LIKE ? || '%' ORDER BY LENGTH(title_ar) ASC LIMIT 1", (text,))
            row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def _parse_betaka(betaka: str) -> Dict[str, str]:
    raw = {}
    for line in (betaka or "").replace("\r", "\n").split("\n"):
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
        elif "：" in line:
            key, val = line.split("：", 1)
        else:
            continue
        key, val = key.strip(), re.sub(r"\s+", " ", val).strip()
        if key and val and key not in raw:
            raw[key] = val
    card = {}
    for label in ("المحقق", "تحقيق", "دراسة وتحقيق", "تحقيق ودراسة", "تحقيق وتعليق", "حققه وعلق عليه"):
        if raw.get(label):
            card["editor"] = raw[label]
            break
    publisher = raw.get("الناشر") or raw.get("دار النشر") or ""
    city = raw.get("بلد النشر") or raw.get("مدينة النشر") or raw.get("مكان النشر") or ""
    if publisher and not city and re.search(r"[،,]", publisher):
        first, rest = re.split(r"\s*[،,]\s*", publisher, maxsplit=1)
        if rest.strip():
            publisher, city = first.strip(), rest.strip()
    if publisher:
        card["publisher"] = publisher
    if city:
        card["city"] = city
    for label in ("الطبعة", "طبعة", "رقم الطبعة"):
        if raw.get(label):
            card["edition"] = raw[label]
            break
    for label in ("عام النشر", "سنة النشر", "سنة الطبع", "تاريخ النشر"):
        if raw.get(label):
            card["year"] = raw[label]
            break
    return card


def resolve_book(book: Any) -> Dict[str, Any]:
    """حلّ كتاب إلى رقمه المعياري ومساره. الرقم هو المفتاح الوحيد لبقية الأدوات.
    عند اشتراك الاسم بين كتب لمؤلفين مختلفين يُكشف الالتباس صراحة مع البدائل،
    بدل حلّ صامت قد يقع على كتاب آخر بالاسم نفسه."""
    row = _book_row(book)
    if not row:
        return _error("BOOK_NOT_FOUND", f"تعذر العثور على الكتاب: {book}")
    rivals = row.pop("_rivals", []) or []
    best_score = row.pop("_score", None)
    out = {
        "status": "ok",
        "book_id": row.get("book_id"),
        "title": row.get("title_ar") or "",
        "author": row.get("main_author_name_ar") or "",
        "death_year": row.get("main_author_death_hijri"),
        "category": row.get("category_name_ar") or "",
        "rel_path": (row.get("rel_path") or "").replace("shamela4_data/", "").strip("/"),
        "volumes": row.get("volume_count_observed"),
    }
    if rivals:
        out["alternatives"] = rivals
        my_author = set(_tok_stems(row.get("main_author_name_ar")))
        ambiguous = any(
            set(_tok_stems(r.get("author"))) and set(_tok_stems(r.get("author"))) != my_author
            and (best_score is None or (r.get("score") or 0) >= best_score - 1)
            for r in rivals)
        out["ambiguous"] = bool(ambiguous)
        if ambiguous:
            out["note"] = ("تنبيه التباس: هذا الاسم مشترك بين كتب لمؤلفين مختلفين، والمختار أعلاه أعلىها "
                           "ترجيحًا آليًا. إن قصدت غيره فثبّت اسم المؤلف في الطلب أو استعمل book_id من البدائل، "
                           "وتثبت من حقل المؤلف قبل النقل عن أي صفحة.")
    return out


def get_book_card(book: Any) -> Dict[str, Any]:
    """بطاقة الكتاب الببليوغرافية من قاعدة الكتب."""
    base = resolve_book(book)
    if base.get("status") != "ok":
        return base
    row = _book_row(book) or {}
    card = _parse_betaka(row.get("betaka_text") or "")
    return {**base, "card": card}


def _read_entry(b_dir: Path, entry: Dict[str, Any]) -> Dict[str, Any]:
    pages_file = b_dir / "pages.jsonl"
    try:
        with open(pages_file, "rb") as f:
            f.seek(entry["offset"])
            data = json.loads(f.readline().decode("utf-8"))
    except Exception:
        return {}
    body = re.sub(r"<[^>]+>", "", data.get("body") or "").strip()
    footnotes = re.sub(r"<[^>]+>", "", data.get("footnotes") or "").strip()
    return {"part": entry["part"], "page_num": entry["page_num"], "seq": entry["seq"], "body": body, "footnotes": footnotes}


def get_page(book: Any, page_num: int, part: Optional[str] = None) -> Dict[str, Any]:
    """قراءة صفحة واحدة بعينها من ملف الكتاب، لا من أي فهرس.

    تنبيه بنيوي: ملف صفحات الشاملة يقطّع الصفحة المطبوعة الواحدة إلى عدة
    قيود (لكل حديث/فقرة قيد، ولعناوين الأبواب قيود) تتشارك رقم الصفحة نفسه؛
    فإرجاع أول قيد وحده صفحة ناقصة قد لا تحوي الشاهد المطلوب. تُدمج هنا
    قيود الصفحة كلها بترتيب page_id (ترتيب القراءة الحقيقي) صفحةً واحدة."""
    b_dir = resolve_book_files(book)
    if not b_dir:
        return _error("BOOK_NOT_FOUND", f"تعذر العثور على ملفات الكتاب: {book}")
    idx = get_book_index(b_dir)
    p_str = str(part).strip() if part and str(part).strip() != "None" else None
    matches = [
        e for e in idx["entries"]
        if (not p_str or e["part"] == p_str)
        and e.get("page_num") is not None and int(e["page_num"]) == int(page_num)
    ]
    if not matches and p_str == "1":
        # الكتب أحادية الجزء تُحفظ بجزء فارغ في ملفاتها، بينما تُكتب إحالتها
        # «ج1» في الحواشي: مطابقة بديلة عند فشل الحرفية فقط (1.10.268).
        matches = [
            e for e in idx["entries"]
            if e["part"] == ""
            and e.get("page_num") is not None and int(e["page_num"]) == int(page_num)
        ]
    if not matches and p_str:
        # الصفحة موجودة في جزء واحد آخر فقط (رسالة داخل مجموع كُتبت إحالتها
        # بجزء غير جزئها): تُفتح منه؛ فلا غموض ما دامت وحيدة الموضع.
        _parts = {
            e["part"] for e in idx["entries"]
            if e.get("page_num") is not None and int(e["page_num"]) == int(page_num)
        }
        if len(_parts) == 1:
            _only = next(iter(_parts))
            matches = [
                e for e in idx["entries"]
                if e["part"] == _only
                and e.get("page_num") is not None and int(e["page_num"]) == int(page_num)
            ]
    if not matches:
        return _error("PAGE_NOT_FOUND", f"الصفحة {page_num} غير موجودة في هذا الكتاب/الجزء.")
    if not p_str:
        first_part = matches[0]["part"]
        matches = [e for e in matches if e["part"] == first_part]
    matches.sort(key=lambda e: (e.get("page_id") if e.get("page_id") is not None else 10**18, e["seq"]))
    pages = [p for p in (_read_entry(b_dir, e) for e in matches) if p]
    if not pages:
        return _error("PAGE_NOT_FOUND", f"الصفحة {page_num} غير موجودة في هذا الكتاب/الجزء.")
    body = "\n".join((p.get("body") or "") for p in pages if (p.get("body") or "").strip())
    footnotes = "\n".join((p.get("footnotes") or "") for p in pages if (p.get("footnotes") or "").strip())
    page = {
        "part": matches[0]["part"], "page_num": matches[0]["page_num"],
        "seq": matches[0]["seq"], "body": body, "footnotes": footnotes,
        "chunks": len(pages),
    }
    return {"status": "ok", "book": resolve_book(book), "page": page}


def get_issue_heading(book: Any, page_num: int, part: Optional[str] = None) -> Dict[str, Any]:
    """الرجوع من صفحة إلى عنوان الباب أو المسألة الحاكم لها في فهرس الكتاب."""
    b_dir = resolve_book_files(book)
    if not b_dir:
        return _error("BOOK_NOT_FOUND", f"تعذر العثور على ملفات الكتاب: {book}")
    idx = get_book_index(b_dir)
    p_str = str(part).strip() if part and str(part).strip() != "None" else None
    target = None
    for entry in idx["entries"]:
        if p_str and entry["part"] != p_str:
            continue
        if entry.get("page_num") is not None and int(entry["page_num"]) == int(page_num):
            target = entry
            break
    if not target:
        return _error("PAGE_NOT_FOUND", f"الصفحة {page_num} غير موجودة في هذا الكتاب/الجزء.")
    toc_file = b_dir / "toc.jsonl"
    heading = None
    if toc_file.exists() and target.get("page_id") is not None:
        try:
            with open(toc_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    pid = item.get("page_id")
                    if pid is not None and int(pid) <= int(target["page_id"]):
                        heading = {"title": item.get("title_text", ""), "page_id": pid}
                    elif pid is not None:
                        break
        except Exception:
            heading = None
    return {
        "status": "ok",
        "book": resolve_book(book),
        "part": target["part"],
        "page_num": target["page_num"],
        "heading": heading,
        "note": "العنوان آخر باب مسجل قبل هذه الصفحة في فهرس الكتاب." if heading else "لا عنوان مسجل قبل هذه الصفحة.",
    }


def search_books_scoped(query: str, book_ids: List[Any], limit_per_book: int = 2, limit: int = 20) -> Dict[str, Any]:
    """بحث لفظي داخل قائمة كتب مغلقة. القائمة إلزامية، ولا مخرج عنها."""
    ids = []
    for raw in book_ids or []:
        text = str(raw).strip().lstrip("#")
        if text and text not in ids:
            ids.append(text)
    if not ids:
        return _error("SCOPE_REQUIRED", "يلزم تمرير book_ids. لا بحث مفتوحاً في المكتبة من هذه الأداة.")
    results = []
    zero = []
    searched = 0
    for book_id in ids:
        found = search_in_book(book=book_id, query=query, limit=max(1, min(int(limit_per_book or 2), 5)))
        if found.get("status") != "ok":
            zero.append(book_id)
            continue
        searched += 1
        hits = found.get("results") or []
        if not hits:
            zero.append(book_id)
        for hit in hits:
            results.append({
                "book_id": book_id,
                "title": found.get("book_title") or "",
                "part": hit.get("part"),
                "page_num": hit.get("page_num"),
                "snippet": hit.get("snippet") or "",
                "quotable": False,
            })
            if len(results) >= max(1, int(limit or 20)):
                break
        if len(results) >= max(1, int(limit or 20)):
            break
    return {
        "status": "ok",
        "query": query,
        "results": results,
        "ledger": {"searched_books": searched, "scope_books": len(ids), "zero_books": zero},
        "note": "مرشحات لفظية غير قابلة للنقل. اقرأ الصفحة ثم طابق قبل أي عزو.",
    }


# =============================================================================
# جدول المراسي التراثية: مقابلة مسألة معاصرة بعبارات من لسان التراث،
# كل عبارة مختبرة حيا ولها شاهد موثق (كتاب/جزء/صفحة). بديل البحث الدلالي
# بلا مخازن متجهات وبلا نماذج تضمين.
# =============================================================================
_ANCHOR_TABLE_CACHE = None

def _anchor_table_data() -> Dict[str, Any]:
    global _ANCHOR_TABLE_CACHE
    if _ANCHOR_TABLE_CACHE is None:
        p = Path(__file__).resolve().parent / "anchor_table.json"
        try:
            _ANCHOR_TABLE_CACHE = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            _ANCHOR_TABLE_CACHE = {"entries": []}
    return _ANCHOR_TABLE_CACHE

def anchor_table_scope_ids() -> List[str]:
    """أرقام كتب النطاق التراثي التي جاءت منها شواهد الجدول (وفاة <= 1000هـ)."""
    ids: List[str] = []
    for e in _anchor_table_data().get("entries", []):
        for a in e.get("anchors", []):
            bid = str(a.get("book_id") or "")
            if bid and bid not in ids:
                ids.append(bid)
    return ids

def anchor_lookup(query: str, limit_entries: int = 5) -> Dict[str, Any]:
    """مطابقة سؤال معاصر بمداخل الجدول. يعيد العبارات التراثية وشواهدها الموثقة."""
    nq = clean_arabic_text(query or "")
    if not nq:
        return {"status": "ok", "matches": [], "scope_book_ids": anchor_table_scope_ids()}
    q_tokens = set(nq.split())
    scored = []
    for e in _anchor_table_data().get("entries", []):
        best, matched_term = 0.0, ""
        for t in [e.get("term", "")] + list(e.get("aliases") or []):
            nt = clean_arabic_text(t or "")
            if not nt:
                continue
            if nt in nq or nq in nt:
                s = 1.0
            else:
                tt = set(nt.split())
                s = (len(tt & q_tokens) / len(tt)) if tt else 0.0
            if s > best:
                best, matched_term = s, t
        if best >= 0.6:
            scored.append((best, matched_term, e))
    scored.sort(key=lambda x: -x[0])
    matches = [{
        "term": e.get("term"), "matched": mt, "match_score": round(sc, 2),
        "category": e.get("cat"),
        "anchors": [{"phrase": a.get("phrase"), "book_id": a.get("book_id"),
                     "title": a.get("title"), "author_death": a.get("author_death"),
                     "part": a.get("part"), "page_num": a.get("page_num"),
                     "level": a.get("level")} for a in e.get("anchors", [])],
    } for sc, mt, e in scored[:limit_entries]]
    return {"status": "ok", "matches": matches, "scope_book_ids": anchor_table_scope_ids()}

def anchor_search(query: str, limit: int = 12, book_ids: Optional[List[Any]] = None) -> Dict[str, Any]:
    """الطبقات كاملة: مطابقة الجدول ثم بحث لفظي بالعبارات في النطاق ثم جلب نصوص الصفحات.
    عند تمرير book_ids يكون النطاق مغلقا عليها ولا يخرج البحث عنها."""
    look = anchor_lookup(query)
    matches = look.get("matches") or []
    if not matches:
        return {"status": "ok", "matches": [], "results": []}
    closed = [str(b).strip().lstrip("#") for b in book_ids if str(b).strip()] if book_ids else None
    results: List[Dict[str, Any]] = []
    seen = set()
    for m in matches[:3]:
        for a in m.get("anchors", []):
            if closed is not None:
                ids = closed
            else:
                ids = [str(a.get("book_id"))] + [b for b in look["scope_book_ids"] if b != str(a.get("book_id"))]
            found = search_books_scoped(query=a.get("phrase") or "", book_ids=ids, limit_per_book=2, limit=6)
            for h in found.get("results") or []:
                key = (str(h.get("book_id")), str(h.get("part") or ""), str(h.get("page_num") or ""))
                if key in seen:
                    continue
                seen.add(key)
                body = ""
                try:
                    pg = get_page(book=h["book_id"], page_num=int(h["page_num"]), part=h.get("part"))
                    body = ((pg.get("page") or {}).get("body") or "") if pg.get("status") == "ok" else ""
                except Exception:
                    body = ""
                results.append({
                    "book_id": str(h.get("book_id")), "title": h.get("title") or "",
                    "part": h.get("part"), "page_num": h.get("page_num"),
                    "phrase": a.get("phrase"), "term": m.get("term"),
                    "witness": (str(h.get("book_id")) == str(a.get("book_id"))
                                and str(h.get("part")) == str(a.get("part"))
                                and str(h.get("page_num")) == str(a.get("page_num"))),
                    "text": body,
                    "snippet": re.sub(r"\s+", " ", body)[:750].strip(),
                })
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break
    return {"status": "ok", "matches": matches, "results": results}

_HADITH_CORE_WORDS = ("صحيح", "سنن", "مسند", "موطأ", "مصنف", "جامع", "معجم")
_HADITH_TAKHRIJ_WORDS = ("تخريج", "علل", "تلخيص", "نصب الراية", "إرواء", "السلسلة", "فتح الباري", "شرح", "عون المعبود", "تحفة الأحوذي")


def trace_hadith(text: str, limit_books: int = 14) -> Dict[str, Any]:
    """تتبع لفظ حديث في كتب الحديث من قاعدة الكتب، بلا نقل من كتب الفقه.

    تصنيف «أصول/شروح وتخريج» هنا آلي من عنوان الكتاب وتصنيفه، وهو ترشيح
    يقرؤه الباحث، ولا يغني عن قراءة الصفحة والمطابقة.
    """
    phrase = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(phrase) < 8:
        return _error("QUERY_TOO_SHORT", "أدخل ألفاظاً مميزة من متن الحديث.")
    conn = _books_conn()
    if not conn:
        return _error("CATALOG_UNAVAILABLE", "قاعدة الكتب غير متاحة.")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT book_id, title_ar, category_name_ar FROM books "
            "WHERE (category_name_ar LIKE '%حديث%' OR category_name_ar LIKE '%سنة%' OR category_name_ar LIKE '%تخريج%') "
            "ORDER BY book_id ASC LIMIT 400"
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    core, commentary, searched = [], [], 0
    cap = max(4, min(int(limit_books or 14), 24))
    for row in rows:
        if len(core) + len(commentary) >= cap * 3:
            break
        title = row.get("title_ar") or ""
        found = search_in_book(book=row["book_id"], query=phrase, limit=1)
        if found.get("status") != "ok":
            continue
        searched += 1
        hits = found.get("results") or []
        if not hits:
            continue
        item = {"book_id": row["book_id"], "title": title, "part": hits[0].get("part"), "page_num": hits[0].get("page_num"), "snippet": hits[0].get("snippet") or ""}
        if any(w in title for w in _HADITH_TAKHRIJ_WORDS):
            commentary.append(item)
        elif any(w in title for w in _HADITH_CORE_WORDS):
            core.append(item)
        else:
            commentary.append(item)
    return {
        "status": "ok",
        "query": phrase,
        "usul": core,
        "shuruh_takhrij": commentary,
        "ledger": {"searched_books": searched, "candidate_books": len(rows)},
        "note": "ترشيح آلي من العناوين والتصنيف. لفظ الحديث وحكمه لا يثبتان إلا بقراءة الصفحة والمطابقة، والحكم من كتب التخريج.",
    }


def execute_mcp_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """الموجّه التنفيذي الموحد: نتائج الملفات تُحفَظ حزمًا عند الخادم (pack_id)
    فتبقى الحالة الوسيطة هنا ويجلب الوكيل شرائحها بـget_pack_slice."""
    result = _execute_mcp_tool_impl(name, args or {})
    if name in ("ayah_dossier", "word_dossier", "fiqh_dossier", "hadith_dossier") \
            and isinstance(result, dict) and result.get("status") == "ok":
        _store_pack(result)
    return result


def _execute_mcp_tool_impl(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """الموجّه التنفيذي الموحد لاستدعاء أدوات الـ MCP"""
    if name == "get_page_range":
        return get_page_range(
            book=args.get("book"),
            start_page=int(args.get("start_page", 1)),
            end_page=int(args.get("end_page", 5)),
            part=args.get("part")
        )
    elif name == "get_surrounding_context":
        return get_surrounding_context(
            book=args.get("book"),
            page_num=int(args.get("page_num", 1)),
            part=args.get("part"),
            before_pages=int(args.get("before_pages", 2)),
            after_pages=int(args.get("after_pages", 2))
        )
    elif name == "get_book_toc":
        return get_book_toc(book=args.get("book"))
    elif name == "verify_quote":
        return verify_quote(
            book=args.get("book"),
            quote_text=args.get("quote_text", ""),
            page_hint=args.get("page_hint")
        )
    elif name == "search_in_book":
        return search_in_book(
            book=args.get("book"),
            query=args.get("query", ""),
            limit=int(args.get("limit", 10))
        )
    elif name == "resolve_book":
        return resolve_book(args.get("book"))
    elif name == "get_book_card":
        return get_book_card(args.get("book"))
    elif name == "get_page":
        return get_page(book=args.get("book"), page_num=int(args.get("page_num", 1)), part=args.get("part"))
    elif name == "get_issue_heading":
        return get_issue_heading(book=args.get("book"), page_num=int(args.get("page_num", 1)), part=args.get("part"))
    elif name == "search_books_scoped":
        return search_books_scoped(
            query=args.get("query", ""),
            book_ids=args.get("book_ids") or [],
            limit_per_book=int(args.get("limit_per_book", 2)),
            limit=int(args.get("limit", 20)),
        )
    elif name == "anchor_lookup":
        return anchor_lookup(query=args.get("query", ""), limit_entries=int(args.get("limit_entries", 5)))
    elif name == "anchor_search":
        return anchor_search(
            query=args.get("query", ""),
            limit=int(args.get("limit", 12)),
            book_ids=args.get("book_ids"),
        )
    elif name == "trace_hadith":
        return trace_hadith(text=args.get("text", ""), limit_books=int(args.get("limit_books", 14)))
    elif name == "ayah_dossier":
        return ayah_dossier(surah=int(args.get("surah") or 0), ayah=int(args.get("ayah") or 0),
                            per_era=int(args.get("per_era") or 5),
                            per_source_chars=int(args.get("per_source_chars") or 2400),
                            brief=bool(args.get("brief")))
    elif name == "word_dossier":
        return word_dossier(word=args.get("word", ""), limit=int(args.get("limit") or 12),
                            brief=bool(args.get("brief")))
    elif name == "fiqh_dossier":
        return fiqh_dossier(topic=args.get("topic", ""), per_cell=int(args.get("per_cell") or 2),
                            death_max=args.get("death_max"), brief=bool(args.get("brief")))
    elif name == "hadith_dossier":
        return hadith_dossier(text=args.get("text", ""), limit=int(args.get("limit") or 8),
                              brief=bool(args.get("brief")))
    elif name == "get_pack_slice":
        return get_pack_slice(pack_id=args.get("pack_id", ""), field=args.get("field"),
                              offset=int(args.get("offset") or 0), limit=int(args.get("limit") or 5))
    elif name == "verify_batch":
        return verify_batch(citations=args.get("citations") or [])
    elif name == "get_book_coverage":
        return get_book_coverage(book=args.get("book", ""))
    elif name in ("search_library", "search_headings", "search_batch", "survey_topic", "dossier_topic",
                  "ayah_loci", "attestations", "hadith_loci", "qawaid_search", "creed_search", "tarikh_search",
                  "lugha_search", "creed_issue", "fiqh_topics", "fiqh_topic_locations", "madhhab_authorities", "authority_books"):
        try:
            import library_search
            return library_search.execute_library_tool(name, args or {})
        except Exception as exc:
            return {"status": "error", "message": f"تعذر البحث المفهرس: {exc}"}
    else:
        return {"error": f"أداة غير معروفة: {name}"}

if __name__ == "__main__":
    # اختبار سريع ومباشر للأدوات
    print("--- اختبار أداة تقليب الصفحات get_page_range في المغني ---")
    res1 = get_page_range(book="2437", start_page=15, end_page=16, part="1")
    print("Book:", res1.get("book_title"), "| Author:", res1.get("author"))
    print("Pages retrieved:", len(res1.get("pages", [])))
    if res1.get("pages"):
        print("Page 1 snippet:", res1["pages"][0]["body"][:120])

    print("\n--- اختبار أداة جلب فهرس الأبواب get_book_toc ---")
    res2 = get_book_toc(book="2437")
    print("Total headings:", res2.get("total_headings"))
    if res2.get("toc"):
        print("Sample heading:", res2["toc"][0])
