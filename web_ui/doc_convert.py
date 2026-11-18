"""رفع وثيقة كاملة وتحويلها نصًا: كتاب أو PDF مصوّر أو ملف صورة.

النص المدمج في الـ PDF يُؤخذ كما هو، والصفحات المصوّرة تُقرأ بالتعرف
البصري المحلي (Vision عند آبل) صفحة صفحة، ويُحفظ الناتج نصًا مقطعًا
بفواصل الصفحات حتى تستطيع المحادثة استحضار مقاطعه ذات الصلة بالسؤال.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_REGISTRY = _HERE / "documents_data.json"
_LOCK = threading.Lock()
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}


def _load_registry() -> dict:
    try:
        return json.loads(_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_registry(reg: dict) -> None:
    tmp = _REGISTRY.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(_REGISTRY)


def _set_meta(doc_id: str, **kw) -> None:
    with _LOCK:
        reg = _load_registry()
        if doc_id in reg:
            reg[doc_id].update(kw)
            _save_registry(reg)


def get_doc(doc_id: str, owner: str = "") -> dict | None:
    with _LOCK:
        meta = _load_registry().get(doc_id)
    if not meta:
        return None
    if owner and meta.get("owner") and meta["owner"] != owner:
        return None
    return dict(meta)


def list_docs(owner: str) -> list:
    with _LOCK:
        reg = _load_registry()
    out = [dict(m) for m in reg.values() if m.get("owner") == owner]
    out.sort(key=lambda m: m.get("created", 0), reverse=True)
    for m in out:
        m.pop("text_path", None)
        m.pop("file_path", None)
    return out


def delete_doc(doc_id: str, owner: str) -> bool:
    with _LOCK:
        reg = _load_registry()
        meta = reg.get(doc_id)
        if not meta or (owner and meta.get("owner") != owner):
            return False
        reg.pop(doc_id, None)
        _save_registry(reg)
    for key in ("text_path", "file_path"):
        try:
            if meta.get(key):
                os.remove(meta[key])
        except OSError:
            pass
    return True


def _ocr_png(png_path: str) -> str:
    """قراءة صورة صفحة بالتعرف البصري المحلي، نصًا بأسطره."""
    try:
        import shamela_pdf
        helper = shamela_pdf._ocr_helper()
    except Exception:
        helper = ""
    if not helper:
        return ""
    try:
        proc = subprocess.run([helper, png_path, "نص"], capture_output=True, text=True, timeout=240)
        data = json.loads(proc.stdout or "{}")
    except Exception:
        return ""
    lines = data.get("lines") or []
    return "\n".join(str(l.get("text") or "").strip() for l in lines if str(l.get("text") or "").strip())


def convert_document(doc_id: str) -> None:
    """تحويل الوثيقة نصًا في خيط خلفي مع تحديث التقدم في السجل."""
    meta = get_doc(doc_id)
    if not meta:
        return
    src = Path(meta.get("file_path") or "")
    ext = src.suffix.lower()
    _set_meta(doc_id, status="converting", page=0, pages=0, error="")
    parts: list[str] = []
    try:
        if ext == ".txt":
            text = src.read_text(encoding="utf-8", errors="ignore")
            _set_meta(doc_id, pages=1, page=1)
            parts.append(text)
        elif ext == ".pdf" or ext in _IMG_EXTS:
            import fitz
            doc = fitz.open(str(src))
            total = doc.page_count
            _set_meta(doc_id, pages=total)
            ocr_missing = False
            for i in range(total):
                page = doc[i]
                embedded = ""
                if ext == ".pdf":
                    try:
                        embedded = (page.get_text() or "").strip()
                    except Exception:
                        embedded = ""
                if len(embedded) >= 20:
                    parts.append(f"[صفحة {i + 1}]\n{embedded}")
                else:
                    pix = page.get_pixmap(dpi=150)
                    fd, tmp = tempfile.mkstemp(suffix=".png")
                    os.close(fd)
                    try:
                        Path(tmp).write_bytes(pix.tobytes("png"))
                        read = _ocr_png(tmp)
                    finally:
                        try:
                            os.remove(tmp)
                        except OSError:
                            pass
                    if read:
                        parts.append(f"[صفحة {i + 1}]\n{read}")
                    else:
                        ocr_missing = True
                        parts.append(f"[صفحة {i + 1}]\n[صفحة مصوّرة تعذّرت قراءتها آليًا]")
                _set_meta(doc_id, page=i + 1)
            doc.close()
            if ocr_missing:
                _set_meta(doc_id, note="بعض الصفحات المصوّرة لم تُقرأ (أداة التعرف البصري خاصة بنسخة Mac)")
        else:
            raise RuntimeError("صيغة غير مدعومة: ارفع PDF أو صورة أو ملفًا نصيًا")
    except Exception as exc:
        _set_meta(doc_id, status="error", error=str(exc)[:300])
        return
    text = "\n\n".join(parts).strip()
    text_path = Path(meta.get("text_path") or "")
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    _set_meta(doc_id, status="done", chars=len(text), finished=int(time.time()))


def register_document(owner: str, name: str, saved_path: Path) -> dict:
    doc_id = f"doc{int(time.time() * 1000)}"
    text_path = saved_path.parent / f"{doc_id}.txt"
    meta = {
        "id": doc_id, "owner": owner, "name": name or saved_path.stem,
        "file_path": str(saved_path), "text_path": str(text_path),
        "status": "queued", "page": 0, "pages": 0, "chars": 0,
        "created": int(time.time()), "error": "", "note": "",
    }
    with _LOCK:
        reg = _load_registry()
        reg[doc_id] = meta
        _save_registry(reg)
    threading.Thread(target=convert_document, args=(doc_id,), daemon=True).start()
    return dict(meta)


_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})


def _fold(text: str) -> str:
    text = re.sub(r"[ً-ٰٓـ]", "", text or "")
    return text.translate(_FOLD)


def _chunks(text: str, size: int = 1200) -> list:
    raw = [c.strip() for c in re.split(r"(?=\[صفحة \d+\])", text or "") if c.strip()]
    out = []
    for piece in raw:
        while len(piece) > size:
            cut = piece.rfind("\n", 0, size)
            if cut < size // 3:
                cut = size
            out.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        if piece:
            out.append(piece)
    return out


_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PAGE_RE = re.compile(r"(?:الصفحة|صفحة|صفحه|ص|page)\s*[:\-]?\s*(\d{1,4})", re.IGNORECASE)


def _requested_pages(query: str) -> list:
    """أرقام الصفحات المطلوبة صراحة في السؤال، بالأرقام الغربية أو المشرقية،
    مع مدى «من صفحة كذا إلى كذا» بحد عشر صفحات."""
    q = (query or "").translate(_DIGITS)
    m = _PAGE_RE.search(q)
    if not m:
        return []
    start = int(m.group(1))
    m2 = re.search(r"(?:إلى|الى|حتى)\s*(?:الصفحة\s*|صفحة\s*|ص\s*)?(\d{1,4})", q[m.end():])
    if m2:
        end = int(m2.group(1))
        if start < end <= start + 10:
            return list(range(start, end + 1))
    return [start]


def _page_segments(text: str) -> dict:
    """نص كل صفحة كاملًا مفصولًا بعلامات [صفحة N] التي زرعها التحويل."""
    segs = {}
    parts = re.split(r"\[صفحة (\d+)\]\s*\n?", text or "")
    for i in range(1, len(parts) - 1, 2):
        try:
            n = int(parts[i])
        except ValueError:
            continue
        segs[n] = (parts[i + 1] or "").strip()
    return segs


def relevant_context(doc_id: str, owner: str, query: str, budget: int = 12000) -> dict:
    """أقرب مقاطع الوثيقة إلى السؤال بموازنة لفظية، بحد حرفي للسياق.
    وإن سمّى السؤال صفحة بعينها أُرجع نصّها كاملًا لا مقاطع لفظية عامة."""
    meta = get_doc(doc_id, owner)
    if not meta:
        return {"chunks": [], "reason": "وثيقة غير موجودة"}
    if meta.get("status") != "done":
        return {"chunks": [], "reason": "الوثيقة لم يكتمل تحويلها بعد"}
    try:
        text = Path(meta["text_path"]).read_text(encoding="utf-8")
    except Exception:
        return {"chunks": [], "reason": "تعذرت قراءة نص الوثيقة"}
    # طلب صفحة بعينها: نصّها الكامل مقدَّم على أي موازنة لفظية
    wanted = _requested_pages(query or "")
    if wanted:
        segs = _page_segments(text)
        page_chunks, used = [], 0
        for n in wanted:
            body = segs.get(n)
            if body is None:
                continue
            chunk = f"[صفحة {n}]\n{body}"
            if used + len(chunk) > budget and page_chunks:
                break
            page_chunks.append(chunk)
            used += len(chunk)
        if page_chunks:
            return {"chunks": page_chunks, "name": meta.get("name", ""), "pages": wanted}
    chunks = _chunks(text)
    terms = [t for t in dict.fromkeys(re.findall(r"[\w]{3,}", _fold(query or ""))) ]
    if not chunks:
        return {"chunks": [], "reason": "الوثيقة فارغة النص"}
    if not terms:
        picked = chunks[:4]
        return {"chunks": picked, "name": meta.get("name", "")}
    scored = []
    for idx, chunk in enumerate(chunks):
        folded = _fold(chunk)
        hits = sum(1 for t in terms if t in folded)
        freq = sum(folded.count(t) for t in terms)
        if hits:
            scored.append((hits, freq, idx))
    scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
    picked = []
    used = 0
    for _, _, idx in scored[:6]:
        chunk = chunks[idx]
        if used + len(chunk) > budget and picked:
            continue
        picked.append(chunk)
        used += len(chunk)
        if used >= budget:
            break
    return {"chunks": picked, "name": meta.get("name", "")}
