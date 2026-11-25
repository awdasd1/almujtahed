# -*- coding: utf-8 -*-
"""حالات ذهبية لمنهجية ضبط المغني (docs/13-منهجية-الضبط.md).

ثابتة بلا نماذج ولا شبكة. كل حالة من خطأ وقع في بحث فعلي:
أي تعديل يكسر واحدة منها يُرَدّ ولو حسّن موضعًا آخر.
التشغيل: .venv/bin/python -m unittest discover -s tests -v
"""
import html
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "web_ui"))

import server  # noqa: E402


def stamps(fragment):
    out = []
    for m in re.finditer(r'<span class="cit-src"([^>]*)>', fragment or ""):
        attrs = {mm.group(1).lower(): html.unescape(mm.group(2))
                 for mm in re.finditer(r'data-([a-z-]+)="([^"]*)"', m.group(1), re.I)}
        out.append(attrs)
    return out


def stamped(fragment, part, page):
    return [s for s in stamps(fragment)
            if str(s.get("part")) == str(part) and str(s.get("page")) == str(page)]


class CitationIdentityTests(unittest.TestCase):
    """يُذكر كتاب فتكون إحالته له وحده: لا قريب بالاسم ولا عام بلا مقيّد."""

    def assert_book(self, fragment, part, page, must, must_not=()):
        rows = stamped(fragment, part, page)
        self.assertTrue(rows, f"لا ختم عند ({part}-{page}) في: {fragment[:200]}")
        for row in rows:
            title = row.get("book") or ""
            self.assertTrue(any(w in title for w in must),
                            f"الكتاب المختوم «{title}» ليس المذكور {must}")
            for bad in must_not:
                self.assertNotIn(bad, title,
                                 f"الكتاب المختوم «{title}» يحمل المحظور «{bad}»")
        return rows

    def test_abu_yaala_is_not_musnad_muallal_nor_ahmad(self):
        out, _ = server.enrich_unstamped_citations(
            "انظر: مسند أبي يعلى لأبو يعلى الموصلي (1-309). "
            "أخرجه أبو يعلى في المسند، (1-309)")
        self.assert_book(out, 1, 309, must=("أبي يعلى", "ابي يعلى"),
                         must_not=("المصنف المعلل", "أحمد"))

    def test_bazzar_is_not_hakim(self):
        out, _ = server.enrich_unstamped_citations(
            "أخرجه البزار في المسند، (2-205)")
        self.assert_book(out, 2, 205, must=("البزار", "البحر الزخار"),
                         must_not=("الحاكم", "المستدرك"))

    def test_hakim_is_not_bazzar(self):
        out, _ = server.enrich_unstamped_citations(
            "أخرجه الحاكم في المستدرك، (5-574)")
        self.assert_book(out, 5, 574, must=("المستدرك",),
                         must_not=("البزار", "البحر الزخار"))

    def test_ahmad_stays_ahmad(self):
        out, _ = server.enrich_unstamped_citations(
            "انظر: مسند أحمد لأحمد بن حنبل (2-128). "
            "أخرجه أحمد في المسند حديث رقم (724)، (2-128)")
        self.assert_book(out, 2, 128, must=("أحمد",),
                         must_not=("يعلى",))

    def test_tabarani_awsat_is_not_kabir(self):
        out, _ = server.enrich_unstamped_citations(
            "انظر: المعجم الأوسط للطبراني (4-181). "
            "أخرجه الطبراني في المعجم الأوسط، حديث رقم (3917)، (4-181)")
        self.assert_book(out, 4, 181, must=("الأوسط",),
                         must_not=("الكبير",))

    def test_tabarani_kabir_stays_kabir(self):
        out, _ = server.enrich_unstamped_citations(
            "انظر: المعجم الكبير للطبراني (18-170). "
            "أخرجه الطبراني في المعجم الكبير، حديث رقم (381)، (18-170)")
        self.assert_book(out, 18, 170, must=("الكبير",),
                         must_not=("الأوسط",))

    def test_ibn_abi_shayba_musannaf_is_not_musnad(self):
        out, _ = server.enrich_unstamped_citations(
            "انظر: المصنف - ابن أبي شيبة (18-546). "
            "أخرجه ابن أبي شيبة في المصنف، حديث رقم (35972)، (18-546)")
        rows = self.assert_book(out, 18, 546, must=("ابن أبي شيبة",))
        for row in rows:
            self.assertIn("المصنف", row.get("book") or "")

    def test_realign_fixes_stamp_that_contradicts_named_book(self):
        wrong = (
            'انظر: <span class="cit-src" data-book="مسند أبي يعلى - ت حسين أسد" '
            'data-rel-path="x" data-book-id="4593" data-part="1" data-page="309" '
            'data-quote="">مسند أبي يعلى لأبو يعلى الموصلي (1-309)</span>. '
            'أخرجه أبو يعلى في المسند، '
            '<span class="cit-src" data-book="المسند المصنف المعلل" '
            'data-rel-path="y" data-book-id="5251" data-part="1" data-page="309" '
            'data-quote="">(1-309)</span>')
        fixed = server._realign_citation_stamps(wrong)
        rows = stamped(fixed, 1, 309)
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("يعلى", row.get("book") or "")
            self.assertEqual(str(row.get("book-id")), "4593")


class RealignBoundaryTests(unittest.TestCase):
    """إعادة الربط لا تعبر حاشية ولا تقرأ نص اقتباس مخفيًا (خطأ بحث ٠٠:٣٣)."""

    RAW = """<p>قال الحسن: لا طاعة لمخلوق في معصية الخالق<sup><small>(٩)</small></sup> وقال الدارقطني كلاما<sup><small>(١٠)</small></sup></p>
<ol>
<li id="fn9"><sup><small>(٩)</small></sup> ينظر: المصنف - ابن أبي شيبة (18-546).</li>
<li id="fn10"><sup><small>(١٠)</small></sup> ينظر: (5-155).</li>
<li id="fn29"><sup><small>(٢٩)</small></sup> انظر: العلل الواردة في الأحاديث النبوية للدارقطني (5-155).</li>
<li id="fn39"><sup><small>(٣٩)</small></sup> انظر: التمهيد - ابن عبد البر (23-277)؛ والتمهيد - ابن عبد البر (23-278).</li>
</ol>"""

    def pipeline(self):
        s1 = server.stamp_citation_sources(self.RAW, [])
        s2, _ = server.enrich_unstamped_citations(s1)
        s3, _stats = server._documentation_gate(s2, [], api_key="")
        return server._realign_citation_stamps(s3)

    def test_named_stamp_survives_previous_footnotes(self):
        out = self.pipeline()
        rows = stamped(out, 5, 155)
        self.assertTrue(rows, "ختم العلل (5-155) غائب")
        for row in rows:
            self.assertIn("الدارقطني", row.get("book") or "")
            self.assertNotIn("ابن أبي شيبة", row.get("book") or "")
        rows39 = stamped(out, 23, 277)
        self.assertTrue(rows39, "ختم التمهيد (23-277) غائب")
        for row in rows39:
            self.assertIn("التمهيد", row.get("book") or "")
            self.assertNotIn("أحمد", row.get("book") or "")

    def test_bare_locator_gets_no_guessed_book(self):
        out = self.pipeline()
        # الحاشية ١٠ موضع عارٍ بلا اسم كتاب: لا يبقى لها ختم بكتاب مخمَّن
        self.assertNotIn('id="fn10"', out)


class ImpossibleLocatorTests(unittest.TestCase):
    """موضع مستحيل في كتابه لا يُختم ولو حلّه الحلّال ضبابيًا.

    حادثة بحث ٠٠:٥٨: كتاب «جولة في كتابي (الأغاني) و(السيف اليماني)»
    لمحمد المجذوب — مقالات أدبية من مجلة، ٤٥٢ صفحة بلا أجزاء في
    المكتبة (صفحاته ٤١٧-٤٥٢) — خُتم بمواضع (36-281) و(1-454) و(5-161)
    لأن حارس الجزء كان يمرّر كل شيء إذا كان عدد المجلدات صفرًا/مجهولًا،
    ولا فحص أصلًا أن الصفحة موجودة في الكتاب."""

    def test_part_plausible_partless_and_bounds(self):
        self.assertFalse(server._part_plausible({"volumes": 0}, "5"))
        self.assertFalse(server._part_plausible({"volumes": 0}, "36"))
        self.assertTrue(server._part_plausible({"volumes": 0}, "1"))
        self.assertFalse(server._part_plausible({"volumes": 8}, "36"))
        self.assertTrue(server._part_plausible({"volumes": 8}, "9"))
        self.assertTrue(server._part_plausible({}, "36"))

    def test_majzoub_never_stamped_at_impossible_locators(self):
        out, _ = server.enrich_unstamped_citations(
            "انظر: جولة في كتابي (الأغاني) و (السيف اليماني) لمحمد المجذوب (5-161). "
            "وانظر: جولة في كتابي (الأغاني) و (السيف اليماني) لمحمد المجذوب (1-454).")
        for row in stamps(out):
            self.assertNotEqual(str(row.get("book-id")), "3707",
                                "خُتم كتاب المجذوب بموضع مستحيل فيه")

    def test_validator_downgrades_impossible_keeps_possible(self):
        text = (
            'انظر: <span class="cit-src" data-book="جولة في كتابي (الأغاني) و (السيف اليماني)" '
            'data-rel-path="32__الأدب/3707__x" data-book-id="3707" data-part="36" data-page="281" '
            'data-quote="">جولة في كتابي (الأغاني) و (السيف اليماني) لمحمد المجذوب (36-281)</span>. '
            'وانظر: <span class="cit-src" data-book="صحيح البخاري - ط السلطانية" '
            'data-rel-path="06__كتب-السنة/1458__x" data-book-id="1458" data-part="9" data-page="63" '
            'data-quote="">صحيح البخاري (9-63)</span>.')
        out = server._validate_citation_stamps(text)
        for row in stamps(out):
            self.assertNotEqual(str(row.get("book-id")), "3707")
        rows = stamped(out, 9, 63)
        self.assertTrue(rows and str(rows[0].get("book-id")) == "1458",
                        "ختم البخاري الصحيح يجب أن يبقى")


class GenericPhraseTests(unittest.TestCase):
    """عبارة عامة ليست اسم كتاب: لا تُحلّ ضبابيًا إلى كتاب يشاركها لفظًا.

    من فحص فعلي: «في الكبير» خُتمت الحاوي الكبير، و«في الشرح» الشرح
    الكبير على المقنع، و«في الرياض» الرياض النضرة، و«في الصحيحين»
    المستدرك على الصحيحين — مواضع ممكنة فيزيائيًا فلا يكفي حارس
    الاستحالة؛ الرفض هنا عند الحلّ نفسه، ويبقى ⚠ على ذمة النموذج."""

    GENERIC = ("في الكبير", "في الشرح", "في التفسير", "في الفتاوى",
               "في الرياض", "في الصحيحين", "في الجامع", "في التاريخ",
               "في الطبقات", "في الأوسط", "الشرح", "الكبير")

    def test_generic_phrases_get_no_stamp(self):
        for phrase in self.GENERIC:
            out, _ = server.enrich_unstamped_citations(
                f"انظر: {phrase} (3-100).")
            self.assertEqual(stamps(out), [],
                             f"العبارة العامة «{phrase}» خُتمت كتابًا")

    def test_distinctive_titles_still_stamp(self):
        cases = [
            ("انظر: المجموع للنووي (3-100).", "المجموع"),
            ("انظر: المغني لابن قدامة (3-100).", "المغني"),
            ("انظر: السنن الكبرى للبيهقي (3-100).", "السنن الكبرى"),
            ("انظر: تفسير ابن كثير (3-100).", "تفسير ابن كثير"),
            ("انظر: فتح الباري لابن حجر (13-242).", "فتح الباري"),
        ]
        for text, must in cases:
            out, _ = server.enrich_unstamped_citations(text)
            rows = stamps(out)
            self.assertTrue(rows, f"لا ختم في: {text}")
            self.assertIn(must, rows[0].get("book") or "")


class RuntimeLensTests(unittest.TestCase):
    """قاطع الاكتفاء لمحادثة بلا فريق فقط، والفريق لا يُتجاوز."""

    QUERY = "تخريج حديث إنما الأعمال بالنيات مختصر موثق دون الدخول في العلل المطولة"
    PROFILE = {"discipline": "حديث", "length": "مختصر"}

    def test_sufficiency_never_with_team(self):
        lens = server._research_runtime_lens(
            self.PROFILE, query=self.QUERY,
            agents=[{"name": "وكيل عزو المصادر", "desc": "تخريج"}])
        self.assertFalse(lens["sufficiency_eligible"])

    def test_sufficiency_in_concise_hadith_chat_without_team(self):
        lens = server._research_runtime_lens(
            self.PROFILE, query=self.QUERY, agents=None)
        self.assertTrue(lens["sufficiency_eligible"])

    def test_negated_depth_is_not_depth(self):
        self.assertFalse(server._named_hadith_needs_depth(self.QUERY))

    def test_requested_depth_is_depth(self):
        self.assertTrue(server._named_hadith_needs_depth(
            "تخريج حديث إنما الأعمال بالنيات مع دراسة العلل والطرق والمتابعات"))

    def test_named_matn_recognized_and_topic_word_is_not_matn(self):
        self.assertIn("إنما الأعمال بالنيات",
                      server._named_hadith_matn("حديث إنما الأعمال بالنيات") or "")
        self.assertIsNone(server._named_hadith_matn("حديث النية"))


class WorkspaceAndArchiveTests(unittest.TestCase):
    """مجلد الحفظ الآمن يُنشأ بمجلداته الفرعية الثمانية، والأرشفة
    تشمل المخطوطات والقراءة والتحليل، وبذور النسخة المشحونة خام."""

    def test_workspace_folders_created(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            server._ensure_workspace_folders(pathlib.Path(td))
            for name in ("المحادثات", "المشاريع", "الأدوات", "الوكلاء",
                         "المخطوطات", "القراءة والتحليل", "الأرشفة",
                         "صور النشر", "uploads"):
                self.assertTrue((pathlib.Path(td) / name).is_dir(), name)

    def test_archive_scopes_include_manuscripts_reading(self):
        scopes = server._normalize_archive_scopes(
            server.ArchiveCreateRequest(scopes=["manuscripts", "reading"]))
        self.assertEqual(scopes, ["manuscripts", "reading"])
        self.assertIn("المخطوطات", server._label_for_scopes(scopes))

    def test_shipped_seeds_are_raw(self):
        import json as _json
        import pathlib
        base = pathlib.Path(server.__file__).parent
        for name in ("default_chats.json", "default_projects.json",
                     "default_agent_groups.json"):
            self.assertEqual(_json.loads((base / name).read_text(
                encoding="utf-8")), [], name)
        seed = _json.loads((base / "static" / "default_settings.json")
                           .read_text(encoding="utf-8"))
        themes = {t.get("name") for t in seed.get("savedVisualThemes") or []}
        self.assertIn("الافتراضي", themes)
        self.assertFalse(any(seed.get("providers", {}).values()))


class BookOpenPerformanceTests(unittest.TestCase):
    """فتح إحالة لا يعيد تحليل ملف صفحات الكتاب كله عند كل جلسة،
    وموضعه يُجلب من قاموس مباشر — بطء ويندوز الفادح عند فتح الكتب
    الضخمة كان من بناء الفهرس سطرًا سطرًا في كل عملية."""

    def test_page_index_sidecar_and_lookup(self):
        import json as _json
        import tempfile
        import shamela_local_mcp as mcp
        with tempfile.TemporaryDirectory() as td:
            import pathlib
            d = pathlib.Path(td)
            rows = [
                {"part": "2", "page_num": 57, "page_id": 10,
                 "body": "نص الصفحة المطلوبة", "footnotes": ""},
                {"part": "2", "page_num": 58, "page_id": 11,
                 "body": "صفحة تالية", "footnotes": ""},
            ]
            (d / "pages.jsonl").write_text(
                "\n".join(_json.dumps(r, ensure_ascii=False) for r in rows),
                encoding="utf-8")
            (d / "book_metadata.json").write_text(
                _json.dumps({"book_id": 999001, "title_ar": "كتاب اختبار",
                             "authors": [], "rel_path": "x"}),
                encoding="utf-8")
            mcp._BOOK_INDEX_CACHE.clear()
            idx = mcp.get_book_index(d)
            self.assertTrue((d / "pages.idx.json").exists(),
                            "لم يُحفظ فهرس الصفحات قرصيًا")
            self.assertIn("2|57", idx["by_loc"])
            mcp._BOOK_INDEX_CACHE.clear()
            idx2 = mcp.get_book_index(d)
            self.assertEqual(idx2["by_loc"]["2|57"][0]["page_id"], 10)


class MethodologyContractTests(unittest.TestCase):
    """حراس نصية لعقود المنهجية حتى لا تُسقطها طبقة لاحقة بصمت."""

    def test_citation_rule_names_identity(self):
        self.assertIn("هوية الإحالة هي اسم الكتاب", server.CITATION_FORMAT_RULE)

    def test_blueprint_projects_dispatch_in_parallel(self):
        with open(os.path.join(ROOT, "web_ui", "static", "js", "projects.js"),
                  encoding="utf-8") as fh:
            self.assertIn("agent_dispatch_mode: 'parallel'", fh.read())

    def test_methodology_doc_exists_with_zero_guess(self):
        with open(os.path.join(ROOT, "docs", "13-منهجية-الضبط.md"),
                  encoding="utf-8") as fh:
            doc = fh.read()
        self.assertIn("صفر تخمين", doc)
        self.assertIn("مصدر حقيقة واحد", doc)

    def test_canonical_label_shape(self):
        label = server.canonical_citation_label(
            "مجموع الفتاوى", "2", "368", author="ابن تيمية")
        self.assertIn("مجموع الفتاوى", label)
        self.assertIn("(2-368)", label)


if __name__ == "__main__":
    unittest.main()
