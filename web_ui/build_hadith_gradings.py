#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بناء فهرس أحكام الحديث الخامل (hadith_gradings.db) من فهرس المكتبة FTS.

المسح: صفحات كتب السنة وشروحها والتخريج والعلل وعلوم الحديث؛ تُستخرج جمل
الحكم (تصحيح/تحسين/تضعيف/توثيق رجال) وتُحفظ بمواضعها، فيقرأها hadith_dossier
حتميًا بدل تعدين وقت السؤال. النسبة للحاكم وصنف الحكم يُحسبان وقت القراءة.
التشغيل: python3 build_hadith_gradings.py [--out DIR] (قابل للاستئناف).
"""
import glob
import os
import re
import sqlite3
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)

META_DB = os.path.join(_ROOT, "shamela_index.db")
CATS = ("كتب السنة", "شروح الحديث", "التخريج والأطراف", "العلل والسؤالات الحديثية", "علوم الحديث")
GRADING_RE = re.compile(
    r"(صحّحه|صححه|حسّنه|حسنه|ضعّفه|ضعفه|وثّقه|وثقه|"
    r"إسناده\s+(?:صحيح|حسن|ضعيف|قوي|جيد|ثابت)|إسناد\s+(?:صحيح|حسن|ضعيف)|"
    r"رجاله\s+(?:ثقات|رجال الصحيح|موثقون|رجال الشيخين)|"
    r"حديث\s+(?:صحيح|حسن|ضعيف|حسن صحيح|صحيح الإسناد|ضعيف الإسناد)|"
    r"(?:صحيح|حسن|ضعيف)\s+الإسناد|حسن صحيح|لا بأس بإسناده|إسناده لا بأس به|"
    r"متفق عليه|أخرجه الشيخان|رواه الشيخان|اتفقا على صحته|أجمعوا على صحته|"
    r"سنده\s+(?:صحيح|حسن|قوي)|رجاله رجال الشيخين|ثقات أثبات)")
SENT_SPLIT = re.compile(r"[.\n؛!؟]")


def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    out_db = os.path.join(out_dir, "hadith_gradings.db")
    con = sqlite3.connect(META_DB)
    books = {r[0] for r in con.execute(
        "SELECT book_id FROM books WHERE category_name_ar IN (%s)" % ",".join("?" * len(CATS)), CATS)}
    con.close()
    print(f"hadith books={len(books)}", flush=True)
    db = sqlite3.connect(out_db)
    db.execute("CREATE TABLE IF NOT EXISTS page_gradings (book_id INT, page_id INT, part TEXT, page_num INT, sentence TEXT)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_pg_page ON page_gradings (page_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_pg_book ON page_gradings (book_id)")
    db.execute("CREATE TABLE IF NOT EXISTS build_meta (k TEXT PRIMARY KEY, v TEXT)")
    done = {r[0] for r in db.execute("SELECT v FROM build_meta WHERE k LIKE 'shard:%'")}
    shards = sorted(glob.glob(os.path.join(out_dir, "shard*.db"))) or \
        sorted(glob.glob(os.path.join(_ROOT, "exp_fts", "full", "shard*.db")))
    t0 = time.time()
    for shard in shards:
        key = f"shard:{os.path.basename(shard)}:{os.path.getsize(shard)}"
        if key in done:
            print(f"skip {key}", flush=True)
            continue
        sc = sqlite3.connect(f"file:{shard}?mode=ro", uri=True)
        rows = []
        try:
            cur = sc.execute("SELECT book_id, page_id, part, page_num, text FROM pages_fts")
            for bid, pid, part, pnum, text in cur:
                if bid not in books or not text:
                    continue
                for sent in SENT_SPLIT.split(text):
                    s = sent.strip()
                    if 12 <= len(s) <= 240 and GRADING_RE.search(s):
                        rows.append((bid, pid, part, pnum, s))
        except Exception as exc:
            print(f"shard err {shard}: {exc}", flush=True)
        sc.close()
        db.executemany("INSERT INTO page_gradings VALUES (?,?,?,?,?)", rows)
        db.execute("INSERT OR REPLACE INTO build_meta VALUES (?,?)", (key, "1"))
        db.commit()
        print(f"{os.path.basename(shard)}: +{len(rows)} gradings {time.time()-t0:.0f}s", flush=True)
    n = db.execute("SELECT count(*) FROM page_gradings").fetchone()[0]
    pg = db.execute("SELECT count(DISTINCT page_id) FROM page_gradings").fetchone()[0]
    db.execute("INSERT OR REPLACE INTO build_meta VALUES ('gradings_total', ?)", (str(n),))
    db.commit()
    db.close()
    print(f"DONE gradings={n} pages={pg} in {time.time()-t0:.0f}s -> {out_db}", flush=True)


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if not out:
        import library_search
        out = library_search.FTS_DIR
    build(out)
