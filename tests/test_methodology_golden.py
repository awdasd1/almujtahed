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
