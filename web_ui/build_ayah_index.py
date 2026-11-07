#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بناء فهرس مواضع الآيات (ayah_index.db) من فهرس المكتبة FTS.

الطريقة: مسح صفحات كتب التفسير (مواضع الشرح) وكل المكتبة (الاستشهاد)،
استخراج مقاطع ﴿...﴾، ومطابقتها على آيات المصحف بنوافذ خماسية مطبّعة.
الناتج: ayah_loci(surah, ayah, book_id, page_id, part, page_num, kind)
حيث kind = tafsir (كتاب تفسير) أو citation (استشهاد في غير التفسير).
التشغيل: python3 build_ayah_index.py [--out DIR] (قابل للاستئناف).
"""
import glob
import json
import os
import re
import sqlite3
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
from shamela_local_mcp import clean_arabic_text as _norm  # noqa: E402

META_DB = os.path.join(_ROOT, "shamela_index.db")
QURAN_JSON = os.path.join(_HERE, "quran_uthmani.json")
SPAN_RE = re.compile(r"﴿([^﴾]{8,700})﴾")
SURAH_NAMES = ["الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام", "الأعراف", "الأنفال", "التوبة", "يونس", "هود", "يوسف", "الرعد", "إبراهيم", "الحجر", "النحل", "الإسراء", "الكهف", "مريم", "طه", "الأنبياء", "الحج", "المؤمنون", "النور", "الفرقان", "الشعراء", "النمل", "القصص", "العنكبوت", "الروم", "لقمان", "السجدة", "الأحزاب", "سبأ", "فاطر", "يس", "الصافات", "ص", "الزمر", "غافر", "فصلت", "الشورى", "الزخرف", "الدخان", "الجاثية", "الأحقاف", "محمد", "الفتح", "الحجرات", "ق", "الذاريات", "الطور", "النجم", "القمر", "الرحمن", "الواقعة", "الحديد", "المجادلة", "الحشر", "الممتحنة", "الصف", "الجمعة", "المنافقون", "التغابن", "الطلاق", "التحريم", "الملك", "القلم", "الحاقة", "المعارج", "نوح", "الجن", "المزمل", "المدثر", "القيامة", "الإنسان", "المرسلات", "النبأ", "النازعات", "عبس", "التكوير", "الانفطار", "المطففين", "الانشقاق", "البروج", "الطارق", "الأعلى", "الغاشية", "الفجر", "البلد", "الشمس", "الليل", "الضحى", "الشرح", "التين", "العلق", "القدر", "البينة", "الزلزلة", "العاديات", "القارعة", "التكاثر", "العصر", "الهمزة", "الفيل", "قريش", "الماعون", "الكوثر", "الكافرون", "النصر", "المسد", "الإخلاص", "الفلق", "الناس"]


_QMARKS = re.compile(r"[ـً-ٰٟۖ-ۜ۟-۪ۭ-ۿࢠ-ࣵ]")


_FOLDS = [("ذالك", "ذلك"), ("الرحمان", "الرحمن"), ("هاذا", "هذا"), ("هاذه", "هذه"),
          ("لاكن", "لكن"), ("الصلواه", "الصلاة"), ("الزكواه", "الزكاة"), ("الحيواه", "الحياة"),
          ("مشكواه", "مشكاة"), ("ءا", "ا")]


def _qnorm(text):
    """تطبيع آيات المصحف العثماني: الألف الخنجرية والوصلية ألفٌ صريحة (الكتاب
    لا الكتب)، ثم التطبيع العام + إزالة علامات المصحف الخاصة، ثم طيّات رسم
    عثماني/إملائي معروفة تُطبَّق على الطرفين (نص الآية ونص الصفحة)."""
    text = (text or "").replace("ٰ", "ا").replace("ٱ", "ا").replace("‌", "").replace("‍", "")
    text = text.replace("‏", "").replace("‎", "")
    t = " ".join(_QMARKS.sub("", _norm(text)).split())
    for a, b in _FOLDS:
        t = t.replace(a, b)
    t = t.replace("ى", "ي")
    # ألف التنوين العثمانية قد تنفصل رمزًا مستقلًّا («قولًا» ← «قول ا») فتسمّم النوافذ؛ تُدمج بسابقتها
    toks = t.split()
    merged = []
    for tok in toks:
        if tok in ("ا", "ي") and merged:
            merged[-1] += tok
        else:
            merged.append(tok)
    return " ".join(merged)


def load_ayahs():
    d = json.load(open(QURAN_JSON, encoding="utf-8"))
    rows = d.get("quran") or d
    ayahs = []
    win2ayah = {}
    for r in rows:
        s, a, t = int(r["chapter"]), int(r["verse"]), _qnorm(r["text"])
        words = t.split()
        ayahs.append((s, a, t))
        for i in range(max(1, len(words) - 4)):
            w = " ".join(words[i:i + 5])
            if len(w) >= 12:
                win2ayah.setdefault(w, []).append((s, a))
    return ayahs, win2ayah


def match_span_all(span_norm, win2ayah):
    """كل آية تنال أصواتًا كافية داخل المقطع (المقطع الواحد قد يضم آيات متعددة)."""
    words = span_norm.split()
    if len(words) < 4:
        return []
    votes = {}
    for i in range(len(words) - 4):
        w = " ".join(words[i:i + 5])
        for sa in win2ayah.get(w, ()):  # مرشحون من نافذة خماسية
            votes[sa] = votes.get(sa, 0) + 1
    # عتبة لكل آية بحسب طولها داخل المقطع: نافذتان خماسيتان على الأقل أو ربع نوافذها الحاضرة
    return [sa for sa, cnt in votes.items() if cnt >= 2 or (len(words) <= 8 and cnt >= 1)]


def build(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    out_db = os.path.join(out_dir, "ayah_index.db")
    meta = {}
    con = sqlite3.connect(META_DB)
    for r in con.execute("SELECT book_id, category_name_ar, main_author_death_hijri FROM books"):
        meta[r[0]] = (r[1], r[2])
    con.close()
    tafsir_ids = {b for b, (c, _) in meta.items() if c == "التفسير"}
    ayahs, win2ayah = load_ayahs()
    print(f"ayahs={len(ayahs)} windows={len(win2ayah)} tafsir_books={len(tafsir_ids)}", flush=True)

    db = sqlite3.connect(out_db)
    db.execute("CREATE TABLE IF NOT EXISTS ayah_loci (surah INT, ayah INT, book_id INT, page_id INT, part TEXT, page_num INT, kind TEXT, PRIMARY KEY (surah, ayah, book_id, page_id))")
    db.execute("CREATE INDEX IF NOT EXISTS idx_loci_ayah ON ayah_loci (surah, ayah)")
    db.execute("CREATE TABLE IF NOT EXISTS build_meta (k TEXT PRIMARY KEY, v TEXT)")
    done = {r[0] for r in db.execute("SELECT k FROM build_meta WHERE k LIKE 'shard4:%'")} if db.execute("SELECT count(*) FROM build_meta").fetchone()[0] else set()

    shards = sorted(glob.glob(os.path.join(out_dir, "shard*.db"))) or \
        sorted(glob.glob(os.path.join(_ROOT, "exp_fts", "full", "shard*.db")))
    t0 = time.time()
    total_rows = 0
    for shard in shards:
        key = f"shard4:{os.path.basename(shard)}:{os.path.getsize(shard)}"
        if key in done:
            print(f"skip {key}", flush=True)
            continue
        sc = sqlite3.connect(f"file:{shard}?mode=ro", uri=True)
        rows = []
        try:
            cur = sc.execute("SELECT book_id, page_id, part, page_num, text FROM pages_fts WHERE text LIKE '%﴿%'")
            for bid, pid, part, pnum, text in cur:
                if bid not in meta:
                    continue
                for m in SPAN_RE.finditer(text or ""):
                    span = m.group(1) or ""
                    for sa in match_span_all(_qnorm(span), win2ayah):
                        rows.append((sa[0], sa[1], bid, pid, part, pnum,
                                     "tafsir" if bid in tafsir_ids else "citation"))
        except Exception as exc:
            print(f"shard err {shard}: {exc}", flush=True)
        sc.close()
        db.executemany("INSERT OR IGNORE INTO ayah_loci VALUES (?,?,?,?,?,?,?)", rows)
        db.execute("INSERT OR REPLACE INTO build_meta VALUES (?,?)", (key, "1"))
        db.commit()
        total_rows += len(rows)
        print(f"{os.path.basename(shard)}: +{len(rows)} loci (total new {total_rows}) {time.time()-t0:.0f}s", flush=True)
    # ---- مرحلة 2: مطلع الآية في التفاسير فقيرة المراسي ﴿﴾ (كمقاتل وسفيان) ----
    # نوافذ رباعية فريدة لكل آية (من مطلعها وجسمها) تُمسح في صفحات تلك الكتب.
    poor = {r[0] for r in db.execute(
        "SELECT book_id FROM ayah_loci WHERE kind='tafsir' GROUP BY book_id "
        "HAVING count(DISTINCT surah || '-' || ayah) < 300")}
    poor |= (tafsir_ids - {r[0] for r in db.execute("SELECT DISTINCT book_id FROM ayah_loci WHERE kind='tafsir'")})
    if poor:
        from collections import Counter
        win_count: Counter = Counter()
        ayah_windows = {}
        for s, a, t in ayahs:
            words = t.split()
            ws = {" ".join(words[o:o + 4]) for o in range(len(words) - 3)}
            ayah_windows[(s, a)] = ws
            for w in ws:
                win_count[w] += 1
        win2one = {}
        for sa, ws in ayah_windows.items():
            for w in ws:
                if win_count[w] == 1:
                    win2one[w] = sa
        print(f"incipit: poor_tafsir_books={len(poor)} unique_windows={len(win2one)}", flush=True)
        done2 = {r[0] for r in db.execute("SELECT k FROM build_meta WHERE k LIKE 'incipit5:%'")}
        for shard in shards:
            key = f"incipit5:{os.path.basename(shard)}:{os.path.getsize(shard)}"
            if key in done2:
                continue
            sc = sqlite3.connect(f"file:{shard}?mode=ro", uri=True)
            rows = []
            try:
                cur = sc.execute("SELECT book_id, page_id, part, page_num, text FROM pages_fts")
                for bid, pid, part, pnum, text in cur:
                    if bid not in poor or not text:
                        continue
                    words = _qnorm(text).split()
                    found = set()
                    for i in range(len(words) - 3):
                        sa = win2one.get(" ".join(words[i:i + 4]))
                        if sa:
                            found.add(sa)
                    for s, a in found:
                        rows.append((s, a, bid, pid, part, pnum, "tafsir_incipit"))
            except Exception as exc:
                print(f"incipit shard err {shard}: {exc}", flush=True)
            sc.close()
            db.executemany("INSERT OR IGNORE INTO ayah_loci VALUES (?,?,?,?,?,?,?)", rows)
            db.execute("INSERT OR REPLACE INTO build_meta VALUES (?,?)", (key, "1"))
            db.commit()
            print(f"incipit {os.path.basename(shard)}: +{len(rows)} loci {time.time()-t0:.0f}s", flush=True)

    # ---- مرحلة 3: آيات بلا أي موضع بعدُ (٤ كلمات فأكثر) في كل كتب التفسير ----
    covered = {(r[0], r[1]) for r in db.execute("SELECT DISTINCT surah, ayah FROM ayah_loci")}
    missing = [(s, a, t) for s, a, t in ayahs if (s, a) not in covered and len(t.split()) >= 4]
    if missing:
        from collections import Counter as _C
        wc: _C = _C()
        mw = {}
        allw = {}
        for s, a, t in ayahs:
            words = t.split()
            allw[(s, a)] = {" ".join(words[o:o + 4]) for o in range(len(words) - 3)}
            for w in allw[(s, a)]:
                wc[w] += 1
        for s, a, t in missing:
            for w in allw[(s, a)]:
                if wc[w] == 1:
                    mw[w] = (s, a)
        print(f"missing-scan: ayahs={len(missing)} unique_windows={len(mw)}", flush=True)
        done3 = {r[0] for r in db.execute("SELECT k FROM build_meta WHERE k LIKE 'missing5:%'")}
        for shard in shards:
            key = f"missing5:{os.path.basename(shard)}:{os.path.getsize(shard)}"
            if key in done3:
                continue
            sc = sqlite3.connect(f"file:{shard}?mode=ro", uri=True)
            rows = []
            try:
                cur = sc.execute("SELECT book_id, page_id, part, page_num, text FROM pages_fts")
                for bid, pid, part, pnum, text in cur:
                    if bid not in tafsir_ids or not text:
                        continue
                    words = _qnorm(text).split()
                    found = set()
                    for i in range(len(words) - 3):
                        sa = mw.get(" ".join(words[i:i + 4]))
                        if sa:
                            found.add(sa)
                    for s, a in found:
                        rows.append((s, a, bid, pid, part, pnum, "tafsir_incipit"))
            except Exception as exc:
                print(f"missing shard err {shard}: {exc}", flush=True)
            sc.close()
            db.executemany("INSERT OR IGNORE INTO ayah_loci VALUES (?,?,?,?,?,?,?)", rows)
            db.execute("INSERT OR REPLACE INTO build_meta VALUES (?,?)", (key, "1"))
            db.commit()
            print(f"missing {os.path.basename(shard)}: +{len(rows)} loci {time.time()-t0:.0f}s", flush=True)

    # ---- مرحلة 4: مراسي عناوين فهارس التفاسير ﴿﴾ (مقعد الآية ولو فُسّرت مجزأة) ----
    done4 = {r[0] for r in db.execute("SELECT k FROM build_meta WHERE k LIKE 'toc2:%'")}
    for shard in shards:
        key = f"toc2:{os.path.basename(shard)}:{os.path.getsize(shard)}"
        if key in done4:
            continue
        sc = sqlite3.connect(f"file:{shard}?mode=ro", uri=True)
        rows = []
        try:
            cur = sc.execute("SELECT book_id, page_id, text FROM headings_fts WHERE text LIKE '%﴿%'")
            for bid, pid, text in cur:
                if bid not in tafsir_ids or not text:
                    continue
                for m in SPAN_RE.finditer(text):
                    for sa in match_span_all(_qnorm(m.group(1) or ""), win2ayah):
                        rows.append((sa[0], sa[1], bid, pid, None, None, "tafsir"))
        except Exception as exc:
            print(f"toc shard err {shard}: {exc}", flush=True)
        sc.close()
        db.executemany("INSERT OR IGNORE INTO ayah_loci VALUES (?,?,?,?,?,?,?)", rows)
        db.execute("INSERT OR REPLACE INTO build_meta VALUES (?,?)", (key, "1"))
        db.commit()
        print(f"toc {os.path.basename(shard)}: +{len(rows)} loci {time.time()-t0:.0f}s", flush=True)

    # ---- مرحلة 5 (v3): ملء تسلسلي داخل التفاسير الكبيرة ----
    # المرحلة 2 غطّت التفاسير «الفقيرة» فقط؛ هنا نمسح بمطالع فريدة الآياتِ
    # الغائبةَ من كتاب كبير بين مرساين معلومين في السورة نفسها (kind=tafsir_seq)
    targets = {r[0] for r in db.execute(
        "SELECT book_id FROM ayah_loci WHERE kind IN ('tafsir','tafsir_incipit') "
        "GROUP BY book_id HAVING count(DISTINCT surah) >= 40")}
    gaps = {}  # book_id -> {(surah, ayah)} بين أول وآخر مرسى في السورة
    for bid in targets:
        known = {}
        for s, a in db.execute(
                "SELECT surah, ayah FROM ayah_loci WHERE book_id=? AND kind IN ('tafsir','tafsir_incipit')",
                (bid,)):
            known.setdefault(s, set()).add(a)
        miss = set()
        for s, ayahs_known in known.items():
            if len(ayahs_known) < 2:
                continue
            for a in range(min(ayahs_known), max(ayahs_known) + 1):
                if a not in ayahs_known:
                    miss.add((s, a))
        if miss:
            gaps[bid] = miss
    if gaps:
        from collections import Counter as _C5
        wc5: _C5 = _C5()
        aw5 = {}
        for s, a, t in ayahs:
            words = t.split()
            ws = {" ".join(words[o:o + 4]) for o in range(len(words) - 3)}
            ws |= {" ".join(words[o:o + 5]) for o in range(len(words) - 4)}
            aw5[(s, a)] = ws
            for w in ws:
                wc5[w] += 1
        win5 = {}
        need = set()
        for miss in gaps.values():
            need |= miss
        for sa in need:
            for w in aw5.get(sa, ()):
                if wc5[w] == 1:
                    win5[w] = sa
        print(f"seqfill: target_books={len(gaps)} gap_ayahs={len(need)} unique_windows={len(win5)}", flush=True)
        done5 = {r[0] for r in db.execute("SELECT k FROM build_meta WHERE k LIKE 'seqfill1:%'")}
        for shard in shards:
            key = f"seqfill1:{os.path.basename(shard)}:{os.path.getsize(shard)}"
            if key in done5:
                continue
            sc = sqlite3.connect(f"file:{shard}?mode=ro", uri=True)
            rows = []
            try:
                cur = sc.execute("SELECT book_id, page_id, part, page_num, text FROM pages_fts")
                for bid, pid, part, pnum, text in cur:
                    miss = gaps.get(bid)
                    if not miss or not text:
                        continue
                    words = _qnorm(text).split()
                    found = set()
                    for i in range(len(words) - 3):
                        sa = win5.get(" ".join(words[i:i + 4]))
                        if sa is None and i + 5 <= len(words):
                            sa = win5.get(" ".join(words[i:i + 5]))
                        if sa and sa in miss:
                            found.add(sa)
                    for s, a in found:
                        rows.append((s, a, bid, pid, part, pnum, "tafsir_seq"))
            except Exception as exc:
                print(f"seqfill shard err {shard}: {exc}", flush=True)
            sc.close()
            db.executemany("INSERT OR IGNORE INTO ayah_loci VALUES (?,?,?,?,?,?,?)", rows)
            db.execute("INSERT OR REPLACE INTO build_meta VALUES (?,?)", (key, "1"))
            db.commit()
            print(f"seqfill {os.path.basename(shard)}: +{len(rows)} loci {time.time()-t0:.0f}s", flush=True)

    # ---- مرحلة 6 (v3): إسناد سياقي للآيات القصيرة والمكررة ----
    # آيات من 1-3 كلمات (كـ«الم») أو مكررة اللفظ لا بصمة نصية لها؛ تُسند إلى
    # صفحة أقرب مرسى معلوم في السورة نفسها داخل الكتاب، موسومة tafsir_ctx
    # (موضع سياقي بين مرساين، لا مطابقة نصية) ليقرأه الباحث في صفحته.
    ctx_rows = []
    book_surahs = {}
    for bid, s, a, pid, part, pnum in db.execute(
            "SELECT book_id, surah, ayah, page_id, part, page_num FROM ayah_loci "
            "WHERE kind IN ('tafsir','tafsir_incipit','tafsir_seq') AND page_id IS NOT NULL"):
        book_surahs.setdefault((bid, s), {})[a] = (pid, part, pnum)
    ayah_counts = {}
    for s, a, t in ayahs:
        ayah_counts[s] = max(ayah_counts.get(s, 0), a)
    for (bid, s), known in book_surahs.items():
        if len(known) < 2:
            continue
        ks = sorted(known)
        have = set(ks)
        # استيفاء بين مرساين معلومين فقط (لا استقراء خارجهما) وبمسافة محدودة
        for a in range(ks[0], ks[-1] + 1):
            if a in have:
                continue
            nxt = next((k for k in ks if k > a), None)
            prv = next((k for k in reversed(ks) if k < a), None)
            if nxt is None or prv is None or nxt - prv > 30:
                continue
            pid, part, pnum = known[nxt]
            ctx_rows.append((s, a, bid, pid, part, pnum, "tafsir_ctx"))
        # حواف السورة: افتتاحيات/خواتم قبل أول مرسى أو بعد آخره بمسافة ≤15 آية
        # تُسند لصفحة مرسى الحافة نفسه (مطلع قسم السورة في الكتاب)
        first, last = ks[0], ks[-1]
        for a in range(max(1, first - 15), first):
            pid, part, pnum = known[first]
            ctx_rows.append((s, a, bid, pid, part, pnum, "tafsir_ctx"))
        for a in range(last + 1, min(ayah_counts.get(s, last), last + 15) + 1):
            pid, part, pnum = known[last]
            ctx_rows.append((s, a, bid, pid, part, pnum, "tafsir_ctx"))
    db.executemany("INSERT OR IGNORE INTO ayah_loci VALUES (?,?,?,?,?,?,?)", ctx_rows)
    db.commit()
    print(f"ctxfill: +{len(ctx_rows)} contextual loci", flush=True)

    n = db.execute("SELECT count(*) FROM ayah_loci").fetchone()[0]
    ay = db.execute("SELECT count(DISTINCT surah||'-'||ayah) FROM ayah_loci").fetchone()[0]
    db.execute("INSERT OR REPLACE INTO build_meta VALUES ('loci_total', ?)", (str(n),))
    db.commit()
    db.close()
    print(f"DONE loci={n} ayahs_covered={ay}/6236 in {time.time()-t0:.0f}s -> {out_db}", flush=True)


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if not out:
        import library_search
        out = library_search.FTS_DIR
    build(out)
