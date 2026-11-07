#!/usr/bin/env python3
"""بحث المكتبة المفهرسة (FTS5) — أدوات MCP من الجيل الثاني.

الفلسفة (على منهج «الفهارس قبل المتون»):
- الفهرس يرشّح المواضع في أجزاء الثانية عبر ٨٥٨٩ كتابًا، والقراءة والمطابقة
  تبقيان من ملفات الكتب عبر shamela_local_mcp.
- سقف الوفاة معامل مرن يختاره الباحث (death_max) وليس ثابتًا: ٥٠٠ أو ١٠٠٠
  أو ١٣٠٠ أو بلا سقف. كتب الأحياء/المجهولين (99999) تُستبعد عند وضع سقف
  ما لم يُطلب شمولها صراحة (include_alive).
"""
import glob
import json
import os
import re
import sqlite3
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
META_DB = os.environ.get("ALMUJTAHED_META_DB", os.path.join(_ROOT, "shamela_index.db"))


def _default_fts_dir() -> str:
    env = os.environ.get("ALMUJTAHED_FTS_DIR")
    if env:
        return env
    # المصدر الحاكم (ملف library_source.txt): shamela → فهرس المستوردة إن وُجد
    try:
        with open(os.path.join(_ROOT, "library_source.txt"), encoding="utf-8") as fh:
            if fh.read().strip().lower() == "shamela":
                cand = os.path.join(_ROOT, "library_fts_shamela")
                if glob.glob(os.path.join(cand, "shard*.db")):
                    return cand
    except OSError:
        pass
    for cand in (os.path.join(_ROOT, "library_fts"), os.path.join(_ROOT, "exp_fts", "full")):
        if glob.glob(os.path.join(cand, "shard*.db")):
            return cand
    return os.path.join(_ROOT, "library_fts")


FTS_DIR = _default_fts_dir()


def index_status() -> dict:
    """حالة الفهرس: جاهز / يُبنى الآن (عند أول تشغيل) / غير مبني."""
    shards = glob.glob(os.path.join(FTS_DIR, "shard*.db"))
    building = os.path.exists(os.path.join(FTS_DIR, ".building"))
    return {"available": bool(shards), "building": building, "shards": len(shards), "dir": FTS_DIR}


_BUILD_STARTED = False


_AYAH_BUILD_STARTED = False


def _ensure_ayah_async() -> None:
    """فهرس الآيات يُبنى في الخلفية عند غيابه (يعتمد على فهرس المكتبة)."""
    global _AYAH_BUILD_STARTED
    if _AYAH_BUILD_STARTED or os.path.exists(os.path.join(FTS_DIR, "ayah_index.db")):
        return
    if not os.path.exists(os.path.join(_HERE, "quran_uthmani.json")):
        return
    _AYAH_BUILD_STARTED = True

    def _run():
        try:
            import build_ayah_index
            build_ayah_index.build(FTS_DIR)
        except Exception as exc:
            print(f"⚠ [AyahIndex] تعذر بناء فهرس الآيات: {exc}")

    import threading as _th
    _th.Thread(target=_run, daemon=True, name="ayah-index-builder").start()
    print("📖 [AyahIndex] بدأ بناء فهرس مواضع الآيات في الخلفية.")


_GRADINGS_BUILD_STARTED = False


def _ensure_gradings_async() -> None:
    """فهرس أحكام الحديث يُبنى في الخلفية عند غيابه."""
    global _GRADINGS_BUILD_STARTED
    if _GRADINGS_BUILD_STARTED or os.path.exists(os.path.join(FTS_DIR, "hadith_gradings.db")):
        return
    _GRADINGS_BUILD_STARTED = True

    def _run():
        try:
            import build_hadith_gradings
            build_hadith_gradings.build(FTS_DIR)
        except Exception as exc:
            print(f"⚠ [GradingsIndex] تعذر بناء فهرس أحكام الحديث: {exc}")

    import threading as _th
    _th.Thread(target=_run, daemon=True, name="gradings-index-builder").start()
    print("📖 [GradingsIndex] بدأ بناء فهرس أحكام الحديث في الخلفية.")


def warm_index_async() -> None:
    """إحماء الفهرس في خيط خلفي: فتح الشظايا وتشغيل استعلامات أولى عند الإقلاع،
    حتى لا يدفع أول وكيل/مستخدم كلفة البدء البارد (خدمة دافئة دائمًا)."""
    def _run():
        try:
            secs = get_index().warm_up()
            print(f"🔥 [FTS] إحماء فهرس المكتبة اكتمل في {secs}s", flush=True)
        except Exception as exc:
            print(f"⚠ [FTS] تعذر إحماء الفهرس: {exc}", flush=True)

    import threading as _th
    _th.Thread(target=_run, daemon=True, name="fts-warmup").start()


def ensure_index_async() -> None:
    """عند غياب الفهرس يُبنى مرة واحدة في خيط خلفي (لا يعطّل إقلاع التطبيق)."""
    global _BUILD_STARTED
    st = index_status()
    if st["available"]:
        _ensure_ayah_async()
        _ensure_gradings_async()
    if st["available"] or st["building"] or _BUILD_STARTED:
        return
    _BUILD_STARTED = True

    def _run():
        try:
            import build_library_index
            build_library_index.build(out_dir=FTS_DIR)
        except Exception as exc:
            print(f"⚠ [FTS] تعذر بناء فهرس المكتبة: {exc}")

    import threading as _th
    _th.Thread(target=_run, daemon=True, name="fts-index-builder").start()
    print("📚 [FTS] فهرس المكتبة غير موجود — بدأ بناؤه في الخلفية (مرة واحدة).")

try:
    from shamela_local_mcp import clean_arabic_text as _normalize
except Exception:  # تشغيل مستقل
    def _normalize(text: str) -> str:
        if not text:
            return ""
        t = re.sub(r"<[^>]+>", " ", text)
        t = re.sub(r"[ً-ٰٟـ]", "", t)
        t = re.sub(r"[إأآا]", "ا", t)
        t = re.sub(r"[ىي]", "ي", t)
        t = t.replace("ة", "ه")
        return " ".join(t.split())

_GEO_CATS = {"البلدان والرحلات", "الأنساب"}
_LEX_CATS = {"الغريب والمعاجم", "كتب اللغة", "النحو والصرف"}
_HEADING_BOOST_PREFIX = ("باب", "فصل", "مساله", "كتاب", "حكم", "في", "ذكر", "حديث", "قوله")


def _match_expr(query: str, mode: str) -> str:
    q = _normalize(query or "")
    if not q:
        return ""
    if mode == "boolean":
        # تمرير منطقي خام بعد تنقية علامات الخطر
        raw = re.sub(r'[;"\']', " ", query)
        raw = re.sub(r"\b(AND|OR|NOT)\b", lambda m: m.group(1), raw, flags=re.I)
        return _normalize(raw) if not re.search(r"\b(AND|OR|NOT)\b", raw, flags=re.I) else raw
    if mode == "phrase":
        return '"' + q.replace('"', " ") + '"'
    if mode == "any":
        return " OR ".join(q.split())
    return " AND ".join(q.split())  # words


class LibraryIndex:
    def __init__(self, fts_dir: str = None, meta_db: str = None):
        self.fts_dir = fts_dir or FTS_DIR
        self.meta_db = meta_db or META_DB
        self.shard_paths = sorted(glob.glob(os.path.join(self.fts_dir, "shard*.db")))
        if not self.shard_paths:
            raise FileNotFoundError(f"no FTS shards in {self.fts_dir}")
        self.meta = {}
        con = sqlite3.connect(self.meta_db)
        for r in con.execute("SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri, category_name_ar FROM books"):
            self.meta[r[0]] = {"title": r[1], "author": r[2], "death": r[3], "category": r[4]}
        con.close()
        self._local = threading.local()

    def _cons(self):
        cons = getattr(self._local, "cons", None)
        if cons is None:
            cons = [sqlite3.connect(f"file:{p}?mode=ro", uri=True) for p in self.shard_paths]
            self._local.cons = cons
        return cons

    # ---------- مرشحات البيانات الوصفية ----------
    def _passes(self, bid, death_max, death_min, categories, include_alive):
        m = self.meta.get(bid)
        if m is None:
            return False
        if categories and m["category"] not in categories:
            return False
        d = m["death"]
        if death_max is not None or death_min is not None:
            if not d or d == 99999:
                return include_alive
            if death_max is not None and d > death_max:
                return False
            if death_min is not None and d < death_min:
                return False
        return True

    def _query_shards(self, table, match, limit, book_ids=None):
        fetch = limit * 4
        in_clause, params_extra = "", []
        if book_ids:
            ids = [int(b) for b in book_ids][:2000]
            in_clause = f" AND book_id IN ({','.join('?' * len(ids))})"
            params_extra = ids
        snip = f"snippet({table},0,'[',']','…',20)" if table == "pages_fts" else "text"
        sql = (f"SELECT book_id, page_id, part, page_num, {snip}, bm25({table}) FROM {table} "
               f"WHERE {table} MATCH ?{in_clause} ORDER BY bm25({table}) LIMIT ?") if table == "pages_fts" else \
              (f"SELECT book_id, page_id, NULL, NULL, text, bm25({table}) FROM {table} "
               f"WHERE {table} MATCH ?{in_clause} ORDER BY bm25({table}) LIMIT ?")
        hits = []
        for con in self._cons():
            try:
                hits.extend(con.execute(sql, [match] + params_extra + [fetch]).fetchall())
            except Exception:
                continue
        hits.sort(key=lambda r: r[5])
        return hits

    def _shape(self, rows, limit, death_max, death_min, categories, include_alive, boost_fn=None):
        out, seen = [], set()
        adj = []
        for r in rows:
            bid = r[0]
            if not self._passes(bid, death_max, death_min, categories, include_alive):
                continue
            score = r[5] - (boost_fn(r) if boost_fn else 0.0)
            adj.append((score, r))
        adj.sort(key=lambda x: x[0])
        for score, r in adj:
            key = (r[0], r[1])
            if key in seen:
                continue
            seen.add(key)
            m = self.meta.get(r[0], {})
            out.append({
                "book_id": r[0], "title": m.get("title"), "author": m.get("author"),
                "author_death_hijri": m.get("death"), "category": m.get("category"),
                "part": r[2], "page_num": r[3], "page_id": r[1],
                "snippet": (r[4] or "")[:400], "score": round(score, 3),
            })
            if len(out) >= limit:
                break
        return out

    def warm_up(self):
        """فتح اتصالات الشظايا وتشغيل استعلامات صغيرة عبر الأدوات الكبرى لتسخين الذاكرة."""
        import time as _time
        t0 = _time.time()
        try:
            self._cons()
            self.search("كسوف الشمس", mode="words", limit=1)
            self.search_headings("القرء", mode="words", limit=1)
            self.tarikh_search("انكسفت الشمس", limit=2)
        except Exception:
            pass
        return round(_time.time() - t0, 2)

    # ---------- الأدوات ----------
    def search(self, query, mode="phrase", death_max=None, death_min=None, categories=None,
               book_ids=None, include_alive=False, limit=10):
        match = _match_expr(query, mode)
        if not match:
            return {"status": "error", "message": "empty query"}
        rows = self._query_shards("pages_fts", match, limit, book_ids)
        results = self._shape(rows, limit, death_max, death_min, categories, include_alive)
        scope_books = len(book_ids) if book_ids else sum(
            1 for bid in self.meta if self._passes(bid, death_max, death_min, categories, include_alive))
        return {"status": "ok", "query": query, "mode": mode, "death_max": death_max,
                "count": len(results), "results": results,
                "coverage": {"returned": len(results), "limit": limit,
                             "books_in_scope": scope_books,
                             "note": "النتائج مرشحات بمقتطفات مرتبة بالصلة، لا إحصاءً كليًا؛ للإحصاء استخدم survey_topic، وللصفر الموثق نطاقًا مغلقًا."}}

    def search_headings(self, query, mode="phrase", death_max=None, death_min=None, categories=None,
                        book_ids=None, include_alive=False, limit=10, demote_lexica=True):
        match = _match_expr(query, mode)
        if not match:
            return {"status": "error", "message": "empty query"}
        rows = self._query_shards("headings_fts", match, limit, book_ids)

        def boost(r):
            m = self.meta.get(r[0], {})
            text = (r[4] or "").strip()
            b = 0.0
            if text.startswith(_HEADING_BOOST_PREFIX):
                b += 1.6
            if m.get("category") in _GEO_CATS:
                b -= 3.0
            elif demote_lexica and m.get("category") in _LEX_CATS:
                b -= 1.2
            return b

        results = self._shape(rows, limit, death_max, death_min, categories, include_alive, boost_fn=boost)
        return {"status": "ok", "query": query, "mode": mode, "death_max": death_max,
                "count": len(results), "results": results}

    def search_batch(self, queries, mode="phrase", death_max=None, death_min=None, categories=None,
                     book_ids=None, include_alive=False, limit_per_query=5):
        qs = [q for q in (queries or []) if q and str(q).strip()][:24]
        groups, merged, seen = [], [], set()
        for q in qs:
            r = self.search(q, mode=mode, death_max=death_max, death_min=death_min,
                            categories=categories, book_ids=book_ids,
                            include_alive=include_alive, limit=limit_per_query)
            groups.append({"query": q, "count": r.get("count", 0), "results": r.get("results", [])})
            for hit in r.get("results", []):
                k = (hit["book_id"], hit["page_id"])
                if k not in seen:
                    seen.add(k)
                    merged.append(hit)
        merged.sort(key=lambda h: h["score"])
        return {"status": "ok", "queries": len(qs), "death_max": death_max,
                "groups": groups, "merged": merged[: limit_per_query * len(qs)]}

    # ---------- ملف موضوع (دوسيه طبقي × مذاهب) ----------
    _DOSSIER_LAYERS = [("حتى 400هـ", None, 400), ("401–700هـ", 401, 700),
                       ("701–1100هـ", 701, 1100), ("بعد 1100هـ", 1101, None)]
    _MADHHAB_CATS = {"حنفي": ["الفقه الحنفي"], "مالكي": ["الفقه المالكي"],
                     "شافعي": ["الفقه الشافعي"], "حنبلي": ["الفقه الحنبلي"],
                     "ظاهري/فقه عام": ["الفقه العام"]}
    _ENCYCLOPEDIA_IDS = [4278, 417, 7747, 7560]  # الكويتية، جمال عبد الناصر (المصرية)، الموسوعة الفقهية، التويجري

    @staticmethod
    def _edition_key(hit):
        t = re.split(r"\s+-\s+|، ت|، ط|\s+ط\s+", (hit.get("title") or ""))[0].strip()
        return t + "|" + (hit.get("author") or "")[:14]

    def dossier_topic(self, topic, per_cell=2, death_max=None):
        """قائمة قراءة مركّبة قبل الحفر: طبقات زمنية أربع × مذاهب أهل السنة
        (الأربعة + الظاهرية/الفقه العام)، بمواضع من الفهرس، وسطر تغطية يوثّق
        كل خلية صفرية بدل إخفائها. death_max سقف الباحث يقصّ الطبقات عنده."""
        topic = (topic or "").strip()
        if not topic:
            return {"status": "error", "message": "empty topic"}
        # مصطلحات تُبحث عند مذهب باسم آخر: التورق اسم حنبلي، وغيرهم يورده في العينة وبيوع الآجال
        aliases = []
        for key, alt in (("التورق", ["بيع العينة", "العينة"]), ("العينة", ["بيع العينة", "التورق"]),
                         ("بيوع الآجال", ["بيع العينة", "العينة"])):
            if key in topic:
                aliases = alt
                break
        cap = max(1, min(int(per_cell or 2), 4))
        fiqh_cats = [c for cats in self._MADHHAB_CATS.values() for c in cats]
        enc_results = []
        for eid in self._ENCYCLOPEDIA_IDS:  # حصة لكل موسوعة بترتيب الاعتماد، لا ترتيب BM25 وحده
            r = self.search(topic, mode="phrase", book_ids=[eid], limit=2)
            if not r.get("results"):
                for alt in aliases:
                    r = self.search(alt, mode="phrase", book_ids=[eid], limit=2)
                    if r.get("results"):
                        break
            enc_results.extend(r.get("results", []))
        enc = {"results": enc_results}
        heads = self.search_headings(topic, mode="phrase", categories=fiqh_cats,
                                     death_max=death_max, limit=8)
        layers_out, zeros, filled = [], [], 0
        for lname, dmin, dmax in self._DOSSIER_LAYERS:
            eff_max = dmax
            if death_max is not None:
                if dmin is not None and dmin > death_max:
                    continue
                eff_max = death_max if dmax is None else min(dmax, death_max)
            cells = {}
            for madhhab, cats in self._MADHHAB_CATS.items():
                alive = (dmax is None and death_max is None)
                r = self.search(topic, mode="phrase", categories=cats, death_min=dmin,
                                death_max=eff_max, include_alive=alive, limit=cap * 3)
                mode_used = "phrase"
                if not r.get("results"):
                    r = self.search(topic, mode="words", categories=cats, death_min=dmin,
                                    death_max=eff_max, include_alive=alive, limit=cap * 3)
                    mode_used = "words"
                if not r.get("results") and len(topic.split()) >= 2:
                    # كلمة الرأس وحدها (العينة في «بيع العينة») تلتقط كتبًا تستعمل الاسم مجردًا
                    r = self.search(topic.split()[-1], mode="words", categories=cats, death_min=dmin,
                                    death_max=eff_max, include_alive=alive, limit=cap * 3)
                    mode_used = "head-word"
                if not r.get("results"):
                    for alt in aliases:  # الاسم الذي يستعمله هذا المذهب للمسألة نفسها
                        r = self.search(alt, mode="phrase", categories=cats, death_min=dmin,
                                        death_max=eff_max, include_alive=alive, limit=cap * 3)
                        if r.get("results"):
                            mode_used = "alias:" + alt
                            break
                        r = self.search(alt, mode="words", categories=cats, death_min=dmin,
                                        death_max=eff_max, include_alive=alive, limit=cap * 3)
                        if r.get("results"):
                            mode_used = "alias:" + alt
                            break
                picked, seen_ed = [], set()
                for h in r.get("results", []):
                    ek = self._edition_key(h)
                    if ek in seen_ed:
                        continue
                    seen_ed.add(ek)
                    picked.append(h)
                    if len(picked) >= cap:
                        break
                if picked:
                    filled += 1
                else:
                    zeros.append(f"{madhhab}/{lname}")
                cells[madhhab] = {"mode": mode_used if picked else None, "hits": picked}
            layers_out.append({"layer": lname, "cells": cells})
        total_cells = sum(len(l["cells"]) for l in layers_out)
        return {"status": "ok", "topic": topic, "death_max": death_max,
                "topic_aliases": aliases,
                "encyclopedia_entries": enc.get("results", []),
                "headings": heads.get("results", []),
                "layers": layers_out,
                "coverage": {"cells_total": total_cells, "cells_filled": filled,
                             "zero_cells_documented": zeros,
                             "scope": "مذاهب أهل السنة: الأربعة + الظاهرية/الفقه العام؛ بلا سقف معاصر إلا بسقف الباحث"},
                "note": "مواضع مرشحة من الفهرس: اقرأ كل صفحة بـget_page وطابق النقل بـverify_quote قبل العزو. الخلية الصفرية موثقة هنا ولا تعني نفي المسألة من كتب المذهب؛ جرّب صياغات وصفية بـsearch_library."}

    # ---------- فهرس الآيات (يقرأ ayah_index.db) ----------
    def ayah_loci(self, surah, ayah, kind="all", limit=40):
        """مواضع آية في التفاسير مرتبة بوفاة المفسر، واستشهاداتها في المكتبة."""
        db_path = os.path.join(self.fts_dir, "ayah_index.db")
        if not os.path.exists(db_path):
            return {"status": "unavailable", "message": "فهرس الآيات يُبنى أو غير موجود بعد."}
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            q = "SELECT book_id, page_id, part, page_num, kind FROM ayah_loci WHERE surah=? AND ayah=?"
            args = [int(surah), int(ayah)]
            if kind == "tafsir":
                q += " AND kind IN ('tafsir','tafsir_incipit','tafsir_seq','tafsir_ctx')"
            elif kind == "citation":
                q += " AND kind='citation'"
            rows = con.execute(q, args).fetchall()
            total_tafsir_books = con.execute(
                "SELECT count(DISTINCT book_id) FROM ayah_loci WHERE surah=? AND ayah=? AND kind IN ('tafsir','tafsir_incipit','tafsir_seq','tafsir_ctx')",
                (int(surah), int(ayah))).fetchone()[0]
            con.close()
        except Exception as exc:
            return {"status": "error", "message": f"تعذر فهرس الآيات: {exc}"}
        out, seen_pg = [], set()
        for bid, pid, part, pnum, k in rows:
            pk = (bid, part, pnum, k)
            if pk in seen_pg:
                continue
            seen_pg.add(pk)
            m = self.meta.get(bid, {})
            out.append({"book_id": bid, "title": m.get("title"), "author": m.get("author"),
                        "author_death_hijri": m.get("death"), "category": m.get("category"),
                        "part": part, "page_num": pnum, "page_id": pid, "kind": k})
        _krank = {"tafsir": 0, "tafsir_incipit": 1, "tafsir_seq": 1, "tafsir_ctx": 2, "citation": 3}
        out.sort(key=lambda h: (_krank.get(h["kind"], 1), h["author_death_hijri"] if h["author_death_hijri"] and h["author_death_hijri"] != 99999 else 99998))
        return {"status": "ok", "surah": int(surah), "ayah": int(ayah),
                "loci": out[: int(limit or 40)],
                "coverage": {"total_loci": len(rows), "tafsir_books_with_locus": total_tafsir_books,
                             "tafsir_books_total": 273,
                             "note": "المواضع من مراسي ﴿﴾ (tafsir) ومن مطلع الآية في التفاسير الخالية منها (tafsir_incipit) ومن ملء تسلسلي بين مرساين (tafsir_seq)؛ وtafsir_ctx موضع سياقي لآية قصيرة أو مكررة اللفظ أُسند لصفحة أقرب مرسى في سورتها بلا مطابقة نصية — اقرأ الصفحة ولا تنقل منه كشاهد نصي."}}

    # ---------- نسب عبارة (أقدم القائلين) ----------
    def attestations(self, phrases, limit_works=12):
        """من قال هذه العبارة وأقدمهم: بحث عباري، طيّ طبعات، ترتيب بالوفيات."""
        phrases = [p for p in (phrases or []) if p and str(p).strip()][:4]
        if not phrases:
            return {"status": "error", "message": "empty phrases"}
        works, cent = {}, {}
        scanned_books = set()
        for ph in phrases:
            r = self.search(ph, mode="phrase", limit=240)
            for h in r.get("results", []):
                scanned_books.add(h["book_id"])
                key = self._edition_key(h)
                d = h.get("author_death_hijri")
                cur = works.get(key)
                if cur is None or (d or 99999) < (cur["author_death_hijri"] or 99999):
                    works[key] = h
                c = ((d - 1) // 100 + 1) if d and d != 99999 else None
                cent[c] = cent.get(c, 0) + 1
        ordered = sorted(works.values(),
                           key=lambda h: (h["author_death_hijri"] if h["author_death_hijri"] and h["author_death_hijri"] != 99999 else 99998))
        # مقدمات المحققين ودراسات الطبعات ليست من متن المؤلف: تُستبعد من «الأقدم» حتى لا تُنسب عبارة حديثة الصياغة لصاحب الكتاب
        _front = ("مقدمة", "مدخل", "تمهيد", "تقديم", "دراسة")
        body_first = [h for h in ordered if not any(w in str(h.get("part") or "") for w in _front)]
        front_n = len(ordered) - len(body_first)
        return {"status": "ok", "phrases": phrases,
                "earliest": (body_first or ordered)[: int(limit_works or 12)],
                "coverage": {"works_found": len(ordered), "books_with_hits": len(scanned_books),
                             "front_matter_excluded_from_earliest": front_n,
                             "by_century": {str(k): v for k, v in sorted(cent.items(), key=lambda kv: (kv[0] is None, kv[0]))},
                             "note": "أقدم ما وُجد فيما أرجعه البحث العباري (٢٤٠ مرشحًا لكل صيغة)؛ ليس حصرًا كليًا، ومقدمات المحققين مستبعدة من الأقدمية."}}

    # ---------- مواضع حديث بأصناف كتب الحديث ----------
    def hadith_loci(self, text, limit=20):
        cats = [("أصول", ["كتب السنة"]), ("شروح", ["شروح الحديث"]),
                ("تخريج", ["التخريج والأطراف", "العلل والسؤالات الحديثية"])]
        groups, seen = {}, set()
        collapsed = 0
        for label, cs in cats:
            r = self.search(text, mode="phrase", categories=cs, limit=int(limit or 20))
            if not r.get("results"):
                r = self.search(text, mode="words", categories=cs, limit=int(limit or 20))
            rows, seen_works = [], set()
            for h in r.get("results", []):
                k = (h["book_id"], h["page_id"])
                if k in seen:
                    continue
                seen.add(k)
                # طيّ طبعات العمل الواحد: أول طبعة ملتقطة تكفي، ولا تزاحم أخواتها
                stem = re.split(r"\s+-\s+|\s+ت\s+|\s+ط\s+", h.get("title") or "")[0].strip()
                if stem in seen_works:
                    collapsed += 1
                    continue
                seen_works.add(stem)
                rows.append(h)
            if label == "أصول":
                def _rank(h):
                    t = h.get("title") or ""
                    r0 = 0 if "صحيح البخاري" in t else (1 if "صحيح مسلم" in t else 2)
                    return (r0, h["author_death_hijri"] if h["author_death_hijri"] and h["author_death_hijri"] != 99999 else 99998)
                rows.sort(key=_rank)  # الصحاح قبل المسانيد والسنن
            else:
                rows.sort(key=lambda h: (h["author_death_hijri"] if h["author_death_hijri"] and h["author_death_hijri"] != 99999 else 99998))
            groups[label] = rows
        return {"status": "ok", "text": text, "groups": groups,
                "editions_collapsed": collapsed,
                "note": "مرشحات نصية لا حكم على الحديث؛ الدرجة من كتب التخريج مقروءة على صفحاتها. طُويت طبعات العمل الواحد إلى أول طبعة ملتقطة، والصحيحان مقدمان في الأصول."}

    # ---------- فهرس قواعد وأشباه (عناوين) ----------
    def qawaid_search(self, query, limit=15):
        cats = ["علوم الفقه والقواعد الفقهية", "أصول الفقه", "الفقه العام"]
        heads = self.search_headings(query, mode="words", categories=cats, limit=int(limit or 15))
        att = self.attestations([query], limit_works=5) if len((query or "").split()) >= 2 else None
        return {"status": "ok", "query": query, "headings": heads.get("results", []),
                "attestation_earliest": (att or {}).get("earliest"),
                "coverage": (att or {}).get("coverage"),
                "note": "عناوين كتب القواعد والأشباه والفروق أولًا؛ اقرأ موضع القاعدة وطابق قبل النقل."}

    # ---------- مركّب مسائل عقدية ----------
    def creed_search(self, query, limit=12):
        cats = ["العقيدة", "الفرق والردود"]
        heads = self.search_headings(query, mode="words", categories=cats, limit=int(limit or 12))
        hits = self.search(query, mode="words", categories=cats, limit=int(limit or 12))
        return {"status": "ok", "query": query, "headings": heads.get("results", []),
                "passages": hits.get("results", []), "coverage": hits.get("coverage"),
                "note": "كتب العقيدة والمقالات بنصوص أصحابها؛ انسب كل قول لقائله بعد قراءة الصفحة، وفرّق بين قول المدرسة ونقل خصومها عنها."}

    # ---------- شجرة موضوعات الفقه (بذرة أبواب × مذاهب) ----------
    _FIQH_TOPICS = [
        ("miyah", "المياه وأقسامها", ["أقسام المياه", "الماء الطهور"]), ("wudu", "الوضوء ونواقضه", ["نواقض الوضوء", "أحكام الوضوء"]),
        ("ghusl", "الغسل وموجباته", ["موجبات الغسل", "أحكام الغسل"]), ("tayammum", "التيمم", ["أحكام التيمم", "شرائط التيمم"]),
        ("hayd", "الحيض والنفاس", ["أحكام الحيض", "أقل الحيض وأكثره"]), ("najasa", "النجاسات وإزالتها", ["إزالة النجاسة", "أقسام النجاسات"]),
        ("adhan", "الأذان والإقامة", ["أحكام الأذان", "مشروعية الأذان"]), ("salah_shurut", "شروط الصلاة وأركانها", ["شروط صحة الصلاة", "أركان الصلاة"]),
        ("sujud_sahw", "سجود السهو", ["سجود السهو", "أحكام السهو في الصلاة"]), ("jamaa", "صلاة الجماعة والإمامة", ["أحكام صلاة الجماعة", "شروط الإمامة"]),
        ("musafir", "صلاة المسافر: القصر والجمع", ["قصر الصلاة في السفر", "الجمع بين الصلاتين"]), ("jumua", "صلاة الجمعة", ["شروط صلاة الجمعة", "أحكام الجمعة"]),
        ("janaza", "صلاة الجنازة وتجهيز الميت", ["صلاة الجنازة", "تغسيل الميت وتكفينه"]), ("qada_fawait", "قضاء الفوائت", ["قضاء الصلوات الفوائت"]),
        ("zakat_mal", "زكاة المال ونصابه", ["نصاب زكاة المال", "أحكام زكاة الذهب والفضة"]), ("zakat_fitr", "زكاة الفطر", ["أحكام زكاة الفطر", "مقدار زكاة الفطر"]),
        ("masarif", "مصارف الزكاة الثمانية", ["مصارف الزكاة", "إعطاء الزكاة للأقارب"]), ("urud", "زكاة عروض التجارة", ["زكاة عروض التجارة"]),
        ("sawm_ruya", "ثبوت رمضان ورؤية الهلال", ["رؤية هلال رمضان", "ثبوت الشهر بالرؤية"]), ("mufsidat", "مفسدات الصوم", ["ما يفسد الصوم", "المفطرات"]),
        ("itikaf", "الاعتكاف", ["أحكام الاعتكاف"]), ("qada_ramadan", "قضاء رمضان وكفارته", ["قضاء صوم رمضان", "كفارة الجماع في رمضان"]),
        ("mawaqit", "مواقيت الحج والعمرة", ["مواقيت الحج", "الإحرام من الميقات"]), ("mahzurat", "محظورات الإحرام", ["محظورات الإحرام", "ما يحرم على المحرم"]),
        ("tawaf", "الطواف والسعي", ["أحكام الطواف", "شروط السعي"]), ("arafa", "الوقوف بعرفة وأيام منى", ["الوقوف بعرفة", "رمي الجمار"]),
        ("hady", "الهدي والفدية", ["أحكام الهدي", "فدية الأذى"]), ("khitba", "الخطبة وأحكامها", ["أحكام الخطبة", "النظر إلى المخطوبة"]),
        ("nikah_arkan", "أركان النكاح والولي والشهود", ["أركان عقد النكاح", "اشتراط الولي في النكاح"]), ("sadaq", "الصداق والمهر", ["أحكام الصداق", "تقدير المهر"]),
        ("shighar", "نكاح الشغار", ["نكاح الشغار"]), ("muta", "نكاح المتعة", ["نكاح المتعة", "تحريم زواج المتعة"]),
        ("maharim", "المحرمات من النساء", ["المحرمات من النساء في النكاح", "الجمع بين الأختين"]), ("uyub", "عيوب النكاح وخيار الفسخ", ["العيوب الموجبة لفسخ النكاح"]),
        ("talaq_sunni", "الطلاق السني والبدعي", ["الطلاق السني والبدعي", "طلاق الحائض"]), ("rajaa", "الرجعة", ["أحكام الرجعة", "إشهاد على الرجعة"]),
        ("ila", "الإيلاء", ["أحكام الإيلاء"]), ("zihar", "الظهار وكفارته", ["أحكام الظهار", "كفارة الظهار"]),
        ("lian", "اللعان", ["أحكام اللعان"]), ("idda", "العدة وأنواعها", ["عدة المطلقة", "عدة المتوفى عنها زوجها"]),
        ("khul", "الخلع", ["أحكام الخلع", "الخلع بغير عوض"]), ("hadana", "الحضانة", ["أحكام الحضانة", "الأحق بالحضانة"]),
        ("nafaqat", "النفقات", ["نفقة الزوجة", "نفقة الأقارب"]), ("ayna", "بيع العينة", ["بيع العينة", "مسألة العينة"]),
        ("tawarruq", "التورق", ["مسألة التورق", "بيع العينة", "العينة"]),
        ("maadum", "بيع المعدوم وما لا يملك", ["بيع المعدوم", "بيع ما لا يملك"]), ("riba", "الربا: الفضل والنسيئة", ["ربا الفضل", "ربا النسيئة"]),
        ("sarf", "الصرف وبيع النقدين", ["أحكام الصرف", "بيع الذهب بالذهب"]), ("salam", "السلم وشروطه", ["عقد السلم", "شروط صحة السلم"]),
        ("rahn", "الرهن", ["أحكام الرهن"]), ("hawala", "الحوالة", ["أحكام الحوالة"]), ("kafala", "الكفالة والضمان", ["أحكام الكفالة", "ضمان الدين"]),
        ("sharika", "الشركة والمضاربة", ["أحكام المضاربة", "أنواع الشركات"]), ("ijara", "الإجارة", ["أحكام الإجارة", "فسخ عقد الإجارة"]),
        ("muzaraa", "المزارعة والمساقاة", ["أحكام المزارعة", "المساقاة"]), ("shufa", "الشفعة", ["أحكام الشفعة"]),
        ("ariya", "العارية والوديعة", ["أحكام العارية", "ضمان الوديعة"]), ("ghasb", "الغصب وضمانه", ["أحكام الغصب", "ضمان المغصوب"]),
        ("luqata", "اللقطة", ["أحكام اللقطة"]), ("shahadat", "الشهادات وأحكامها", ["شروط الشهادة", "شهادة النساء"]),
        ("ayman_qada", "الأيمان في الدعاوى", ["اليمين في الدعوى", "النكول عن اليمين"]), ("iqrar", "الإقرار", ["أحكام الإقرار"]),
        ("zina", "حد الزنا وإثباته", ["حد الزنا", "إثبات الزنا بالإقرار"]), ("qadhf", "حد القذف", ["حد القذف"]),
        ("sariqa", "حد السرقة ونصابها", ["نصاب السرقة", "شروط قطع اليد"]), ("khamr", "حد شرب الخمر", ["حد شارب الخمر"]),
        ("hiraba", "الحرابة وقطع الطريق", ["حد الحرابة", "عقوبة المحاربين"]), ("ridda", "الردة وأحكام المرتد", ["أحكام المرتد", "استتابة المرتد"]),
        ("qisas", "القصاص في النفس والأعضاء", ["القصاص في القتل العمد", "شروط القصاص"]), ("diyat", "الديات ومقاديرها", ["دية القتل الخطأ", "مقدار الدية"]),
        ("aqila", "العاقلة والقسامة", ["تحمل العاقلة الدية", "أحكام القسامة"]), ("ghanaim", "الغنائم والفيء", ["قسمة الغنائم", "أحكام الفيء"]),
        ("jizya", "الجزية وأحكام أهل الذمة", ["أخذ الجزية", "عقد الذمة"]), ("dhabaih", "الذبائح وشروطها", ["شروط الذكاة", "ذكاة ما لا يؤكل"]),
        ("sayd", "الصيد وأحكامه", ["أحكام الصيد", "صيد الكلب المعلم"]), ("atima", "الأطعمة المحرمة والأشربة", ["المحرمات من الأطعمة", "أكل الميتة للمضطر"]),
        ("ayman_nudhur", "الأيمان والنذور وكفارتها", ["كفارة اليمين", "أحكام النذر"]), ("wasiyya", "الوصية وحدودها", ["الوصية للوارث", "الوصية بأكثر من الثلث"]),
        ("faraid", "الفرائض: أصحاب الفروض والعصبات", ["أصحاب الفروض", "التعصيب في الميراث"]), ("hajb", "الحجب في الميراث", ["حجب الحرمان", "حجب النقصان"]),
        ("waqf", "الوقف وأحكامه", ["أحكام الوقف", "شرط الواقف"]), ("taam_qabl_qabd", "بيع الطعام قبل قبضه", ["بيع الطعام قبل قبضه", "بيع ما اشترى قبل القبض"]),
    ]

    def _match_seed(self, query, seeds):
        q = _normalize(query or "")
        best, best_score = None, 0.0
        for item in seeds:
            title, phrases = item[1], item[2]
            for c in [title] + list(phrases):
                cn = _normalize(c)
                if cn and (cn in q or q in cn):
                    score = 2.0
                else:
                    ct, qt = set(cn.split()), set(q.split())
                    score = len(ct & qt) / max(1, len(ct | qt)) if ct and qt else 0.0
                if score > best_score:
                    best, best_score = item, score
        return (best, best_score) if best_score >= 0.34 else (None, best_score)

    def fiqh_topics(self, query=""):
        """موضوعات شجرة الفقه المنسّقة: الموضوع المطابق وعدد مواضعه عند كل مذهب."""
        item, _ = self._match_seed(query, self._FIQH_TOPICS) if query else (None, 0.0)
        out = []
        items = [item] if item else self._FIQH_TOPICS
        for iid, title, phrases in items:
            counts = {}
            for madhhab, cats in self._MADHHAB_CATS.items():
                h = self.search_headings(phrases[0], mode="phrase", categories=cats, limit=1)
                counts[madhhab] = h.get("count", 0)
            if not any(counts.values()):
                # عناوين الأبواب غالبًا باسم الباب مجردًا («كتاب الخلع») لا بصياغة المسألة
                for madhhab, cats in self._MADHHAB_CATS.items():
                    h = self.search_headings(title, mode="phrase", categories=cats, limit=1)
                    counts[madhhab] = h.get("count", 0)
            out.append({"topic_id": iid, "topic": title, "phrases": phrases, "locations_by_madhhab": counts})
        return {"status": "ok", "query": query, "matched": bool(item),
                "topics": out, "seed_total": len(self._FIQH_TOPICS),
                "note": "شجرة موضوعات منسّقة تنمو؛ المواضع التفصيلية بـfiqh_topic_locations، ولكل موضوع غير مفهرس استعمل dossier_topic."}

    def fiqh_topic_locations(self, topic, madhhab=None, per_madhhab=6):
        """مواضع موضوع فقهي موسومة بالمذهب من عناوين أبواب كتب المذاهب نفسها."""
        item, _ = self._match_seed(topic, self._FIQH_TOPICS)
        if not item:
            return {"status": "not_indexed", "query": topic,
                    "indexed_topics": [t for _, t, _ in self._FIQH_TOPICS],
                    "note": "الموضوع ليس في الشجرة بعد؛ استعمل dossier_topic أو fiqh_dossier له."}
        iid, title, phrases = item
        groups = {}
        for mh, cats in self._MADHHAB_CATS.items():
            if madhhab and mh != madhhab and not mh.startswith(str(madhhab)):
                continue
            locs = []
            for ph in phrases:
                h = self.search_headings(ph, mode="phrase", categories=cats, limit=int(per_madhhab or 6))
                locs = h.get("results", [])
                if locs:
                    break
            if not locs:
                h = self.search_headings(phrases[0], mode="words", categories=cats, limit=int(per_madhhab or 6))
                locs = h.get("results", [])
            groups[mh] = [{"book_id": x["book_id"], "title": x["title"], "author": x["author"],
                           "author_death_hijri": x["author_death_hijri"], "part": x["part"],
                           "page_num": x["page_num"], "page_id": x["page_id"], "heading": x["snippet"]}
                          for x in locs]
        return {"status": "ok", "topic_id": iid, "topic": title, "phrases": phrases,
                "locations_by_madhhab": groups,
                "coverage": {k: len(v) for k, v in groups.items()},
                "note": "مواضع من عناوين أبواب كتب كل مذهب؛ اقرأ الصفحة وطابق قبل النقل، والشجرة تنمو موضوعًا موضوعًا."}

    # ---------- فهرس مسائل العقيدة (بذرة منسّقة × مدارس) ----------
    _CREED_ISSUES = [
        ("iman_ziyada", "زيادة الإيمان ونقصانه", ["الإيمان يزيد وينقص"]),
        ("iman_qawl_wa_amal", "الإيمان قول وعمل", ["الإيمان قول وعمل", "الإيمان قول باللسان وعمل"]),
        ("istithna", "الاستثناء في الإيمان", ["أنا مؤمن إن شاء الله", "الاستثناء في الإيمان"]),
        ("kalam_allah", "القرآن كلام الله غير مخلوق", ["القرآن كلام الله غير مخلوق", "كلام الله غير مخلوق"]),
        ("ruya", "رؤية الله يوم القيامة", ["رؤية الله يوم القيامة", "يرون ربهم", "النظر إلى وجه الله"]),
        ("istiwa_wa_uluw", "الاستواء وعلو الله على خلقه", ["الرحمن على العرش استوى", "الله فوق عرشه", "علو الله على خلقه"]),
        ("sifat_khabariyya", "الصفات الخبرية (الوجه واليدان ونحوهما)", ["إثبات صفة اليدين", "صفة الوجه لله", "الصفات الخبرية"]),
        ("qadar_afal", "خلق أفعال العباد والقدر", ["خلق أفعال العباد", "أفعال العباد مخلوقة", "القدر خيره وشره"]),
        ("kabira_takfir", "مرتكب الكبيرة والتكفير", ["حكم مرتكب الكبيرة", "تكفير مرتكب الكبائر"]),
        ("irja", "الإرجاء والمرجئة", ["تعريف الإرجاء", "المرجئة والإيمان"]),
        ("shafaa", "الشفاعة لأهل الكبائر", ["الشفاعة لأهل الكبائر", "شفاعة النبي لأمته"]),
        ("adhab_qabr", "عذاب القبر ونعيمه", ["عذاب القبر ونعيمه", "إثبات عذاب القبر"]),
        ("mizan_hawd_sirat", "الميزان والحوض والصراط", ["الميزان يوم القيامة", "الحوض المورود", "الصراط على متن جهنم"]),
        ("karamat", "كرامات الأولياء", ["كرامات الأولياء", "إثبات كرامات الأولياء"]),
        ("sahaba", "فضل الصحابة وترتيبهم في الفضل", ["تفضيل أبي بكر وعمر", "فضل الصحابة وترتيبهم"]),
        ("sama_taa", "السمع والطاعة لولاة الأمر", ["السمع والطاعة للأئمة", "طاعة ولاة الأمور"]),
        ("ashrat", "أشراط الساعة: الدجال ونزول عيسى", ["خروج الدجال", "نزول عيسى ابن مريم"]),
        ("lafz_quran", "مسألة اللفظ بالقرآن", ["لفظي بالقرآن مخلوق", "اللفظ بالقرآن"]),
        ("janna_nar", "خلق الجنة والنار وبقاؤهما", ["الجنة والنار مخلوقتان", "بقاء الجنة والنار"]),
        ("asma_sifat_tawqif", "أسماء الله وصفاته توقيفية", ["أسماء الله توقيفية", "إثبات أسماء الله وصفاته"]),
        ("islam_iman_farq", "الفرق بين الإسلام والإيمان", ["الفرق بين الإسلام والإيمان", "الإسلام والإيمان إذا اجتمعا افترقا"]),
        ("kalam_harf_sawt", "كلام الله بحرف وصوت مسموع", ["كلام الله بحرف وصوت", "كلام الله مسموع منه"]),
        ("irada_sharia", "إرادة الله الكونية والشرعية", ["الإرادة الكونية والشرعية", "الفرق بين المشيئة والمحبة"]),
        ("hikma_talil", "حكمة الله وتعليل أفعاله", ["أفعال الله معللة بالحكم", "الحكمة والتعليل في أفعال الله"]),
        ("husn_qubh", "التحسين والتقبيح العقليان", ["التحسين والتقبيح العقليان", "حسن الأشياء وقبحها بالعقل"]),
        ("awwal_wajib", "أول واجب على المكلف", ["أول واجب على المكلف", "وجوب النظر على المكلف"]),
        ("iman_muqallid", "إيمان المقلد", ["إيمان المقلد", "حكم إيمان المقلد"]),
        ("waad_waeed", "الوعد والوعيد وخلود أهل الكبائر", ["خلود أهل الكبائر في النار", "الوعد والوعيد عند المعتزلة"]),
        ("imama_khilafa", "الإمامة وثبوت خلافة أبي بكر", ["ثبوت خلافة أبي بكر", "إمامة أبي بكر الصديق"]),
        ("adala_sahaba", "عدالة الصحابة", ["عدالة الصحابة", "الصحابة كلهم عدول"]),
        ("maratib_qadar", "مراتب القدر الأربع", ["مراتب القدر", "العلم والكتابة والمشيئة والخلق"]),
        ("lawh_qalam", "اللوح المحفوظ وكتابة المقادير", ["اللوح المحفوظ", "كتب الله مقادير الخلائق"]),
        ("isma_anbiya", "عصمة الأنبياء", ["عصمة الأنبياء", "تنزيه الأنبياء عن الكبائر والصغائر"]),
        ("isra_miraj", "الإسراء والمعراج ورؤية النبي ربه", ["المعراج يقظة بالروح والجسد", "هل رأى النبي ربه ليلة المعراج"]),
        ("jinn", "الإيمان بالجن والشياطين", ["وجود الجن والشياطين", "الإيمان بالجن"]),
        ("ruh", "حقيقة الروح وخلقها", ["الروح مخلوقة", "حقيقة الروح وماهيتها"]),
        ("atfal_mushrikin", "أطفال المشركين في الآخرة", ["أطفال المشركين", "أولاد المشركين في الآخرة"]),
        ("sihr", "حقيقة السحر وحكم تعلمه", ["حقيقة السحر وتأثيره", "حكم تعلم السحر"]),
        ("kahana", "الكهانة والعرافة وتصديق الكهان", ["إتيان الكهان والعرافين", "تصديق الكهان"]),
        ("tamaim_ruqa", "التمائم والرقى", ["حكم تعليق التمائم", "الرقية الشرعية وشروطها"]),
        ("halaf", "الحلف بغير الله", ["الحلف بغير الله", "من حلف بغير الله فقد أشرك"]),
        ("dhabh_nadhr", "الذبح والنذر لغير الله", ["الذبح لغير الله", "النذر لغير الله"]),
        ("tiyara", "الطيرة والتشاؤم", ["الطيرة شرك", "لا عدوى ولا طيرة"]),
        ("qubur_bina", "زيارة القبور والبناء عليها", ["البناء على القبور", "حكم زيارة النساء للقبور"]),
        ("istighatha_tawassul", "الاستغاثة والتوسل", ["الاستغاثة بالموتى", "التوسل بجاه النبي"]),
        ("wala_bara", "الولاء والبراء", ["الولاء والبراء", "تحريم موالاة الكفار"]),
        ("hukm_bighayr", "الحكم بغير ما أنزل الله", ["الحكم بغير ما أنزل الله", "كفر دون كفر في الحكم"]),
        ("khuruj", "الخروج على الأئمة", ["الخروج على الإمام", "تحريم الخروج على ولاة الأمر"]),
        ("kaff_sahaba", "الكف عما شجر بين الصحابة", ["الكف عما شجر بين الصحابة", "ما وقع بين الصحابة من الفتن"]),
        ("sifat_filiyya", "الصفات الفعلية الاختيارية", ["الصفات الفعلية الاختيارية", "قيام الأفعال الاختيارية بالله"]),
        ("shurut_tawhid", "شروط لا إله إلا الله ونواقض الإسلام", ["شروط لا إله إلا الله", "نواقض الإسلام"]),
        ("malak_bashar", "تفضيل الملائكة والأنبياء", ["تفضيل الملائكة على صالحي البشر", "أيهما أفضل الملائكة أم الأنبياء"]),
        ("khatm_nubuwwa", "ختم النبوة بمحمد ﷺ", ["لا نبي بعدي", "خاتم النبيين"]),
        ("iman_kutub_rusul", "الإيمان بالكتب والرسل", ["الإيمان بالكتب المنزلة", "الإيمان بالرسل والأنبياء"]),
        ("tafdil_anbiya", "التفاضل بين الأنبياء", ["تفضيل بعض الأنبياء على بعض", "لا تفضلوني على يونس"]),
        ("bath_nushur", "البعث والنشور وحشر الأجساد", ["البعث والنشور", "حشر الأجساد يوم القيامة"]),
        ("nafkha", "النفخ في الصور والصعقة", ["النفخ في الصور", "صعقة الخلائق"]),
        ("hisab_jaza", "الحساب والجزاء وتطاير الصحف", ["عرض الأعمال يوم القيامة", "تطاير صحف الأعمال"]),
        ("atfal_muminin", "أطفال المؤمنين في الآخرة", ["أطفال المؤمنين في الجنة", "أولاد المسلمين في الآخرة"]),
        ("sabb_sahaba", "حكم سب الصحابة", ["حكم من سب الصحابة", "تحريم سب الصحابة"]),
        ("takfir_muayyan", "تكفير المعيّن وشروطه", ["تكفير المعين وضوابطه", "موانع التكفير"]),
        ("shirk_asghar", "الشرك الأصغر وكفر دون كفر", ["الشرك الأصغر والرياء", "كفر دون كفر"]),
        ("nifaq", "النفاق الاعتقادي والعملي", ["النفاق الأكبر والأصغر", "النفاق العملي"]),
        ("jahmiyya", "حكم الجهمية", ["كفر الجهمية", "حكم الجهمية عند السلف"]),
        ("isma_samiyyat", "إثبات السمع والبصر وسائر الصفات السمعية", ["إثبات صفة السمع والبصر", "الصفات السمعية"]),
        ("ghadab_rida", "إثبات الغضب والرضا والمحبة لله", ["إثبات صفة الغضب لله", "إثبات محبة الله لعباده"]),
        ("nuzul_ityan", "النزول والمجيء والإتيان", ["نزول الله إلى سماء الدنيا", "يأتي الله يوم القيامة في ظلل"]),
        ("qadam_kursi", "القدم والكرسي والعرش", ["وضع الجبار قدمه في النار", "الكرسي موضع القدمين"]),
        ("awwal_makhluq", "أول المخلوقات: القلم والعرش", ["أول ما خلق الله القلم", "العرش أول المخلوقات"]),
        ("sura_adam", "خلق آدم على الصورة", ["خلق الله آدم على صورته", "مسألة الصورة في الصفات"]),
        ("taklim_musa", "تكليم الله موسى", ["كلم الله موسى تكليما", "سماع موسى كلام الله"]),
        ("qadariyya_jabriyya", "القدرية والجبرية", ["القدرية مجوس هذه الأمة", "الجبرية والقدرية والمرجئة"]),
        ("khawarij", "الخوارج وحكم قتالهم", ["حكم الخوارج", "قتال الخوارج والحرورية"]),
        ("mahdi", "خروج المهدي", ["خروج المهدي في آخر الزمان", "المهدي من أهل البيت"]),
        ("yajuj_dabba", "يأجوج ومأجوج والدابة", ["خروج يأجوج ومأجوج", "خروج دابة الأرض"]),
        ("tulu_shams", "طلوع الشمس من مغربها والدخان", ["طلوع الشمس من مغربها", "الدخان من أشراط الساعة"]),
        ("tasdiq_tarif", "مسمى الإيمان عند المتكلمين: التصديق", ["الإيمان هو التصديق", "مسمى الإيمان عند الأشاعرة"]),
        ("kalam_nafsi", "الكلام النفسي عند الأشاعرة", ["الكلام النفسي", "إثبات الكلام النفسي"]),
        ("ruya_manam", "رؤية الله في المنام", ["رؤية الله في المنام", "رأيت ربي في المنام"]),
        ("huduth_alam", "حدوث العالم", ["حدوث العالم", "إثبات حدوث الأجسام"]),
        ("taklif_mala_yutaq", "تكليف ما لا يُطاق", ["تكليف ما لا يطاق", "جواز تكليف المحال"]),
        ("israr_saghira", "الإصرار على الصغيرة", ["الإصرار على الصغيرة كبيرة", "لا صغيرة مع الإصرار"]),
        ("tawba", "التوبة وقبولها من العصاة", ["قبول توبة العاصي", "التوبة النصوح وشروطها"]),
        ("malaika_khalq", "خلق الملائكة والإيمان بهم", ["خلق الملائكة من نور", "الإيمان بالملائكة وصفاتهم"]),
        ("maqam_mahmud", "المقام المحمود", ["المقام المحمود هو الشفاعة", "تفسير المقام المحمود"]),
        ("barzakh_hayat", "حياة الأنبياء والشهداء في قبورهم", ["الأنبياء أحياء في قبورهم", "حياة الشهداء عند ربهم"]),
        ("fitan_ashrat_kubra", "الفتن وأشراط الساعة الكبرى", ["أشراط الساعة الكبرى", "الفتن قبل قيام الساعة"]),
        ("iman_bilghayb", "الإيمان بالغيب وأركان الإيمان الستة", ["أركان الإيمان الستة", "الإيمان بالغيب"]),
        ("qada_wa_qadar_dua", "الدعاء ورد القضاء", ["الدعاء يرد القضاء", "لا يرد القضاء إلا الدعاء"]),
        ("hubb_lillah", "الحب والبغض في الله من الإيمان", ["الحب في الله من الإيمان", "أوثق عرى الإيمان"]),
        ("dhikr_qalb", "حياة القلوب ومرضها في الإيمان", ["مرض القلب وشكّه", "قسوة القلب وعلاجها"]),
        ("amr_qadar_shar", "الأمر بالمعروف ركن في مسائل الإيمان عند الفرق", ["الأمر بالمعروف عند المعتزلة", "الأصل الخامس الأمر بالمعروف"]),
    ]
    _CREED_SCHOOLS = [
        ("أهل الحديث والأثر", ["الآجري", "اللالكائي", "ابن بطة", "الخلال", "حرب الكرماني", "ابن خزيمة",
                                "الدارمي", "ابن منده", "الصابوني", "ابن قدامة", "ابن تيمية", "ابن القيم",
                                "البربهاري", "ابن أبي عاصم", "عبد الله بن أحمد", "المروزي"], []),
        ("الأشاعرة", ["الباقلاني", "ابن فورك", "الجويني", "الغزالي", "فخر الدين الرازي", "الآمدي",
                      "الإيجي", "السنوسي", "اللقاني", "البيجوري", "القشيري", "الجرجاني", "الدواني"], []),
        ("الماتريدية", ["الماتريدي", "أبو المعين النسفي", "نجم الدين النسفي", "التفتازاني", "البابرتي",
                        "الكمال بن الهمام", "الطحاوي", "ابن أبي العز", "البزدوي", "الخيالي"], []),
        ("الظاهرية", ["ابن حزم"], []),
        ("المعتزلة (من كتبهم الباقية)", ["القاضي عبد الجبار", "عبد الجبار الهمذاني", "الزمخشري", "أبو الحسين البصري"], []),
        ("كتب المقالات والفرق (نقل عن المدارس)", [], ["مقالات الإسلاميين", "الملل والنحل", "الفرق بين الفرق",
                                                      "الفصل في الملل", "التنبيه والرد على أهل الأهواء"]),
    ]

    def _creed_corpora(self):
        if getattr(self, "_creed_corpora_cache", None) is not None:
            return self._creed_corpora_cache
        corpora = {}
        for school, authors, titles in self._CREED_SCHOOLS:
            ids = []
            for bid, m in self.meta.items():
                au = _normalize(m.get("author") or "")
                ti = _normalize(m.get("title") or "")
                if any(_normalize(a) in au and "والد" not in au for a in authors) or \
                   any(_normalize(t) in ti for t in titles):
                    ids.append(bid)
            corpora[school] = ids
        self._creed_corpora_cache = corpora
        return corpora

    def creed_issue(self, issue, per_school=4):
        """مسألة عقدية مفهرسة: أقسامها من كتب كل مدرسة (بذرة مسائل منسّقة وأشهر
        كتب المدارس)، مع عدّاد لكل مدرسة وفصل بين قول المدرسة من كتبها ونقل المقالات عنها."""
        q = _normalize(issue or "")
        best, best_score = None, 0.0
        for iid, title, phrases in self._CREED_ISSUES:
            candidates = [title] + phrases
            for c in candidates:
                cn = _normalize(c)
                if cn and (cn in q or q in cn):
                    score = 2.0
                else:
                    ct, qt = set(cn.split()), set(q.split())
                    score = len(ct & qt) / max(1, len(ct | qt)) if ct and qt else 0.0
                if score > best_score:
                    best, best_score = (iid, title, phrases), score
        if not best or best_score < 0.34:
            fb = self.creed_search(issue, limit=10)
            return {"status": "not_indexed", "query": issue,
                    "indexed_issues": [t for _, t, _ in self._CREED_ISSUES],
                    "fallback": fb,
                    "note": "هذه المسألة ليست في البذرة المفهرسة بعد؛ هذه نتائج بحث العقيدة العام، ويمكن طلب إضافتها للبذرة."}
        iid, title, phrases = best
        corpora = self._creed_corpora()
        by_school = {}
        for school, _, _ in self._CREED_SCHOOLS:
            ids = corpora.get(school) or []
            sections, passages = [], []
            if ids:
                for ph in phrases:
                    h = self.search_headings(ph, mode="phrase", book_ids=ids, limit=int(per_school or 4))
                    sections = h.get("results", [])
                    if sections:
                        break
                if not sections:
                    h = self.search_headings(phrases[0], mode="words", book_ids=ids, limit=int(per_school or 4))
                    sections = h.get("results", [])
                p = self.search(phrases[0], mode="words", book_ids=ids, limit=int(per_school or 4))
                passages = p.get("results", [])
                if not sections and passages:
                    # حصاد عنوان الباب الحاكم من فهرس كتاب كل مقطع (من طبقة الشاملة)،
                    # بشرط ملاءمته لألفاظ المسألة حتى لا يدخل عناوين أبواب مجاورة.
                    try:
                        import shamela_local_mcp as _sm
                        _stop = {"في", "من", "على", "الى", "إلى", "عن", "ما", "لا", "ال"}
                        issue_words = set()
                        for ph in phrases:
                            issue_words |= {w for w in _normalize(ph).split() if len(w) > 2 and w not in _stop}
                        for h in passages[: int(per_school or 4)]:
                            if not h.get("page_num"):
                                continue
                            gh = _sm.get_issue_heading(h["book_id"], h["page_num"], h.get("part"))
                            hd = (gh or {}).get("heading") or {}
                            htitle = (hd.get("title") or "").strip()
                            hwords = {w for w in _normalize(htitle).split() if len(w) > 2}
                            if len(htitle) >= 8 and (hwords & issue_words):
                                sections.append({"book_id": h["book_id"], "title": h["title"],
                                                 "snippet": htitle, "page_num": h["page_num"],
                                                 "part": h.get("part"), "page_id": h["page_id"],
                                                 "harvested_from_toc": True})
                    except Exception:
                        pass
            by_school[school] = {"corpus_books": len(ids), "sections": sections, "passages": passages}
        return {"status": "ok", "issue_id": iid, "issue": title, "phrases": phrases,
                "by_school": by_school,
                "coverage": {s: {"sections": len(v["sections"]), "passages": len(v["passages"]),
                                 "corpus_books": v["corpus_books"]} for s, v in by_school.items()},
                "note": "أقسام من كتب كل مدرسة نفسها (والمقالات نقلٌ عنها لا قول لها)؛ انسب بعد قراءة الصفحة، والبذرة تنمو مسألة مسألة."}

    # ---------- مركّب لغة ومعاجم ----------
    @staticmethod
    def _work_stem(title):
        return re.split(r"\s+-\s+|\s+ت\s+|\s+ط\s+", title or "")[0].strip()

    def _diverse_order(self, rows, limit, per_work=1):
        """ترتيب وفيات مع حدّ لكل عمل (لا لكل طبعة): طبعات عمل واحد لا تحتكر النتائج."""
        seen, works, ordered = set(), {}, []
        for h in sorted(rows,
                        key=lambda x: (x["author_death_hijri"] if x.get("author_death_hijri") and x["author_death_hijri"] != 99999 else 99998)):
            k = (h["book_id"], h["page_id"])
            stem = self._work_stem(h.get("title"))
            if k in seen or works.get(stem, 0) >= per_work:
                continue
            seen.add(k)
            works[stem] = works.get(stem, 0) + 1
            ordered.append(h)
            if len(ordered) >= int(limit or 12):
                break
        return ordered

    def lugha_search(self, word, limit=16):
        cats = ["كتب اللغة", "الغريب والمعاجم"]
        heads = self.search_headings(word, mode="words", categories=cats, limit=int(limit or 12))
        # تجميع واسع ثم تنويع بحسب العمل: بلا ذلك لا تبلغ مادة العين/الصحاح القصيرة
        # أعلى BM25 بين آلاف الصفحات الحاوية للفظ (bench12: لم يظهرا أصلًا).
        # والصيغة المعرّفة بأل تُبحث أيضًا: مادة الصحاح لا تحمل «قرء» مجردًا قط.
        lim = max(int(limit or 12) * 6, 60)
        hits = self.search(word, mode="words", categories=cats, limit=lim)
        pool = list(hits.get("results", []))
        w = (word or "").strip()
        if w and not w.startswith("ال") and " " not in w:
            hits2 = self.search("ال" + w, mode="words", categories=cats, limit=lim)
            have = {(h["book_id"], h["page_id"]) for h in pool}
            pool.extend(h for h in hits2.get("results", []) if (h["book_id"], h["page_id"]) not in have)
        in_pool = {(h["book_id"], h["page_id"]) for h in pool}
        for hd in heads.get("results", []):
            # عناوين مواد المعاجم هي أبواب المداخل نفسها: مرشح بموضع صفحته
            if (hd["book_id"], hd["page_id"]) not in in_pool:
                pool.append({**hd, "snippet": hd.get("snippet") or hd.get("heading") or "", "via_heading": True})
        ordered = self._diverse_order(pool, int(limit or 12), per_work=1)
        return {"status": "ok", "word": word, "lexicon_headings": heads.get("results", []),
                "passages_by_death": ordered, "coverage": hits.get("coverage"),
                "note": "مواد المعاجم وكتب الغريب مرتبة بوفيات أصحابها؛ مادة اللفظ في المعجم تُقرأ في صفحتها كاملة، فقد يبدأ الشاهد قبل موضع المطابقة."}

    # ---------- مركّب تاريخ وسير ----------
    def _page_text(self, book_id, page_id):
        cache = getattr(self, "_page_text_cache", None)
        if cache is None:
            cache = self._page_text_cache = {}
        key = (book_id, page_id)
        if key in cache:
            return cache[key]
        cons = self._cons()
        shard_map = getattr(self, "_book_shard", None) or {}
        order = list(range(len(cons)))
        cached = shard_map.get(book_id)
        if cached is not None:
            order = [cached] + [i for i in order if i != cached]
        for i in order:
            try:
                row = cons[i].execute(
                    "SELECT text FROM pages_fts WHERE book_id=? AND page_id=? LIMIT 1",
                    (book_id, page_id)).fetchone()
            except Exception:
                continue
            if row:
                if shard_map is not None:
                    shard_map[book_id] = i
                if len(cache) > 300:
                    cache.clear()
                cache[key] = row[0]
                return row[0]
        return None

    def _verified_snippet(self, book_id, page_id, snippet):
        """مقتطف البحث لا يُنقل إلا إن ثبت تتابع فعلي منه في نص صفحته (مطابقة داخلية).
        المقتطف قد يجمع شذرات متباعدة بينها «…»؛ تُفحص كل شذرة ويُعتمد أطول ثابتة."""
        text = self._page_text(book_id, page_id)
        if not text:
            return None
        pw = _normalize(text).split()

        def _is_seq(qw):
            for st in [i for i, w in enumerate(pw) if w == qw[0]]:
                pi, ok = st, True
                for w in qw[1:]:
                    found = -1
                    for k in range(pi + 1, min(len(pw), pi + 2 + 6)):
                        if pw[k] == w:
                            found = k
                            break
                    if found < 0:
                        ok = False
                        break
                    pi = found
                if ok:
                    return True
            return False

        best = None
        for frag in re.split(r"…+", snippet or ""):
            q = " ".join(re.sub(r"[\[\]]", " ", frag).split())
            qw = _normalize(q).split()
            if len(qw) >= 4 and _is_seq(qw) and (best is None or len(q) > len(best)):
                best = q
        return best

    _YEAR_STRONG = re.compile(r"(دخلت سنه|ابتداء سنه|ذكر سنه)")
    _YEAR_WEAK = re.compile(r"سنه\s+([0-9٠-٩]+|واحد|اثنت|ثلاث|اربع|خمس|ست|سبع|ثمان|تسع|عشر|مائ)")

    def _year_headings(self, book_id):
        """كل ترويسات السنة في كتاب (مخبأة): تُجلب مرة وتُستشار لكل مواضعه."""
        cache = getattr(self, "_year_headings_cache", None)
        if cache is None:
            cache = self._year_headings_cache = {}
        if book_id in cache:
            return cache[book_id]
        cons = self._cons()
        shard_map = getattr(self, "_book_shard", None)
        if shard_map is None:
            shard_map = self._book_shard = {}
        order = list(range(len(cons)))
        cached = shard_map.get(book_id)
        if cached is not None:
            order = [cached] + [i for i in order if i != cached]
        rows_out = []
        for i in order:
            try:
                rows = cons[i].execute(
                    "SELECT page_id, text FROM headings_fts WHERE headings_fts MATCH 'سنه' "
                    "AND book_id=? ORDER BY page_id",
                    (book_id,)).fetchall()
            except Exception:
                continue
            if rows:
                shard_map[book_id] = i
                rows_out = [(pid, " ".join((t or "").split())) for pid, t in rows]
                break
        cache[book_id] = rows_out
        return rows_out

    def _year_context(self, book_id, page_id):
        """أقرب ترويسة سنة سابقة لموضع داخل الكتاب نفسه من فهرس العناوين.

        أخبار الحوليات تُروى بـ«وفيها» وسنتها في ترويسة متقدمة؛ بلا هذا السياق
        يصل الباحث خبرًا بلا تاريخ (كسوف الكامل 453هـ وصل بلا سنة في bench13)."""
        import bisect
        rows = self._year_headings(book_id)
        if not rows:
            return None
        pids = [r[0] for r in rows]
        i = bisect.bisect_right(pids, page_id) - 1
        fallback = None
        steps = 0
        while i >= 0 and steps < 80:
            pid, t = rows[i]
            n = _normalize(t)
            if self._YEAR_STRONG.search(n):
                return {"year_heading": t, "year_heading_page_id": pid}
            if fallback is None and len(t) <= 60 and self._YEAR_WEAK.search(n):
                fallback = {"year_heading": t, "year_heading_page_id": pid}
            i -= 1
            steps += 1
        return fallback

    _YEAR_WORDS = {"واحد": 1, "احد": 1, "اثنتين": 2, "اثنين": 2, "ثنتين": 2, "ثلاث": 3, "اربع": 4,
                   "خمس": 5, "ست": 6, "سبع": 7, "ثمان": 8, "تسع": 9, "عشر": 10, "عشره": 10,
                   "عشرين": 20, "ثلاثين": 30, "اربعين": 40, "خمسين": 50, "ستين": 60,
                   "سبعين": 70, "ثمانين": 80, "تسعين": 90,
                   "مائه": 100, "مايه": 100, "مائتين": 200, "مايتين": 200,
                   "ثلاثمائه": 300, "اربعمائه": 400, "خمسمائه": 500, "ستمائه": 600,
                   "سبعمائه": 700, "ثمانمائه": 800, "تسعمائه": 900}

    def _parse_year(self, heading):
        """رقم السنة من ترويسة مطبعة («ثم دخلت سنه تسع وستين ومائتين») أو None."""
        n = _normalize(heading or "")
        m = re.search(r"سنه\s+([^.]+)", n)
        if not m:
            return None
        rest = m.group(1)
        digits = re.search(r"[0-9٠-٩]+", rest)
        if digits:
            try:
                return int(digits.group(0).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
            except Exception:
                return None
        total, seen = 0, False
        for tok in re.split(r"[\sو]+", rest):
            v = self._YEAR_WORDS.get(tok)
            if v is not None:
                total += v
                seen = True
            elif tok in ("من", "الهجره") or not tok:
                continue
            elif seen:
                break
        return total if seen and total > 0 else None

    def tarikh_search(self, query, limit=12):
        cats = ["التاريخ", "السيرة النبوية", "التراجم والطبقات", "البلدان والرحلات"]
        heads = self.search_headings(query, mode="words", categories=cats, limit=int(limit or 12))
        # تجميع واسع ثم تنويع بحسب العمل: بلا ذلك تخنق قصة مشهورة واحدة
        # (كسوف يوم موت إبراهيم في عشرات كتب السيرة وطبعاتها) أخبارَ الحوليات المؤرخة (bench13).
        pool_limit = max(int(limit or 12) * 10, 240)
        hits = self.search(query, mode="words", categories=cats, limit=pool_limit)
        pool = list(hits.get("results", []))
        for h in pool:
            yc = self._year_context(h["book_id"], h["page_id"])
            if yc:
                h["year_context"] = yc
                h["year"] = self._parse_year(yc.get("year_heading"))
        ordered = self._diverse_order(pool, int(limit or 12), per_work=1)
        quotes = []
        for h in ordered:
            q = self._verified_snippet(h["book_id"], h["page_id"], h.get("snippet") or "")
            if q and len(q) >= 30:
                quotes.append({"book_id": h["book_id"], "title": h.get("title"),
                               "author": h.get("author"), "part": h.get("part"),
                               "page_num": h.get("page_num"), "year": h.get("year"),
                               "year_heading": (h.get("year_context") or {}).get("year_heading"),
                               "quote": q, "match_status": "MATCH_NORMALIZED"})
        # عناقيد وقائع على كامل التجميع لا على المعروض فقط: تعداد الأحداث المؤرخة
        events_map = {}
        for h in pool:
            if not h.get("year"):
                continue
            ev = events_map.setdefault(h["year"], {"year": h["year"], "books": [], "hits": 0, "quote": None})
            ev["hits"] += 1
            title = h.get("title")
            if title and title not in ev["books"]:
                ev["books"].append(title)
            if ev["quote"] is None and ev.get("_qtries", 0) < 2:
                ev["_qtries"] = ev.get("_qtries", 0) + 1
                q = self._verified_snippet(h["book_id"], h["page_id"], h.get("snippet") or "")
                if q and len(q) >= 30:
                    ev["quote"] = {"book_id": h["book_id"], "title": title, "part": h.get("part"),
                                   "page_num": h.get("page_num"), "quote": q,
                                   "match_status": "MATCH_NORMALIZED"}
        events = sorted(events_map.values(), key=lambda e: e["year"])
        for e in events:
            e.pop("_qtries", None)
        return {"status": "ok", "query": query, "headings": heads.get("results", []),
                "passages_by_death": ordered, "coverage": hits.get("coverage"),
                "quotes": quotes, "events": events,
                "note": "روايات مرتبة بوفاة المؤرخ لتتبع طبقات النقل؛ قابل بين الأصول قبل الترجيح. "
                        "حقل year_context عند وجوده هو أقرب ترويسة سنة سابقة للموضع في كتابه — به تُقرأ أخبار «وفيها» مؤرخة. "
                        "حقل quotes اقتباسات من المقتطفات ثبتت مطابقتها لنص صفحاتها داخل الخادم، مؤرخة بترويساتها؛ النقل المعتمد منها. "
                        "حقل events عناقيد سنوات مؤرخة على كامل تجميع البحث (لا المعروض فقط) بأسماء الكتب الحاملة واقتباس ثابت لكل سنة — هي هيكل التعداد، وتفاصيل كل واقعة من صفحتها."}

    def survey(self, term, death_max=None, categories=None, include_alive=False):
        match = _match_expr(term, "words")
        if not match:
            return {"status": "error", "message": "empty term"}
        per_book = {}
        for con in self._cons():
            try:
                for bid, c in con.execute(
                        "SELECT book_id, count(*) FROM pages_fts WHERE pages_fts MATCH ? GROUP BY book_id", (match,)):
                    per_book[bid] = per_book.get(bid, 0) + c
            except Exception:
                continue
        total_pages = 0
        by_cat, by_century, book_rows = {}, {}, []
        for bid, c in per_book.items():
            if not self._passes(bid, death_max, None, categories, include_alive):
                continue
            m = self.meta.get(bid, {})
            total_pages += c
            by_cat[m.get("category")] = by_cat.get(m.get("category"), 0) + c
            d = m.get("death")
            cent = ((d - 1) // 100 + 1) if d and d != 99999 else None
            by_century[cent] = by_century.get(cent, 0) + c
            book_rows.append({"book_id": bid, "title": m.get("title"), "death": d, "hits": c})
        book_rows.sort(key=lambda r: -r["hits"])
        return {"status": "ok", "term": term, "death_max": death_max,
                "matching_pages": total_pages, "books_with_hits": len(book_rows),
                "by_category": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
                "by_century": {str(k): v for k, v in sorted(by_century.items(), key=lambda kv: (kv[0] is None, kv[0]))},
                "top_books": book_rows[:12]}


_INDEX = None

def get_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = LibraryIndex()
    return _INDEX


LIBRARY_MCP_TOOLS_SPEC = [
    {"name": "search_library",
     "description": "بحث فوري في نصوص المكتبة كلها (٨٥٨٩ كتابًا) عبر الفهرس. mode: phrase عبارة حرفية متتابعة (الأقوى للشواهد)، words كل الكلمات في الصفحة، any أي كلمة، boolean منطقي. death_max سقف وفاة المؤلف هجريًا يختاره الباحث (٥٠٠/١٠٠٠/١٣٠٠...) أو اتركه بلا سقف. categories تصنيفات بعينها، book_ids نطاق كتب وكيل.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "mode": {"type": "string", "enum": ["phrase", "words", "any", "boolean"]},
         "death_max": {"type": "integer"}, "death_min": {"type": "integer"},
         "categories": {"type": "array", "items": {"type": "string"}},
         "book_ids": {"type": "array", "items": {"type": "integer"}},
         "include_alive": {"type": "boolean"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "search_headings",
     "description": "بحث في عناوين الأبواب والفصول (٤ ملايين عنوان) للوصول إلى فصل المسألة قبل قراءة المتون. يقدّم صيغ الأبواب (باب/فصل/مسألة/حكم) ويؤخّر معاجم البلدان واللغة افتراضيًا.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "mode": {"type": "string", "enum": ["phrase", "words", "any"]},
         "death_max": {"type": "integer"}, "categories": {"type": "array", "items": {"type": "string"}},
         "book_ids": {"type": "array", "items": {"type": "integer"}}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "search_batch",
     "description": "حتى ٢٤ بحثًا في استدعاء واحد بنفس المرشحات، مدموجة ومنزوعة التكرار — مثالية لمراسي اللجنة الخمس دفعة واحدة.",
     "inputSchema": {"type": "object", "properties": {
         "queries": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["phrase", "words", "any"]},
         "death_max": {"type": "integer"}, "categories": {"type": "array", "items": {"type": "string"}},
         "book_ids": {"type": "array", "items": {"type": "integer"}}, "limit_per_query": {"type": "integer"}}, "required": ["queries"]}},
    {"name": "survey_topic",
     "description": "مسح إحصائي قبل الحفر: كم صفحة تحوي المصطلح، موزعة بحسب التصنيف والقرن الهجري وأغزر الكتب — ليعرف الباحث أين يتركز موضوعه قبل البحث العميق.",
     "inputSchema": {"type": "object", "properties": {
         "term": {"type": "string"}, "death_max": {"type": "integer"},
         "categories": {"type": "array", "items": {"type": "string"}}}, "required": ["term"]}},
    {"name": "dossier_topic",
     "description": "ملف موضوع فقهي مركّب قبل الحفر: مداخل الموسوعات الفقهية عندنا (الكويتية والتويجري) + عناوين أبواب + قائمة قراءة بأربع طبقات زمنية (حتى ٤٠٠ / ٤٠١–٧٠٠ / ٧٠١–١١٠٠ / بعد ١١٠٠) مضروبة في مذاهب أهل السنة (حنفي/مالكي/شافعي/حنبلي/ظاهري-فقه عام)، بموضعين لكل خلية من الفهرس، وسطر تغطية يوثق الخلايا الصفرية. death_max سقف الباحث يقص الطبقات. بعده: اقرأ بـget_page وطابق بـverify_quote، وللحديث trace_hadith.",
     "inputSchema": {"type": "object", "properties": {
         "topic": {"type": "string"}, "per_cell": {"type": "integer"},
         "death_max": {"type": "integer"}}, "required": ["topic"]}},
    {"name": "ayah_loci",
     "description": "مواضع آية (بالسورة والرقم) في كتب التفسير مرتبة بوفاة المفسر من فهرس مراسي ﴿﴾ المبني على المكتبة كلها، مع استشهادات الآية في بقية الكتب وسطر تغطية (كم تفسيرًا لها موضع من ٢٧٣). kind: all/tafsir/citation. بعدها اقرأ المواضع بـget_page.",
     "inputSchema": {"type": "object", "properties": {
         "surah": {"type": "integer"}, "ayah": {"type": "integer"},
         "kind": {"type": "string", "enum": ["all", "tafsir", "citation"]},
         "limit": {"type": "integer"}}, "required": ["surah", "ayah"]}},
    {"name": "attestations",
     "description": "نسب عبارة قصيرة ثابتة: من قالها وأقدمهم بترتيب وفيات المؤلفين، مع طيّ طبعات العمل الواحد وتوزيع قرون — لأسئلة «من أول من قال» و«هل سُبق إليه». النتيجة أقدم ما وُجد في مرشحات البحث لا حصر كلي.",
     "inputSchema": {"type": "object", "properties": {
         "phrases": {"type": "array", "items": {"type": "string"}},
         "limit_works": {"type": "integer"}}, "required": ["phrases"]}},
    {"name": "hadith_loci",
     "description": "مواضع متن حديث في كتب الحديث مصنفة: أصول (كتب السنة) وشروح وتخريج وعلل، مرتبة داخل كل صنف بوفاة المؤلف — أسرع من trace_hadith ومن الفهرس مباشرة. مرشحات لا حكم؛ الدرجة من كتب التخريج مقروءة.",
     "inputSchema": {"type": "object", "properties": {
         "text": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["text"]}},
    {"name": "qawaid_search",
     "description": "بحث قاعدة فقهية/أصولية: عناوين كتب القواعد والأشباه والفروق والأصول الحاملة لها، مع أقدم شاهد على صياغتها بترتيب الوفيات — لأسئلة القواعد والفروق والأشباه والنظائر.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "creed_search",
     "description": "مسألة عقدية: عناوين ومواضع في كتب العقيدة والفرق والردود بنصوص أصحابها، لاستخراج مقالات المدارس من كتبها مع التنبيه على الفرق بين قول المدرسة ونقل خصومها.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "tarikh_search",
     "description": "حدث أو علم تاريخي: عناوين كتب التاريخ والسير والتراجم، وروايات مرتبة بوفاة المؤرخ لتتبع طبقات النقل والمقابلة بين الأصول.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "lugha_search",
     "description": "لفظ لغوي: مواد المعاجم وكتب الغريب والمعاني مرتبة بوفيات أصحابها، لتعريف اللفظ وتاريخ استعماله عند اللغويين والمفسرين الأوائل.",
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["word"]}},
    {"name": "creed_issue",
     "description": "مسألة عقدية مفهرسة: أقسام المسألة من كتب كل مدرسة سنية (أهل الحديث والأثر/الأشاعرة/الماتريدية/الظاهرية) وكتب المقالات ناقلة عنها، من بذرة مسائل منسّقة. إن لم تكن المسألة مفهرسة أُعيدت قائمة المسائل مع بحث عام.",
     "inputSchema": {"type": "object", "properties": {
         "issue": {"type": "string"}, "per_school": {"type": "integer"}}, "required": ["issue"]}},
    {"name": "fiqh_topics",
     "description": "شجرة موضوعات الفقه المنسّقة: موضوعات الأبواب الفقهية وعدد مواضع كل موضوع عند كل مذهب. ابحث فيها قبل fiqh_topic_locations.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}}, "required": []}},
    {"name": "fiqh_topic_locations",
     "description": "مواضع موضوع فقهي موسومة بالمذهب من عناوين أبواب كتب المذاهب نفسها، بعناوين حقيقية ومواضع قابلة للقراءة والمطابقة.",
     "inputSchema": {"type": "object", "properties": {
         "topic": {"type": "string"}, "madhhab": {"type": "string"}, "per_madhhab": {"type": "integer"}}, "required": ["topic"]}},
    {"name": "madhhab_authorities",
     "description": "فهرس ضبط المذهب: الكتب المعتمدة الحاسمة مرتبة بطبقات العصر (نص/تحرير/ترجيح/اعتماد/ضبط متأخر) مع علماء كل طبقة وقاموس اصطلاحي موزون (الأظهر/المشهور/النص/وجهان...) وقواعد الترجيح داخل المذهب — كل اقتباس موثّق بمطابقة على صفحته. استعمله قبل الحكم بأن قولًا هو «المذهب» أو «المقرر».",
     "inputSchema": {"type": "object", "properties": {
         "madhhab": {"type": "string", "description": "الحنفي أو المالكي أو الشافعي أو الحنبلي أو الظاهري"}}, "required": ["madhhab"]}},
    {"name": "authority_books",
     "description": "فهارس ضبط ثلاثة: كتب الإجماع التي تنقل الإجماع (ابن المنذر، ابن حزم، ابن عبد البر...)، وكتب أسباب الخلاف (البطليوسي، رفع الملام، بداية المجتهد)، وكتب الخلاف العالي بين المذاهب (المروزي، التجريد، الخلافيات، الإفصاح...) — طبقات الكتب وأدوارها ومبادئ موثّقة من مقدماتها. استعمل قسم الإجماع قبل أي ادعاء إجماع، وقسم الأسباب عند تعليل الخلاف، وقسم الخلاف للمقارنة العالية.",
     "inputSchema": {"type": "object", "properties": {
         "kind": {"type": "string", "description": "ijma (إجماع) أو asbab (أسباب الخلاف) أو khilaf (الخلاف العالي)"}}, "required": ["kind"]}},
]


_MADHHAB_AUTHORITY_CACHE = None


def _load_madhhab_authority():
    global _MADHHAB_AUTHORITY_CACHE
    if _MADHHAB_AUTHORITY_CACHE is None:
        path = os.path.join(_HERE, "madhhab_authority.json")
        try:
            with open(path, encoding="utf-8") as f:
                _MADHHAB_AUTHORITY_CACHE = json.load(f)
        except Exception:
            _MADHHAB_AUTHORITY_CACHE = {}
    return _MADHHAB_AUTHORITY_CACHE


def madhhab_authorities(madhhab: str):
    """خريطة ضبط مذهب: طبقات الكتب المعتمدة + الاصطلاح + قواعد الترجيح، بمصادر موثّقة."""
    data = _load_madhhab_authority()
    madahib = data.get("madahib") or {}
    key = (madhhab or "").strip()
    if key not in madahib:
        for k in madahib:
            if key and (key in k or k in key or key.replace("ال", "") == k.replace("ال", "")):
                key = k
                break
    if key not in madahib:
        return {"status": "not_built", "madhhab": madhhab,
                "available": sorted(madahib.keys()),
                "message": "هذا المذهب لم يُبنَ فهرس ضبطه بعد. " + (data.get("gaps") or "")}
    out = {"status": "ok", "madhhab": key, "discipline": data.get("discipline"),
           "gaps": data.get("gaps")}
    out.update(madahib[key])
    return out


_DISCIPLINE_BOOKS_CACHE = None


def _load_discipline_books():
    global _DISCIPLINE_BOOKS_CACHE
    if _DISCIPLINE_BOOKS_CACHE is None:
        path = os.path.join(_HERE, "discipline_books.json")
        try:
            with open(path, encoding="utf-8") as f:
                _DISCIPLINE_BOOKS_CACHE = json.load(f)
        except Exception:
            _DISCIPLINE_BOOKS_CACHE = {}
    return _DISCIPLINE_BOOKS_CACHE


_AUTHORITY_KIND_ALIASES = {
    "ijma": "ijma", "إجماع": "ijma", "الاجماع": "ijma", "الإجماع": "ijma",
    "asbab": "asbab", "أسباب": "asbab", "اسباب": "asbab", "أسباب الخلاف": "asbab",
    "khilaf": "khilaf", "خلاف": "khilaf", "الخلاف": "khilaf", "الخلاف العالي": "khilaf",
}


def authority_books(kind: str):
    """فهرس ضبط: كتب الإجماع / أسباب الخلاف / الخلاف العالي، بطبقات ومبادئ موثّقة."""
    data = _load_discipline_books()
    sections = data.get("sections") or {}
    raw = (kind or "").strip()
    key = _AUTHORITY_KIND_ALIASES.get(raw) or _AUTHORITY_KIND_ALIASES.get(raw.lower())
    if not key:
        for alias, candidate in _AUTHORITY_KIND_ALIASES.items():
            if alias and alias in raw:
                key = candidate
                break
    if not key or key not in sections:
        return {"status": "not_built", "kind": kind,
                "available": {k: v.get("name") for k, v in sections.items()},
                "message": "اطلب ijma للإجماع أو asbab لأسباب الخلاف أو khilaf للخلاف العالي."}
    out = {"status": "ok", "kind": key, "discipline": data.get("discipline")}
    out.update(sections[key])
    return out


def ijma_book_ids():
    """أرقام كتب الإجماع المعتمدة عند بوابة التوثيق لحسم ادعاءات الإجماع."""
    try:
        section = (_load_discipline_books().get("sections") or {}).get("ijma") or {}
        ids = set()
        for layer in section.get("layers") or []:
            for b in layer.get("books") or []:
                if b.get("book_id"):
                    ids.add(str(b["book_id"]))
        return ids
    except Exception:
        return set()


def _shamela_bridge(name: str, args: dict):
    """اعتراض المسار الكسول: بحث مباشر في فهرس الشاملة وقت التشغيل بدل
    فهرسنا الجاهز. يُفعَّل عند مصدر shamela ووجود فهرسها؛ غير ذلك None (سقوط)."""
    if name not in ("search_library", "search_headings"):
        return None
    try:
        from shamela_local_mcp import _library_source
        if _library_source() != "shamela":
            return None
        import shamela_search
        picked = None
        if args.get("book_ids") is not None or args.get("categories"):
            try:
                picked = args.get("book_ids") or _book_ids_for_categories(args.get("categories") or [])
            except Exception:
                picked = args.get("book_ids")
        q = str(args.get("query") or args.get("text") or "")
        r = shamela_search.search(q, mode=str(args.get("mode") or "phrase"),
                                  death_max=args.get("death_max"), death_min=args.get("death_min"),
                                  categories=args.get("categories"), book_ids=picked,
                                  include_alive=bool(args.get("include_alive")),
                                  limit=max(1, int(args.get("limit") or 10)))
        if name == "search_headings":
            r["note"] = ("العناوين عندهم داخل متن الصفحات (بيانات فهرس الشاملة): "
                         "النتائج شواهد متن تشتمل على العنوان — اقرأ الصفحة لالتقاط التبويب.")
        return r
    except Exception:
        return None


def execute_library_tool(name: str, args: dict):
    if name == "madhhab_authorities":
        return madhhab_authorities((args or {}).get("madhhab", ""))
    if name == "authority_books":
        return authority_books((args or {}).get("kind", ""))
    bridged = _shamela_bridge(name, args or {})
    if bridged is not None:
        return bridged
    st = index_status()
    if not st["available"]:
        return {"status": "unavailable",
                "message": "فهرس المكتبة يُبنى الآن لأول مرة وسيكون جاهزًا خلال دقائق؛ أعد المحاولة بعد قليل." if st["building"]
                           else "فهرس المكتبة غير مبني بعد؛ سيُبنى تلقائيًا عند تشغيل التطبيق."}
    idx = get_index()
    a = args or {}
    if name == "search_library":
        return idx.search(a.get("query", ""), mode=a.get("mode", "phrase"), death_max=a.get("death_max"),
                          death_min=a.get("death_min"), categories=a.get("categories"),
                          book_ids=a.get("book_ids"), include_alive=bool(a.get("include_alive")),
                          limit=int(a.get("limit") or 10))
    if name == "search_headings":
        return idx.search_headings(a.get("query", ""), mode=a.get("mode", "phrase"), death_max=a.get("death_max"),
                                   categories=a.get("categories"), book_ids=a.get("book_ids"),
                                   limit=int(a.get("limit") or 10))
    if name == "search_batch":
        return idx.search_batch(a.get("queries") or [], mode=a.get("mode", "phrase"), death_max=a.get("death_max"),
                                categories=a.get("categories"), book_ids=a.get("book_ids"),
                                limit_per_query=int(a.get("limit_per_query") or 5))
    if name == "survey_topic":
        return idx.survey(a.get("term", ""), death_max=a.get("death_max"), categories=a.get("categories"))
    if name == "dossier_topic":
        return idx.dossier_topic(a.get("topic", ""), per_cell=int(a.get("per_cell") or 2),
                                 death_max=a.get("death_max"))
    if name == "ayah_loci":
        return idx.ayah_loci(a.get("surah"), a.get("ayah"), kind=a.get("kind", "all"),
                             limit=int(a.get("limit") or 40))
    if name == "attestations":
        return idx.attestations(a.get("phrases") or [], limit_works=int(a.get("limit_works") or 12))
    if name == "hadith_loci":
        return idx.hadith_loci(a.get("text", ""), limit=int(a.get("limit") or 20))
    if name == "qawaid_search":
        return idx.qawaid_search(a.get("query", ""), limit=int(a.get("limit") or 15))
    if name == "creed_search":
        return idx.creed_search(a.get("query", ""), limit=int(a.get("limit") or 12))
    if name == "tarikh_search":
        return idx.tarikh_search(a.get("query", ""), limit=int(a.get("limit") or 12))
    if name == "lugha_search":
        return idx.lugha_search(a.get("word", ""), limit=int(a.get("limit") or 12))
    if name == "creed_issue":
        return idx.creed_issue(a.get("issue", ""), per_school=int(a.get("per_school") or 4))
    if name == "fiqh_topics":
        return idx.fiqh_topics(a.get("query", ""))
    if name == "fiqh_topic_locations":
        return idx.fiqh_topic_locations(a.get("topic", ""), madhhab=a.get("madhhab"),
                                        per_madhhab=int(a.get("per_madhhab") or 6))
    return {"status": "error", "message": f"unknown tool {name}"}
