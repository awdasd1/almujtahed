"""النسخة المصوّرة من الشاملة: ربط صفحة النص بصفحة الـ PDF الممسوح.

المصدر: تطبيق الشاملة نفسه — كتالوجه master.db فيه لكل كتاب pdf_links
(قائمة ملفات المصوّرة ووسم الجزء لكل ملف)، والملفات منزّلة عنده تحت
pdf/<المؤلف>/<الكتاب>/. القاعدة المثبتة بالفحص على كتب مفردة ومتعددة
الأجزاء: رقم صفحة المصوّرة داخل ملف جزئها يساوي رقم الصفحة المطبوعة
(page_num) نفسه. التغطية جزئية (~خُمس المكتبة)، فغياب الملف جواب مشروع.
"""
from __future__ import annotations

import json
import sqlite3
import sys
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


def _their_parts(their_id: int) -> list:
    """أجزاء الكتاب عندهم بترتيب ظهورها في صفحاتهم."""
    db_dir = shamela_link.data_database_dir()
    if not db_dir:
        return []
    cand = db_dir / "book" / f"{their_id % 1000:03d}" / f"{their_id}.db"
    if not cand.exists():
        found = list((db_dir / "book").rglob(f"{their_id}.db"))
        if not found:
            return []
        cand = found[0]
    try:
        con = sqlite3.connect(f"file:{cand}?mode=ro", uri=True)
        rows = con.execute("SELECT part FROM page GROUP BY part ORDER BY MIN(id)").fetchall()
        con.close()
        return [str(r[0] or "") for r in rows]
    except Exception:
        return []


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
    """{الجزء: اسم ملف المصوّرة} من وسوم الملفات ثم بترتيب القائمة."""
    assigned = {}
    pool = []
    for entry in entries:
        tag = entry["tag"]
        if tag and not tag.startswith("#") and tag in parts:
            assigned.setdefault(tag, entry["name"])
        elif tag in _INTRO_TAGS and "المقدمة" in parts:
            assigned.setdefault("المقدمة", entry["name"])
        elif tag and not tag.startswith("#"):
            # وسم جزء غير معروف عندنا (تقديم بلا جزء مقدمة): يبقى احتياطًا أخيرًا
            pool.append(entry)
        else:
            pool.append(entry)
    rest = [p for p in parts if p not in assigned]
    for entry, part in zip(pool, rest):
        assigned[part] = entry["name"]
    if len(entries) == 1 and parts:
        only = entries[0]["name"]
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
        out["reason"] = "لا نسخة مصوّرة لهذا الكتاب في الشاملة"
        return out
    entries = _parse_entries(row["pdf_links"])
    if not entries:
        out["reason"] = "لا نسخة مصوّرة لهذا الكتاب في الشاملة"
        return out
    root = _pdf_root()
    if not root:
        out["reason"] = "مجلد مصوّرات الشاملة غير موجود على هذا الجهاز"
        return out
    index = _file_index(root)
    parts = _their_parts(their_id)
    want_part = str(part or "").strip()
    if want_part == "None":
        want_part = ""
    if parts and want_part not in parts:
        # أجزاؤنا قد تختلف تسميتها عن أجزائهم؛ أقرب جزئيًا أو الأول
        want_part = parts[0]
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
    if total and page > total:
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
