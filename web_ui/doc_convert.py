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


_OCR_RUNTIME: dict = {}
_CANCEL_EVENTS: dict = {}
_ACTIVE: dict = {}
_LAST_OCR_ERROR: dict = {}


def _await_fallback_decision(doc_id: str, model: str, reason: str, cancel_ev) -> str:
    """تعذّر نموذج القراءة: يُعلَّق التحويل ويُعرض على الباحث أن النموذج لا
    يقرأ وأن البديل هو المحرك الافتراضي لأنظمة ماك (القراءة المحلية)،
    فيختار قبولًا فيُكمل محليًا أو إلغاءً فيقف التحويل بما تمّ."""
    _set_meta(doc_id, fallback_prompt={"model": model or "", "reason": reason or ""},
              fallback_decision="")
    decision = ""
    deadline = time.time() + 1800
    while time.time() < deadline:
        if cancel_ev is not None and cancel_ev.is_set():
            decision = "cancel"
            break
        got = (get_doc(doc_id) or {}).get("fallback_decision") or ""
        if got in ("accept", "cancel"):
            decision = got
            break
        time.sleep(0.4)
    _set_meta(doc_id, fallback_prompt=None)
    return decision or "cancel"


def resolve_fallback(doc_id: str, owner: str, decision: str) -> bool:
    """قرار الباحث على عرض الرجوع للمحرك المحلي: قبول أو إلغاء."""
    meta = get_doc(doc_id, owner)
    if not meta or not meta.get("fallback_prompt"):
        return False
    if decision not in ("accept", "cancel"):
        return False
    _set_meta(doc_id, fallback_decision=decision)
    return True


class _ConversionCancelled(Exception):
    """أوقف الباحث التحويل يدويًا: يُحفظ ما تمّ ويُختم الحال."""


def _register_active(doc_id, handle) -> None:
    if doc_id and handle is not None:
        _ACTIVE.setdefault(doc_id, set()).add(handle)


def _unregister_active(doc_id, handle) -> None:
    if doc_id and doc_id in _ACTIVE:
        _ACTIVE[doc_id].discard(handle)


def request_cancel(doc_id: str, owner: str) -> bool:
    """إيقاف فوري للتحويل: تُقتل قراءة الصفحة الجارية نفسها وتُسقط،
    ويُكتفى بالصفحات المعالجة قبلها."""
    meta = get_doc(doc_id, owner)
    if not meta or meta.get("status") not in ("queued", "converting"):
        return False
    ev = _CANCEL_EVENTS.get(doc_id)
    if ev is None:
        ev = threading.Event()
        _CANCEL_EVENTS[doc_id] = ev
    ev.set()
    for handle in list(_ACTIVE.get(doc_id, [])):
        try:
            if hasattr(handle, "kill"):
                handle.kill()
            elif hasattr(handle, "close"):
                handle.close()
        except Exception:
            pass
    return True
_OCR_PROMPT = (
    "استخرج نص هذه الصفحة العربية كاملًا كما هو مكتوب، سطرًا سطرًا من أولها "
    "إلى آخرها شاملاً الحواشي أسفلها وعلاماتها، دون أي شرح أو تعليق أو "
    "عناوين من عندك، ودون تنسيق ماركداون أو أسوار رمزية."
)


def set_ocr_runtime(doc_id: str, api_key: str) -> None:
    """مفتاح OpenRouter لمحرك قراءة نموذجي: يُحفظ في الذاكرة فقط لا في السجل."""
    if api_key:
        _OCR_RUNTIME[doc_id] = api_key


def _ocr_openrouter_lines(png_path: str, model: str, api_key: str, doc_id: str = "") -> list:
    """قراءة صفحة بنموذج رؤية من OpenRouter (بديل المحلي على ويندوز
    أو عند رداءة المسح)، سطورًا بمواضع تقريبية متسلسلة."""
    import base64
    import urllib.request
    import urllib.error
    if not model or not api_key:
        if doc_id:
            _LAST_OCR_ERROR[doc_id] = "لم يُضبط مفتاح OpenRouter أو اسم النموذج"
        return []
    try:
        b64 = base64.b64encode(Path(png_path).read_bytes()).decode("ascii")
        body = json.dumps({
            "model": model,
            "temperature": 0,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": _OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body, method="POST",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json",
                     "HTTP-Referer": "http://localhost:8085",
                     "X-Title": "Almoghni Sharia Engine"})
        resp = urllib.request.urlopen(req, timeout=240)
        _register_active(doc_id, resp)
        try:
            data = json.loads(resp.read().decode("utf-8"))
        finally:
            _unregister_active(doc_id, resp)
            try:
                resp.close()
            except Exception:
                pass
        _LAST_OCR_ERROR.pop(doc_id, None)
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if isinstance(content, list):
            content = "".join(str(c.get("text") or "") for c in content if isinstance(c, dict))
        lines = [l.strip() for l in str(content).splitlines() if l.strip()]
        lines = [l for l in lines if not l.startswith("```")]
        total = max(1, len(lines))
        return [{"text": l, "y": i / total} for i, l in enumerate(lines)]
    except Exception as exc:
        # يُحفظ سبب الفشل ليُعرض على الباحث قبل أي رجوع للمحرك المحلي
        if doc_id:
            msg = ""
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    payload = json.loads(exc.read().decode("utf-8", "ignore") or "{}")
                    msg = str((payload.get("error") or {}).get("message") or "")[:200]
                except Exception:
                    msg = ""
                if not msg:
                    msg = f"خطأ HTTP {exc.code} من OpenRouter"
            else:
                msg = f"{type(exc).__name__}: {exc}"[:200]
            _LAST_OCR_ERROR[doc_id] = msg
        return []


def _ocr_lines(png_path: str, ocr: dict | None = None, strict: bool = False):
    """سطور صورة صفحة بمحرك القراءة المختار: نموذج OpenRouter أو المحلي.
    عند strict وفشل نموذج OpenRouter يُرجع None (لا رجوع صامت للمحلي)
    ليعرض التحويلُ الأمرَ على الباحث قبل المتابعة بأي محرك آخر."""
    if ocr and ocr.get("engine") == "openrouter" and ocr.get("model"):
        got = _ocr_openrouter_lines(png_path, ocr["model"],
                                    _OCR_RUNTIME.get(ocr.get("doc_id") or "", ""),
                                    ocr.get("doc_id") or "")
        if got:
            return got
        if strict:
            return None
    try:
        import shamela_pdf
        helper = shamela_pdf._ocr_helper()
    except Exception:
        helper = ""
    if not helper:
        return []
    doc_key = (ocr or {}).get("doc_id") or ""
    proc = None
    try:
        proc = subprocess.Popen([helper, png_path, "نص"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        _register_active(doc_key, proc)
        out, _ = proc.communicate(timeout=240)
        data = json.loads(out or "{}")
    except Exception:
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        return []
    finally:
        _unregister_active(doc_key, proc)
    out = []
    for l in data.get("lines") or []:
        text = str(l.get("text") or "").strip()
        if text:
            out.append({"text": text, "y": float(l.get("y") or 0)})
    return out


def _ocr_png(png_path: str, ocr: dict | None = None, strict: bool = False):
    """قراءة صورة صفحة بالتعرف البصري، نصًا بأسطره (None عند strict وفشل النموذج)."""
    lines = _ocr_lines(png_path, ocr, strict=strict)
    if lines is None:
        return None
    return "\n".join(l["text"] for l in lines)


def _norm_line(text: str) -> str:
    return re.sub(r"\s+", " ", _fold(text or "")).strip(" .،:؛»«()")


def _clamp_dpi(value) -> int:
    """دقة قراءة الصفحات المصوّرة بنقطة/بوصة: بين 50 و600، والافتراضي 150."""
    try:
        return max(50, min(600, int(value)))
    except (TypeError, ValueError):
        return 150


def _footnote_band_text(page, page_text: str, dpi: int = 300, ocr: dict | None = None) -> str:
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
            lines = _ocr_lines(tmp, ocr)
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


def _convert_one(src: Path, progress, dpi: int = 300, only=None, ocr: dict | None = None, cancel_ev=None) -> tuple:
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
        if cancel_ev is not None and cancel_ev.is_set():
            break
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
                read = _ocr_png(tmp, ocr, strict=True)
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            if read is None and not (ocr or {}).get("doc_id"):
                read = _ocr_png(tmp, ocr)  # بلا سياق وثيقة: الرجوع القديم
            if read is None:
                # النموذج لا يقرأ: لا رجوع صامت — يُعرض الأمر على الباحث أولًا
                doc_key = (ocr or {}).get("doc_id") or ""
                decision = _await_fallback_decision(
                    doc_key, (ocr or {}).get("model") or "",
                    _LAST_OCR_ERROR.get(doc_key) or "فشل الاتصال بنموذج القراءة في OpenRouter",
                    cancel_ev)
                if decision != "accept":
                    if cancel_ev is not None:
                        cancel_ev.set()
                    break
                (ocr or {})["engine"] = "local"
                _set_meta(doc_key, ocr_fallback="local")
                try:
                    Path(tmp).write_bytes(pix.tobytes("png"))
                    read = _ocr_png(tmp, ocr)
                finally:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
            if cancel_ev is not None and cancel_ev.is_set():
                # أُسقطت الصفحة قيد القراءة بالإيقاف الفوري: لا تُحسب معالَجة
                break
            if read:
                band = _footnote_band_text(page, read, dpi, ocr)
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
    ocr = {"engine": meta.get("ocr_engine") or "local",
           "model": meta.get("ocr_model") or "", "doc_id": doc_id}
    scope = _norm_scope(meta.get("scope"))
    multi = len(volumes) > 1
    totals = [_count_pages(Path(v.get("file_path") or "")) for v in volumes]
    onlys = [_scope_only(scope, vi + 1, totals[vi]) for vi in range(len(volumes))]
    sel = [totals[vi] if onlys[vi] is None else len(onlys[vi]) for vi in range(len(volumes))]
    done_before = sum(sel[:start_volume])
    prev_pages = int(meta.get("pages") or 0)
    cancel_ev = _CANCEL_EVENTS.get(doc_id)
    if cancel_ev is None:
        cancel_ev = threading.Event()
        _CANCEL_EVENTS[doc_id] = cancel_ev
    state = {"done": done_before, "new": 0}
    def _tick():
        state["done"] += 1
        state["new"] += 1
        _set_meta(doc_id, page=state["done"])
    _set_meta(doc_id, status="converting", pages=sum(sel), page=done_before,
              error="", started=int(time.time()))
    parts: list[str] = []
    ocr_missing = False
    cancelled = False
    try:
        if ocr.get("engine") == "openrouter" and str(ocr.get("model") or "").endswith(":batch"):
            # نماذج :batch لا تُقرأ بالتحويل الفوري أصلًا: التنبيه قبل أي تحويل
            decision = _await_fallback_decision(
                doc_id, ocr.get("model") or "",
                "نماذج اللاحقة :batch لا تعمل عبر التحويل المباشر الفوري؛ تحتاج واجهة Batch غير المتزامنة التي تُسلّم النتائج بعد ساعات",
                cancel_ev)
            if decision == "accept":
                ocr["engine"] = "local"
                _set_meta(doc_id, ocr_fallback="local")
            else:
                raise _ConversionCancelled()
        for vi in range(start_volume, len(volumes)):
            if cancel_ev.is_set():
                raise _ConversionCancelled()
            volumes[vi]["pages"] = totals[vi]
            if onlys[vi] is not None and not onlys[vi]:
                _set_meta(doc_id, volumes=volumes)
                continue
            vparts, n, miss = _convert_one(
                Path(volumes[vi].get("file_path") or ""), _tick, dpi, onlys[vi], ocr, cancel_ev)
            ocr_missing = ocr_missing or miss
            if vparts:
                if multi:
                    parts.append(f"[الجزء {vi + 1}]")
                parts.extend(vparts)
            _set_meta(doc_id, volumes=volumes)
    except _ConversionCancelled:
        cancelled = True
    except Exception as exc:
        _set_meta(doc_id, status="error", error=str(exc)[:300], finished=int(time.time()))
        _CANCEL_EVENTS.pop(doc_id, None); _ACTIVE.pop(doc_id, None)
        return
    if cancel_ev.is_set():
        cancelled = True
    if scope and not cancelled and start_volume == 0 and state["done"] == 0:
        _set_meta(doc_id, status="error", finished=int(time.time()),
                  error="النطاق المحدد خارج صفحات الوثيقة: لم تُحوَّل أي صفحة")
        _CANCEL_EVENTS.pop(doc_id, None); _ACTIVE.pop(doc_id, None)
        return
    text_path = Path(meta.get("text_path") or "")
    text_path.parent.mkdir(parents=True, exist_ok=True)
    new_text = "\n\n".join(parts).strip()
    if start_volume > 0 and text_path.exists():
        old = text_path.read_text(encoding="utf-8")
        full = (old.rstrip() + "\n\n" + new_text).strip() if new_text else old
    elif cancelled and not new_text and text_path.exists():
        # إيقاف قبل أول صفحة في إعادة تحويل: يبقى النص السابق كما هو
        full = text_path.read_text(encoding="utf-8")
    else:
        full = new_text
    text_path.write_text(full, encoding="utf-8")
    final_pages = state["done"] if start_volume == 0 else prev_pages + state["new"]
    kw = {"status": "cancelled" if cancelled else "done", "chars": len(full),
          "pages": final_pages, "page": final_pages,
          "finished": int(time.time()), "volumes": volumes}
    if cancelled:
        kw["note"] = f"أُوقف التحويل يدويًا بعد {state['new']} صفحة في هذه الجولة (حُفظ ما تمّ، وأعد التحويل للاستكمال)"
    if ocr_missing:
        kw["note"] = "بعض الصفحات المصوّرة لم تُقرأ (تحقق من محرك القراءة المختار: المحلي خاص بنظام Mac، وعلى ويندوز اختر نموذج OpenRouter)"
    _set_meta(doc_id, **kw)
    _CANCEL_EVENTS.pop(doc_id, None); _ACTIVE.pop(doc_id, None)


def convert_document(doc_id: str) -> None:
    """تحويل الوثيقة نصًا في خيط خلفي مع تحديث التقدم في السجل."""
    _convert_volumes(doc_id, 0)


def _apply_ocr_meta(kw: dict, ocr) -> None:
    """حفظ اختيار محرك القراءة في بيانات الوثيقة ومفتاحه في الذاكرة."""
    if isinstance(ocr, dict) and ocr.get("engine") in ("local", "openrouter"):
        kw["ocr_engine"] = ocr["engine"]
        kw["ocr_model"] = str(ocr.get("model") or "") if ocr["engine"] == "openrouter" else ""


def register_document(owner: str, name: str, saved, dpi=None, scope=None, ocr=None) -> dict:
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
    _apply_ocr_meta(meta, ocr)
    with _LOCK:
        reg = _load_registry()
        reg[doc_id] = meta
        _save_registry(reg)
    if isinstance(ocr, dict):
        set_ocr_runtime(doc_id, str(ocr.get("api_key") or ""))
    threading.Thread(target=convert_document, args=(doc_id,), daemon=True).start()
    return dict(meta)


def reconvert_document(doc_id: str, owner: str, dpi=None, scope="keep", ocr=None) -> bool:
    """إعادة تحويل وثيقة من ملفاتها الأصلية (لالتقاط ما فات بدقة أعلى مثلًا).
    scope: ‏"keep" للإبقاء على نطاقها، أو None لكامل الوثيقة، أو قاموس نطاق."""
    if not get_doc(doc_id, owner):
        return False
    kw = {"status": "queued", "page": 0, "chars": 0, "error": ""}
    if dpi is not None:
        kw["dpi"] = _clamp_dpi(dpi)
    if scope != "keep":
        kw["scope"] = _norm_scope(scope)
    _apply_ocr_meta(kw, ocr)
    _set_meta(doc_id, **kw)
    if isinstance(ocr, dict):
        set_ocr_runtime(doc_id, str(ocr.get("api_key") or ""))
    threading.Thread(target=convert_document, args=(doc_id,), daemon=True).start()
    return True


def append_volumes(doc_id: str, owner: str, saved, dpi=None, scope="keep", ocr=None) -> dict | None:
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
    _apply_ocr_meta(kw, ocr)
    _set_meta(doc_id, **kw)
    if isinstance(ocr, dict):
        set_ocr_runtime(doc_id, str(ocr.get("api_key") or ""))
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


def set_archived(doc_id: str, owner: str, archived: bool) -> bool:
    """أرشفة وثيقة أو استرجاعها من الأرشيف (تبقى ملفاتها ونصها)."""
    if not get_doc(doc_id, owner):
        return False
    _set_meta(doc_id, archived=bool(archived))
    return True


def browse_info(doc_id: str, owner: str) -> dict | None:
    """هيكل الوثيقة للتصفح صفحة بصفحة: أجزاؤها وصفحات كل جزء وأصولها."""
    meta = get_doc(doc_id, owner)
    if not meta:
        return None
    vols = meta.get("volumes") or ([{"file_path": meta.get("file_path"), "pages": meta.get("pages", 0)}] if meta.get("file_path") else [])
    out = []
    for i, v in enumerate(vols, 1):
        fp = v.get("file_path") or ""
        out.append({"volume": i, "pages": int(v.get("pages") or 0),
                    "has_original": bool(fp) and Path(fp).suffix.lower() != ".txt"})
    return {"id": doc_id, "name": meta.get("name", ""), "status": meta.get("status"),
            "scope": meta.get("scope"), "volumes": out}


def volume_file(doc_id: str, owner: str, volume: int) -> Path | None:
    """ملف أصل جزء بعينه لعرض صورته في التصفح."""
    meta = get_doc(doc_id, owner)
    if not meta:
        return None
    vols = meta.get("volumes") or ([{"file_path": meta.get("file_path")}] if meta.get("file_path") else [])
    if 1 <= volume <= len(vols):
        fp = vols[volume - 1].get("file_path")
        if fp and Path(fp).exists():
            return Path(fp)
    return None


def page_text(doc_id: str, owner: str, volume: int, page: int) -> dict:
    """النص المحوَّل لصفحة بعينها من جزء بعينه للمقارنة مع أصلها."""
    info = browse_info(doc_id, owner)
    if not info:
        return {"text": "", "converted": False, "volumes": []}
    meta = get_doc(doc_id, owner)
    body = None
    try:
        text = Path(meta["text_path"]).read_text(encoding="utf-8")
        body = _page_segments(text).get((volume, page))
    except Exception:
        body = None
    info.update({"volume": volume, "page": page,
                 "text": body or "", "converted": body is not None})
    return info


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_FN_MARK = re.compile(r"\(\s*([٠-٩0-9]{1,3})\s*\)|\(\s*([٠-٩0-9]{1,3})(?=[\s،.؛:»\"']|$)")
_FN_START = re.compile(r"^\s*(?:\(\s*([٠-٩0-9]{1,3})\s*\)|([٠-٩0-9]{1,3})\s*[-–.)،:]|([٠-٩0-9]{1,3})\s+)\s*")
_HEADING_LINE = re.compile(r"^\(?\s*(فصل|باب|مسألة|المسألة|تنبيه|فائدة|خاتمة|مقدمة|المبحث|المطلب|القاعدة)\b")


def _fn_entries(fn_lines: list) -> list:
    """حواشي صفحة من سطورها المقروءة: كل مرقّمة مدخل، وما عداها تتمة سابقه."""
    entries: list[str] = []
    for line in fn_lines:
        m = _FN_START.match(line)
        num = None
        if m:
            raw = next((g for g in m.groups() if g), "")
            try:
                num = int(raw.translate(_AR_DIGITS))
            except ValueError:
                num = None
        if m and num is not None and (not entries or num == len(entries) + 1 or num == 1):
            entries.append(line[m.end():].strip())
        elif entries:
            entries[-1] = (entries[-1] + " " + line).strip()
        else:
            entries.append(line)
    return [e for e in entries if e]


def _runs_with_refs(par_text: str, fn_start: int, fn_total: int) -> tuple:
    """مقاطع فقرة بإحالات حواشيها: علامة (ن) المطبوعة في المتن تُستبدل
    بإحالة Word الحقيقية التي يرسمها الباني رقمًا مرتفعًا بين قوسين."""
    runs = []
    pos = 0
    k = fn_start
    for m in _FN_MARK.finditer(par_text):
        if k >= fn_total:
            break
        raw = m.group(1) or m.group(2) or ""
        try:
            num = int(raw.translate(_AR_DIGITS))
        except ValueError:
            continue
        if num != (k - fn_start) + 1 and fn_total > 1:
            continue
        if m.start() > pos:
            runs.append({"t": par_text[pos:m.start()]})
        if runs:
            runs[-1] = {**runs[-1], "fn": k}
        else:
            runs.append({"t": "", "fn": k})
        k += 1
        pos = m.end()
    if pos < len(par_text):
        runs.append({"t": par_text[pos:]})
    if not runs:
        runs.append({"t": par_text})
    return runs, k


def document_export_payload(doc_id: str, owner: str) -> dict | None:
    """حمولة تصدير Word بمحرك طباعة الأبحاث (build_docx_bytes): كتل متن
    وعناوين صفحات وأجزاء، وحواشٍ سفلية حقيقية مرتبطة بأرقامها في المتن،
    ترقيمها يعاد كل صفحة كما في الكتاب المطبوع."""
    meta = get_doc(doc_id, owner)
    if not meta:
        return None
    try:
        text = Path(meta["text_path"]).read_text(encoding="utf-8")
    except Exception:
        return None
    blocks: list[dict] = [{"kind": "title", "runs": [{"t": meta.get("name") or "وثيقة", "b": True}]}]
    footnotes: list[dict] = []
    page_stats: list[tuple] = []
    multi = "[الجزء " in text
    cur_vol = 1
    page_lines: list[str] = []
    page_no = None

    def flush_page():
        nonlocal page_lines, page_no
        if page_no is None:
            page_lines = []
            return
        fn_at = next((i for i, l in enumerate(page_lines) if l.strip() == "——————"), None)
        body = page_lines if fn_at is None else page_lines[:fn_at]
        fn_lines = [] if fn_at is None else page_lines[fn_at + 1:]
        entries = _fn_entries(fn_lines)
        fn_start = len(footnotes)
        for e in entries:
            footnotes.append({"runs": [{"t": e}]})
        blocks.append({"kind": "pageBreak"})
        head = f"صفحة {page_no}" if not multi else f"الجزء {cur_vol} – صفحة {page_no}"
        blocks.append({"kind": "h", "runs": [{"t": head, "b": True}]})
        # دمج سطور القراءة فقرات: سطر العناوين الداخلية يبدأ فقرة جديدة
        paras: list[str] = []
        for line in body:
            s = line.strip()
            if not s:
                continue
            if paras and not _HEADING_LINE.match(s) and not (len(s) < 30 and s.startswith("(") and s.endswith(")")):
                paras[-1] += " " + s
            else:
                paras.append(s)
        page_stats.append((sum(len(p) for p in paras),
                           sum(len(e) for e in entries), len(paras)))
        k = fn_start
        for pi, par in enumerate(paras):
            runs, k = _runs_with_refs(par, k, fn_start + len(entries))
            if pi == len(paras) - 1:
                # حواشٍ لم تُعثر على علاماتها في المتن (شوّهتها القراءة):
                # إحالاتها آخر فقرة الصفحة فلا تضيع
                while k < fn_start + len(entries):
                    runs.append({"t": "", "fn": k})
                    k += 1
            blocks.append({"kind": "p", "runs": runs})
        if not paras and entries:
            runs = []
            k = fn_start
            while k < fn_start + len(entries):
                runs.append({"t": "", "fn": k})
                k += 1
            blocks.append({"kind": "p", "runs": runs})
        page_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        mv = re.fullmatch(r"\[الجزء (\d+)\]", line.strip())
        if mv:
            flush_page()
            page_no = None
            cur_vol = int(mv.group(1))
            blocks.append({"kind": "partTitle", "runs": [{"t": f"الجزء {cur_vol}", "b": True}]})
            continue
        mp = re.fullmatch(r"\[صفحة (\d+)\]", line.strip())
        if mp:
            flush_page()
            page_no = int(mp.group(1))
            continue
        if page_no is not None:
            page_lines.append(line)
    flush_page()
    size = _fit_body_size(page_stats)
    return {
        "styles": {
            "body": {"font": "Traditional Arabic", "size": size, "weight": 400},
            "h": {"font": "Traditional Arabic", "size": min(18, size + 1), "weight": 700},
            "title": {"font": "Traditional Arabic", "size": 22, "weight": 700},
            "fn": {"font": "Traditional Arabic", "size": max(8, round(size * 0.66)), "weight": 400},
        },
        "blocks": blocks,
        "footnotes": footnotes,
        "footnote_restart": "eachPage",
    }


def _fit_body_size(page_stats: list, base: float = 16.0) -> float:
    """أكبر مقاس (حتى 16) تبقى به كل صفحة وثيقة داخل صفحة Word واحدة،
    فيُصغَّر الخط تلقائيًا عند تجاوز حدود الصفحة ولا ينزاح الترتيب.
    نموذج ارتفاع: عرض قابل للطباعة 493 نقطة وارتفاع 717 (A4 بهوامش
    محرك الطباعة)، وعرض الحرف العربي الوسطي 0.42 من المقاس."""
    if not page_stats:
        return base
    import math
    def fits(size: float) -> bool:
        fn_size = max(8.0, size * 0.66)
        for body_chars, fn_chars, n_paras in page_stats:
            body_lines = math.ceil(body_chars * 0.42 * size / 493) if body_chars else 0
            height = body_lines * (1.45 * size) + 3 * n_paras + 34
            if fn_chars:
                fn_lines = math.ceil(fn_chars * 0.42 * fn_size / 493)
                height += fn_lines * (1.45 * fn_size + 2) + 12
            if height > 717 * 0.99:
                return False
        return True
    size = base
    while size > 10 and not fits(size):
        size -= 0.5
    return size


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
