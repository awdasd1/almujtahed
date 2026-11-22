# -*- coding: utf-8 -*-
"""محرك التخريج المتدرج للأحاديث والآثار.

سياسة الاكتفاء المعتمدة:
1) إن كان الحديث في البخاري ومسلم أو في أحدهما فهذا أهم تخريج ويُكتفى به.
2) وإلا يُخرَّج من الكتب الستة مع صحيح ابن خزيمة وصحيح ابن حبان ومستدرك
   الحاكم.
3) فإن خلت، بُحث في تمام التسعة: مسند أحمد وموطأ مالك ومسند الدارمي.
4) ثم سنن الدارقطني، ثم سنن البيهقي، ثم معاجم الطبراني الثلاثة، ثم
   المصنفات والآثار.

وكتب الإرشاد إلى المواضع والمدار (تحفة الأشراف، المعجم المفهرس، التلخيص
الحبير، نصب الراية، إرواء الغليل) تُبحث دلالةً لا تخريجًا أصليًا.

لا تبعية على الخادم: يُستورد جسر الشاملة كسولًا من مجلد هذا الملف، وتُحلّ
طبعات كل عمل بمحلّل هوية الكتب (book_identity) فيُبحث في طبعة رئيسة واحدة
لكل عمل. وأي فشل يرجع نتيجة فارغة ولا يرمي — خط الرجعة: غياب المحرك لا
يعطّل ما عداه.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_DIAC = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_FOLD_MAP = str.maketrans({"إ": "ا", "أ": "ا", "آ": "ا", "ى": "ي",
                           "ة": "ه", "ؤ": "و", "ئ": "ي"})


def to_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).translate(_DIGITS).strip())
    except Exception:
        return None


def fold(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", str(text or ""))
    t = _DIAC.sub("", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.translate(_FOLD_MAP).split())


def _ascii_digits(text: str) -> str:
    return str(text or "").translate(_DIGITS)


# أصحاب الأعمال بترتيب التخريج: (اسم العمل للبحث، الاسم المشهور للعزو)
TIERS: List[tuple] = [
    ("الصحيحان", [
        ("صحيح البخاري", "البخاري"),
        ("صحيح مسلم", "مسلم"),
    ]),
    ("الستة وملحقات التصحيح", [
        ("سنن أبي داود", "أبو داود"),
        ("سنن الترمذي", "الترمذي"),
        ("سنن النسائي", "النسائي"),
        ("سنن ابن ماجه", "ابن ماجه"),
        ("صحيح ابن خزيمة", "ابن خزيمة"),
        ("صحيح ابن حبان", "ابن حبان"),
        ("المستدرك على الصحيحين", "الحاكم"),
    ]),
    ("تمام التسعة", [
        ("مسند أحمد", "أحمد"),
        ("موطأ مالك", "مالك"),
        ("مسند الدارمي", "الدارمي"),
    ]),
    ("سنن الدارقطني", [("سنن الدارقطني", "الدارقطني")]),
    ("سنن البيهقي", [("السنن الكبرى للبيهقي", "البيهقي")]),
    ("معاجم الطبراني", [
        ("المعجم الكبير للطبراني", "الطبراني في الكبير"),
        ("المعجم الأوسط للطبراني", "الطبراني في الأوسط"),
        ("المعجم الصغير للطبراني", "الطبراني في الصغير"),
    ]),
    ("المصنفات والآثار", [
        ("مصنف عبد الرزاق", "عبد الرزاق"),
        ("مصنف ابن أبي شيبة", "ابن أبي شيبة"),
        ("شرح معاني الآثار", "الطحاوي"),
    ]),
]

# كتب الإرشاد إلى المواضع والمدار: تُفتح أولًا اختصارًا للبحث.
GUIDE_BOOKS = [
    (4255, "تحفة الأشراف بمعرفة الأطراف"),
    (3903, "المعجم المفهرس لألفاظ الحديث"),
    (5765, "التلخيص الحبير"),
    (4276, "نصب الراية"),
    (5927, "إرواء الغليل"),
]


def _search():
    import shamela_search
    return shamela_search


def _mcp():
    import shamela_local_mcp
    return shamela_local_mcp


def editions_for_work(work_name: str, db_path: str) -> List[Dict[str, Any]]:
    """كل طبعات العمل المحسومة (لا الطبعة الأولى وحدها): البحث في إحداها يكفي."""
    out: List[Dict[str, Any]] = []
    seen = set()

    def _add(bid: Any, title: str) -> None:
        try:
            n = int(bid)
        except Exception:
            return
        if n in seen:
            return
        seen.add(n)
        out.append({"book_id": n, "title": title or work_name})

    try:
        import book_identity
        r = book_identity.resolve_book(work_name, db_path, limit=8)
        title = str(r.get("title") or work_name)
        for bid in r.get("book_ids") or []:
            _add(bid, title)
        for c in r.get("candidates") or []:
            ctitle = str(c.get("title") or title)
            for bid in (c.get("book_ids") or [c.get("book_id")]):
                _add(bid, ctitle)
    except Exception:
        pass
    if not out:
        ed = _primary_edition(work_name, db_path)
        if ed:
            out.append(ed)
    return out


def _primary_edition(work_name: str, db_path: str) -> Optional[Dict[str, Any]]:
    """الطبعة الرئيسة لعمل واحد بمحلّل الهوية (أول طبعة محسومة)."""
    try:
        import book_identity
        r = book_identity.resolve_book(work_name, db_path)
        if r.get("status") == "resolved" and r.get("book_ids"):
            bid = int(r["book_ids"][0])
            for c in r.get("candidates") or []:
                if int(c.get("book_id") or 0) == bid:
                    return {"book_id": bid, "title": c.get("title") or work_name}
            return {"book_id": bid, "title": work_name}
    except Exception:
        pass
    try:
        row = _mcp().resolve_book(work_name)
        if row and row.get("book_id"):
            return {"book_id": int(row["book_id"]),
                    "title": row.get("title") or work_name}
    except Exception:
        pass
    return None


_NUM_BEFORE = re.compile(r"(?:\[\s*(\d{1,5})\s*\]|(\d{1,5})\s*[-–—]|[حح]\s*(\d{1,5}))")


def _prep(body: str) -> str:
    """نص موحّد للفحص: لا وسوم ولا تشكيل، أرقامه لاتينية، حروفه مطوية —
    وبهذه الصورة الواحدة تُبحث الأرقام والمتون فلا تنزاح المواضع."""
    t = re.sub(r"<[^>]+>", " ", str(body or ""))
    t = _DIAC.sub("", t).translate(_DIGITS).translate(_FOLD_MAP)
    t = re.sub(r"[^\w\s\[\]-]", " ", t)
    return " ".join(t.split())


def hadith_number_at(body: str, quote: str) -> Optional[int]:
    """رقم الحديث الذي يسبق موضع النقل في متن الصفحة نفسها."""
    if not body:
        return None
    text = _prep(body)
    qf = fold(quote)
    pos = -1
    for a, b in ((0, 42), (len(qf) // 3, len(qf) // 3 + 42),
                 (max(0, len(qf) - 42), len(qf))):
        seg = qf[a:b].strip()
        if len(seg) >= 14 and seg in text:
            pos = text.find(seg)
            break
    if pos < 0:
        return None
    found = None
    for m in _NUM_BEFORE.finditer(text[:pos]):
        found = next((g for g in m.groups() if g), None) or found
    return to_int(found) if found else None


def page_has_number(body: str, number: int) -> bool:
    """الصفحة تحمل رقم الحديث: بهيئته «N -» أو «[N]» أو «ح N»."""
    if not body or not number:
        return False
    text = _ascii_digits(re.sub(r"<[^>]+>", " ", body))
    n = str(int(number))
    return bool(re.search(r"(?:\[\s*" + n + r"\s*\]|(?<!\d)" + n + r"\s*[-–—]|[حح]\s*" + n + r"(?!\d))", text))


_PAGE_MAPS: Dict[int, Dict[tuple, str]] = {}


def page_text(book_id: int, part: Any, page: Any) -> str:
    """متن الصفحة كاملًا: جلب الصفحة الواحدة من الخادم قد يرجع شطرها
    (صفحة الكتاب موزعة على سجلات)، فتُجمع سجلاتها من ملف الكتاب نفسه."""
    try:
        bid = int(book_id)
    except Exception:
        return ""
    if bid not in _PAGE_MAPS:
        mapping: Dict[tuple, str] = {}
        try:
            import json as _json
            row = _mcp().resolve_book(bid) or {}
            rel = str(row.get("rel_path") or "")
            bdir = _mcp()._dir_for_rel(rel) if rel else None
            pfile = (bdir / "pages.jsonl") if bdir is not None else None
            if pfile is not None and pfile.exists():
                with open(pfile, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            d = _json.loads(line)
                        except Exception:
                            continue
                        key = (str(d.get("part") or ""), str(d.get("page_num") or ""))
                        body = str(d.get("body") or "")
                        if body:
                            mapping[key] = (mapping.get(key, "") + "\n" + body)
        except Exception:
            mapping = {}
        _PAGE_MAPS[bid] = mapping
    text = _PAGE_MAPS[bid].get((str(part or ""), str(page or "")))
    if text:
        return text
    try:
        pg = _mcp().get_page(bid, int(page), part or None)
        if pg.get("status") == "ok":
            return str((pg.get("page") or {}).get("body") or "")
    except Exception:
        pass
    return ""


def _page_body(book_id: int, page: Any, part: Any) -> str:
    return page_text(book_id, part, page)


def _contains(page_body: str, quote: str) -> bool:
    pf, qf = fold(page_body), fold(quote)
    if not pf or len(qf) < 14:
        return False
    for a, b in ((0, 42), (len(qf) // 3, len(qf) // 3 + 42),
                 (max(0, len(qf) - 42), len(qf))):
        seg = qf[a:b].strip()
        if len(seg) >= 14 and seg in pf:
            return True
    words = {w for w in qf.split() if len(w) >= 4}
    if not words:
        return False
    return sum(1 for w in words if w in pf) / len(words) >= 0.8


def page_contains_text(page_body: str, quote: str) -> bool:
    """الصفحة تحمل متن النقل (بتسامح الروايات المختلفة اللفظ)."""
    return _contains(page_body or "", quote)


def locate_in_book(book_id: int, quote: str, limit: int = 6) -> List[Dict[str, Any]]:
    """كل مواضع النقل المثبتة في كتاب واحد: جزء وصفحة ورقم حديث."""
    out: List[Dict[str, Any]] = []
    try:
        words = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", fold(quote))]
        if len(words) < 4:
            return out
        search = _search()
        hits = []
        r = search.search(" ".join(words[:7]), mode="phrase",
                          book_ids=[int(book_id)], limit=limit)
        hits.extend(r.get("results") or [])
        if not hits:
            distinct = sorted(set(words), key=len, reverse=True)[:6]
            if len(distinct) >= 3:
                r2 = search.search(" ".join(distinct), mode="words",
                                   book_ids=[int(book_id)], limit=limit)
                hits.extend(r2.get("results") or [])
        seen = set()
        for h in hits:
            key = (str(h.get("part") or ""), str(h.get("page_num") or ""))
            if key in seen:
                continue
            seen.add(key)
            body = _page_body(book_id, h.get("page_num"), h.get("part"))
            if body and _contains(body, quote):
                out.append({"book_id": int(book_id),
                            "part": str(h.get("part") or ""),
                            "page": to_int(h.get("page_num")) or h.get("page_num"),
                            "number": hadith_number_at(body, quote)})
    except Exception:
        return out
    out.sort(key=lambda x: (str(x["part"]), int(x["page"]) if str(x["page"]).isdigit() else 0))
    return out


def _search_work(work_name: str, famous: str, quote: str,
                 db_path: str) -> Optional[Dict[str, Any]]:
    """أول طبعة يثبت فيها المتن على الصفحة؛ لا يُكتفى بطبعة رئيسة خالية."""
    for ed in editions_for_work(work_name, db_path):
        locs = locate_in_book(ed["book_id"], quote, limit=3)
        if not locs:
            continue
        first = locs[0]
        return {"work": work_name, "famous": famous, "book_id": ed["book_id"],
                "title": ed.get("title") or work_name, "part": first["part"],
                "page": first["page"], "number": first["number"],
                "occurrences": len(locs)}
    return None


def takhrij(text: str, db_path: str, guides: bool = False) -> Dict[str, Any]:
    """تخريج متدرج بنص الحديث: يطبق سياسة الاكتفاء طبقة طبقة.

    الرجوع: {in_sahih: [...], found: [...], tier: اسم الطبقة التي وُجد فيها
    أولًا أو None, sufficient: وُجد في الصحيحين أو أحدهما, note: خلاصة}.
    """
    result: Dict[str, Any] = {"in_sahih": [], "found": [], "tier": None,
                              "sufficient": False, "note": ""}
    quote = " ".join(str(text or "").split())
    if len(quote) < 14:
        result["note"] = "نص أقصر من أن يُبحث عنه"
        return result
    try:
        for tier_name, works in TIERS:
            tier_hits = []
            for work_name, famous in works:
                hit = _search_work(work_name, famous, quote, db_path)
                if hit:
                    hit["tier"] = tier_name
                    tier_hits.append(hit)
            if tier_hits:
                result["found"] = tier_hits
                result["tier"] = tier_name
                if tier_name == "الصحيحان":
                    result["in_sahih"] = tier_hits
                    result["sufficient"] = True
                    names = " و".join(h["famous"] for h in tier_hits)
                    result["note"] = f"في {names}: تخريج يُكتفى به"
                else:
                    result["note"] = f"أول وجود في طبقة: {tier_name}"
                break
        if not result["found"]:
            result["note"] = "لم يوجد في طبقات التخريج المعتمدة كلها"
        if guides:
            result["guides"] = guide_hits(quote)
    except Exception as exc:  # خط الرجعة: فشل المحرك لا يكسر ما عداه
        result["note"] = f"تعذر التخريج الآلي: {exc}"
    return result


def guide_hits(text: str, limit: int = 2) -> List[Dict[str, Any]]:
    """إشارات كتب الإرشاد (أطراف ومدار وتخريجات الأئمة) إلى الحديث."""
    out: List[Dict[str, Any]] = []
    try:
        search = _search()
        words = [w for w in re.findall(r"[\u0600-\u06FF]{3,}", fold(text))]
        if len(words) < 4:
            return out
        probe = " ".join(words[:7])
        for bid, title in GUIDE_BOOKS:
            try:
                r = search.search(probe, mode="phrase", book_ids=[bid], limit=limit)
                for h in (r.get("results") or [])[:limit]:
                    out.append({"book_id": bid, "title": title,
                                "part": str(h.get("part") or ""),
                                "page": h.get("page_num"),
                                "snippet": " ".join(str(h.get("snippet") or "").split())[:200]})
            except Exception:
                continue
    except Exception:
        pass
    return out
