#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خادم MCP الخاص بالمجتهد: بروتوكول MCP قياسي فوق مكتبة الشاملة المحلية.

المبدأ: الفهرس والبحث يرشّحان الصفحة، وملف الكتاب وحده مصدر النقل،
ولا إحالة إلا بعد مطابقة. الخادم قراءة فقط، ولا أداة كتابة فيه.

التشغيل:
    python3 almujtahed_mcp_server.py            # HTTP على 127.0.0.1:8765/mcp
    python3 almujtahed_mcp_server.py --stdio    # قناة stdio لعملاء MCP
البيئة: SHAMELA4_DATA_DIR لمجلد الشاملة، وALMUJTAHED_MCP_PORT للمنفذ.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shamela_local_mcp as shamela

SERVER_NAME = "almujtahed"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2025-03-26"

GUIDE = """ترتيب العمل في المجتهد (إلزامي):
0. لمسألة فقهية مقارنة: ابدأ بـ fiqh_topic_locations إن كان موضوعها في شجرة الفقه (fiqh_topics لاكتشاف الموضوعات)، أو fiqh_dossier لملف بالنصوص، أو dossier_topic (طبقات زمنية × مذاهب أهل السنة، وخلايا صفرية موثقة)، ثم اقرأ خلاياه وطابق.
   آية: ayah_loci وملفها الطبقي ayah_dossier؛ من قال أولًا: attestations؛ حديث: hadith_loci وملفه hadith_dossier؛ قاعدة: qawaid_search؛ عقيدة: creed_search ومسألة مفهرسة creed_issue؛ تاريخ: tarikh_search؛ لغة: lugha_search؛ ضبط مذهب (المعتمد والمقرر والاصطلاح): madhhab_authorities؛ إجماع وأسباب خلاف وخلاف عال: authority_books بأقسامها ijma/asbab/khilaf؛ قبل التسليم: verify_batch؛ لإثبات غياب: get_book_coverage.
1. ابدأ بـ almujtahed_guide مرة واحدة في الجلسة.
2. حلّ كل كتاب برقمه: resolve_book. الرقم هو المفتاح الوحيد، والعنوان للعرض.
3. ابحث داخل النطاق المغلق فقط: search_passages أو search_books_scoped بقائمة أرقام كتب.
   إن مرّت قائمة كتب لم يخرج البحث عنها، ولا يوجد بحث مفتوح في المكتبة.
4. النتائج مرشحات غير قابلة للنقل. اقرأ الصفحة كاملة: get_page أو get_page_range،
   واستكمل سياقها بـ get_surrounding_context، واعرف بابها بـ get_issue_heading.
5. لا تنقل حرفاً واحداً قبل verify_quote. حالة NOT_FOUND تمنع النقل منعاً باتاً.
6. الحديث: لفظه من trace_hadith في كتب الحديث، ولا ينقل من كتاب فقه.
   حكمه من كتب التخريج بعد قراءة صفحاتها، ولا يبحث عن درجة ما في الصحيحين.
   عند تعدد طبعات الكتاب اكتفِ بأول طبعة تلتقطها (لا نقل من طبعتين لعمل واحد)،
   والصحيحان مقدمان على المسانيد والسنن. وفي قول كل مذهب مثّل طبقاته:
   متقدمًا ومتوسطًا ومتأخرًا ما وجدت نصوصها، لا طبقة واحدة.
7. إن خلت النتيجة فأعد البحث بمراسٍ من لغة المصنفين داخل الكتب نفسها، حتى ثلاث جولات،
   ثم صرّح أن النطاق لم يرجع شيئاً. لا تكمل من الذاكرة.
8. للمسائل المعاصرة (ألفاظ حديثة كالباروكة والعملات الرقمية ونقل الأعضاء): ابدأ بـ
   anchor_lookup لترجمتها إلى عبارات من لسان التراث قبل 1000هـ بشواهد موثقة، ثم ابحث
   بتلك العبارات. المقابل التراثي لا لفظ السؤال الحديث هو مفتاح النتائج.
العزو: «انظر» للنقل الحرفي و«ينظر» للنقل بالمعنى، واسم الكتاب ومؤلفه وجزؤه وصفحته
من كائن الإحالة الموثق حصراً."""


def _tool(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties, "required": required},
    }


TOOLS = [
    _tool("almujtahed_guide", "دليل ترتيب العمل في خادم المجتهد: النطاق، القراءة، المطابقة، والعزو. يُستدعى مرة واحدة أول الجلسة.", {}, []),
    _tool("resolve_book", "حلّ كتاب إلى رقمه المعياري ومؤلفه وتصنيفه ومساره.", {"book": {"type": "string"}}, ["book"]),
    _tool("get_book_card", "بطاقة الكتاب: المحقق والطبعة والناشر ومدينة النشر وسنة الطبع.", {"book": {"type": "string"}}, ["book"]),
    _tool("get_book_toc", "فهرس أبواب الكتاب وعناوينه.", {"book": {"type": "string"}}, ["book"]),
    _tool("get_page", "قراءة صفحة واحدة بنصها وهوامشها من ملف الكتاب. مصدر النقل الوحيد.", {"book": {"type": "string"}, "page_num": {"type": "integer"}, "part": {"type": "string"}}, ["book", "page_num"]),
    _tool("get_page_range", "قراءة صفحات متتالية كاملة بنصها وهوامشها.", {"book": {"type": "string"}, "start_page": {"type": "integer"}, "end_page": {"type": "integer"}, "part": {"type": "string"}}, ["book", "start_page", "end_page"]),
    _tool("get_surrounding_context", "الصفحات المحيطة بصفحة لاستيفاء سياقها.", {"book": {"type": "string"}, "page_num": {"type": "integer"}, "part": {"type": "string"}, "before_pages": {"type": "integer"}, "after_pages": {"type": "integer"}}, ["book", "page_num"]),
    _tool("get_issue_heading", "عنوان الباب أو المسألة الحاكم لصفحة.", {"book": {"type": "string"}, "page_num": {"type": "integer"}, "part": {"type": "string"}}, ["book", "page_num"]),
    _tool("search_in_book", "بحث حرفي داخل كتاب واحد.", {"book": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}}, ["book", "query"]),
    _tool("search_books_scoped", "بحث لفظي داخل قائمة كتب مغلقة. مرشحات غير قابلة للنقل.", {"query": {"type": "string"}, "book_ids": {"type": "array", "items": {"type": "string"}}, "limit_per_book": {"type": "integer"}, "limit": {"type": "integer"}}, ["query", "book_ids"]),
    _tool("anchor_lookup", "جدول المراسي التراثية: يطابق مسألة معاصرة بعبارات من لسان التراث قبل 1000هـ مع شاهد موثق لكل عبارة (كتاب/جزء/صفحة). ابدأ بها في المسائل المعاصرة.", {"query": {"type": "string"}, "limit_entries": {"type": "integer"}}, ["query"]),
    _tool("anchor_search", "بحث الطبقات بالمراسي: مطابقة الجدول ثم بحث لفظي بعباراته في كتب التراث مع نصوص الصفحات. مرر book_ids لإغلاق النطاق.", {"query": {"type": "string"}, "book_ids": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}}, ["query"]),
    _tool("search_passages", "بحث داخل نطاق مغلق: لفظي في هذا الخادم المستقل، وهجين دلالي عند تشغيله داخل التطبيق. مرشحات غير قابلة للنقل.", {"query": {"type": "string"}, "book_ids": {"type": "array", "items": {"type": "string"}}, "anchors": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}}, ["query", "book_ids"]),
    _tool("verify_quote", "مطابقة اقتباس على صفحات كتابه: MATCH_EXACT أو MATCH_NORMALIZED أو NOT_FOUND مع أقرب موضع.", {"book": {"type": "string"}, "quote_text": {"type": "string"}, "page_hint": {"type": "integer"}, "part": {"type": "string"}}, ["book", "quote_text"]),
    _tool("trace_hadith", "تتبع ألفاظ حديث في كتب الحديث: أصول وشروح وتخريج. لا نقل من كتب الفقه.", {"text": {"type": "string"}, "limit_books": {"type": "integer"}}, ["text"]),
    _tool("research_evidence", "حزمة شواهد: بحث منغلق بمراسٍ حتى ثلاث جولات، ثم قراءة الصفحات ومطابقة مقتطفاتها، مع سجل بحث يثبت النطاقات الصفرية.", {"query": {"type": "string"}, "book_ids": {"type": "array", "items": {"type": "string"}}, "anchors": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}}, ["query", "book_ids"]),
    _tool("search_library", "بحث فوري في نصوص المكتبة كلها عبر الفهرس (٨٥٨٩ كتابًا، أجزاء ثانية). mode: phrase/words/any/boolean. death_max سقف وفاة يختاره الباحث، categories تصنيفات، book_ids نطاق وكيل. النتائج مرشحات: اقرأ وطابق قبل النقل.", {"query": {"type": "string"}, "mode": {"type": "string", "enum": ["phrase", "words", "any", "boolean"]}, "death_max": {"type": "integer"}, "death_min": {"type": "integer"}, "categories": {"type": "array", "items": {"type": "string"}}, "book_ids": {"type": "array", "items": {"type": "integer"}}, "include_alive": {"type": "boolean"}, "limit": {"type": "integer"}}, ["query"]),
    _tool("search_headings", "بحث في عناوين الأبواب والفصول (٤ ملايين عنوان) لبلوغ فصل المسألة قبل المتون، بنفس المرشحات.", {"query": {"type": "string"}, "mode": {"type": "string", "enum": ["phrase", "words", "any"]}, "death_max": {"type": "integer"}, "categories": {"type": "array", "items": {"type": "string"}}, "book_ids": {"type": "array", "items": {"type": "integer"}}, "limit": {"type": "integer"}}, ["query"]),
    _tool("search_batch", "حتى ٢٤ بحثًا في استدعاء واحد بنفس المرشحات، مدموجة ومنزوعة التكرار — لمراسي اللجنة دفعة واحدة.", {"queries": {"type": "array", "items": {"type": "string"}}, "mode": {"type": "string", "enum": ["phrase", "words", "any"]}, "death_max": {"type": "integer"}, "categories": {"type": "array", "items": {"type": "string"}}, "book_ids": {"type": "array", "items": {"type": "integer"}}, "limit_per_query": {"type": "integer"}}, ["queries"]),
    _tool("survey_topic", "مسح إحصائي قبل الحفر: صفحات المصطلح موزعة بحسب التصنيف والقرن وأغزر الكتب.", {"term": {"type": "string"}, "death_max": {"type": "integer"}, "categories": {"type": "array", "items": {"type": "string"}}}, ["term"]),
    _tool("dossier_topic", "ملف موضوع فقهي مركّب قبل الحفر: مداخل الموسوعات الفقهية وعناوين أبواب وقائمة قراءة بأربع طبقات زمنية × مذاهب أهل السنة (حنفي/مالكي/شافعي/حنبلي/ظاهري)، مع توثيق الخلايا الصفرية. ابدأ به في الفقه المقارن ثم اقرأ وطابق.", {"topic": {"type": "string"}, "per_cell": {"type": "integer"}, "death_max": {"type": "integer"}}, ["topic"]),
    _tool("ayah_loci", "مواضع آية (سورة/رقم) في التفاسير مرتبة بوفاة المفسر من فهرس مراسي ﴿﴾، مع استشهاداتها وسطر تغطية.", {"surah": {"type": "integer"}, "ayah": {"type": "integer"}, "kind": {"type": "string", "enum": ["all", "tafsir", "citation"]}, "limit": {"type": "integer"}}, ["surah", "ayah"]),
    _tool("attestations", "نسب عبارة: أقدم قائليها بترتيب وفيات المؤلفين مع طي الطبعات وتوزيع القرون.", {"phrases": {"type": "array", "items": {"type": "string"}}, "limit_works": {"type": "integer"}}, ["phrases"]),
    _tool("hadith_loci", "مواضع متن حديث في الأصول والشروح وكتب التخريج والعلل من الفهرس، مرتبة بالوفيات داخل كل صنف.", {"text": {"type": "string"}, "limit": {"type": "integer"}}, ["text"]),
    _tool("qawaid_search", "قاعدة فقهية/أصولية: عناوين كتب القواعد والأشباه والفروق الحاملة لها وأقدم شاهد على صياغتها.", {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    _tool("ayah_dossier", "ملف آية طبقي: مواضعها في التفاسير مطوية بحسب الكتاب على أربع طبقات عصر، بمقتطف من كل مصدر وقائلي السلف آليًا. brief لمقتطفات أقصر.", {"surah": {"type": "integer"}, "ayah": {"type": "integer"}, "per_era": {"type": "integer"}, "brief": {"type": "boolean"}}, ["surah", "ayah"]),
    _tool("hadith_dossier", "ملف حديث: مواضع المتن مجمعة (أصول/شروح/تخريج) مع نصوص مرفقة من صفحات الأصول والتخريج الأصلية لنقل المتن من كتابه، وأحكام مستخرجة آليًا تُقرأ بسياقها. brief لمخرجات نحيفة.", {"text": {"type": "string"}, "limit": {"type": "integer"}, "brief": {"type": "boolean"}}, ["text"]),
    _tool("word_dossier", "ملف لفظ بالنصوص: مواد المعاجم والغريب بالوفيات مع نص مادة كل مصدر. brief لنصوص أقل.", {"word": {"type": "string"}, "limit": {"type": "integer"}, "brief": {"type": "boolean"}}, ["word"]),
    _tool("fiqh_dossier", "ملف موضوع فقهي بالنصوص: طبقات × مذاهب مع نصوص الموسوعات وأوائل الخلايا. brief لمخرجات نحيفة سريعة.", {"topic": {"type": "string"}, "per_cell": {"type": "integer"}, "death_max": {"type": "integer"}, "brief": {"type": "boolean"}}, ["topic"]),
    _tool("verify_batch", "سجل مطابقة: حتى ٤٠ نقلًا تُطابق دفعة على صفحاتها بالتوازي مع تسريع بالفهرس، مع إعادة تحديد في طبعات أخرى عند الفشل.", {"citations": {"type": "array", "items": {"type": "object"}}}, ["citations"]),
    _tool("get_book_coverage", "بطاقة تغطية كتاب: أجزاؤه وصفحاته وتحذير بتر إن نقص النص عن مجلدات الطبعة.", {"book": {"type": "string"}}, ["book"]),
    _tool("creed_search", "مسألة عقدية: عناوين ومواضع في كتب العقيدة والفرق والردود بنصوص أصحابها.", {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    _tool("tarikh_search", "حدث تاريخي: عناوين التاريخ والسير والتراجم وروايات مرتبة بوفاة المؤرخ.", {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    _tool("lugha_search", "لفظ لغوي: مواد المعاجم وكتب الغريب والمعاني مرتبة بوفيات أصحابها.", {"word": {"type": "string"}, "limit": {"type": "integer"}}, ["word"]),
    _tool("creed_issue", "مسألة عقدية مفهرسة: أقسامها من كتب كل مدرسة سنية وكتب المقالات ناقلة عنها (بذرة منسّقة).", {"issue": {"type": "string"}, "per_school": {"type": "integer"}}, ["issue"]),
    _tool("get_pack_slice", "شريحة من حزمة ملف محفوظة عند الخادم برقم pack_id (يأتي مع نتائج ملفات الآية والحديث واللفظ والفقه): بلا field أسماء الحقول، وبـfield قائمة عناصرها مجزأة. الحالة عند الخادم لا في سياقك؛ والنقل الحرفي من حقل quotes الموثق في نتيجة الملف.", {"pack_id": {"type": "string"}, "field": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, ["pack_id"]),
    _tool("fiqh_topics", "شجرة موضوعات الفقه: الموضوعات المنسّقة وعدد مواضعها عند كل مذهب.", {"query": {"type": "string"}}, []),
    _tool("fiqh_topic_locations", "مواضع موضوع فقهي موسومة بالمذهب من عناوين أبواب كتب المذاهب.", {"topic": {"type": "string"}, "madhhab": {"type": "string"}, "per_madhhab": {"type": "integer"}}, ["topic"]),
    _tool("madhhab_authorities", "فهرس ضبط المذهب: الكتب المعتمدة بطبقاتها وقاموس الاصطلاح الموزون وقواعد الترجيح، باقتباسات موثّقة. استعمله قبل وصف قول بأنه «المذهب» أو «المقرر». (المذاهب الخمسة مبنية)", {"madhhab": {"type": "string"}}, ["madhhab"]),
    _tool("authority_books", "فهارس ضبط: كتب الإجماع الناقلة له (kind=ijma)، وكتب أسباب الخلاف (kind=asbab)، وكتب الخلاف العالي بين المذاهب (kind=khilaf) — طبقاتها وأدوارها ومبادئ موثّقة. قبل ادعاء إجماع راجع ijma.", {"kind": {"type": "string"}}, ["kind"]),
]

TOOL_NAMES = [t["name"] for t in TOOLS]


def _evidence(query: str, book_ids: List[Any], anchors: List[str], limit: int) -> Dict[str, Any]:
    ids = [str(b).strip().lstrip("#") for b in (book_ids or []) if str(b).strip()]
    if not ids:
        return shamela._error("SCOPE_REQUIRED", "يلزم تمرير book_ids. لا بحث مفتوحاً في المكتبة.")
    cap = max(1, min(int(limit or 12), 40))
    rounds = [("query", query)] + [("anchor", a) for a in (anchors or [])[:14]]
    seen = set()
    items: List[Dict[str, Any]] = []
    ledger_rounds = []
    for round_no, (kind, text) in enumerate(rounds[: 1 + 14], 1):
        if round_no > 4 and items:
            break
        found = shamela.search_books_scoped(query=text, book_ids=ids, limit_per_book=2, limit=cap)
        added = 0
        for hit in found.get("results") or []:
            key = (hit.get("book_id"), str(hit.get("part") or ""), str(hit.get("page_num") or ""))
            if key in seen:
                continue
            seen.add(key)
            page = shamela.get_page(book=hit["book_id"], page_num=int(hit["page_num"]), part=hit.get("part"))
            body = ((page.get("page") or {}).get("body") or "") if page.get("status") == "ok" else ""
            phrase = (hit.get("snippet") or "")[:70].strip()
            check = shamela.verify_quote(book=hit["book_id"], quote_text=phrase, page_hint=int(hit["page_num"])) if phrase else {}
            items.append({
                "book_id": hit.get("book_id"),
                "title": hit.get("title") or "",
                "part": hit.get("part"),
                "page_num": hit.get("page_num"),
                "round": round_no,
                "via": kind,
                "text": body[:1400],
                "verification": check.get("match_status") or "UNCHECKED",
                "citation": shamela.resolve_book(hit["book_id"]) if check.get("match_status") in ("MATCH_EXACT", "MATCH_NORMALIZED") else None,
            })
            added += 1
            if len(items) >= cap:
                break
        ledger_rounds.append({"round": round_no, "via": kind, "text": text, "new": added})
        if len(items) >= cap:
            break
    return {
        "status": "ok",
        "query": query,
        "evidence": items,
        "ledger": {"rounds": ledger_rounds, "scope_books": len(ids), "returned": len(items)},
        "note": "لا يعتمد من الحزمة إلا ما حالته MATCH_EXACT أو MATCH_NORMALIZED، وبعد قراءة نصه كاملاً.",
    }


def call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    args = args or {}
    # الخادم المستقل للوكلاء الخارجيين: الملفات بحجمها النحيف افتراضيًا ما لم يُطلب الكامل صراحة
    if name in ("ayah_dossier", "hadith_dossier", "word_dossier", "fiqh_dossier") and "brief" not in args:
        args = {**args, "brief": True}
    if name == "almujtahed_guide":
        return {"status": "ok", "guide": GUIDE, "tools": TOOL_NAMES}
    if name == "search_passages":
        rounds = [args.get("query") or ""] + list(args.get("anchors") or [])
        merged: List[Dict[str, Any]] = []
        seen = set()
        for text in rounds:
            if not text:
                continue
            found = shamela.search_books_scoped(query=text, book_ids=args.get("book_ids") or [], limit=int(args.get("limit") or 20))
            if found.get("status") != "ok":
                return found
            for hit in found.get("results") or []:
                key = (hit.get("book_id"), str(hit.get("part") or ""), str(hit.get("page_num") or ""))
                if key not in seen:
                    seen.add(key)
                    merged.append(hit)
        return {"status": "ok", "results": merged[: int(args.get("limit") or 20)], "note": "مرشحات غير قابلة للنقل. اقرأ الصفحة ثم طابق."}
    if name == "research_evidence":
        return _evidence(args.get("query") or "", args.get("book_ids") or [], list(args.get("anchors") or []), int(args.get("limit") or 12))
    if name in ("resolve_book", "get_book_card", "get_book_toc", "get_page", "get_page_range",
                "get_surrounding_context", "get_issue_heading", "search_in_book",
                "search_books_scoped", "verify_quote", "trace_hadith",
                "anchor_lookup", "anchor_search",
                "search_library", "search_headings", "search_batch", "survey_topic", "dossier_topic",
                "ayah_loci", "attestations", "hadith_loci", "qawaid_search",
                "verify_batch", "get_book_coverage", "creed_search", "tarikh_search", "lugha_search",
                "ayah_dossier", "hadith_dossier", "creed_issue", "word_dossier", "fiqh_dossier",
                "get_pack_slice", "fiqh_topics", "fiqh_topic_locations", "madhhab_authorities", "authority_books"):
        return shamela.execute_mcp_tool(name, args)
    return shamela._error("UNKNOWN_TOOL", f"أداة غير معروفة: {name}")


def handle(payload: Dict[str, Any]) -> Any:
    method = payload.get("method") or ""
    rid = payload.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": GUIDE,
        }}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = payload.get("params") or {}
        name = params.get("name") or ""
        try:
            result = call_tool(name, params.get("arguments") or {})
        except Exception as exc:
            result = shamela._error("TOOL_FAILED", f"تعذر تنفيذ الأداة: {exc}")
        is_error = result.get("status") == "error"
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "structuredContent": result,
            "isError": is_error,
        }}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"طريقة غير معروفة: {method}"}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"name": SERVER_NAME, "version": SERVER_VERSION, "tools": len(TOOLS)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            payload = {}
        result = handle(payload if isinstance(payload, dict) else {})
        if result is None:
            self.send_response(202)
            self.end_headers()
            return
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        result = handle(payload)
        if result is not None:
            sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    # إحماء فهرس المكتبة في الخلفية من أول لحظة: الخدمة دافئة لأول وكيل كما لعاشر وكيل
    try:
        import library_search as _ls
        _ls.warm_index_async()
    except Exception:
        pass
    if "--stdio" in sys.argv:
        _stdio()
    else:
        port = int(os.getenv("ALMUJTAHED_MCP_PORT", "8765"))
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
