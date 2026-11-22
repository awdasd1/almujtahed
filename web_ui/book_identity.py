#!/usr/bin/env python3
"""هوية الكتب: حلّ اسم مطلوب إلى كتاب/كتب الشاملة بلا استبعاد صامت.

المسار الجديد طبقة فوق المسار التاريخي لا بديل قسري عنه:
- بطاقة هوية لكل كتاب من قاعدة «books»: العنوان، الاسم في بطاقة الشاملة
  (سطر «الكتاب:»)، صيغ العنوان بعد فصل لاحقة الطبعة/التحقيق، المؤلف ووفاته.
- تمثيل متجهي محلي خفيف (شذرات حروف وكلمات) وحسم هجين: تطابق تام، احتواء،
  تشابه كلمات وشذرات، وعلاوة مؤلف؛ ولا نموذج تضمين ولا مخزن خارجي.
- بصمة عمل (work fingerprint) من الاسم المعياري في البطاقة + المؤلف تجمع
  طبعات العمل الواحد، فيُرجَع العمل وطبعاته لا طبعة يتيمة.
- ثلاث درجات: resolved (قبول آلي)، candidates (مرشحون مرتبون بأدلتهم)،
  unresolved. المستدعي القديم يبقى خط الرجعة عند إطفاء العلم أو أي عطل.
"""
import hashlib
import os
import re
import sqlite3
import threading
import unicodedata

_LOCK = threading.Lock()
_CACHE = {"key": None, "cards": [], "token_index": {}, "gram_index": {}}

_STOP = {
    "الكتاب", "كتاب", "في", "من", "علي", "الي", "عن", "ما", "لا", "بن", "ابن",
    "ابي", "ابو", "ت", "ط", "تحقيق", "طبع", "طبعه", "دار", "مكتبه", "المكتبه",
}
_EDITION_HINT = re.compile(
    r"\s+[-–=]\s+.*$|\s+(?:ط|ت)\s+[\u0600-\u06FF].*$|\s+تحقيق\s+.*$|\s+ط\s+[\u0600-\u06FF].*$"
)


def enabled() -> bool:
    return (os.environ.get("ALMOGHNI_BOOK_IDENTITY", "on") or "on").strip().lower() not in (
        "0", "off", "false", "no",
    )


def normalize_ar(text) -> str:
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = t.replace("«", " ").replace("»", " ").replace('"', " ").replace("'", " ")
    t = re.sub(r"[^\w\u0600-\u06FF]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(text) -> list:
    out = []
    for w in normalize_ar(text).split():
        if len(w) >= 2 and w not in out:
            out.append(w)
    return out


def _grams(text) -> set:
    t = " " + normalize_ar(text) + " "
    return {t[i:i + 3] for i in range(max(0, len(t) - 2))}


def _dice(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def _edition_stem(title: str) -> str:
    t = str(title or "").strip()
    t = re.split(r"\s+[-–=]\s+", t)[0].strip()
    t = re.sub(r"\s+(?:ط|ت)\s+[\u0600-\u06FF].*$", "", t).strip()
    return t


def _betaka_title(betaka: str) -> str:
    m = re.search(r"الكتاب:\s*([^\r\n]+)", betaka or "")
    return m.group(1).strip() if m else ""


def _variants(title_ar: str, betaka: str) -> list:
    raw = []
    bt = _betaka_title(betaka)
    if bt:
        raw.append(bt)
        for part in re.split(r"\s*=\s*|،", bt):
            if part.strip():
                raw.append(part.strip())
    raw.append(title_ar or "")
    raw.append(_edition_stem(title_ar or ""))
    if bt:
        # اسم داخل «» لا يكون بديلًا إلا حين يختم الاسمَ اسمًا مشهورًا له
        # (الجامع الصحيح «صحيح مسلم»)، لا حين يكون كتابًا مشروحًا/مُحالًا إليه
        m_alias = re.match(r"^[^«]*(«[^»]+»)\s*$", bt)
        if m_alias and not re.search(r"شرح|من\s*$", bt[: m_alias.start(1)]):
            raw.append(m_alias.group(1).strip("«»"))
    # صيغة بلا لاحقة نسبة للمؤلف: «المغني لابن قدامة» -> «المغني»
    for item in list(raw):
        short = re.split(r"\s+(?:لابن|لابي|لأبي|للشافعي|للسرخسي|للطبري|لـ)\s+", item)[0].strip()
        if short and short != item:
            raw.append(short)
    out, seen = [], set()
    for item in raw:
        n = normalize_ar(item)
        # شذرات مؤلف من بطاقة (لابن حجر...) ليست اسم كتاب
        if n.startswith(("لابن ", "لابي ", "لل ")) or n in ("لابن", "لابي"):
            continue
        if len(n) >= 2 and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _work_fingerprint(work_norm: str, author_norm: str) -> str:
    author_key = " ".join(w for w in author_norm.split() if w not in _STOP)
    raw = f"{work_norm}|{author_key}".encode("utf-8")
    return "W" + hashlib.sha1(raw).hexdigest()[:12]


def _load_cards(db_path: str):
    key = None
    try:
        st = os.stat(db_path)
        key = (db_path, st.st_mtime_ns, st.st_size)
    except OSError:
        return [], {}, {}
    with _LOCK:
        if _CACHE["key"] == key:
            return _CACHE["cards"], _CACHE["token_index"], _CACHE["gram_index"]
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT book_id, title_ar, main_author_name_ar, main_author_death_hijri,"
            " category_name_ar, volume_count_observed, betaka_text, rel_path FROM books"
        ).fetchall()
        con.close()
        cards, token_index, gram_index = [], {}, {}
        for r in rows:
            variants = _variants(r["title_ar"] or "", r["betaka_text"] or "")
            if not variants:
                continue
            work = variants[0]
            author_norm = normalize_ar(r["main_author_name_ar"] or "")
            card = {
                "book_id": int(r["book_id"]),
                "title": r["title_ar"] or "",
                "author": r["main_author_name_ar"] or "",
                "death": r["main_author_death_hijri"],
                "category": r["category_name_ar"] or "",
                "volumes": int(r["volume_count_observed"] or 0),
                "rel_path": r["rel_path"] or "",
                "variants": variants,
                "work_norm": work,
                "author_norm": author_norm,
                "work_id": _work_fingerprint(work, author_norm),
                "token_sets": [set(v.split()) for v in variants],
                "gram_sets": [_grams(v) for v in variants],
                "author_tokens": set(author_norm.split()),
            }
            idx = len(cards)
            cards.append(card)
            toks = set()
            for ts in card["token_sets"]:
                toks |= ts
            toks |= card["author_tokens"]
            for tok in toks:
                if len(tok) >= 2:
                    token_index.setdefault(tok, []).append(idx)
            grams = set()
            for gs in card["gram_sets"]:
                grams |= gs
            for g in grams:
                gram_index.setdefault(g, []).append(idx)
        _CACHE.update({"key": key, "cards": cards, "token_index": token_index, "gram_index": gram_index})
        return cards, token_index, gram_index


_AUTHOR_GENERIC = {"ابن", "ابي", "ابو", "بن", "ال", "لابي", "لابن"}


def _distinctive(tokens: set) -> set:
    return {t for t in tokens if t not in _AUTHOR_GENERIC and len(t) >= 3}


def _score_card(q_norm: str, q_tokens: set, q_grams: set, card: dict, explicit_author: set) -> tuple:
    best, evidence = 0.0, []
    for vi, variant in enumerate(card["variants"]):
        vt = card["token_sets"][vi]
        if q_norm == variant:
            s, ev = 1.0, "تطابق تام مع اسم العمل"
        elif variant.startswith(q_norm) or q_norm.startswith(variant):
            ratio = min(len(q_norm), len(variant)) / max(1, max(len(q_norm), len(variant)))
            s, ev = 0.86 + 0.10 * ratio, "احتواء اسمي (اسم مشهور/مختصر)"
        elif q_tokens and (q_tokens <= vt or (vt <= q_tokens and len(vt) >= 3)):
            s, ev = 0.88, "احتواء كلمات العنوان"
        else:
            token_dice = _dice(q_tokens, vt)
            gram_dice = _dice(q_grams, card["gram_sets"][vi])
            s = 0.62 * token_dice + 0.38 * gram_dice
            ev = "تشابه كلمات وشذرات"
        # شرح/حاشية على كتاب مطلوب ليس الكتاب نفسه ما لم يُطلب شرح
        vt_first = variant.split()[0] if variant.split() else ""
        if vt_first in ("شرح", "حاشيه", "تكمله", "تعليق", "تعليقات", "تلخيص") and (
            not q_norm.startswith(vt_first)
        ):
            s = max(0.0, s - 0.08)
        if s > best:
            best, evidence = s, [ev]

    def _al_strip(tokens):
        return {(t[2:] if t.startswith("ال") and len(t) > 4 else t) for t in tokens}

    card_author = _al_strip(_distinctive(card["author_tokens"]))
    for variant_tokens in card["token_sets"]:
        card_author |= _al_strip(_distinctive(variant_tokens))
    explicit_author = _al_strip(set(explicit_author))
    if explicit_author:
        if explicit_author & card_author:
            best = min(1.0, best + 0.10)
            evidence.append("موافقة مؤلف")
        else:
            # مؤلف صريح في الطلب لا يوافق هذه البطاقة: كتاب آخر بالاسم نفسه
            best = max(0.0, best - 0.22)
            evidence.append("مخالفة مؤلف الطلب")
    return best, evidence


def _explicit_author_tokens(q_raw: str, author_hint: str) -> set:
    if author_hint:
        return _distinctive(set(_tokens(author_hint)))
    toks = _tokens(q_raw)
    out = set()
    for i, tok in enumerate(toks):
        if tok in ("لابن", "لابي", "لأبي", "لل") and i + 1 < len(toks):
            out.add(toks[i + 1])
        elif tok.startswith("لل") and len(tok) >= 5:
            out.add(tok[2:])
        elif tok.startswith("لابن") and len(tok) >= 7:
            out.add(tok[4:])
    return _distinctive(out)


def _title_tokens(q_raw: str, explicit_author: set) -> list:
    drop = set(explicit_author) | {"لابن", "لابي", "لأبي"}
    out = []
    for tok in _tokens(q_raw):
        if tok in drop:
            continue
        if tok.startswith("لل") and tok[2:] in explicit_author:
            continue
        if tok.startswith("لابن") and len(tok) >= 7 and tok[4:] in explicit_author:
            continue
        out.append(tok)
    return out or _tokens(q_raw)


def resolve_book(query: str, db_path: str, author_hint: str = "", limit: int = 5) -> dict:
    """حل اسم واحد. لا يرفع استثناء؛ عند العطل يرجع unresolved ليكمل خط الرجعة."""
    q_raw = str(query or "").strip()
    base = {"query": q_raw, "status": "unresolved", "book_ids": [], "candidates": [], "work_id": ""}
    if not q_raw or not db_path:
        return base
    try:
        cards, token_index, gram_index = _load_cards(db_path)
    except Exception as exc:
        base["error"] = str(exc)[:160]
        return base
    if not cards:
        return base
    q_full = normalize_ar(re.sub(r"^#?\d+\s*[-:]*\s*", "", q_raw))
    q_full = normalize_ar(_edition_stem(q_full))
    if len(q_full) < 2:
        return base
    explicit_author = _explicit_author_tokens(q_full, author_hint)
    # التقييم الاسمي على العنوان وحده، والمؤلف الصريح إشارة مستقلة
    title_toks = _title_tokens(q_full, explicit_author)
    q_norm = " ".join(title_toks)
    q_tokens = set(title_toks)
    q_grams = _grams(q_norm)

    cand_idx = set()
    for tok in q_tokens | explicit_author:
        cand_idx.update(token_index.get(tok, []))
    if len(cand_idx) < 8:
        gram_hits = {}
        for g in q_grams:
            for idx in gram_index.get(g, []):
                gram_hits[idx] = gram_hits.get(idx, 0) + 1
        for idx, _n in sorted(gram_hits.items(), key=lambda kv: -kv[1])[:40]:
            cand_idx.add(idx)
    if not cand_idx:
        return base

    scored = []
    for idx in cand_idx:
        card = cards[idx]
        s, ev = _score_card(q_norm, q_tokens, q_grams, card, explicit_author)
        if s >= 0.45:
            scored.append((s, card, ev))
    if not scored:
        return base
    scored.sort(key=lambda x: (-x[0], -x[1]["volumes"], x[1]["book_id"]))

    # تجميع الطبعات: بطاقتان عملٌ واحد إن اشتركتا في صيغة اسم ووافق المؤلف المميز،
    # حتى لو اختلف سطر «الكتاب:» بين طبعة وأخرى (الجامع الصحيح/صحيح مسلم)
    clusters = []
    for s, card, ev in scored:
        placed = None
        card_vars = set(card["variants"])
        card_auth = _distinctive(card["author_tokens"])
        for cl in clusters:
            head = cl["card"]
            shared = card_vars & set(head["variants"])
            head_auth = _distinctive(head["author_tokens"])
            if shared and (not card_auth or not head_auth or card_auth & head_auth):
                placed = cl
                break
        if placed is None:
            placed = {"score": s, "card": card, "evidence": ev, "editions": []}
            clusters.append(placed)
        placed["score"] = max(placed["score"], s)
        if "موافقة مؤلف" in ev and "موافقة مؤلف" not in placed["evidence"]:
            placed["evidence"] = list(placed["evidence"]) + ["موافقة مؤلف"]
        placed["editions"].append(card)
    ordered = sorted(clusters, key=lambda g: (-g["score"], -len(g["editions"]), -g["card"]["volumes"], g["card"]["book_id"]))
    for g in ordered:
        g["editions"].sort(key=lambda c: (-c["volumes"], c["book_id"]))

    cands = []
    for g in ordered[: max(1, limit)]:
        head = g["editions"][0]
        cands.append({
            "work_id": g["card"]["work_id"],
            "book_id": head["book_id"],
            "book_ids": [c["book_id"] for c in g["editions"][:16]],
            "title": head["title"],
            "author": head["author"],
            "confidence": round(float(g["score"]), 3),
            "evidence": g["evidence"],
            "editions": len(g["editions"]),
        })
    base["candidates"] = cands
    top = ordered[0]
    second = ordered[1]["score"] if len(ordered) > 1 else 0.0
    margin = float(top["score"]) - float(second)
    if len(ordered) > 1 and not explicit_author:
        # اسم مشهور واحد لعملين مختلفين (فتح الباري لابن حجر/لابن رجب):
        # بلا مؤلف في الطلب لا يُحسم، بل يبقى مرشحين موثقين
        second_exact = any(
            q_norm in c["variants"] for c in ordered[1]["editions"]
        )
        if second_exact and second >= 0.88 and margin < 0.15:
            base["status"] = "candidates"
            base["work_id"] = top["card"]["work_id"]
            return base
    author_ok = "موافقة مؤلف" in (top["evidence"] or [])
    if top["score"] >= 0.90 or (top["score"] >= 0.86 and (margin >= 0.05 or author_ok)):
        base.update({
            "status": "resolved",
            "work_id": top["card"]["work_id"],
            "book_ids": [c["book_id"] for c in top["editions"][:16]],
            "title": top["editions"][0]["title"],
            "confidence": round(float(top["score"]), 3),
            "evidence": top["evidence"],
        })
    elif top["score"] >= 0.60:
        base["status"] = "candidates"
        base["work_id"] = top["card"]["work_id"]
    return base


def resolve_book_ids(queries, db_path: str, limit_per_book: int = 4) -> dict:
    """حل قائمة أسماء: أرقام مقبولة آليًا + تقرير مرشحين/غير محلول (لا حذف صامت)."""
    ids, report = [], {"resolved": [], "candidates": [], "unresolved": []}
    for q in queries or []:
        r = resolve_book(str(q), db_path)
        if r["status"] == "resolved":
            for bid in r["book_ids"][:limit_per_book]:
                if str(bid) not in ids:
                    ids.append(str(bid))
            report["resolved"].append(r)
        elif r["status"] == "candidates":
            report["candidates"].append(r)
        else:
            report["unresolved"].append(r)
    return {"book_ids": ids, "report": report}
