"""النسخة المصوّرة من الشاملة: ربط صفحة النص بصفحة الـ PDF الممسوح.

المصدر: تطبيق الشاملة نفسه — كتالوجه master.db فيه لكل كتاب pdf_links
(قائمة ملفات المصوّرة ووسم الجزء لكل ملف)، والملفات منزّلة عنده تحت
pdf/<المؤلف>/<الكتاب>/. القاعدة المثبتة بالفحص على كتب مفردة ومتعددة
الأجزاء: رقم صفحة المصوّرة داخل ملف جزئها يساوي رقم الصفحة المطبوعة
(page_num) نفسه. التغطية جزئية (~خُمس المكتبة)، فغياب الملف جواب مشروع.
"""
from __future__ import annotations

import json
import re
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
