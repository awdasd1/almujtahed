"""النسخة المصوّرة من الشاملة: ربط صفحة النص بصفحة الـ PDF الممسوح.

المصدر: تطبيق الشاملة نفسه — كتالوجه master.db فيه لكل كتاب pdf_links
(قائمة ملفات المصوّرة ووسم الجزء لكل ملف)، والملفات منزّلة عنده تحت
pdf/<المؤلف>/<الكتاب>/. القاعدة المثبتة بالفحص على كتب مفردة ومتعددة
الأجزاء: رقم صفحة المصوّرة داخل ملف جزئها يساوي رقم الصفحة المطبوعة
(page_num) نفسه. التغطية جزئية (~خُمس المكتبة)، فغياب الملف جواب مشروع.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import shamela_link

_INTRO_TAGS = {"المقدمة", "المقدمه", "تقديم", "مقدمة", "التمهيد"}
_FILE_INDEX = {"root": None, "by_name": {}}


def _pdf_root():
    root = shamela_link.find_shamela_root()
    if not root:
        return None
    pdf = root / "pdf"
    return pdf if pdf.is_dir() else None


def _file_index(root: Path) -> dict:
    """{اسم الملف: [مساراته]} — يُبنى مرة ويُعاد بناؤه إن تغيّر الجذر."""
    if _FILE_INDEX["root"] == str(root) and _FILE_INDEX["by_name"]:
        return _FILE_INDEX["by_name"]
    by_name = {}
    for path in root.rglob("*.pdf"):
        by_name.setdefault(path.name, []).append(path)
    _FILE_INDEX.update({"root": str(root), "by_name": by_name})
    return by_name


def _their_id(book_id, rel_path: str = ""):
    """رقم الكتاب عند الشاملة: من عمود shamela_id في كتالوجنا أو خريطة الهوية."""
    cat = shamela_link._catalog_path()
    if cat.exists():
        try:
            con = sqlite3.connect(f"file:{cat}?mode=ro", uri=True)
            row = None
            if book_id:
                row = con.execute("SELECT shamela_id FROM books WHERE book_id=?", (int(book_id),)).fetchone()
            if not row and rel_path:
                row = con.execute("SELECT shamela_id FROM books WHERE rel_path=?", (str(rel_path),)).fetchone()
            con.close()
            if row and row[0]:
                return int(row[0])
        except Exception:
            pass
    if book_id:
        mapped = shamela_link.load_id_map().get(str(book_id))
        if mapped:
            return int(mapped)
    return None


def _master_row(their_id: int):
    db_dir = shamela_link.data_database_dir()
    if not db_dir:
        return None
    master = db_dir / "master.db"
    if not master.exists():
        return None
    con = sqlite3.connect(f"file:{master}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT book_name, pdf_links, pdf_ondisk FROM book WHERE book_id=?", (their_id,)
    ).fetchone()
    con.close()
    return dict(row) if row else None


def _their_book_db(their_id: int):
    db_dir = shamela_link.data_database_dir()
    if not db_dir:
        return None
    cand = db_dir / "book" / f"{their_id % 1000:03d}" / f"{their_id}.db"
    if cand.exists():
        return cand
    found = list((db_dir / "book").rglob(f"{their_id}.db"))
    return found[0] if found else None


def _their_parts(their_id: int) -> list:
    """أجزاء الكتاب عندهم بترتيب ظهورها في صفحاتهم."""
    cand = _their_book_db(their_id)
    if not cand:
        return []
    try:
        con = sqlite3.connect(f"file:{cand}?mode=ro", uri=True)
        rows = con.execute("SELECT part FROM page GROUP BY part ORDER BY MIN(id)").fetchall()
        con.close()
        return [str(r[0] or "") for r in rows]
    except Exception:
        return []


def _part_ranges(their_id: int) -> list:
    """[(الجزء، عدد صفحاته، أول صفحة مطبوعة، آخرها)] بترتيب الكتاب."""
    cand = _their_book_db(their_id)
    if not cand:
        return []
    try:
        con = sqlite3.connect(f"file:{cand}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT part, COUNT(*), MIN(page), MAX(page) FROM page GROUP BY part ORDER BY MIN(id)"
        ).fetchall()
        con.close()
        return [(str(r[0] or ""), int(r[1]), int(r[2] or 0), int(r[3] or 0)) for r in rows]
    except Exception:
        return []


def _seq_within(their_id: int, ranges: list, part: str, page_num: int, covered: list):
    """موضع الصفحة تسلسليًا داخل ملف يضم أجزاء عدة (حين لا يكفي الرقم المطبوع)."""
    cand = _their_book_db(their_id)
    if not cand:
        return None
    try:
        con = sqlite3.connect(f"file:{cand}?mode=ro", uri=True)
        offset = 0
        for name, count, _mn, _mx in ranges:
            if name not in covered:
                continue
            if name == part:
                rank = con.execute(
                    "SELECT COUNT(*) FROM page WHERE part=? AND page<=?", (part, page_num)
                ).fetchone()[0]
                con.close()
                return offset + max(1, int(rank))
            offset += count
        con.close()
    except Exception:
        return None
    return None


def _is_intro(part: str) -> bool:
    return any(w in (part or "") for w in ("مقدمة", "مقدمه", "تقديم"))


def _parse_entries(pdf_links: str) -> list:
    try:
        data = json.loads(pdf_links or "{}")
    except Exception:
        return []
    entries = []
    for raw in data.get("files") or []:
        seg = str(raw).split("|")
        name = Path(seg[0].strip()).name
        tag = seg[1].strip() if len(seg) > 1 else ""
        if name:
            entries.append({"name": name, "tag": tag})
    return entries


def _assign_files(entries: list, parts: list) -> dict:
    """{الجزء: اسم ملف المصوّرة} بأعراف الشاملة نفسها:
    وسم صريح، ثم لاحقة p للمقدمة وi للفهارس، ثم الرقم أول الاسم هو رقم
    الجزء المرقّم (و00 غلاف لا جزء)، ثم الباقي بترتيب القائمة."""
    intro_parts = [p for p in parts if _is_intro(p)]
    numbered = [p for p in parts if p not in intro_parts]
    assigned = {}
    deferred = []
    front = None
    for entry in entries:
        name, tag = entry["name"], entry["tag"]
        stem = name[:-4] if name.lower().endswith(".pdf") else name
        if tag and not tag.startswith("#"):
            if tag in parts:
                assigned.setdefault(tag, name)
                continue
            if _is_intro(tag) or tag.startswith("مقدمة"):
                if intro_parts:
                    assigned.setdefault(intro_parts[0], name)
                continue
            if tag == "0":
                for part in numbered:
                    assigned.setdefault(part, name)
                continue
            if tag.isdigit() and 1 <= int(tag) <= len(numbered):
                assigned.setdefault(numbered[int(tag) - 1], name)
                continue
        if re.search(r"\d(ps|p)$", stem) and intro_parts:
            assigned.setdefault(intro_parts[0], name)
            continue
        if re.search(r"^\d+i$", stem):
            continue  # ملف فهارس لا متن
        m = re.match(r"^(\d+)", name)
        if m:
            num = int(m.group(1))
            if num == 0:
                front = front or name
                continue
            if num <= len(numbered):
                assigned.setdefault(numbered[num - 1], name)
                continue
        deferred.append(name)
    rest = [p for p in numbered if p not in assigned]
    for name, part in zip(deferred, rest):
        assigned[part] = name
    if intro_parts and intro_parts[0] not in assigned and front:
        assigned[intro_parts[0]] = front
    distinct = set(assigned.values()) | set(deferred)
    if len(distinct) == 1 and parts:
        only = next(iter(distinct))
        for part in parts:
            assigned.setdefault(part, only)
    return assigned


def _pdf_pages(path: Path) -> int:
    try:
        import fitz
        doc = fitz.open(str(path))
        count = doc.page_count
        doc.close()
        return count
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


def resolve_pdf(book_id=None, rel_path: str = "", part=None, page_num=None) -> dict:
    """حلّ صفحة النص إلى ملف مصوّرة ورقم صفحة فيها. available=False سبب مشروع."""
    out = {"available": False}
    their_id = _their_id(book_id, rel_path)
    if not their_id:
        out["reason"] = "لا مقابل لهذا الكتاب عند الشاملة"
        return out
    out["their_id"] = their_id
    row = _master_row(their_id)
    if not row or not row.get("pdf_links"):
        out["reason"] = "لا توجد نسخة مصوّرة لهذا الكتاب في الشاملة يمكنك إضافتها عن طريق الشاملة إن كانت متوفرة هنا أو رفع نسخة من جهاز أو سحبها من الشبكة"
        return out
    entries = _parse_entries(row["pdf_links"])
    if not entries:
        out["reason"] = "لا توجد نسخة مصوّرة لهذا الكتاب في الشاملة يمكنك إضافتها عن طريق الشاملة إن كانت متوفرة هنا أو رفع نسخة من جهاز أو سحبها من الشبكة"
        return out
    root = _pdf_root()
    if not root:
        out["reason"] = "مجلد مصوّرات الشاملة غير موجود على هذا الجهاز"
        return out
    index = _file_index(root)
    ranges = _part_ranges(their_id)
    parts = [r[0] for r in ranges]
    want_part = str(part or "").strip()
    if want_part == "None":
        want_part = ""
    if parts and want_part not in parts:
        # جزءنا برقمه قد يقابل جزءهم بموضعه بين الأجزاء المرقّمة
        numbered = [p for p in parts if not _is_intro(p)]
        if want_part.isdigit() and 1 <= int(want_part) <= len(numbered):
            want_part = numbered[int(want_part) - 1]
        elif numbered:
            want_part = numbered[0]
    assigned = _assign_files(entries, parts or [want_part])
    file_name = assigned.get(want_part)
    if not file_name and entries:
        file_name = entries[0]["name"]
    if not file_name:
        out["reason"] = "لا ملف مصوّرة لهذا الجزء"
        return out
    candidates = index.get(file_name) or []
    if not candidates:
        out["reason"] = "النسخة المصوّرة غير منزّلة على هذا الجهاز"
        return out
    book_name = str(row.get("book_name") or "")
    path = next((p for p in candidates if p.parent.name == book_name), candidates[0])
    total = _pdf_pages(path)
    try:
        page = int(page_num or 0)
    except (TypeError, ValueError):
        page = 0
    if page <= 0:
        page = 1
    clamped = False
    covered = [p for p, f in assigned.items() if f == file_name]
    if total and len(covered) > 1:
        # ملف واحد لأجزاء عدة: إن كانت مطبوعاتها متصلة فالرقم المطبوع يكفي،
        # وإن استأنف كل جزء ترقيمه فالموضع التسلسلي داخل الملف هو الصواب
        covered_ranges = [r for r in ranges if r[0] in covered]
        restarts = any(
            covered_ranges[i][2] <= covered_ranges[i - 1][3]
            for i in range(1, len(covered_ranges))
        )
        if restarts:
            seq = _seq_within(their_id, ranges, want_part, page, covered)
            if seq:
                page = seq
    if total and page > total:
        seq = _seq_within(their_id, ranges, want_part, page, covered)
        if seq and 1 <= seq <= total:
            page = seq
        else:
            page = total
            clamped = True
    out.update({
        "available": True,
        "file_name": file_name,
        "pdf_path": str(path),
        "pdf_page": page,
        "pdf_pages": total,
        "book_name": book_name,
        "clamped": clamped,
    })
    return out


def _ocr_helper():
    env = os.getenv("ALMOGHNI_OCR_HELPER", "").strip()
    cands = [
        Path(env) if env else None,
        _HERE / "tools" / "ocr_locate",
        _HERE / "ocr_locate",
    ]
    for cand in cands:
        if cand and cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return shutil.which("ocr_locate") or ""


_LOCATE_CACHE = {}


def _witness_target(phrase: str) -> str:
    """نص الشاهد بحرفه: بين علامتي تنصيص، أو متن الحديث بعد قال رسول الله.
    ما كان معنويًا بقي كما هو فيفشل التحقق الحرفي ولا يُحدَّد له موضع."""
    raw = re.sub(r"\s+", " ", str(phrase or "")).strip()
    if not raw:
        return ""
    m = re.search(r"«([^»]{8,})»", raw) or re.search(r"“([^”]{8,})”", raw) or re.search(r'"([^"]{8,})"', raw)
    if m:
        return m.group(1).strip()
    m = re.search(r"(قال رسول الله|قال النبي|أن رسول الله|ان رسول الله|عن رسول الله|عن النبي)", raw)
    if m:
        rest = raw[m.end():]
        rest = re.sub(r"^[\s:ﷺ]*(صلى الله عليه (وآله )?وسلم)?[\s:ﷺ]*", "", rest)
        rest = re.sub(r"\s*\(?(رواه|أخرجه|متفق عليه).*$", "", rest)
        if len(rest.strip()) >= 8:
            return rest.strip()
    return (re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip() or raw)


def locate_witness(book_id=None, rel_path: str = "", part=None, page_num=None,
                   pdf_page=None, phrase: str = "") -> dict:
    """موضع الشاهد على صفحة المصوّرة بتعرف بصري (Vision عند آبل) إن توفر."""
    out = {"found": False}
    helper = _ocr_helper()
    if not helper:
        out["reason"] = "أداة التعرف البصري غير متوفرة على هذا الجهاز"
        return out
    # صياغة سؤال ليست شاهدًا وإن وافقت ألفاظها عنوان الباب أو متن الصفحة،
    # ما لم تحمل نقلًا منطوقًا بين علامتي تنصيص فهو الشاهد حينئذ
    _raw = re.sub(r"\s+", " ", str(phrase or "")).strip()
    if not re.search(r"«[^»]{8,}»", _raw) and (
            re.match(r"^(ما|ماذا|هل|متى|أين|اين|كيف|لماذا|من|ما حكم|ما معنى|ما المراد)\b", _raw)
            or _raw.rstrip().endswith(("؟", "?"))):
        out["reason"] = "صياغة سؤال لا شاهد منطوقًا فلا تحديد له"
        return out
    target = _witness_target(phrase)
    words = [w for w in re.split(r"\s+", target) if len(w) >= 3]
    if not words:
        out["reason"] = "لا شاهد محددًا للبحث عنه"
        return out
    needles = list(dict.fromkeys(words[:4] + sorted(words, key=len, reverse=True)[:4]))[:8]
    info = resolve_pdf(book_id, rel_path, part, page_num)
    if not info.get("available"):
        out["reason"] = info.get("reason") or "لا نسخة مصوّرة"
        return out
    page = int(pdf_page or info["pdf_page"])
    cache_key = (info["pdf_path"], page, tuple(needles))
    if cache_key in _LOCATE_CACHE:
        return dict(_LOCATE_CACHE[cache_key])
    try:
        import fitz
        doc = fitz.open(info["pdf_path"])
        pix = doc[max(0, min(doc.page_count - 1, page - 1))].get_pixmap(dpi=150)
        doc.close()
    except Exception as exc:
        out["reason"] = f"تعذر تصيير الصفحة: {exc}"
        return out
    fd, name = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        Path(name).write_bytes(pix.tobytes("png"))
        proc = subprocess.run(
            [helper, name, *needles], capture_output=True, text=True, timeout=240)
        data = json.loads(proc.stdout or "{}")
    except Exception as exc:
        out["reason"] = f"تعذر التعرف البصري: {exc}"
        return out
    finally:
        try:
            os.remove(name)
        except OSError:
            pass
    lines = data.get("lines") or []
    if not lines:
        out["reason"] = "لم يُعثر على الشاهد في هذه الصفحة"
        _LOCATE_CACHE[cache_key] = out
        return out

    # مطابقة على مستوى الكلمات بصناديق كل كلمة: أطول تتابع حرفي من الشاهد
    # داخل كلمات الصفحة، فيقع الصندوق على الشاهد نفسه أينما كان من الصفحة.
    # الشاهد المعنوي لا تتابع حرفيًا له فلا يُرسم له صندوق
    match = _match_witness_words(target, lines)
    if not match:
        out["reason"] = "الشاهد غير منطوق بحرفه في هذه الصفحة فلا موضع له"
        _LOCATE_CACHE[cache_key] = out
        return out
    pad = 0.004
    out.update({
        "found": True,
        "rect": {
            "x": max(0.0, match["x"] - pad), "y": max(0.0, match["y"] - pad),
            "w": min(1.0, match["w"] + 2 * pad), "h": min(1.0, match["h"] + 2 * pad),
        },
        "text": match["text"],
        "target": target,
        "pdf_page": page,
    })
    _LOCATE_CACHE[cache_key] = out
    return dict(out)


_PUNCT = "،؛:.«»\"'“”‘’()[]{}<>؟?!|/\\-–—*_=+~^#@%&$؛.,;:!?\"'«»()[]"
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _norm_word(word: str) -> str:
    """توحيد كلمة للمطابقة: بلا تشكيل ولا ترقيم وبأحرف مطوية وأرقام لاتينية.

    الترقيم يُحذف من أي موضع لا من الطرفين فقط، وأرقام الحواشي الملتصقة
    بآخر الكلمة («الحجر»(٢) تُحذف، وإلا انكسرت مطابقة كل شاهد مختوم بحاشية."""
    text = re.sub(r"[ً-ٰٓـ]", "", str(word or ""))
    text = (text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
            .replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و").replace("ة", "ه"))
    text = text.translate(_DIGITS)
    text = "".join(ch for ch in text if ch not in _PUNCT)
    return re.sub(r"^\d+|\d+$", "", text).strip()


def _match_witness_words(target: str, lines: list):
    """أطول تتابع كلمات منطوق بحرفه من الشاهد داخل الصفحة، بصندوق كلماته.

    يعيد None إن لم يوجد تتابع معتبر (شاهد معنوي) فلا تحديد له."""
    from difflib import SequenceMatcher

    twords = [w for w in (_norm_word(w) for w in re.split(r"\s+", target or "")) if w]
    if not twords:
        return None
    # تيار كلمات الصفحة: (كلمة موحّدة، صندوقها، رقم سطرها، نصها الأصلي)
    stream = []
    for li, line in enumerate(lines):
        words = line.get("words") or []
        if words:
            for wd in words:
                nw = _norm_word(wd.get("t") or "")
                if nw:
                    stream.append((nw, wd, li, str(wd.get("t") or "")))
        else:  # أداة قديمة بلا كلمات: السطر كله وحدة
            for tok in re.split(r"\s+", str(line.get("text") or "")):
                nw = _norm_word(tok)
                if nw:
                    stream.append((nw, line, li, tok))
    if not stream:
        return None
    pwords = [s[0] for s in stream]

    def _box_of(p_start: int, p_end: int):
        picked = stream[p_start:p_end]
        if not picked:
            return None
        x0 = min(float(wd["x"]) for _, wd, _, _ in picked)
        y0 = min(float(wd["y"]) for _, wd, _, _ in picked)
        x1 = max(float(wd["x"]) + float(wd["w"]) for _, wd, _, _ in picked)
        y1 = max(float(wd["y"]) + float(wd["h"]) for _, wd, _, _ in picked)
        line_ids = sorted({li for _, _, li, _ in picked})
        return {
            "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
            "text": "\n".join(str(lines[i].get("text") or "") for i in line_ids if 0 <= i < len(lines)),
        }

    matcher = SequenceMatcher(None, twords, pwords, autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size > 0]
    if blocks:
        main = max(blocks, key=lambda b: b.size)
        # شاهد قصير جدًا: لا يقبل إلا منطوقًا كله
        exact_ok = (main.size >= len(twords)) if len(twords) <= 3 else (main.size >= 4)
        if exact_ok:
            # مدّ الموضع بكتل مجاورة تفصلها أخطاء تعرف يسيرة ليكتمل الشاهد
            chosen = []
            for b in blocks:
                if (abs(b.a - main.a) <= main.size + 6 and abs(b.b - main.b) <= main.size + 10
                        and not (b.size == 1 and len(twords[b.a]) < 4)):
                    chosen.append(b)
            return _box_of(min(b.b for b in chosen), max(b.b + b.size for b in chosen))
    # طبقة متسامحة: طبعات كثيفة قديمة يشوّش تعرفها (كلمات مدمجة أو مبتورة
    # أو بحرف ناقص) فلا تتابع حرفيًا كاملًا؛ محاذاة تقريبية بترتيب الشاهد
    # نفسه وكثافة مطابقة عالية، فلا يمرّ بها شاهد معنوي مبثوث الألفاظ
    fuzzy = _fuzzy_word_match(twords, pwords)
    if fuzzy is None:
        return None
    box = _box_of(fuzzy[0], fuzzy[1] + 1)
    # حارس ضد مصادفات العناوين: مطابقة متسامحة في شريط رأس الصفحة تُرفض،
    # فالسؤال المعنوي قد يوافق ألفاظ عنوان الباب فيُتوهم شاهدًا في الأعلى
    if box and box["y"] < 0.10:
        return None
    return box


def _lev_le1(a: str, b: str) -> bool:
    """مسافة تحرير ≤ 1 بين كلمتين (حرف ناقص أو زائد أو مبدّل)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = j = diff = 0
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        else:
            diff += 1
            j += 1
            if diff > 1:
                return False
    return True


def _word_sim(a: str, b: str) -> bool:
    """تشابه كلمة شاهد وكلمة مقروءة رغم تشويش التعرف البصري."""
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 2 and (long_.startswith(short) or long_.endswith(short)):
        return True  # كلمة مدمجة بأختها أو مبتورة أحد الطرفين («دبن» فيها «بن»)
    return len(a) >= 4 and len(b) >= 4 and _lev_le1(a, b)


def _fuzzy_word_match(twords: list, pwords: list):
    """محاذاة الشاهد بترتيبه داخل كلمات الصفحة (برمجة ديناميكية محلية).

    يعيد (أول كلمة، آخر كلمة) في تيار الصفحة أو None. لا يُقبل إلا ما
    طابق أكثر كلمات الشاهد بترتيبها وبكلمات تامة عدة، فالشاهد المعنوي
    المبعثر الألفاظ لا يجتمع له ذلك وإن تشابهت مفرداته."""
    n, m = len(twords), len(pwords)
    if n == 0 or m == 0:
        return None
    # H[i][j]: أفضل درجة لمحاذاة تنتهي عند كلمة الشاهد i وكلمة الصفحة j
    H = [[0.0] * (m + 1) for _ in range(n + 1)]
    best_val, best_i, best_j = 0.0, 0, 0
    for i in range(1, n + 1):
        tw = twords[i - 1]
        row, prow = H[i], H[i - 1]
        for j in range(1, m + 1):
            pw = pwords[j - 1]
            diag = prow[j - 1] + (3.0 if pw == tw else (2.0 if _word_sim(tw, pw) else -3.0))
            val = max(0.0, diag, prow[j] - 1.0, row[j - 1] - 1.0)
            row[j] = val
            if val > best_val:
                best_val, best_i, best_j = val, i, j
    if best_i == 0:
        return None
    # تتبع خلفي لعدّ المطابقات وحدّي الموضع في التيار
    i, j = best_i, best_j
    matched = exact = 0
    first = last = None
    while i > 0 and j > 0 and H[i][j] > 0:
        tw, pw = twords[i - 1], pwords[j - 1]
        step = 3.0 if pw == tw else (2.0 if _word_sim(tw, pw) else -3.0)
        if abs(H[i][j] - (H[i - 1][j - 1] + step)) < 1e-9 and step > 0:
            matched += 1
            exact += 1 if pw == tw else 0
            if last is None:
                last = j - 1
            first = j - 1
            i -= 1
            j -= 1
        elif abs(H[i][j] - (H[i - 1][j] - 1.0)) < 1e-9:
            i -= 1
        else:
            j -= 1
    need = max(4, -(-50 * n // 100))
    if matched < need or exact < 3 or first is None:
        return None
    return first, last


def ocr_region_text(book_id=None, rel_path: str = "", part=None, page_num=None,
                    pdf_page=None, rect: dict = None) -> dict:
    """نص أي جزء مقصوص من صفحة المصوّرة بالتعرف البصري، لنقله إلى المحادثة."""
    out = {"text": ""}
    helper = _ocr_helper()
    if not helper:
        out["reason"] = "أداة التعرف البصري غير متوفرة على هذا الجهاز"
        return out
    rect = rect or {}
    try:
        rx, ry = float(rect.get("x") or 0), float(rect.get("y") or 0)
        rw, rh = float(rect.get("w") or 0), float(rect.get("h") or 0)
    except (TypeError, ValueError):
        out["reason"] = "قصاصة غير صالحة"
        return out
    if rw < 0.01 or rh < 0.005:
        out["reason"] = "حدّد قصاصة أولاً"
        return out
    info = resolve_pdf(book_id, rel_path, part, page_num)
    if not info.get("available"):
        out["reason"] = info.get("reason") or "لا نسخة مصوّرة"
        return out
    page = int(pdf_page or info["pdf_page"])
    try:
        import fitz
        doc = fitz.open(info["pdf_path"])
        pg = doc[max(0, min(doc.page_count - 1, page - 1))]
        clip = fitz.Rect(rx * pg.rect.width, ry * pg.rect.height,
                         (rx + rw) * pg.rect.width, (ry + rh) * pg.rect.height)
        pix = pg.get_pixmap(dpi=200, clip=clip)
        doc.close()
    except Exception as exc:
        out["reason"] = f"تعذر تصيير القصاصة: {exc}"
        return out
    fd, name = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        Path(name).write_bytes(pix.tobytes("png"))
        proc = subprocess.run(
            [helper, name, "نص"], capture_output=True, text=True, timeout=240)
        data = json.loads(proc.stdout or "{}")
    except Exception as exc:
        out["reason"] = f"تعذر التعرف البصري: {exc}"
        return out
    finally:
        try:
            os.remove(name)
        except OSError:
            pass
    lines = data.get("lines") or []
    text = "\n".join(str(l.get("text") or "").strip() for l in lines if str(l.get("text") or "").strip())
    if not text:
        out["reason"] = "لم يُقرأ نص في هذه القصاصة"
        return out
    out["text"] = text
    out["pdf_page"] = page
    return out


def render_pdf_page(book_id=None, rel_path: str = "", part=None, page_num=None, pdf_page=None) -> bytes:
    """تصيير صفحة المصوّرة المطلوبة صورة PNG."""
    info = resolve_pdf(book_id, rel_path, part, page_num)
    if not info.get("available"):
        raise RuntimeError(info.get("reason") or "لا نسخة مصوّرة")
    try:
        import fitz
    except ImportError:
        raise RuntimeError("محرك تصيير المصوّرات (PyMuPDF) غير مثبّت")
    doc = fitz.open(info["pdf_path"])
    try:
        page = int(pdf_page or info["pdf_page"])
        page = max(1, min(doc.page_count, page))
        pix = doc[page - 1].get_pixmap(dpi=130)
        return pix.tobytes("png")
    finally:
        doc.close()
