#!/usr/bin/env python3
"""بناء فهرس مكتبة المغني (FTS5: نصوص + عناوين أبواب) — مرة واحدة عند أول تشغيل.

تقسيم الكتب على شظايا متوازية (عملية لكل عامل)، كل شظية قاعدة SQLite.
المسار السريع (الافتراضي): عمال متكيفة مع الذاكرة، دفعات محدودة الحجم،
إيقاف دمج FTS5 أثناء الإدخال ثم دمج متدرج محدود، وموازنة الشظايا بحجم
ملفات الصفحات. المسار القديم يبقى للرجوع إليه بمفتاح التحويل:
  ALMOGHNI_FTS_LEGACY=1  (أو --legacy في التشغيل اليدوي)
الاستعمال اليدوي:  python3 build_library_index.py [--out DIR] [--workers N]
"""
import argparse, ctypes, json, os, sqlite3, sys, time
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from library_search import _normalize as normalize  # تطبيع واحد لكل المنظومة

INDEX_DB = os.path.join(_ROOT, "shamela_index.db")
BATCH = 5000
MERGE_PAGES = 256


def _load_books():
    con = sqlite3.connect(INDEX_DB)
    con.row_factory = sqlite3.Row
    books = [dict(r) for r in con.execute("SELECT book_id, rel_path FROM books ORDER BY book_id")]
    con.close()
    return books


def _total_ram_gb():
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except (ValueError, OSError, AttributeError):
        pass
    if sys.platform.startswith("win"):
        try:
            class _MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = _MemStatus()
            status.dwLength = ctypes.sizeof(_MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullTotalPhys / 1e9
        except Exception:
            pass
    return 16.0


def _default_workers():
    cpu = os.cpu_count() or 4
    by_ram = max(1, int(_total_ram_gb() // 4))  # عامل لكل ~٤ غيغابايت
    return max(1, min(6, cpu - 1, by_ram))


def _book_dir(rel_path):
    clean = str(rel_path).replace("shamela4_data/", "").strip("/")
    cands = []
    src_root = os.environ.get("ALMOGHNI_FTS_SOURCE_ROOT", "")
    if src_root:
        cands.append(os.path.join(src_root, clean))
    cands += [os.path.join(_ROOT, rel_path), os.path.join(_ROOT, clean)]
    for c in cands:
        if os.path.exists(os.path.join(c, "pages.jsonl")):
            return c
    return cands[0]


def _book_weight(rel_path):
    d = _book_dir(rel_path)
    total = 0
    for name in ("pages.jsonl", "toc.jsonl"):
        try:
            total += os.path.getsize(os.path.join(d, name))
        except OSError:
            pass
    return total


def _balance_by_size(books, workers):
    weighted = sorted(((_book_weight(b["rel_path"]), b) for b in books), key=lambda x: -x[0])
    shards = [[] for _ in range(workers)]
    loads = [0] * workers
    for w, b in weighted:
        i = loads.index(min(loads))
        shards[i].append(b)
        loads[i] += w
    return [s for s in shards if s]


def _build_shard(args):
    shard_path, books = args
    if os.path.exists(shard_path):
        os.remove(shard_path)
    con = sqlite3.connect(shard_path)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("PRAGMA cache_size=-65536")  # ٦٤ ميغابايت لكل عامل كحد أقصى
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA page_size=8192")
    con.execute("CREATE VIRTUAL TABLE pages_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, part UNINDEXED, page_num UNINDEXED, seq UNINDEXED, tokenize='unicode61')")
    con.execute("CREATE VIRTUAL TABLE headings_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, tokenize='unicode61')")
    for table in ("pages_fts", "headings_fts"):
        con.execute(f"INSERT INTO {table}({table}, rank) VALUES('automerge', 0)")
        con.execute(f"INSERT INTO {table}({table}, rank) VALUES('crisismerge', 1000000)")
    npages = 0
    for b in books:
        bdir = _book_dir(b["rel_path"])
        try:
            with open(os.path.join(bdir, "pages.jsonl"), encoding="utf-8") as f:
                batch = []
                for line in f:
                    pg = json.loads(line)
                    txt = normalize(pg.get("body") or "")
                    if txt:
                        batch.append((txt, b["book_id"], pg.get("page_id"), pg.get("part") or "", pg.get("page_num") or 0, pg.get("sequence_num") or 0))
                        npages += 1
                        if len(batch) >= BATCH:
                            con.executemany("INSERT INTO pages_fts VALUES (?,?,?,?,?,?)", batch)
                            batch = []
                if batch:
                    con.executemany("INSERT INTO pages_fts VALUES (?,?,?,?,?,?)", batch)
            toc = os.path.join(bdir, "toc.jsonl")
            if os.path.exists(toc):
                with open(toc, encoding="utf-8") as f:
                    hb = []
                    for line in f:
                        tc = json.loads(line)
                        txt = normalize(tc.get("title_text") or "")
                        if txt:
                            hb.append((txt, b["book_id"], tc.get("page_id")))
                            if len(hb) >= BATCH:
                                con.executemany("INSERT INTO headings_fts VALUES (?,?,?)", hb)
                                hb = []
                    if hb:
                        con.executemany("INSERT INTO headings_fts VALUES (?,?,?)", hb)
        except Exception as ex:
            print(f"[FTS] book fail {b['book_id']}: {ex}", flush=True)
    con.commit()
    for table in ("pages_fts", "headings_fts"):
        for _ in range(10000):
            before = con.total_changes
            con.execute(f"INSERT INTO {table}({table}, rank) VALUES('merge', ?)", (MERGE_PAGES,))
            if con.total_changes - before < 2:
                break
    con.commit()
    con.close()
    return npages


def build(out_dir: str = None, workers: int = None, books: list = None) -> dict:
    if os.environ.get("ALMOGHNI_FTS_LEGACY") == "1":
        return build_legacy(out_dir=out_dir, workers=workers, books=books)
    out_dir = out_dir or os.path.join(_ROOT, "library_fts")
    workers = workers or _default_workers()
    os.makedirs(out_dir, exist_ok=True)
    marker = os.path.join(out_dir, ".building")
    with open(marker, "w") as f:
        f.write(str(time.time()))
    try:
        books = books if books is not None else _load_books()
        shards = _balance_by_size(books, workers)
        jobs = [(os.path.join(out_dir, f"shard{i}.db"), s) for i, s in enumerate(shards) if s]
        t0 = time.time()
        with Pool(len(jobs)) as p:
            counts = p.map(_build_shard, jobs)
        report = {"books": len(books), "pages": sum(counts), "wall_sec": round(time.time() - t0, 1), "shards": len(jobs)}
        with open(os.path.join(out_dir, "build_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False)
        print(f"📚 [FTS] اكتمل بناء الفهرس: {report}")
        return report
    finally:
        if os.path.exists(marker):
            os.remove(marker)


# ---------------------------------------------------------------------------
# المسار القديم — يبقى كما كان للرجوع إليه بمفتاح ALMOGHNI_FTS_LEGACY=1
# ---------------------------------------------------------------------------

def _build_shard_legacy(args):
    shard_path, books = args
    if os.path.exists(shard_path):
        os.remove(shard_path)
    con = sqlite3.connect(shard_path)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("CREATE VIRTUAL TABLE pages_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, part UNINDEXED, page_num UNINDEXED, seq UNINDEXED, tokenize='unicode61')")
    con.execute("CREATE VIRTUAL TABLE headings_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, tokenize='unicode61')")
    npages = 0
    for b in books:
        bdir = _book_dir(b["rel_path"])
        try:
            with open(os.path.join(bdir, "pages.jsonl"), encoding="utf-8") as f:
                batch = []
                for line in f:
                    pg = json.loads(line)
                    txt = normalize(pg.get("body") or "")
                    if txt:
                        batch.append((txt, b["book_id"], pg.get("page_id"), pg.get("part") or "", pg.get("page_num") or 0, pg.get("sequence_num") or 0))
                        npages += 1
                con.executemany("INSERT INTO pages_fts VALUES (?,?,?,?,?,?)", batch)
            with open(os.path.join(bdir, "toc.jsonl"), encoding="utf-8") as f:
                hb = []
                for line in f:
                    tc = json.loads(line)
                    txt = normalize(tc.get("title_text") or "")
                    if txt:
                        hb.append((txt, b["book_id"], tc.get("page_id")))
                con.executemany("INSERT INTO headings_fts VALUES (?,?,?)", hb)
        except Exception as ex:
            print(f"[FTS] book fail {b['book_id']}: {ex}", flush=True)
    con.commit()
    con.execute("INSERT INTO pages_fts(pages_fts) VALUES('optimize')")
    con.execute("INSERT INTO headings_fts(headings_fts) VALUES('optimize')")
    con.commit()
    con.close()
    return npages


def build_legacy(out_dir: str = None, workers: int = None, books: list = None) -> dict:
    out_dir = out_dir or os.path.join(_ROOT, "library_fts")
    workers = workers or max(1, min(10, (os.cpu_count() or 4) - 1))
    os.makedirs(out_dir, exist_ok=True)
    marker = os.path.join(out_dir, ".building")
    with open(marker, "w") as f:
        f.write(str(time.time()))
    try:
        books = books if books is not None else _load_books()
        shards = [[] for _ in range(workers)]
        for i, b in enumerate(books):
            shards[i % workers].append(b)
        jobs = [(os.path.join(out_dir, f"shard{i}.db"), s) for i, s in enumerate(shards) if s]
        t0 = time.time()
        with Pool(len(jobs)) as p:
            counts = p.map(_build_shard_legacy, jobs)
        report = {"books": len(books), "pages": sum(counts), "wall_sec": round(time.time() - t0, 1), "shards": len(jobs)}
        with open(os.path.join(out_dir, "build_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False)
        print(f"📚 [FTS] اكتمل بناء الفهرس (قديم): {report}")
        return report
    finally:
        if os.path.exists(marker):
            os.remove(marker)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--legacy", action="store_true")
    a = ap.parse_args()
    if a.legacy:
        os.environ["ALMOGHNI_FTS_LEGACY"] = "1"
    build(out_dir=a.out, workers=a.workers)
