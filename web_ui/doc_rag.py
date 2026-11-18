"""فهرسة دلالية خفيفة (RAG) لوثائق الباحث المرفوعة.

تُقسَّم الوثيقة المحوّلة إلى مقاطع قصيرة منسوبة لجزئها وصفحتها، تُضمّن
بنموذج تضمين عبر OpenRouter (الافتراضي baai/bge-m3، قوي بالعربية ورخيص)،
وتُحفظ المتجهات بجانب نص الوثيقة مصفوفةً مضغوطة (float16) مع فهرس JSON.
البحث بعدها محلي خالص بـ numpy: تشابه جيب التمام في أجزاء الثانية، ويُدمج
مع البحث اللفظي في doc_convert.relevant_context اندماجًا رتبيًا.
المفتاح لا يُحفظ إلا في ذاكرة التشغيل، وبصمة نص الوثيقة في الفهرس تجعله
لاغيًا تلقائيًا إذا أُعيد تحويل الوثيقة بنص مختلف.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import doc_convert as dc

MODEL_DEFAULT = "baai/bge-m3"
BATCH = 64
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150

_RUNTIME_KEYS: dict = {}
_CANCEL: dict = {}
_ACTIVE: dict = {}
_CACHE: dict = {}
_LOCK = threading.Lock()


def set_runtime_key(doc_id: str, api_key: str) -> None:
    """مفتاح OpenRouter لفهرسة وثيقة: في الذاكرة فقط لا في السجل."""
    if api_key:
        _RUNTIME_KEYS[doc_id] = api_key


def _register(doc_id, handle) -> None:
    if doc_id and handle is not None:
        _ACTIVE.setdefault(doc_id, set()).add(handle)


def _unregister(doc_id, handle) -> None:
    if doc_id and doc_id in _ACTIVE:
        _ACTIVE[doc_id].discard(handle)


def request_cancel(doc_id: str, owner: str) -> bool:
    """إيقاف فهرسة جارية: تُجهض دفعة التضمين الحالية ويُبقى ما لم يُفهرس."""
    meta = dc.get_doc(doc_id, owner)
    if not meta or meta.get("rag_status") != "building":
        return False
    ev = _CANCEL.get(doc_id)
    if ev is None:
        ev = threading.Event()
        _CANCEL[doc_id] = ev
    ev.set()
    for handle in list(_ACTIVE.get(doc_id, [])):
        try:
            handle.close()
        except Exception:
            pass
    return True


def _index_paths(meta: dict) -> tuple[Path, Path]:
    text_path = Path(meta.get("text_path") or "")
    base = str(text_path)
    if base.endswith(".txt"):
        base = base[:-4]
    return Path(base + ".rag.json"), Path(base + ".rag.npz")


def remove_index(meta: dict) -> None:
    """حذف ملفي فهرس وثيقة (عند حذفها)."""
    try:
        j, n = _index_paths(meta)
        for p in (j, n):
            try:
                p.unlink()
            except OSError:
                pass
    except Exception:
        pass
    _CACHE.pop((meta or {}).get("id") or "", None)


def make_chunks(text: str) -> list:
    """مقاطع ~٩٠٠ حرف بتداخل يسير، لا يعبر أيٌّ منها حدَّ صفحة: فالنسبة
    للجزء والصفحة دقيقة لتوثيق الجواب."""
    segs = dc._page_segments(text or "")
    vols = sorted({v for v, _ in segs})
    out = []
    for (vol, page) in sorted(segs):
        body = (segs[(vol, page)] or "").strip()
        if not body:
            continue
        start = 0
        while start < len(body):
            piece = body[start:start + CHUNK_CHARS]
            if start + CHUNK_CHARS < len(body):
                cut = piece.rfind("\n")
                if cut > CHUNK_CHARS // 3:
                    piece = piece[:cut]
            piece = piece.strip()
            if len(piece) >= 40:
                out.append({"v": vol, "p": page, "text": piece})
            if start + CHUNK_CHARS >= len(body):
                break
            start += max(200, len(piece) - CHUNK_OVERLAP)
    return out


def _embed(texts: list, model: str, api_key: str, doc_id: str, cancel_ev) -> list:
    """تضمين دفعة نصوص بنموذج OpenRouter، متجهات كما جاءت."""
    if not api_key:
        raise RuntimeError("مفتاح OpenRouter غير مضبوط في الخدمات")
    body = json.dumps({"model": model, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/embeddings",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "HTTP-Referer": "http://localhost:8085",
                 "X-Title": "Almoghni Sharia Engine"})
    resp = urllib.request.urlopen(req, timeout=180)
    _register(doc_id, resp)
    try:
        data = json.loads(resp.read().decode("utf-8"))
    finally:
        _unregister(doc_id, resp)
        try:
            resp.close()
        except Exception:
            pass
    if cancel_ev is not None and cancel_ev.is_set():
        raise RuntimeError("أُوقفت الفهرسة")
    rows = sorted(data.get("data") or [], key=lambda r: r.get("index", 0))
    vecs = [r.get("embedding") or [] for r in rows]
    if len(vecs) != len(texts) or any(not v for v in vecs):
        raise RuntimeError("ردّ نموذج التضمين ناقص أو فارغ")
    return vecs


def build_index(doc_id: str, owner: str, model: str = "") -> None:
    """بناء فهرس الوثيقة الدلالي (يُستدعى في خيط خلفي): يحدّث التقدم في
    سجل الوثيقة rag_* وينتهي done/error/cancelled."""
    import numpy as np
    meta = dc.get_doc(doc_id, owner)
    if not meta:
        return
    model = (model or meta.get("rag_model") or MODEL_DEFAULT).strip() or MODEL_DEFAULT
    key = _RUNTIME_KEYS.get(doc_id, "")
    cancel_ev = _CANCEL.get(doc_id)
    if cancel_ev is None:
        cancel_ev = threading.Event()
        _CANCEL[doc_id] = cancel_ev
    try:
        text = Path(meta["text_path"]).read_text(encoding="utf-8")
    except Exception:
        dc._set_meta(doc_id, rag_status="error", rag_error="تعذرت قراءة نص الوثيقة")
        return
    chunks = make_chunks(text)
    if not chunks:
        dc._set_meta(doc_id, rag_status="error", rag_error="الوثيقة فارغة النص")
        return
    dc._set_meta(doc_id, rag_status="building", rag_model=model,
                 rag_total=len(chunks), rag_done=0, rag_error="")
    vecs: list = []
    try:
        for i in range(0, len(chunks), BATCH):
            if cancel_ev.is_set():
                dc._set_meta(doc_id, rag_status="cancelled")
                return
            batch = [c["text"] for c in chunks[i:i + BATCH]]
            vecs.extend(_embed(batch, model, key, doc_id, cancel_ev))
            dc._set_meta(doc_id, rag_done=min(len(chunks), i + BATCH))
    except Exception as exc:
        if cancel_ev.is_set():
            dc._set_meta(doc_id, rag_status="cancelled")
        else:
            msg = str(exc)[:250]
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    payload = json.loads(exc.read().decode("utf-8", "ignore") or "{}")
                    msg = str((payload.get("error") or {}).get("message") or msg)[:250]
                except Exception:
                    pass
            dc._set_meta(doc_id, rag_status="error", rag_error=msg)
        return
    finally:
        _CANCEL.pop(doc_id, None)
        _ACTIVE.pop(doc_id, None)
    try:
        mat = np.asarray(vecs, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = (mat / norms).astype(np.float16)
        jpath, npath = _index_paths(meta)
        tmp_npz = npath.with_suffix(".tmp.npz")
        np.savez(str(tmp_npz), vecs=mat)
        os.replace(tmp_npz, npath)
        side = {"model": model, "dim": int(mat.shape[1]) if mat.ndim == 2 else 0,
                "count": len(chunks), "chunks": chunks,
                "text_sha": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "created": int(time.time())}
        tmp_json = jpath.with_suffix(".tmp.json")
        tmp_json.write_text(json.dumps(side, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_json, jpath)
        _CACHE.pop(doc_id, None)
        dc._set_meta(doc_id, rag_status="done", rag_chunks=len(chunks),
                     rag_model=model, rag_done=len(chunks), rag_error="")
    except Exception as exc:
        dc._set_meta(doc_id, rag_status="error", rag_error=str(exc)[:250])


def start_build(doc_id: str, owner: str, api_key: str, model: str = "") -> bool:
    """إطلاق بناء الفهرس في خيط خلفي إن لم يكن جاريًا."""
    meta = dc.get_doc(doc_id, owner)
    if not meta or meta.get("status") != "done":
        return False
    if meta.get("rag_status") == "building":
        return False
    set_runtime_key(doc_id, api_key)
    if model:
        dc._set_meta(doc_id, rag_model=model)
    _CANCEL[doc_id] = threading.Event()
    t = threading.Thread(target=build_index, args=(doc_id, owner, model), daemon=True)
    t.start()
    return True


def _load(doc_id: str, owner: str, text: str | None = None):
    """فهرس الوثيقة جاهزًا للبحث (مقاطع + مصفوفة مطبّعة) أو None؛
    بصمة النص تجعل الفهرس لاغيًا بعد إعادة تحويل تغيّر النص."""
    import numpy as np
    meta = dc.get_doc(doc_id, owner)
    if not meta or meta.get("rag_status") != "done":
        return None
    jpath, npath = _index_paths(meta)
    try:
        stamp = npath.stat().st_mtime_ns
        if text is None:
            text = Path(meta["text_path"]).read_text(encoding="utf-8")
    except OSError:
        return None
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cached = _CACHE.get(doc_id)
    if cached and cached[0] == (stamp, text_sha):
        return cached[1]
    try:
        side = json.loads(jpath.read_text(encoding="utf-8"))
        if side.get("text_sha") != text_sha:
            return None
        with np.load(str(npath)) as z:
            mat = z["vecs"].astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        entry = {"chunks": side.get("chunks") or [], "mat": mat / norms,
                 "model": side.get("model") or MODEL_DEFAULT}
    except Exception:
        return None
    if len(entry["chunks"]) != int(mat.shape[0]):
        return None
    _CACHE[doc_id] = ((stamp, text_sha), entry)
    return entry


def ready(doc_id: str, owner: str, text: str | None = None) -> bool:
    return _load(doc_id, owner, text) is not None


def semantic_search(doc_id: str, owner: str, query: str, api_key: str,
                    top: int = 6, text: str | None = None) -> list:
    """أقرب مقاطع الوثيقة دلاليًا إلى السؤال: [{v,p,text,score}] تنازليًا.
    أي فشل (لا فهرس/لا شبكة) يرجع [] ليسقط الاسترجاع على اللفظي وحده."""
    import numpy as np
    entry = _load(doc_id, owner, text)
    if not entry or not (query or "").strip() or not api_key:
        return []
    try:
        qv = _embed([query], entry["model"], api_key, doc_id, None)[0]
    except Exception:
        return []
    q = np.asarray(qv, dtype=np.float32)
    n = float(np.linalg.norm(q))
    if n == 0:
        return []
    scores = entry["mat"] @ (q / n)
    order = np.argsort(-scores)[:max(1, top)]
    out = []
    for i in order:
        if float(scores[i]) <= 0.05:
            continue
        c = entry["chunks"][int(i)]
        out.append({"v": c["v"], "p": c["p"], "text": c["text"],
                    "score": float(scores[i])})
    return out
