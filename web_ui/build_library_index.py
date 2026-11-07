#!/usr/bin/env python3
"""بناء فهرس مكتبة المجتهد (FTS5: نصوص + عناوين أبواب) — مرة واحدة عند أول تشغيل.

تقسيم الكتب على شظايا متوازية (عملية لكل نواة تقريبًا)، كل شظية قاعدة SQLite.
الاستعمال اليدوي:  python3 build_library_index.py [--out DIR] [--workers N]
"""
import argparse, json, os, sqlite3, sys, time
from multiprocessing import Pool

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from library_search import _normalize as normalize  # تطبيع واحد لكل المنظومة

INDEX_DB = os.path.join(_ROOT, "shamela_index.db")


def _load_books():
    con = sqlite3.connect(INDEX_DB)
    con.row_factory = sqlite3.Row
    books = [dict(r) for r in con.execute("SELECT book_id, rel_path FROM books ORDER BY book_id")]
    con.close()
    return books


def _build_shard(args):
    shard_path, books = args
    if os.path.exists(shard_path):
        os.remove(shard_path)
    con = sqlite3.connect(shard_path)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("CREATE VIRTUAL TABLE pages_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, part UNINDEXED, page_num UNINDEXED, seq UNINDEXED, tokenize='unicode61')")
    con.execute("CREATE VIRTUAL TABLE headings_fts USING fts5(text, book_id UNINDEXED, page_id UNINDEXED, tokenize='unicode61')")
    npages = 0
    _src_root = os.environ.get("ALMUJTAHED_FTS_SOURCE_ROOT", "")
    for b in books:
        _clean = str(b["rel_path"]).replace("shamela4_data/", "").strip("/")
        _cands = []
        if _src_root:
            _cands.append(os.path.join(_src_root, _clean))
        _cands += [os.path.join(_ROOT, b["rel_path"]), os.path.join(_ROOT, _clean)]
        bdir = next((c for c in _cands if os.path.exists(os.path.join(c, "pages.jsonl"))), _cands[0])
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


def build(out_dir: str = None, workers: int = None, books: list = None) -> dict:
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
        with Pool(workers) as p:
            counts = p.map(_build_shard, jobs)
        report = {"books": len(books), "pages": sum(counts), "wall_sec": round(time.time() - t0, 1), "shards": len(jobs)}
        with open(os.path.join(out_dir, "build_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False)
        print(f"📚 [FTS] اكتمل بناء الفهرس: {report}")
        return report
    finally:
        if os.path.exists(marker):
            os.remove(marker)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    build(out_dir=a.out, workers=a.workers)
