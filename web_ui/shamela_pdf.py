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


def group_visual_lines(lines):
    """تجميع ملاحظات التعرف البصري في أسطر بصرية حقيقية: محرك Vision
    يرجع العربية أحيانًا كلمةً كلمة (ملاحظة لكل كلمة) فتخرج الكلمات
    عمودية سطرًا لكل كلمة إن جُمعت كما هي. الكلمات المتقاربة رأسيًا
    (ضمن ارتفاع سطر) سطرٌ واحد يُرتب يمينًا إلى يسار كما يُقرأ."""
    rows = []
    for line in sorted(lines or [], key=lambda z: (float(z.get("y") or 0), -float(z.get("x") or 0))):
        text = str(line.get("text") or "").strip()
        if not text:
            continue
        y = float(line.get("y") or 0)
        tol = max(0.008, 0.6 * float(line.get("h") or 0.02))
        if rows and abs(y - rows[-1]["y"]) <= tol:
            rows[-1]["items"].append({"text": text, "x": float(line.get("x") or 0)})
        else:
            rows.append({"y": y, "items": [{"text": text, "x": float(line.get("x") or 0)}]})
    out = []
    for row in rows:
        items = sorted(row["items"], key=lambda z: -z["x"])
        out.append({"text": " ".join(item["text"] for item in items), "y": row["y"]})
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
    lines = group_visual_lines(data.get("lines") or [])
    text = "\n".join(l["text"] for l in lines)
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
