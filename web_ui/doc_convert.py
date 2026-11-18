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
        m["volume_count"] = len(m.get("volumes") or ([1] if m.get("pages") else []))
        m.pop("volumes", None)
    return out


def delete_doc(doc_id: str, owner: str) -> bool:
    with _LOCK:
        reg = _load_registry()
        meta = reg.get(doc_id)
        if not meta or (owner and meta.get("owner") != owner):
            return False
        reg.pop(doc_id, None)
        _save_registry(reg)
    paths = [meta.get("text_path")]
    for v in (meta.get("volumes") or []):
        paths.append(v.get("file_path"))
    if not meta.get("volumes"):
        paths.append(meta.get("file_path"))
    for p in paths:
        try:
            if p:
                os.remove(p)
        except OSError:
            pass
    return True


def _ocr_lines(png_path: str) -> list:
    """سطور صورة صفحة بالتعرف البصري المحلي مع مواضعها النسبية."""
    try:
        import shamela_pdf
        helper = shamela_pdf._ocr_helper()
    except Exception:
        helper = ""
    if not helper:
        return []
    try:
        proc = subprocess.run([helper, png_path, "نص"], capture_output=True, text=True, timeout=240)
        data = json.loads(proc.stdout or "{}")
    except Exception:
        return []
    out = []
    for l in data.get("lines") or []:
        text = str(l.get("text") or "").strip()
        if text:
            out.append({"text": text, "y": float(l.get("y") or 0)})
    return out


def _ocr_png(png_path: str) -> str:
    """قراءة صورة صفحة بالتعرف البصري المحلي، نصًا بأسطره."""
    return "\n".join(l["text"] for l in _ocr_lines(png_path))


def _norm_line(text: str) -> str:
    return re.sub(r"\s+", " ", _fold(text or "")).strip(" .،:؛»«()")


def _clamp_dpi(value) -> int:
    """دقة قراءة الصفحات المصوّرة بنقطة/بوصة: بين 50 و600، والافتراضي 300."""
    try:
        return max(50, min(600, int(value)))
    except (TypeError, ValueError):
        return 300


def _footnote_band_text(page, page_text: str, dpi: int = 300) -> str:
    """حواشي أسفل الصفحة المصوّرة: يُعاد قراءة خُمسها الأسفل مكبّرًا، وما جدّ
    من سطوره (ليست في متن الصفحة المقروء) يُرجع ليُلحق بعد خط فاصل كما في
    المطبوع؛ فخط الحواشي الصغير يضيع في قراءة الصفحة كاملة منخفضة الدقة."""
    try:
        import fitz
        rect = page.rect
        band = fitz.Rect(rect.x0, rect.y0 + rect.height * 0.80, rect.x1, rect.y1)
        pix = page.get_pixmap(dpi=dpi, clip=band)
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            Path(tmp).write_bytes(pix.tobytes("png"))
            lines = _ocr_lines(tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
    except Exception:
        return ""
    page_norm = _norm_line(page_text)
    page_lines = [_norm_line(l) for l in (page_text or "").splitlines() if l.strip()]
    novel = []
    from difflib import SequenceMatcher
    for l in lines:
        if l["y"] < 0.30:
            # أعلى الشريط ذيلُ متنٍ مقروء غالبًا لا حواشٍ
            continue
        norm = _norm_line(l["text"])
        if len(norm) < 4 or norm in page_norm:
            continue
        if any(SequenceMatcher(None, norm, pl).ratio() > 0.82 for pl in page_lines):
            continue
        novel.append(l["text"])
    return "\n".join(novel)


def _natural_key(path: Path):
    """فرز طبيعي لأسماء ملفات الأجزاء: جزء2 قبل جزء10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def _convert_one(src: Path, progress, dpi: int = 300, only=None) -> tuple:
    """تحويل ملف واحد إلى أجزاء صفحاته، يُرجع (الأجزاء، عدد الصفحات، فشل بصري؟).
    only مجموعة أرقام صفحات (1-based) تُحوَّل وحدها إن أُعطيت، بأرقامها الحقيقية."""
    ext = src.suffix.lower()
    parts: list[str] = []
    if ext == ".txt":
        if only is not None and 1 not in only:
            return parts, 1, False
        parts.append(src.read_text(encoding="utf-8", errors="ignore"))
        progress()
        return parts, 1, False
    if ext != ".pdf" and ext not in _IMG_EXTS:
        raise RuntimeError("صيغة غير مدعومة: ارفع PDF أو صورة أو ملفًا نصيًا")
    import fitz
    doc = fitz.open(str(src))
    total = doc.page_count
    ocr_missing = False
    for i in range(total):
        if only is not None and (i + 1) not in only:
            continue
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
            # بالدقة المختارة (افتراضي 300): خط الحواشي الصغير لا يلتقطه
            # المحرك بالدقات الدنيا، والأعلى أوضح وأبطأ
            pix = page.get_pixmap(dpi=dpi)
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
                band = _footnote_band_text(page, read, dpi)
                if band:
                    read = read + "\n——————\n" + band
                parts.append(f"[صفحة {i + 1}]\n{read}")
            else:
                ocr_missing = True
                parts.append(f"[صفحة {i + 1}]\n[صفحة مصوّرة تعذّرت قراءتها آليًا]")
        progress()
    doc.close()
    return parts, total, ocr_missing


def _count_pages(src: Path) -> int:
    ext = src.suffix.lower()
    if ext == ".pdf":
        try:
            import fitz
            d = fitz.open(str(src))
            n = d.page_count
            d.close()
            return n
        except Exception:
            return 0
    return 1


def _norm_scope(scope) -> dict | None:
    """تطبيع نطاق التحويل: كامل، أو صفحة، أو نطاق — من جزء بعينه أو الكل."""
    if not isinstance(scope, dict):
        return None
    mode = scope.get("mode")
    if mode not in ("page", "range"):
        return None
    def _pos(v):
        try:
            n = int(v)
            return n if n >= 1 else None
        except (TypeError, ValueError):
            return None
    frm = _pos(scope.get("from"))
    if frm is None:
        return None
    to = _pos(scope.get("to")) if mode == "range" else frm
    if to is None:
        to = frm
    if to < frm:
        frm, to = to, frm
    return {"mode": mode, "volume": _pos(scope.get("volume")), "from": frm, "to": to}


def _scope_only(scope, volume_no: int, total: int):
    """صفحات جزء ما الواقعة في النطاق، أو None للكل، أو مجموعة فارغة للتخطي."""
    if not scope:
        return None
    if scope.get("volume") and scope["volume"] != volume_no:
        return set()
    return set(range(max(1, scope["from"]), min(total, scope["to"]) + 1))


def _convert_volumes(doc_id: str, start_volume: int) -> None:
    """تحويل أجزاء الوثيقة من جزء مبدئي، ملحقة بنصها القائم إن وُجد،
    في حدود نطاق التحويل المحفوظ إن اختار الباحث صفحة أو نطاقًا."""
    meta = get_doc(doc_id)
    if not meta:
        return
    volumes = meta.get("volumes") or ([{"file_path": meta.get("file_path")}] if meta.get("file_path") else [])
    dpi = _clamp_dpi(meta.get("dpi"))
    scope = _norm_scope(meta.get("scope"))
    multi = len(volumes) > 1
    totals = [_count_pages(Path(v.get("file_path") or "")) for v in volumes]
    onlys = [_scope_only(scope, vi + 1, totals[vi]) for vi in range(len(volumes))]
    sel = [totals[vi] if onlys[vi] is None else len(onlys[vi]) for vi in range(len(volumes))]
    done_before = sum(sel[:start_volume])
    prev_pages = int(meta.get("pages") or 0)
    state = {"done": done_before, "new": 0}
    def _tick():
        state["done"] += 1
        state["new"] += 1
        _set_meta(doc_id, page=state["done"])
    _set_meta(doc_id, status="converting", pages=sum(sel), page=done_before, error="")
    parts: list[str] = []
    ocr_missing = False
    try:
        for vi in range(start_volume, len(volumes)):
            volumes[vi]["pages"] = totals[vi]
            if onlys[vi] is not None and not onlys[vi]:
                _set_meta(doc_id, volumes=volumes)
                continue
            vparts, n, miss = _convert_one(
                Path(volumes[vi].get("file_path") or ""), _tick, dpi, onlys[vi])
            ocr_missing = ocr_missing or miss
            if vparts:
                if multi:
                    parts.append(f"[الجزء {vi + 1}]")
                parts.extend(vparts)
            _set_meta(doc_id, volumes=volumes)
    except Exception as exc:
        _set_meta(doc_id, status="error", error=str(exc)[:300])
        return
    if scope and start_volume == 0 and state["done"] == 0:
        _set_meta(doc_id, status="error",
                  error="النطاق المحدد خارج صفحات الوثيقة: لم تُحوَّل أي صفحة")
        return
    text_path = Path(meta.get("text_path") or "")
    text_path.parent.mkdir(parents=True, exist_ok=True)
    new_text = "\n\n".join(parts).strip()
    if start_volume > 0 and text_path.exists():
        old = text_path.read_text(encoding="utf-8")
        full = (old.rstrip() + "\n\n" + new_text).strip() if new_text else old
    else:
        full = new_text
    text_path.write_text(full, encoding="utf-8")
    final_pages = state["done"] if start_volume == 0 else prev_pages + state["new"]
    kw = {"status": "done", "chars": len(full), "pages": final_pages,
          "page": final_pages, "finished": int(time.time()), "volumes": volumes}
    if ocr_missing:
        kw["note"] = "بعض الصفحات المصوّرة لم تُقرأ (أداة التعرف البصري خاصة بنسخة Mac)"
    _set_meta(doc_id, **kw)


def convert_document(doc_id: str) -> None:
    """تحويل الوثيقة نصًا في خيط خلفي مع تحديث التقدم في السجل."""
    _convert_volumes(doc_id, 0)


def register_document(owner: str, name: str, saved, dpi=None, scope=None) -> dict:
    """تسجيل وثيقة من ملف أو ملفات أجزاء مرتبة بفرز طبيعي لأسمائها."""
    paths = [saved] if isinstance(saved, (str, Path)) else list(saved)
    paths = sorted((Path(p) for p in paths), key=_natural_key)
    doc_id = f"doc{int(time.time() * 1000)}"
    text_path = paths[0].parent / f"{doc_id}.txt"
    meta = {
        "id": doc_id, "owner": owner, "name": name or paths[0].stem,
        "file_path": str(paths[0]), "text_path": str(text_path),
        "volumes": [{"file_path": str(p), "pages": 0} for p in paths],
        "dpi": _clamp_dpi(dpi), "scope": _norm_scope(scope),
        "status": "queued", "page": 0, "pages": 0, "chars": 0,
        "created": int(time.time()), "error": "", "note": "",
    }
    with _LOCK:
        reg = _load_registry()
        reg[doc_id] = meta
        _save_registry(reg)
    threading.Thread(target=convert_document, args=(doc_id,), daemon=True).start()
    return dict(meta)


def reconvert_document(doc_id: str, owner: str, dpi=None, scope="keep") -> bool:
    """إعادة تحويل وثيقة من ملفاتها الأصلية (لالتقاط ما فات بدقة أعلى مثلًا).
    scope: ‏"keep" للإبقاء على نطاقها، أو None لكامل الوثيقة، أو قاموس نطاق."""
    if not get_doc(doc_id, owner):
        return False
    kw = {"status": "queued", "page": 0, "chars": 0, "error": ""}
    if dpi is not None:
        kw["dpi"] = _clamp_dpi(dpi)
    if scope != "keep":
        kw["scope"] = _norm_scope(scope)
    _set_meta(doc_id, **kw)
    threading.Thread(target=convert_document, args=(doc_id,), daemon=True).start()
    return True


def append_volumes(doc_id: str, owner: str, saved, dpi=None, scope="keep") -> dict | None:
    """إضافة أجزاء جديدة إلى وثيقة قائمة وتحويلها ملحقة بنصها."""
    meta = get_doc(doc_id, owner)
    if not meta:
        return None
    paths = [saved] if isinstance(saved, (str, Path)) else list(saved)
    paths = sorted((Path(p) for p in paths), key=_natural_key)
    volumes = meta.get("volumes") or ([{"file_path": meta.get("file_path"), "pages": meta.get("pages", 0)}] if meta.get("file_path") else [])
    start = len(volumes)
    volumes.extend({"file_path": str(p), "pages": 0} for p in paths)
    kw = {"volumes": volumes, "status": "converting"}
    if dpi is not None:
        kw["dpi"] = _clamp_dpi(dpi)
    if scope != "keep":
        kw["scope"] = _norm_scope(scope)
    _set_meta(doc_id, **kw)
    threading.Thread(target=_convert_volumes, args=(doc_id, start), daemon=True).start()
    out = get_doc(doc_id, owner) or meta
    return dict(out)


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
_VOL_RE = re.compile(r"(?:الجزء|جزء|المجلد|مجلد)\s*[:\-]?\s*(\d{1,3})")
_SLASH_RE = re.compile(r"(\d{1,3})\s*/\s*(\d{1,4})")


def _requested_refs(query: str) -> list:
    """مواضع مطلوبة صراحة: [(الجزء أو None، الصفحة)]، بأرقام غربية أو
    مشرقية، وبصيغ «صفحة ٢٣٠ من جزء ٤» و«٤/٢٣٠»، مع مدى صفحات بحد عشر."""
    q = (query or "").translate(_DIGITS)
    vol = None
    mv = _VOL_RE.search(q)
    if mv:
        vol = int(mv.group(1))
    mp = _PAGE_RE.search(q)
    if mp:
        start = int(mp.group(1))
        pages = [start]
        m2 = re.search(r"(?:إلى|الى|حتى)\s*(?:الصفحة\s*|صفحة\s*|ص\s*)?(\d{1,4})", q[mp.end():])
        if m2:
            end = int(m2.group(1))
            if start < end <= start + 10:
                pages = list(range(start, end + 1))
        return [(vol, p) for p in pages]
    ms = _SLASH_RE.search(q)
    if ms and vol is None:
        v, p = int(ms.group(1)), int(ms.group(2))
        if 1 <= v <= 60 and 1 <= p <= 5000:
            return [(v, p)]
    return []


def _page_segments(text: str) -> dict:
    """نص كل صفحة كاملًا بمفتاح (الجزء، الصفحة) من علامات التحويل؛
    ما قبل أي رأس جزء يُنسب للجزء الأول."""
    segs = {}
    vol = 1
    tokens = re.split(r"\[(?:الجزء (\d+)|صفحة (\d+))\]\s*\n?", text or "")
    # tokens: [قبل, جزء, صفحة, نص, جزء, صفحة, نص, ...] بمجموعات ثلاثية
    cur_page = None
    for i in range(1, len(tokens) - 2, 3):
        g_vol, g_page, body = tokens[i], tokens[i + 1], tokens[i + 2]
        if g_vol:
            vol = int(g_vol)
            cur_page = None
            continue
        if g_page:
            cur_page = int(g_page)
            segs[(vol, cur_page)] = (body or "").strip()
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
    # طلب موضع بعينه (جزء/صفحة): نصّه الكامل مقدَّم على أي موازنة لفظية
    refs = _requested_refs(query or "")
    if refs:
        segs = _page_segments(text)
        vols_present = sorted({v for v, _ in segs})
        multi = len(vols_present) > 1
        page_chunks, used = [], 0
        for vol, page in refs:
            targets = [(vol, page)] if vol else [(v, page) for v in vols_present if (v, page) in segs]
            for v, p in targets:
                body = segs.get((v, p))
                if body is None:
                    continue
                label = f"[جزء {v}، صفحة {p}]" if multi else f"[صفحة {p}]"
                chunk = f"{label}\n{body}"
                if used + len(chunk) > budget and page_chunks:
                    break
                page_chunks.append(chunk)
                used += len(chunk)
        if page_chunks:
            return {"chunks": page_chunks, "name": meta.get("name", ""),
                    "pages": [p for _, p in refs], "volumes": [v for v, _ in refs]}
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
