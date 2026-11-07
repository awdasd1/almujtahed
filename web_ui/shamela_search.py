#!/usr/bin/env python3
"""بحث مباشر في فهرس Lucene داخل تطبيق الشاملة (المسار الكسول).

قرار المنتج: لا تحويل جماعي ولا فهرس مكرر. نبحث في فهرس الشاملة نفسه
بأدواتهم المدمجة (JRE + Lucene عبر JPype)، والكتاب يُحوَّل إلى صيغتنا
عند أول لمس له فقط (قراءة/تحقق) عبر shamela_link.extract — فيتراكم
عندنا مع الوقت ما تلمسه البحوث فعلًا، ونبقى خفافًا عند التثبيت.

الحقول المستعملة كما هي في فهرسهم: n_body نص مطبّع بمواضع (عبارات
ممكنة)، book_key كلمة رقم الكتاب عندهم، وbook/date قيم رقمية (الكتاب
ووفاة المؤلف) للفلترة. الربط برقمنا عبر خريطة هوية محفوظة يبنيها
shamela_link من مطابقة العناوين.
"""
import json
import os
import re
import sqlite3
import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_LOCK = threading.Lock()
_STATE = {"jpype": None, "reader": None, "searcher": None, "sf": None, "root": None}


def _attach():
    import jpype
    if not jpype.isJVMStarted():
        return False
    try:
        if not jpype.isThreadAttachedToJVM():
            jpype.attachThreadToJVM()
    except Exception:
        pass
    return True


def _ensure_reader():
    """فتح قارئ فهرس الشاملة (مرة واحدة، ويُجدَّد عند تغيّر المقاطع)."""
    import shamela_link as SL
    root = SL.find_shamela_root()
    if not root:
        return None
    store = root / "database" / "store" / "page"
    if not store.exists():
        return None
    with _LOCK:
        if _STATE["reader"] is not None and _STATE["root"] == root:
            try:
                import jpype
                if _attach():
                    DirectoryReader = jpype.JClass("org.apache.lucene.index.DirectoryReader")
                    newer = DirectoryReader.openIfChanged(_STATE["reader"])
                    if newer is not None:
                        _STATE["reader"] = newer
                        _STATE["searcher"] = jpype.JClass("org.apache.lucene.search.IndexSearcher")(newer)
                        _STATE["sf"] = newer.storedFields()
            except Exception:
                pass
            return _STATE["reader"]
        try:
            import jpype  # type: ignore
        except ImportError:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "jpype1"])
            import jpype  # type: ignore
        jvm, jars = SL._find_jvm_and_jars(root)
        if not jvm or not jars:
            return None
        if not jpype.isJVMStarted():
            jpype.startJVM(jvm, classpath=jars, convertStrings=True)
        _attach()
        Paths = jpype.JClass("java.nio.file.Paths")
        FSDirectory = jpype.JClass("org.apache.lucene.store.FSDirectory")
        DirectoryReader = jpype.JClass("org.apache.lucene.index.DirectoryReader")
        reader = DirectoryReader.open(FSDirectory.open(Paths.get(str(store))))
        _STATE.update({
            "jpype": jpype, "reader": reader,
            "searcher": jpype.JClass("org.apache.lucene.search.IndexSearcher")(reader),
            "sf": reader.storedFields(), "root": root,
        })
        return reader


def _bytesref(jpype, s: str):
    return jpype.JClass("org.apache.lucene.util.BytesRef")(jpype.JArray(jpype.JByte)(s.encode("utf-8")))


_OURS_CACHE = None


def _ours() -> dict:
    """{our_id: {title, author, death, category, rel_path}} من كتالوجنا (يُخزَّن)."""
    global _OURS_CACHE
    if _OURS_CACHE is not None:
        return _OURS_CACHE
    import shamela_link as SL
    out = {}
    p = SL._catalog_path()
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        for bid, rel, title, author, death, cat in con.execute(
                "SELECT book_id, rel_path, title_ar, main_author_name_ar,"
                " main_author_death_hijri, category_name_ar FROM books"):
            out[int(bid)] = {"rel_path": str(rel or ""), "title": str(title or ""),
                             "author": str(author or ""), "death": death,
                             "category": str(cat or "")}
        con.close()
    except Exception:
        pass
    _OURS_CACHE = out
    return out


def _book_meta(our_id: int) -> dict:
    return _ours().get(int(our_id)) or {}


def search(query, mode="phrase", death_max=None, death_min=None, categories=None,
           book_ids=None, include_alive=False, limit=10):
    """نفس شكل library_search.search تقريبًا، من فهرس الشاملة مباشرة."""
    reader = _ensure_reader()
    if reader is None:
        return {"status": "error", "message": "shamela lucene unavailable", "results": []}
    import shamela_link as SL
    import shamela_local_mcp as _MCP
    jpype = _STATE["jpype"]
    _attach()
    J = jpype.JClass
    # حقل body عندهم مصطلحاته بتطبيع قريب من تطبيعنا (حذف تشكيل وتوحيد
    # حروف) — نبحث فيه مباشرة، وm_body (جذور صرفية) توسيع عند الجفاف.
    q_text = _MCP.clean_arabic_text(query or "")
    tokens = [re.sub(r"[^\w]", "", t) for t in q_text.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return {"status": "error", "message": "empty query", "results": []}

    Term = J("org.apache.lucene.index.Term")
    Builder = J("org.apache.lucene.search.BooleanQuery$Builder")
    Occur = J("org.apache.lucene.search.BooleanClause$Occur")

    def _build(field):
        b = Builder()
        if mode == "phrase" and len(tokens) > 1:
            PhraseQuery = J("org.apache.lucene.search.PhraseQuery")
            pq = PhraseQuery.Builder()
            for t in tokens:
                pq.add(Term(field, _bytesref(jpype, t)))
            b.add(pq.build(), Occur.MUST)
        elif mode == "any":
            for t in tokens:
                b.add(J("org.apache.lucene.search.TermQuery")(Term(field, _bytesref(jpype, t))), Occur.SHOULD)
            try:
                b.setMinimumNumberShouldMatch(1)
            except Exception:
                pass
        else:  # words
            for t in tokens:
                b.add(J("org.apache.lucene.search.TermQuery")(Term(field, _bytesref(jpype, t))), Occur.MUST)
        return b

    # فلتر نطاق الكتب: أرقامنا → أرقامهم عبر خريطة الهوية
    id_map = SL.ensure_id_map()  # {our_id(str): their_id}

    def _full_query(field):
        bb = _build(field)
        if book_ids:
            fb = Builder()
            any_scope = False
            for oid in book_ids:
                tid = id_map.get(str(oid))
                if tid is not None:
                    fb.add(J("org.apache.lucene.search.TermQuery")(
                        Term("book_key", _bytesref(jpype, str(tid)))), Occur.SHOULD)
                    any_scope = True
            if any_scope:
                bb.add(fb.build(), Occur.FILTER)
        return bb.build()

    searcher = _STATE["searcher"]
    fetch = max(int(limit) * 4, int(limit))
    hits = searcher.search(_full_query("body"), fetch)
    if hits.totalHits == 0 and mode != "phrase":
        hits = searcher.search(_full_query("m_body"), fetch)  # جذور صرفية أوسع
    sf = _STATE["sf"]
    their2our = {v: k for k, v in id_map.items()}

    # بيانات الجزء/الصفحة من قواعد كتبهم عند الحاجة
    page_cache = {}

    def _part_page(tid: int, seq: int):
        key = (tid, seq)
        if key in page_cache:
            return page_cache[key]
        book_db = next(iter(__import__("glob").glob(
            str(SL.find_shamela_root() / "database" / "book" / "*" / f"{tid}.db"))), None)
        part, pnum = "", 0
        if book_db:
            try:
                con = sqlite3.connect(f"file:{book_db}?mode=ro", uri=True)
                row = con.execute("SELECT part, page FROM page WHERE id=?", (seq,)).fetchone()
                con.close()
                if row:
                    part, pnum = str(row[0] or ""), int(row[1] or 0)
            except Exception:
                pass
        page_cache[key] = (part, pnum)
        return part, pnum

    out, seen = [], set()
    for sd in hits.scoreDocs:
        doc = sf.document(int(sd.doc))
        idv = str(doc.get("id") or "")
        if "-" not in idv:
            continue
        tid_s, seq_s = idv.rsplit("-", 1)
        try:
            tid, seq = int(tid_s), int(seq_s)
        except ValueError:
            continue
        our_id = their2our.get(tid)
        if our_id is None:
            continue  # كتاب لا نعرفه عندنا إطلاقًا (لا توأم ولا تسجيل)
        if (our_id, seq) in seen:
            continue
        meta = _book_meta(our_id)
        death = meta.get("death")
        if death_max is not None:
            d = int(death) if str(death or "").isdigit() else 99999
            if d > int(death_max) and not include_alive:
                continue
        if death_min is not None:
            d = int(death) if str(death or "").isdigit() else 99999
            if d < int(death_min):
                continue
        if categories:
            if (meta.get("category") or "") not in categories:
                continue
        seen.add((our_id, seq))
        part, pnum = _part_page(tid, seq)
        body = str(doc.get("body") or "")
        snippet = " ".join(re.sub(r"<[^>]+>", " ", body).split())[:400]
        out.append({
            "book_id": int(our_id), "shamela_id": tid,
            "title": meta.get("title") or "", "author": meta.get("author") or "",
            "author_death_hijri": death, "category": meta.get("category") or "",
            "part": part, "page_num": pnum,
            "page_id": int(our_id) * 1000000 + seq,
            "snippet": snippet, "score": round(float(sd.score), 3),
            "_seq": seq,
        })
        if len(out) >= int(limit):
            break
    return {"status": "ok", "query": query, "mode": mode,
            "count": len(out), "results": out,
            "coverage": {"returned": len(out), "limit": limit,
                         "note": "بحث مباشر في فهرس الشاملة المثبتة (مسار كسول)"}}


def search_headings(query, **kw):
    """عناوين الأبواب: نبحث في المتن المطبّع نفسه (وسوم العناوين داخله)."""
    return search(query, **kw)
