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
_STATE = {"jpype": None, "reader": None, "searcher": None, "sf": None, "root": None,
          "executor": None}

# --- طبقة التوسيع (1.10.270): الجسر كان ينهار تحت التوازي العالي لثلاث علل:
# (1) كل نتيجة تفتح اتصال SQLite ومسح مجلد جديدًا في _part_page،
# (2) مثال StoredFields واحد مشترك يفسد فكّ ضغطه تحت التزامن (DataFormatException)،
# (3) لا ذاكرة للبحوث المتكررة بين الوكلاء والجولات.
_PAGE_TABLES: dict = {}          # their_id -> {seq: (part, page)}
_PAGE_TABLE_ORDER: list = []     # LRU أسماء الكتب المحمّلة
_PAGE_TABLE_MAX = 96
_DB_PATHS: dict = {}             # their_id -> مسار قاعدة الكتاب عندهم
_T2O = {"sig": None, "inv": {}}
from collections import OrderedDict as _OD
_RESULT_CACHE: "_OD" = _OD()     # مفتاح البحث -> النتيجة
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 256


def _their2our(id_map: dict) -> dict:
    sig = (len(id_map), id(id_map))
    if _T2O["sig"] != sig:
        _T2O["inv"] = {v: k for k, v in id_map.items()}
        _T2O["sig"] = sig
    return _T2O["inv"]


def _book_db_path(tid: int):
    if tid in _DB_PATHS:
        return _DB_PATHS[tid]
    import shamela_link as SL
    _dbd = SL.data_database_dir()
    found = next(iter(__import__("glob").glob(
        str(_dbd / "book" / "*" / f"{tid}.db"))), None) if _dbd else None
    _DB_PATHS[tid] = found
    return found


def _page_table(tid: int) -> dict:
    """جدول صفحات الكتاب كله بقضية واحدة، يُحمَّل مرة ويُخزَّن (LRU)."""
    tab = _PAGE_TABLES.get(tid)
    if tab is not None:
        return tab
    tab = {}
    book_db = _book_db_path(tid)
    if book_db:
        try:
            con = sqlite3.connect(f"file:{book_db}?mode=ro", uri=True)
            for pid, part, pnum in con.execute("SELECT id, part, page FROM page"):
                tab[int(pid)] = (str(part or ""), int(pnum or 0))
            con.close()
        except Exception:
            tab = {}
    _PAGE_TABLES[tid] = tab
    _PAGE_TABLE_ORDER.append(tid)
    while len(_PAGE_TABLE_ORDER) > _PAGE_TABLE_MAX:
        _PAGE_TABLES.pop(_PAGE_TABLE_ORDER.pop(0), None)
    return tab


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
    """فتح قارئ فهرس الشاملة (مرة واحدة، ويُجدَّد عند تغيّر المقاطع).
    مصدر الفهرس: مرآتنا الداخلية إن اكتملت، وإلا تثبيت الشاملة نفسه؛
    والـ JRE/Lucene يُستعاران دائمًا من تثبيت الشاملة."""
    import shamela_link as SL
    app_root = SL.find_shamela_root()
    db_dir = SL.data_database_dir()
    if not app_root or not db_dir:
        return None
    store = db_dir / "store" / "page"
    if not store.exists():
        return None
    with _LOCK:
        if _STATE["reader"] is not None and _STATE.get("store") == str(store):
            try:
                import jpype
                if _attach():
                    DirectoryReader = jpype.JClass("org.apache.lucene.index.DirectoryReader")
                    newer = DirectoryReader.openIfChanged(_STATE["reader"])
                    if newer is not None:
                        _STATE["reader"] = newer
                        _STATE["searcher"] = _new_searcher(jpype, newer)
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
        jvm, jars = SL._find_jvm_and_jars(app_root)
        root = app_root
        if not jvm or not jars:
            return None
        if not jpype.isJVMStarted():
            # سقف ذاكرة متواضع لكل JVM: مع تعدد جسور العمال لا يجوز أن
            # يستأثر كلٌّ منها بربع ذاكرة الجهاز؛ الفهرس نفسه mmap خارج الكومة.
            jpype.startJVM(jvm, "-Xmx768m", classpath=jars, convertStrings=True)
        _attach()
        Paths = jpype.JClass("java.nio.file.Paths")
        FSDirectory = jpype.JClass("org.apache.lucene.store.FSDirectory")
        DirectoryReader = jpype.JClass("org.apache.lucene.index.DirectoryReader")
        reader = DirectoryReader.open(FSDirectory.open(Paths.get(str(store))))
        _STATE.update({
            "jpype": jpype, "reader": reader,
            "searcher": _new_searcher(jpype, reader),
            "sf": reader.storedFields(), "root": root, "store": str(store),
        })
        return reader


def _new_searcher(jpype, reader):
    """داخل عامل جسر (عملية مستقلة تجيب طلبًا واحدًا كل مرة) نمنح الباحث
    مجمّع خيوط جافا صغيرًا فيتوازى الاستعلام الواحد عبر مقاطع الفهرس.
    في العملية الأم (احتياطي محلي) باحث عادي: المجمّع المشترك أغرق تحت
    تزامن بحوث كثيرة كما أظهر قياس الضغط."""
    IndexSearcher = jpype.JClass("org.apache.lucene.search.IndexSearcher")
    if os.environ.get("ALMUJTAHED_BRIDGE_WORKER") == "1":
        if _STATE.get("executor") is None:
            try:
                Executors = jpype.JClass("java.util.concurrent.Executors")
                _STATE["executor"] = Executors.newFixedThreadPool(4)
            except Exception:
                _STATE["executor"] = None
        if _STATE.get("executor") is not None:
            try:
                return IndexSearcher(reader, _STATE["executor"])
            except Exception:
                pass
    return IndexSearcher(reader)


def warm():
    """تسخين الجسر عند إقلاع الخادم: تشغيل جسور العمال وتسخينها، حتى لا
    تدفع الجولة الأولى كلفة الإقلاع البارد متزامنة مع تزاحم الوكلاء.
    داخل عامل: تسخين محلي فقط."""
    if os.environ.get("ALMUJTAHED_BRIDGE_WORKER") == "1":
        try:
            if _ensure_reader() is None:
                return False
            _ours()
            _search_local("الغناء", mode="words", limit=1)
            return True
        except Exception:
            return False
    if _pool_start():
        return True
    try:
        if _ensure_reader() is None:
            return False
        _ours()
        import shamela_link as SL
        SL.ensure_id_map()
        _search_local("الغناء", mode="words", limit=1)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# تجميع الجسور المتوازية: عمليات عاملة لكل منها JVM وقارئها، توزَّع عليها
# الطلبات (الأقل انشغالًا أولًا) وتُجمع الأجوبة. الفهرس واحد للقراءة فقط،
# فلا تجزئة ولا دمج نتائج — كل جسر يرى الفهرس كاملًا ويجيب عن طلبه كاملًا.
# ---------------------------------------------------------------------------
import atexit as _atexit
import queue as _queue
import subprocess as _subprocess
import tempfile as _tempfile

_POOL = {"workers": [], "lock": threading.Lock(), "started": False}
try:
    _POOL_N = int(os.environ.get("ALMUJTAHED_BRIDGE_WORKERS", "3") or 3)
except Exception:
    _POOL_N = 3


class _BridgeWorker:
    def __init__(self, idx: int):
        self.idx = idx
        self.busy = 0
        self.lock = threading.Lock()
        self.resp: "_queue.Queue" = _queue.Queue()
        self.proc = None
        self._spawn()

    def _spawn(self):
        env = dict(os.environ)
        env["ALMUJTAHED_BRIDGE_WORKER"] = "1"
        log_path = Path(_tempfile.gettempdir()) / f"almujtahed-bridge-{self.idx}.log"
        try:
            err = open(log_path, "ab")
        except Exception:
            err = _subprocess.DEVNULL
        self.proc = _subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve().parent / "shamela_bridge_worker.py")],
            stdin=_subprocess.PIPE, stdout=_subprocess.PIPE, stderr=err,
            env=env, text=True, encoding="utf-8", bufsize=1)

        def _pump():
            try:
                for line in self.proc.stdout:
                    self.resp.put(line)
            except Exception:
                pass
            self.resp.put(None)  # علامة موت العامل

        threading.Thread(target=_pump, daemon=True, name=f"bridge-pump-{self.idx}").start()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def request(self, payload: dict, timeout: float = 300.0) -> dict:
        with self.lock:
            if not self.alive():
                self._spawn()
            self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
            line = self.resp.get(timeout=timeout)
            if line is None:
                raise RuntimeError("bridge worker died")
            return json.loads(line)

    def kill(self):
        try:
            if self.proc is not None:
                self.proc.kill()
        except Exception:
            pass


def _pool_start() -> bool:
    """تشغيل عمال الجسور مرة واحدة + نبض تسخين لكل عامل. False إن تعذّر."""
    if _POOL_N <= 0 or os.environ.get("ALMUJTAHED_BRIDGE_WORKER") == "1":
        return False
    with _POOL["lock"]:
        if _POOL["started"]:
            return bool(_POOL["workers"])
        _POOL["started"] = True
        try:
            _POOL["workers"] = [_BridgeWorker(i) for i in range(_POOL_N)]
        except Exception:
            _POOL["workers"] = []
            return False

        def _shutdown():
            for w in _POOL["workers"]:
                w.kill()

        _atexit.register(_shutdown)
    ok = 0
    for w in _POOL["workers"]:
        try:
            if w.request({"ping": 1}, timeout=180).get("pong"):
                ok += 1
        except Exception:
            pass
    if ok:
        print(f"🌉 [Bridge Pool] {_POOL_N} جسور شاملة متوازية جاهزة (أجاب {ok})", flush=True)
    return ok > 0


def _pool_route(payload: dict) -> dict:
    with _POOL["lock"]:
        workers = [w for w in _POOL["workers"] if w.alive()]
        if not workers:
            workers = _POOL["workers"]
        w = min(workers, key=lambda x: x.busy)
        w.busy += 1
    try:
        return w.request(payload)
    finally:
        with _POOL["lock"]:
            w.busy -= 1


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


def _id_map_cached() -> dict:
    """خريطة الهوية تُقرأ من قرصها مرة وتُجدَّد ببصمة زمن الملف فقط؛ كانت
    تُقرأ وتُحلَّل كاملة مع كل بحث فصارت ضريبة ثابتة حتى على ضربات الذاكرة."""
    import shamela_link as SL
    try:
        sig = SL._id_map_file().stat().st_mtime_ns
    except Exception:
        sig = None
    if _STATE.get("idmap") is not None and _STATE.get("idmap_sig") == sig:
        return _STATE["idmap"]
    m = SL.ensure_id_map()
    _STATE["idmap"] = m
    _STATE["idmap_sig"] = sig
    return m


def _search_local(query, mode="phrase", death_max=None, death_min=None, categories=None,
                  book_ids=None, include_alive=False, limit=10):
    """التنفيذ المحلي المباشر في فهرس الشاملة (JVM هذه العملية)."""
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
    id_map = _id_map_cached()  # {our_id(str): their_id}

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

    def _run_search():
        # StoredFields طازج لكل استعلام: المثال المشترك الواحد كان يفسد فكّ
        # ضغطه تحت التزامن (DataFormatException) فيسقط بحوثًا كاملة بصمت.
        _sf = _STATE["reader"].storedFields()
        _hits = searcher.search(_full_query("body"), fetch)
        if _hits.totalHits == 0 and mode != "phrase":
            _hits = searcher.search(_full_query("m_body"), fetch)  # جذور صرفية أوسع
        return _hits, _sf

    try:
        hits, sf = _run_search()
    except Exception:
        hits, sf = _run_search()  # محاولة ثانية وحيدة للعابر من أخطاء الإدخال/الإخراج
    their2our = _their2our(id_map)

    def _part_page(tid: int, seq: int):
        return _page_table(tid).get(seq, ("", 0))

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
        body = " ".join(re.sub(r"<[^>]+>", " ", str(doc.get("body") or "")).split())
        # مقطع متمركز حول أول لفظ من ألفاظ البحث لا من مطلع الصفحة
        _at = -1
        for _tok in tokens:
            _i = body.find(_tok)
            if _i >= 0 and (_at < 0 or _i < _at):
                _at = _i
        snippet = body[max(0, _at - 120):(_at + 560)] if _at >= 0 else body[:480]
        out.append({
            "book_id": int(our_id), "shamela_id": tid,
            "title": meta.get("title") or "", "author": meta.get("author") or "",
            "author_death_hijri": death, "category": meta.get("category") or "",
            "rel_path": meta.get("rel_path") or "",
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


def search(query, mode="phrase", death_max=None, death_min=None, categories=None,
           book_ids=None, include_alive=False, limit=10):
    """بحث الجسر: ذاكرة نتائج أولًا، ثم توزيع على جسور العمال المتوازية إن
    قامت، وإلا تنفيذ محلي. أي سقوط من عامل يُبتلع وينفَّذ محليًا."""
    _ckey = (str(query or ""), mode, death_max, death_min,
             tuple(categories or ()), tuple(sorted(int(b) for b in book_ids or [])),
             bool(include_alive), int(limit))
    with _CACHE_LOCK:
        _hit_cache = _RESULT_CACHE.get(_ckey)
        if _hit_cache is not None:
            _RESULT_CACHE.move_to_end(_ckey)
            return {**_hit_cache, "results": [dict(r) for r in _hit_cache["results"]]}
    result = None
    if os.environ.get("ALMUJTAHED_BRIDGE_WORKER") != "1" and _POOL_N > 0:
        if not _POOL["started"]:
            _pool_start()
        if _POOL["workers"]:
            try:
                result = _pool_route({
                    "q": query, "mode": mode, "death_max": death_max,
                    "death_min": death_min, "categories": list(categories or []),
                    "book_ids": [int(b) for b in book_ids or []],
                    "include_alive": bool(include_alive), "limit": int(limit)})
                if not result or result.get("status") != "ok":
                    result = None
            except Exception:
                result = None  # سقوط صامت للمسار المحلي الاحتياطي
    if result is None:
        result = _search_local(query, mode=mode, death_max=death_max,
                               death_min=death_min, categories=categories,
                               book_ids=book_ids, include_alive=include_alive,
                               limit=limit)
    if result.get("status") == "ok":
        with _CACHE_LOCK:
            _RESULT_CACHE[_ckey] = result
            _RESULT_CACHE.move_to_end(_ckey)
            while len(_RESULT_CACHE) > _CACHE_MAX:
                _RESULT_CACHE.popitem(last=False)
        return {**result, "results": [dict(r) for r in result["results"]]}
    return result


def search_headings(query, **kw):
    """عناوين الأبواب: نبحث في المتن المطبّع نفسه (وسوم العناوين داخله)."""
    return search(query, **kw)
