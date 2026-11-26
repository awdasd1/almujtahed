"""النسخة المصوّرة من الشاملة: ربط صفحة النص بصفحة الـ PDF الممسوح.

الطريقة هي طريقة تطبيق الشاملة نفسه حرفيًا (فُكّكت من شيفرته وقورنت
ببياناته): كتالوجه master.db فيه لكل كتاب pdf_links، وكل قيد ملف فيها
يُقرأ هكذا — مفتاح الجزء ابتداءً هو أول رقم في اسم الملف (وصفر يعني
«@@»: غلاف/واجهة لا متن)، ثم قطع «|» اللاحقة تُلغي وتضيف: القطعة
الفارغة «@@»، و«#N» إصدار الملف، و«@N» فرق الترقيم (difference)،
و«fN» اسم مستعار لمجلد، وأي قطعة أخرى هي اسم الجزء بعينه. وعرض
الصفحة عندهم: رقم صفحة المصوّرة = الرقم المطبوع (page من جدول صفحات
الكتاب عندهم) + فرق ملف جزئها، وجزء الصفحة إن غاب من خريطتهم سقط
إلى مفتاح «0». لا تخمين عندنا بعد اليوم: ما لا تحسمه خريطتهم لا
يُخترع له مقابل (إلا ملفًا وحيدًا لا ثاني له فهو الكتاب كله بيقين).
التغطية جزئية (~خُمس المكتبة)، فغياب الملف جواب مشروع.
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


def _printed_span(mn, mx, count=0) -> int:
    try:
        span = int(mx or 0) - int(mn or 0) + 1
    except (TypeError, ValueError):
        span = 0
    if span <= 0:
        span = int(count or 0)
    return max(1, span) if (span or count) else 0


def _is_intro(part: str) -> bool:
    return any(w in (part or "") for w in ("مقدمة", "مقدمه", "تقديم"))


def _val(text: str) -> int:
    """أول عدد في النص (دالة val عند الشاملة)، و0 عند غيابه."""
    try:
        return int(re.findall(r"\d+|$", str(text or ""))[0])
    except Exception:
        return 0


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _norm_part_key(part) -> str:
    key = str(part or "").strip().translate(_AR_DIGITS)
    return "" if key in ("None", "null") else key


def _parse_entries(pdf_links: str) -> list:
    """قيود ملفات المصوّرة كما يقرؤها تطبيق الشاملة (CoreDb.getMeta):
    {name, part, difference, version} — مفتاح الجزء من أول رقم في اسم
    الملف (0 يصير «@@»)، وقطع «|» من بعده: فارغة «@@»، و«#N» إصدار،
    و«@N» فرق ترقيم، و«fN» مجلد مستعار يُهمل هنا، وغيرها اسم الجزء."""
    try:
        data = json.loads(pdf_links or "{}")
    except Exception:
        return []
    entries = []
    for raw in data.get("files") or []:
        if isinstance(raw, dict):
            raw = str(raw.get("file") or raw.get("name") or "")
        raw = str(raw or "")
        if not raw:
            continue
        base = raw[raw.rfind("/") + 1:] if "/" in raw else raw
        part = str(_val(base))
        if part == "0":
            part = "@@"
        difference, version = 0, 1
        pieces = base.split("|")
        if len(pieces) > 1:
            base = pieces[0]
            for piece in pieces[1:]:
                if not piece:
                    part = "@@"
                    continue
                head, rest = piece[0], piece[1:]
                if head == "#":
                    try:
                        version = int(rest)
                    except ValueError:
                        pass
                elif head == "@":
                    try:
                        difference = int(rest)
                    except ValueError:
                        pass
                elif head == "f":
                    continue
                else:
                    part = piece.strip()
        name = Path(base.strip()).name
        if name:
            entries.append({"name": name, "part": part,
                            "difference": difference, "version": version})
    return entries


def _pdf_map(entries: list) -> dict:
    """{مفتاح الجزء: قيد ملفه} — القيد الأخير يغلب كما في قاموسهم."""
    out = {}
    for entry in entries:
        out[str(entry.get("part") or "")] = entry
    return out


def _select_entry(pdf_map: dict, want_part, parts: list):
    """قيد ملف جزء بعينه باختيار الشاملة (DisplayBook.currentPdf):
    جزء الصفحة نفسه (أو «0» لكتاب بلا أجزاء)، والساقط منه يرجع إلى
    «0». من بعدها لا اجتهاد إلا في يقينين: مقدمة بمفتاح مقدمة وحيد،
    أو كتاب لا ملف له إلا واحد فهو لكل أجزائه."""
    if not pdf_map:
        return None, ""
    has_parts = bool([p for p in (parts or []) if str(p or "").strip()])
    key = _norm_part_key(want_part) if has_parts else "0"
    if has_parts and not key:
        key = _norm_part_key(parts[0])
    entry = pdf_map.get(key)
    if entry is None and key.isdigit():
        entry = pdf_map.get(str(int(key)))
        if entry is not None:
            key = str(int(key))
    if entry is None:
        entry = pdf_map.get("0")
        if entry is not None:
            key = "0"
    if entry is None and _is_intro(key):
        intros = [k for k in pdf_map if _is_intro(k)]
        if len(intros) == 1:
            key = intros[0]
            entry = pdf_map[key]
    if entry is None:
        distinct = {e.get("name") for e in pdf_map.values()}
        if len(distinct) == 1:
            entry = next(iter(pdf_map.values()))
            key = next(k for k, e in pdf_map.items() if e is entry)
    return entry, key


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
    pdf_map = _pdf_map(entries)
    entry, map_key = _select_entry(pdf_map, part, parts)
    if entry is None:
        out["reason"] = "لا ملف مصوّرة لهذا الجزء"
        return out
    file_name = entry["name"]
    candidates = index.get(file_name) or []
    if not candidates:
        out["reason"] = "النسخة المصوّرة غير منزّلة على هذا الجهاز"
        return out
    book_name = str(row.get("book_name") or "")
    path = next((p for p in candidates if p.parent.name == book_name), candidates[0])
    total = _pdf_pages(path)
    try:
        printed = int(page_num or 0)
    except (TypeError, ValueError):
        printed = 0
    if printed <= 0:
        printed = 1
    # صيغة الشاملة نفسها: صفحة المصوّرة = المطبوعة + فرق ترقيم ملف الجزء
    page = printed + int(entry.get("difference") or 0)
    clamped = False
    if page < 1:
        page, clamped = 1, True
    if total and page > total:
        page, clamped = total, True
    volumes = []
    for name, count, mn, _mx in ranges:
        e2, _k2 = _select_entry(pdf_map, name, parts)
        if not e2 or e2.get("name") != file_name:
            continue
        volumes.append({
            "name": name,
            "pages": _printed_span(mn, _mx, count),
            "pdf_start": max(1, int(mn or 1) + int(e2.get("difference") or 0)),
        })
    out.update({
        "available": True,
        "file_name": file_name,
        "pdf_path": str(path),
        "pdf_page": page,
        "pdf_pages": total,
        "book_name": book_name,
        "clamped": clamped,
        "difference": int(entry.get("difference") or 0),
        "part_key": map_key,
        "volumes": volumes,
    })
    return out


_MISSING_PDF = "لا توجد نسخة مصوّرة لهذا الكتاب في الشاملة يمكنك إضافتها عن طريق الشاملة إن كانت متوفرة هنا أو رفع نسخة من جهاز أو سحبها من الشبكة"


def list_volumes(book_id=None, rel_path: str = "") -> dict:
    """أجزاء الكتاب في المصوّرة، وهل ملف كل جزء منزّل على الجهاز."""
    out = {"available": False, "volumes": []}
    their_id = _their_id(book_id, rel_path)
    if not their_id:
        out["reason"] = "لا مقابل لهذا الكتاب عند الشاملة"
        return out
    row = _master_row(their_id)
    if not row or not row.get("pdf_links"):
        out["reason"] = _MISSING_PDF
        return out
    entries = _parse_entries(row["pdf_links"])
    if not entries:
        out["reason"] = _MISSING_PDF
        return out
    root = _pdf_root()
    index = _file_index(root) if root else {}
    ranges = _part_ranges(their_id)
    parts = [r[0] for r in ranges]
    pdf_map = _pdf_map(entries)
    volumes = []
    if ranges:
        for name, count, _mn, _mx in ranges:
            entry, _k = _select_entry(pdf_map, name, parts)
            fn = entry.get("name") if entry else None
            cands = index.get(fn) if fn else None
            volumes.append({
                "name": str(name or "").strip() or "1",
                "pages": _printed_span(_mn, _mx, count),
                "file_name": fn,
                "available": bool(cands),
            })
    else:
        for i, entry in enumerate(entries):
            fn = entry["name"]
            volumes.append({
                "name": str(entry.get("part") or "").strip() or str(i + 1),
                "pages": 0,
                "file_name": fn,
                "available": bool(index.get(fn)),
            })
    out["volumes"] = volumes
    out["book_name"] = str(row.get("book_name") or "")
    out["available"] = any(v["available"] for v in volumes)
    if not root:
        out["reason"] = "مجلد مصوّرات الشاملة غير موجود على هذا الجهاز"
    elif not out["available"]:
        out["reason"] = "النسخة المصوّرة غير منزّلة على هذا الجهاز"
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
    words = [w for w in re.split(r"\s+", target) if len(w) >= 2]
    if not words:
        out["reason"] = "لا شاهد محددًا للبحث عنه"
        return out
    needles = list(dict.fromkeys(words))[:24]
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
    pad = 0.003
    rects = []
    for r in match["rects"]:
        rects.append({
            "x": max(0.0, float(r["x"]) - pad),
            "y": max(0.0, float(r["y"]) - pad),
            "w": min(1.0, float(r["w"]) + 2 * pad),
            "h": min(1.0, float(r["h"]) + 2 * pad),
        })
    out.update({
        "found": True,
        "rect": rects[0],
        "rects": rects,
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


def _word_rects(stream, indices):
    """صندوق لكل لفظ، وتُدمج المتجاورات في السطر نفسه فلا يُرسم مستطيل يبتلع ما بينهما."""
    idxs = sorted({int(i) for i in indices if 0 <= int(i) < len(stream)})
    if not idxs:
        return []
    runs, run = [], [idxs[0]]
    for i in idxs[1:]:
        prev = stream[run[-1]]
        cur = stream[i]
        if i == run[-1] + 1 and prev[2] == cur[2]:
            run.append(i)
        else:
            runs.append(run)
            run = [i]
    runs.append(run)
    rects = []
    for run in runs:
        picked = [stream[i] for i in run]
        x0 = min(float(wd["x"]) for _, wd, _, _ in picked)
        y0 = min(float(wd["y"]) for _, wd, _, _ in picked)
        x1 = max(float(wd["x"]) + float(wd["w"]) for _, wd, _, _ in picked)
        y1 = max(float(wd["y"]) + float(wd["h"]) for _, wd, _, _ in picked)
        rects.append({"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})
    return rects


def _match_from_indices(stream, lines, indices):
    idxs = sorted({int(i) for i in indices if 0 <= int(i) < len(stream)})
    rects = _word_rects(stream, idxs)
    if not rects:
        return None
    line_ids = sorted({stream[i][2] for i in idxs})
    return {
        "rects": rects,
        "text": "\n".join(str(lines[i].get("text") or "") for i in line_ids if 0 <= i < len(lines)),
    }


def _match_witness_words(target: str, lines: list):
    """كل ألفاظ الشاهد المنطوقة بحرفها على الصفحة، بصندوق لكل لفظ أو تتابع في سطره.

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
            indices = []
            for b in chosen:
                indices.extend(range(b.b, b.b + b.size))
            found = _match_from_indices(stream, lines, indices)
            if found:
                return found
    # طبقة متسامحة: طبعات كثيفة قديمة يشوّش تعرفها (كلمات مدمجة أو مبتورة
    # أو بحرف ناقص) فلا تتابع حرفيًا كاملًا؛ محاذاة تقريبية بترتيب الشاهد
    # نفسه وكثافة مطابقة عالية، فلا يمرّ بها شاهد معنوي مبثوث الألفاظ
    fuzzy = _fuzzy_word_match(twords, pwords)
    if fuzzy is None:
        return None
    found = _match_from_indices(stream, lines, fuzzy)
    if not found:
        return None
    # حارس ضد مصادفات العناوين: مطابقة متسامحة في شريط رأس الصفحة تُرفض،
    # فالسؤال المعنوي قد يوافق ألفاظ عنوان الباب فيُتوهم شاهدًا في الأعلى
    top = min(r["y"] for r in found["rects"])
    bot = max(r["y"] + r["h"] for r in found["rects"])
    if top < 0.10 and bot < 0.14:
        return None
    return found


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

    يعيد قائمة فهارس الكلمات المطابقة في تيار الصفحة أو None. لا يُقبل إلا ما
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
    hit = []
    while i > 0 and j > 0 and H[i][j] > 0:
        tw, pw = twords[i - 1], pwords[j - 1]
        step = 3.0 if pw == tw else (2.0 if _word_sim(tw, pw) else -3.0)
        if abs(H[i][j] - (H[i - 1][j - 1] + step)) < 1e-9 and step > 0:
            matched += 1
            exact += 1 if pw == tw else 0
            hit.append(j - 1)
            i -= 1
            j -= 1
        elif abs(H[i][j] - (H[i - 1][j] - 1.0)) < 1e-9:
            i -= 1
        else:
            j -= 1
    need = max(4, -(-50 * n // 100))
    if matched < need or exact < 3 or not hit:
        return None
    return hit


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
