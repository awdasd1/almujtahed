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


class WorkspacePendingFlagTests(unittest.TestCase):
    """طلب تغيير المجلد يفرض سؤال المستخدم عند الإقلاع التالي حتى لو
    وُجدت قاعدة مؤقتة مزروعة في مجلد التشغيل."""

    def test_pending_flag_forces_question(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            flag = root / "workspace-pending.flag"
            orig_flag = server._WORKSPACE_PENDING_FLAG
            orig_pointer = server._WORKSPACE_POINTER
            orig_legacy = server._legacy_data_exists
            try:
                server._WORKSPACE_PENDING_FLAG = flag
                server._WORKSPACE_POINTER = root / "workspace.json"
                server._legacy_data_exists = lambda: True
                flag.write_text("1", encoding="utf-8")
                path, from_ptr = server._workspace_decision()
                self.assertIsNone(path)
                self.assertFalse(from_ptr)
                flag.unlink()
                path, from_ptr = server._workspace_decision()
                self.assertEqual(path, server.BASE_DIR)
            finally:
                server._WORKSPACE_PENDING_FLAG = orig_flag
                server._WORKSPACE_POINTER = orig_pointer
                server._legacy_data_exists = orig_legacy


class WorkspaceBootIdTests(unittest.TestCase):
    """حالة مساحة العمل تحمل بصمة إقلاع العملية حتى لا تقرأ الواجهة
    جاهزية خادم قديم يموت أثناء إعادة التشغيل بعد حفظ المجلد."""

    def test_status_has_boot_id(self):
        import asyncio
        from starlette.requests import Request
        req = Request({"type": "http", "method": "GET",
                       "path": "/api/workspace/status", "headers": []})
        out = asyncio.run(server.workspace_status(req))
        self.assertTrue(out.get("boot"))


class WorkspacePickConfirmTests(unittest.TestCase):
    """اختيار مجلد الحفظ لا يحفظ ولا ينشئ شيئًا وحده؛ الحفظ بضغطة
    «حفظ المجلد» تأكيدًا فقط."""

    def test_pick_returns_path_without_saving(self):
        import asyncio
        from starlette.requests import Request
        calls = {"set": 0}
        orig_pick = server._native_pick_folder
        orig_set = server._set_workspace
        orig_admin = server.require_admin
        try:
            server.require_admin = lambda req: "admin"
            server._native_pick_folder = lambda: "/tmp/picked/folder"
            server._set_workspace = lambda p: calls.__setitem__(
                "set", calls["set"] + 1) or {}
            req = Request({"type": "http", "method": "POST",
                           "path": "/api/workspace/pick", "headers": []})
            out = asyncio.run(server.workspace_pick(req))
            self.assertEqual(out["path"], "/tmp/picked/folder")
            self.assertEqual(calls["set"], 0,
                             "الاختيار وحده نفّذ حفظًا قبل تأكيد المستخدم")
        finally:
            server._native_pick_folder = orig_pick
            server._set_workspace = orig_set
            server.require_admin = orig_admin


class SupervisorRestartContractTests(unittest.TestCase):
    """إعادة تشغيل ويندوز بيد المشرف لا بتوليد ذاتي: الخادم يخرج برمز
    إعادة التشغيل وlaunch.ps1 يعيد إقلاعه عبر start_local كاملًا.
    التوليد المنفصل السابق ([pythonw, server.py] بلا مجارٍ إخراج)
    كان يموت عند أول طباعة بصمت فيتوقف السيرفر نهائيًا."""

    def test_windows_restart_exits_with_supervisor_code(self):
        import os
        import sys
        from unittest import mock
        captured = []

        class FakeTimer:
            def __init__(self, interval, fn):
                self.fn = fn

            def start(self):
                self.fn()

        def no_spawn(*a, **k):
            raise AssertionError("توليد ذاتي ممنوع: الإعادة بيد المشرف")

        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(server.threading, "Timer", FakeTimer), \
                mock.patch.object(os, "_exit",
                                  side_effect=lambda c: captured.append(c)), \
                mock.patch("subprocess.Popen", no_spawn):
            server._restart_self()
        self.assertEqual(captured, [server._RESTART_EXIT_CODE])

    def test_launcher_loop_uses_same_code(self):
        import pathlib
        root = pathlib.Path(server.__file__).resolve().parent.parent
        ps1 = (root / "windows" / "launch.ps1").read_text(encoding="utf-8")
        self.assertIn(f"$restartCode = {server._RESTART_EXIT_CODE}", ps1)
        self.assertIn("while ($true)", ps1)
        src = pathlib.Path(server.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Popen([sys.executable] + sys.argv", src)

    def test_workspace_pick_prefers_host_bridge(self):
        import pathlib
        root = pathlib.Path(server.__file__).resolve().parent.parent
        js = (root / "web_ui" / "static" / "js" / "app.js").read_text(
            encoding="utf-8")
        self.assertIn("_pickFolderViaHost", js)
        self.assertIn("almoghniFolder", js)
        self.assertLess(js.index("await _pickFolderViaHost"),
                        js.index("fetch('/api/workspace/pick'"))


class WorkspaceRestartPatienceTests(unittest.TestCase):
    """إعادة إقلاع بعد حفظ المجلد قد تطول دقائق (استيراد + إحماء جسر):
    الواجهة تصبر وتطارد الخادم الجديد ولا تستسلم بتحميل في الفراغ ولا
    برسالة خطأ إنجليزية خام، والمشرف يعيد الإقلاع سريعًا بلا تعداد."""

    def test_frontend_waits_minutes_not_seconds(self):
        import pathlib
        root = pathlib.Path(server.__file__).resolve().parent.parent
        js = (root / "web_ui" / "static" / "js" / "app.js").read_text(
            encoding="utf-8")
        self.assertIn("i < 240", js)
        self.assertIn("_watchWorkspaceGate", js)
        self.assertIn("تعذّر الاتصال بخادم المغني", js)
        # ضياع رد الحفظ نفسه يُطارد ولا يُحكم عليه بالفشل فورًا
        self.assertIn("await _workspaceSaved({ path })", js)

    def test_supervisor_relaunch_is_fast(self):
        import pathlib
        root = pathlib.Path(server.__file__).resolve().parent.parent
        ps1 = (root / "windows" / "launch.ps1").read_text(encoding="utf-8")
        start = (root / "start_local.py").read_text(encoding="utf-8")
        self.assertIn("ALMOGHNI_FAST_RESTART", ps1)
        self.assertIn('os.environ.get("ALMOGHNI_FAST_RESTART")', start)
        self.assertIn("ALMOGHNI_T0", start)


class GpuProbeCacheTests(unittest.TestCase):
    """فحص كرت الشاشة/المحركات يُحسب مرة واحدة في عمر العملية؛ تكراره
    عند كل طلب موارد خنق خادم ويندوز عشرات الثواني لكل طلب."""

    def test_engine_probe_cached(self):
        server._GPU_ENGINE_CACHE.clear()
        first = server._engine_can_use_gpu()
        self.assertIn("engine", server._GPU_ENGINE_CACHE)
        self.assertEqual(server._engine_can_use_gpu(), first)


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


class ExternalArchiveRestoreTests(unittest.TestCase):
    """استرجاع نسخة مؤرشفة من أي مجلد خارجي: فحص يقرأ وصفها ويرفض
    المجلدات الغريبة، واسترجاع يستخدم منطق الأرشيف الداخلي نفسه."""

    def _make_archive(self, root):
        import json as _json
        import pathlib
        folder = pathlib.Path(root) / "archive_20260101_120000"
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(_json.dumps({
            "owner_id": server.ADMIN_OWNER_ID,
            "scopes": ["projects"],
            "counts": {"projects": 2},
            "note": "نسخة تجريبية",
            "created_at": "2026-01-01 12:00",
        }), encoding="utf-8")
        (folder / "projects_data.json").write_text(
            _json.dumps([{"id": "p1"}, {"id": "p2"}]), encoding="utf-8")
        return folder

    def test_inspect_and_restore_from_any_folder(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            folder = self._make_archive(td)
            info = server._inspect_archive_dir(str(folder))
            self.assertEqual(info["note"], "نسخة تجريبية")
            self.assertEqual(info["scopes"], ["projects"])
            self.assertIn("2 مشروع", info["summary"])

            saved = {}
            orig_status = server._book_index_status
            orig_assert = server._assert_book_index_stable
            orig_save = server.save_stored_projects
            try:
                server._book_index_status = lambda: {"books": 5}
                server._assert_book_index_stable = lambda b: {"books": 5}
                server.save_stored_projects = lambda items, owner: \
                    saved.update(items=items, owner=owner)
                out = server._restore_archive_dir(str(folder), "admin")
            finally:
                server._book_index_status = orig_status
                server._assert_book_index_stable = orig_assert
                server.save_stored_projects = orig_save
            self.assertTrue(out["restored_projects"])
            self.assertEqual(len(saved["items"]), 2)

    def test_inspect_rejects_foreign_folder(self):
        import tempfile
        from fastapi import HTTPException
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(HTTPException):
                server._inspect_archive_dir(td)

    def test_endpoints_and_ui_exist(self):
        import pathlib
        root = pathlib.Path(server.__file__).resolve().parent.parent
        src = pathlib.Path(server.__file__).read_text(encoding="utf-8")
        self.assertIn("/api/archives/restore-path/preview", src)
        self.assertIn("/api/archives/restore-path", src)
        js = (root / "web_ui" / "static" / "js" / "archive.js").read_text(
            encoding="utf-8")
        self.assertIn("restoreExternalArchive", js)
        html = (root / "web_ui" / "templates" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("externalArchivePath", html)


class WorkspaceMirrorTests(unittest.TestCase):
    """المرآة المقروءة: ملفات بشرية من الأعمال داخل المجلدات المسماة،
    تُحدَّث وتُحذف المستهلَكة، ولا تمسّ ملفًا وضعه المستخدم بيده."""

    def test_mirror_writes_readable_files(self):
        import pathlib
        import tempfile

        class FakeConn:
            def execute(self, *a):
                return iter([])

            def close(self):
                pass

        chat = {"id": "chat123456", "title": "بحث في السهو",
                "createdAt": "2026-01-01",
                "messages": [{"role": "user", "content": "سؤالي"},
                             {"role": "assistant", "content": "الجواب"}]}
        proj = {"id": "proj123456", "name": "مشروع الفقه",
                "query": "سؤال المشروع"}
        tool = {"id": "tool123456", "name": "أداة تجريبية",
                "python_code": "print('x')"}
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / "ws"
            root.mkdir()
            uploads = pathlib.Path(td) / "uploads"
            design = uploads / "admin" / "designs"
            design.mkdir(parents=True)
            (design / "a.png").write_bytes(b"\x89PNG")
            saved = {}
            names = ("_WORKSPACE_FROM_POINTER", "_ensure_app_memory",
                     "_read_chat_sessions", "load_stored_projects",
                     "load_stored_agent_groups", "load_stored_tools",
                     "_load_owned_list", "_rd_load_bundle",
                     "UPLOADS_BUCKET_DIR")
            for name in names:
                saved[name] = getattr(server, name)
            try:
                server._WORKSPACE_FROM_POINTER = root
                server._ensure_app_memory = lambda: FakeConn()
                server._read_chat_sessions = lambda c, o: [chat]
                server.load_stored_projects = lambda o: [proj]
                server.load_stored_agent_groups = lambda o: []
                server.load_stored_tools = lambda o: [tool]
                server._load_owned_list = lambda o, k: []
                server._rd_load_bundle = lambda o: {
                    "projects": [], "assistants": [], "readers": []}
                server.UPLOADS_BUCKET_DIR = uploads
                out = server._sync_workspace_mirror()
                self.assertTrue(out["enabled"], out)
                chat_files = list((root / "المحادثات").glob("*.md"))
                self.assertEqual(len(chat_files), 1)
                text = chat_files[0].read_text(encoding="utf-8")
                self.assertIn("## أنت", text)
                self.assertIn("الجواب", text)
                self.assertTrue(
                    list((root / "المشاريع").glob("*.md")))
                self.assertTrue(
                    (root / "صور النشر" / "a.png").exists())
                # ملف المستخدم الأجنبي يبقى، والمحادثة المحذوفة تُزال
                mine = root / "المحادثات" / "ملفي الخاص.txt"
                mine.write_text("لي", encoding="utf-8")
                server._read_chat_sessions = lambda c, o: []
                server._sync_workspace_mirror()
                self.assertTrue(mine.exists())
                self.assertEqual(
                    list((root / "المحادثات").glob("*.md")), [])
            finally:
                for name, value in saved.items():
                    setattr(server, name, value)

    def test_mirror_endpoints_and_ui_exist(self):
        import pathlib
        root = pathlib.Path(server.__file__).resolve().parent.parent
        src = pathlib.Path(server.__file__).read_text(encoding="utf-8")
        self.assertIn("/api/workspace/mirror", src)
        js = (root / "web_ui" / "static" / "js" / "archive.js").read_text(
            encoding="utf-8")
        self.assertIn("syncWorkspaceMirror", js)
        html = (root / "web_ui" / "templates" / "index.html").read_text(
            encoding="utf-8")
        self.assertIn("mirrorStatus", html)


class VirtualBookTests(unittest.TestCase):
    """كتب افتراضية: فتح كتاب غير مستخرج يبني فهرس مواضع فقط من قاعدة
    كتاب الشاملة ويجلب الصفحة عبر الجسر — لا استخراج نصوص بالجملة."""

    def test_fetch_pages_empty_is_free(self):
        import shamela_search
        self.assertEqual(shamela_search.fetch_pages(1, []),
                         {"status": "ok", "pages": {}})

    def test_virtual_index_from_page_table(self):
        import pathlib
        import tempfile
        import shamela_search
        rel = "اختبار/1__كتاب افتراضي"
        saved = {}
        for name in ("_their_id_for_book", "_virtual_book_dir",
                     "_book_meta_for_rel"):
            saved[name] = getattr(server, name)
        orig_table = shamela_search._page_table
        server.BOOK_PAGE_INDEX_CACHE.pop(rel, None)
        with tempfile.TemporaryDirectory() as td:
            bdir = pathlib.Path(td) / "book"
            try:
                server._their_id_for_book = lambda r, b=None: 4242
                server._virtual_book_dir = lambda r: bdir
                server._book_meta_for_rel = lambda r: {}
                shamela_search._page_table = lambda tid: {
                    3: ("2", 7), 1: ("", 1), 2: ("1", 4)}
                idx = server._virtual_index(rel)
                self.assertIsNotNone(idx)
                self.assertTrue(idx["virtual"])
                self.assertEqual([e["seq"] for e in idx["entries"]],
                                 [1, 2, 3])
                self.assertEqual(idx["parts"], ["1", "2"])
                self.assertEqual(idx["by_loc"]["2|7"], 2)
                self.assertTrue((bdir / "virtual_index.json").exists())
                # صفحات افتراضية: تُجلب مرة ثم تُقرأ من المخزن المحلي
                calls = {"n": 0}

                def fake_fetch(tid, seqs):
                    calls["n"] += 1
                    return {"status": "ok", "pages": {
                        str(s): {"body": "نص الصفحة",
                                 "footnotes": "حاشية"} for s in seqs}}

                orig_fetch = shamela_search.fetch_pages
                shamela_search.fetch_pages = fake_fetch
                try:
                    got = server._virtual_pages(idx, [2])
                    self.assertEqual(got[2]["body"], "نص الصفحة")
                    got = server._virtual_pages(idx, [2])
                    self.assertEqual(calls["n"], 1)
                finally:
                    shamela_search.fetch_pages = orig_fetch
                # كتاب صار مستخرجًا لا يعود افتراضيًا من ذاكرة قديمة
                (bdir / "pages.jsonl").write_text(
                    '{"part": "1", "page_num": 1, "body": "x"}\n',
                    encoding="utf-8")
                server.BOOK_PAGE_INDEX_CACHE[rel] = dict(idx)
                rebuilt = server.get_or_build_book_index(
                    rel, bdir / "pages.jsonl")
                self.assertFalse(rebuilt.get("virtual"))
            finally:
                for name, value in saved.items():
                    setattr(server, name, value)
                shamela_search._page_table = orig_table
                server.BOOK_PAGE_INDEX_CACHE.pop(rel, None)


class VirtualResolveTests(unittest.TestCase):
    """حلّ القراءة لكتاب غير مستخرج يحتفظ بمسار الكتالوج ويصل الافتراضي
    (كان مسار الكتالوج يضيع لأن باحث ملف الصفحات يعيد None مزدوجًا)."""

    def test_resolve_keeps_catalog_rel_for_virtual(self):
        class FakeCursor:
            def execute(self, *a):
                pass

            def fetchone(self):
                return {"rel_path": "shamela4_data/01__x/8586__y"}

        class FakeDB:
            def cursor(self):
                return FakeCursor()

        saved = {}
        for name in ("get_db", "_pages_file_for_rel", "_virtual_index"):
            saved[name] = getattr(server, name)
        try:
            server.get_db = lambda: FakeDB()
            server._pages_file_for_rel = lambda r: (None, None)
            sentinel = {"virtual": True, "entries": []}
            server._virtual_index = lambda rel, bid=None: sentinel
            rel, pages, virt = server._resolve_book_for_reading(
                None, None, 8586)
            self.assertEqual(rel, "01__x/8586__y")
            self.assertIsNone(pages)
            self.assertIs(virt, sentinel)
        finally:
            for name, value in saved.items():
                setattr(server, name, value)


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


class ShamelaPdfMappingTests(unittest.TestCase):
    """مقابلة النصي بالمصوّر بطريقة الشاملة حرفيًا: مفتاح الجزء من أول
    رقم في اسم الملف (00 غلاف «@@» لا متن)، وقطع «|» تلغي وتضيف
    («@N» فرق الترقيم)، وصفحة المصوّرة = المطبوعة + فرق ملف الجزء.
    الخلل الذي وقع: «الطبقات الكبرى» جُعل غلافُها (tisaad00، صفحة
    واحدة) مصوّرةَ جزئها الأول فانزاحت كل الأجزاء ملفًا كاملًا."""

    LINKS = ('{"files": ["tisaad00.pdf", "tisaad01p.pdf|المقدمة",'
             ' "tisaad01.pdf", "tisaad02.pdf|@-2", "book9.pdf|#3",'
             ' "one.pdf|7"]}')

    def _map(self):
        import shamela_pdf as sp
        return sp, sp._pdf_map(sp._parse_entries(self.LINKS))

    def test_parse_shamela_pieces(self):
        sp, _m = self._map()
        by_name = {e["name"]: e for e in sp._parse_entries(self.LINKS)}
        self.assertEqual(by_name["tisaad00.pdf"]["part"], "@@")
        self.assertEqual(by_name["tisaad01p.pdf"]["part"], "المقدمة")
        self.assertEqual(by_name["tisaad01.pdf"]["part"], "1")
        self.assertEqual(by_name["tisaad02.pdf"]["difference"], -2)
        self.assertEqual(by_name["book9.pdf"]["version"], 3)
        self.assertEqual(by_name["book9.pdf"]["part"], "9")
        self.assertEqual(by_name["one.pdf"]["part"], "7")

    def test_part_one_is_not_the_cover(self):
        sp, m = self._map()
        parts = ["المقدمة", "1", "2"]
        entry, key = sp._select_entry(m, "1", parts)
        self.assertEqual(entry["name"], "tisaad01.pdf")
        entry, key = sp._select_entry(m, "المقدمة", parts)
        self.assertEqual(entry["name"], "tisaad01p.pdf")
        # صفحة المصوّرة = المطبوعة + الفرق (هنا ‎-2)
        entry, key = sp._select_entry(m, "2", parts)
        self.assertEqual(50 + entry["difference"], 48)

    def test_missing_part_falls_to_zero_then_nothing(self):
        sp, m = self._map()
        entry, _k = sp._select_entry(m, "99", ["1", "2"])
        self.assertIsNone(entry, "جزء لا مقابل له عند الشاملة لا يُخترع له ملف")
        entry, _k = sp._select_entry({"0": m["1"]}, "99", ["1"])
        self.assertEqual(entry["name"], "tisaad01.pdf")

    def test_single_file_book_is_whole_book(self):
        sp, m = self._map()
        one = sp._pdf_map(sp._parse_entries('{"files": ["/1/41557.pdf"]}'))
        entry, _k = sp._select_entry(one, "", [])
        self.assertEqual(entry["name"], "41557.pdf")


class RemovedFeaturesTests(unittest.TestCase):
    """مُزالان بقرار المستخدم فلا يرجعان بصمت: بانر «رأس المسألة
    الفقهية الحاكمة» في نافذة تصفح الكتاب (كان يظهر [object Object])،
    وتحديد موضع الشاهد بصريًا على المصوّرة (غير منضبط)."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_no_fiqh_banner_in_reader(self):
        reader = self._read("web_ui/static/js/reader.js")
        self.assertNotIn("fiqhIssue", reader)
        self.assertNotIn("رأس المسألة الفقهية الحاكمة: ${", reader)

    def test_no_witness_locate_anywhere(self):
        self.assertNotIn("locatePdfWitness",
                         self._read("web_ui/templates/index.html"))
        self.assertNotIn("pdf-locate", self._read("web_ui/static/js/reader.js"))
        self.assertNotIn("pdf-locate", self._read("web_ui/static/js/reading.js"))
        import shamela_pdf
        self.assertFalse(hasattr(shamela_pdf, "locate_witness"))
        self.assertTrue(hasattr(shamela_pdf, "ocr_region_text"),
                        "قصاصة OCR بقيت — ليست هي المزالة")

    def test_no_auto_highlight_on_text_and_lens_search_exists(self):
        reader = self._read("web_ui/static/js/reader.js")
        self.assertNotIn("highlightReaderPhrase", reader,
                         "تحديد الشاهد التلقائي على الكتاب النصي مُزال")
        index = self._read("web_ui/templates/index.html")
        self.assertIn("btnReaderLensSearch", index)
        self.assertNotIn("بمنظار", index, "عبارة «بمنظار» مُزالة من الواجهة")
        self.assertNotIn("readerLensBar", index,
                         "شريط البحث القديم مُزال — نافذة لا شريط")
        self.assertIn("z-index:100600", reader,
                      "نافذة البحث فوق طبقة نافذة الكتاب (100500) لا تحتها")
        # النافذة مستنسخة من «بحث في الإجابة»: فتح وتحديد تلقائي وسابق/تالٍ
        for fn in ("openReaderSearch", "closeReaderSearch", "runReaderSearch",
                   "jumpToReaderMark", "stepReaderSearch",
                   "refreshReaderSearchIfOpen", "_ensureReaderSearchModal"):
            self.assertIn(fn, reader, fn)
        self.assertIn('oninput="runReaderSearch()"', reader,
                      "التحديد فوري أثناء الكتابة كما في بحث الإجابة")


class BookIdentityProbesTests(unittest.TestCase):
    """هوية الكتاب على منهج الشاملة: (اسم العمل + المؤلف) لا الرقم وحده
    ولا ضبابية الاسم. الاسم المشترك بلا مؤلف لا يُحسم لأحد الطرفين أبدًا
    («فتح الباري» ليس ابن حجر ولا ابن رجب حتى يُذكر المؤلف)، والمؤلف
    المصرّح به مرشّح حاسم، والختم الصامت على الملتبس ممنوع."""

    @classmethod
    def setUpClass(cls):
        import book_identity
        cls.bi = book_identity
        cls.db = str(server.DB_INDEX_PATH)

    def _ids(self, query):
        r = self.bi.resolve_book(query, self.db)
        return r.get("status"), set(r.get("book_ids") or [])

    def test_shared_name_without_author_never_resolves(self):
        for q in ("فتح الباري", "المجموع", "المغني", "الموطأ"):
            status, _ = self._ids(q)
            self.assertEqual(status, "candidates", q)

    def test_explicit_author_decides_namesakes(self):
        self.assertEqual(self._ids("فتح الباري لابن حجر")[1], {1455})
        self.assertEqual(self._ids("فتح الباري لابن رجب")[1], {128})
        self.assertEqual(self._ids("المجموع للنووي")[1], {1618})
        self.assertEqual(self._ids("السيرة النبوية لابن هشام")[1], {6180, 2621})

    def test_editions_group_under_one_work(self):
        status, ids = self._ids("صحيح البخاري")
        self.assertEqual(status, "resolved")
        self.assertIn(1458, ids)  # ط السلطانية رأس العمل

    def test_mcp_author_filter_and_head_gate(self):
        import shamela_local_mcp as mcp
        self.assertIn(mcp.resolve_book("السيرة النبوية لابن هشام").get("book_id"),
                      (6180, 2621))
        self.assertIsNone(mcp.resolve_book("الشرح الكبير لابن قدامة").get("book_id"))
        self.assertTrue(mcp.resolve_book("فتح الباري").get("ambiguous"))

    def test_stamp_gate_blocks_bare_ambiguous(self):
        out, _ = server.enrich_unstamped_citations("انظر: فتح الباري (3/45)")
        self.assertIn("cit-unresolved", out)
        out, _ = server.enrich_unstamped_citations("انظر: فتح الباري لابن رجب (3/45)")
        self.assertIn('data-book-id="128"', out)


class SearchTabCleanupTests(unittest.TestCase):
    """تبويب البحث: لا شارة «دلالي مباشر %» ولا زر «تحقق حرفي (MCP)»
    على البطاقات، وزر «بحث في النتائج» بجانب عدد النتائج يفتح نافذة
    على نسق «بحث في الإجابة» (تحديد تلقائي وسابق/تالٍ)."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_results_selection_tooltip_in_template(self):
        index = self._read("web_ui/templates/index.html")
        self.assertIn("resultsSelectionTooltip", index)
        self.assertIn("sendResultSelectionToChat()", index)
        self.assertIn('onmouseup="onResultsTextSelected()"', index)

    def test_badges_removed_and_results_search_exists(self):
        search = self._read("web_ui/static/js/search.js")
        self.assertNotIn("دلالي مباشر", search)
        self.assertNotIn("تحقق حرفي (MCP)", search)
        self.assertNotIn("مناقشة في الشات", search)
        # النقل إلى الشات بنمط القارئ: تظليل ثم «اضغط للمدارسة»
        self.assertIn("resultsSelectionTooltip", search)
        self.assertIn("onResultsTextSelected", search)
        self.assertIn("sendResultSelectionToChat", search)
        index = self._read("web_ui/templates/index.html")
        self.assertIn("btnSearchInResults", index)
        self.assertIn('onclick="openResultsSearch()"', index)
        for fn in ("openResultsSearch", "closeResultsSearch", "runResultsSearch",
                   "jumpToResultsMark", "stepResultsSearch",
                   "refreshResultsSearchIfOpen", "_ensureResultsSearchModal"):
            self.assertIn(fn, search, fn)
        self.assertIn('oninput="runResultsSearch()"', search)


class ChatBeautifyTests(unittest.TestCase):
    """تجميل المحادثة الافتراضي: KaTeX للرموز الرياضية واقتباس مميز
    مصنف للآيات والأحاديث وأقوال العلماء — ويتعطل كاملًا إن كان في
    مجموعة الإجابة وكيل تنسيق وطباعة (يبقى على تعليماته السابقة)."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_katex_vendored_and_loaded(self):
        self.assertTrue(os.path.exists(os.path.join(
            ROOT, "web_ui", "static", "vendor", "katex", "katex.min.js")))
        self.assertTrue(os.path.exists(os.path.join(
            ROOT, "web_ui", "static", "vendor", "katex", "katex.min.css")))
        self.assertTrue(os.path.exists(os.path.join(
            ROOT, "web_ui", "static", "vendor", "katex", "fonts",
            "KaTeX_Main-Regular.woff2")))
        index = self._read("web_ui/templates/index.html")
        self.assertIn("/static/vendor/katex/katex.min.css", index)
        self.assertIn("/static/vendor/katex/katex.min.js", index)

    def test_beautify_logic_and_formatting_gate(self):
        chat = self._read("web_ui/static/js/chat.js")
        for fn in ("_protectMath", "_restoreMath", "_scholarQuoteMarkdown",
                   "_classScholarQuotes", "_groupHasFormattingAgent",
                   "_msgHasFormattingAgent"):
            self.assertIn(fn, chat, fn)
        self.assertIn("formattingAgent: _msgHasFormattingAgent(msg)", chat)
        self.assertIn("scholar-quote-${kind}", chat)
        self.assertIn("'quran'", chat)
        self.assertIn("'hadith'", chat)
        css2 = self._read("web_ui/static/css/claude_theme.css")
        self.assertIn(".scholar-quote-quran", css2)
        self.assertIn(".scholar-quote-hadith", css2)
        css = self._read("web_ui/static/css/claude_theme.css")
        self.assertIn(".scholar-quote", css)
        self.assertIn(".math-display", css)


class OcrModelReflowTests(unittest.TestCase):
    """نماذج قراءة الصفحات على ويندوز قد ترجع كلمة في كل سطر (لوحظ في
    Gemini Flash): تُعاد تدفق الكلمات أسطرًا أفقية عند قلة كلمات السطر،
    والأسطر الطبيعية لا تُمس، والتوجيه يمنع التفريق أصلًا."""

    def test_reflow_wiring_and_behavior(self):
        import importlib.util
        with open(os.path.join(ROOT, "web_ui/doc_convert.py"), encoding="utf-8") as fh:
            conv = fh.read()
        self.assertIn("def _reflow_model_lines", conv)
        self.assertIn("_reflow_model_lines([{\"text\": l} for l in lines])", conv)
        self.assertIn("ولا تضع كلمة واحدة في سطر أبدًا", conv)
        spec = importlib.util.spec_from_file_location(
            "doc_convert_g", os.path.join(ROOT, "web_ui/doc_convert.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        frag = [{"text": w} for w in
                "قال رسول الله صلى الله عليه وسلم كلمة كلمة في أسطر كثيرة متفرقة هنا حتى يطول النص المفرق كثيرًا جدًا".split()]
        out = mod._reflow_model_lines(frag)
        self.assertLess(len(out), len(frag))
        self.assertGreater(len(out[0]["text"].split()), 5)
        normal = [{"text": "هذا سطر طبيعي كامل الكلمات في صفحة مقروءة"},
                  {"text": "وسطر ثان كامل أيضًا بكلماته المتصلة"}]
        self.assertEqual([l["text"] for l in mod._reflow_model_lines(normal)],
                         [n["text"] for n in normal])


class OcrVisualLineGroupingTests(unittest.TestCase):
    """قراءة الصفحات المصورة محليًا: محرك Vision يفرّق العربية كلمةً
    كلمة أحيانًا، فتُجمَّع الكلمات المتقاربة رأسيًا في أسطر أفقية
    يمينًا إلى يسار وإلا خرج النص عموديًا كلمةً في كل سطر."""

    def test_grouping_source_and_wiring(self):
        with open(os.path.join(ROOT, "web_ui/shamela_pdf.py"), encoding="utf-8") as fh:
            shamela = fh.read()
        self.assertIn("def group_visual_lines", shamela)
        self.assertIn("group_visual_lines(data.get(\"lines\") or [])", shamela)
        with open(os.path.join(ROOT, "web_ui/doc_convert.py"), encoding="utf-8") as fh:
            conv = fh.read()
        self.assertIn("shamela_pdf.group_visual_lines(raw)", conv)

    def test_grouping_behavior(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "shamela_pdf_g", os.path.join(ROOT, "web_ui/shamela_pdf.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        frag = [
            {"text": "كيف", "y": 0.205, "x": 0.75, "h": 0.03},
            {"text": "رأينا", "y": 0.206, "x": 0.85, "h": 0.03},
            {"text": "الإمام", "y": 0.2055, "x": 0.60, "h": 0.03},
            {"text": "في", "y": 0.244, "x": 0.80, "h": 0.03},
            {"text": "القصة", "y": 0.243, "x": 0.70, "h": 0.03},
        ]
        out = mod.group_visual_lines(frag)
        self.assertEqual([l["text"] for l in out], ["رأينا كيف الإمام", "في القصة"])
        full = [
            {"text": "سطر كامل أول", "y": 0.20, "x": 0.09, "h": 0.03},
            {"text": "سطر كامل ثان", "y": 0.24, "x": 0.09, "h": 0.03},
        ]
        self.assertEqual([l["text"] for l in mod.group_visual_lines(full)],
                         ["سطر كامل أول", "سطر كامل ثان"])


class DefaultModelsTabTests(unittest.TestCase):
    """تبويب «النماذج الافتراضية»: مرجع واحد لنسخ الصوت والصوت المولّد
    وقراء المخطوطات والمدقق وقارئ الصفحات المصورة ورسم الصور، والاختيارات
    ملغاة من مواضع الاستعمال وتُقرأ منه وحده."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_tab_exists_with_all_sections(self):
        html = self._read("web_ui/templates/index.html")
        self.assertIn("switchSettingsTab('defaultModels')", html)
        self.assertIn('id="setPaneDefaultModels"', html)
        for sid in ("dmSttSelect", "dmTtsSelect", "dmMsReader1Select", "dmMsReader2Select",
                    "dmMsReader3Select", "dmMsAuditorSelect", "dmPageReaderSelect", "dmImageSelect",
                    "dmEmbeddingSelect"):
            self.assertIn(f'id="{sid}"', html)
        self.assertIn("resetDefaultModel('stt')", html)
        self.assertIn("resetDefaultModel('image')", html)
        self.assertIn("resetDefaultModel('embedding')", html)
        # بطاقة معلومات النموذج عند التمرير كما في قائمة المحادثات
        self.assertGreaterEqual(html.count('data-model-picker="1"'), 9)

    def test_defaults_and_consumers(self):
        app = self._read("web_ui/static/js/app.js")
        self.assertIn("DEFAULT_MODEL_DEFS", app)
        self.assertIn("'google/gemini-4-neon'", app)
        self.assertIn("window.defaultModel = defaultModel", app)
        chat = self._read("web_ui/static/js/chat.js")
        self.assertIn("defaultModel('stt')", chat)
        self.assertIn("defaultModel('tts')", chat)
        self.assertIn("defaultModel('image')", chat)
        self.assertNotIn('id="presImageModel"', chat)
        self.assertNotIn('id="treeImgModel"', chat)
        ms = self._read("web_ui/static/js/manuscripts.js")
        self.assertIn("defaultModel('msReader1')", ms) if "defaultModel('msReader1')" in ms else self.assertIn("dm('msReader1'", ms)
        self.assertNotIn("function msSaveModelChoice", ms)
        docs = self._read("web_ui/static/js/documents.js")
        self.assertIn("defaultModel('pageReader')", docs)
        self.assertNotIn("pickDocOcrModel", docs)
        designs = self._read("web_ui/static/js/designs.js")
        self.assertIn("defaultModel('image')", designs)
        html = self._read("web_ui/templates/index.html")
        self.assertNotIn('id="designImageModel"', html)
        self.assertNotIn('id="docOcrModal"', html)
        self.assertNotIn('id="btnDocOcrPick"', html)

    def test_server_accepts_default_models(self):
        server = self._read("web_ui/server.py")
        self.assertIn("tts_model: Optional[str] = None", server)
        self.assertIn("model: Optional[str] = None", server)
        self.assertIn('DESIGN_IMAGE_MODELS["gpt54"]', server)
        self.assertIn("def _design_image_model_id", server)
        # كتالوج التضمينات يُجلب مع كتالوج النماذج لتصنيف قسم الفهرسة
        self.assertIn("api/v1/embeddings/models", server)

    def test_catalog_filtering_and_embedding_section(self):
        app = self._read("web_ui/static/js/app.js")
        self.assertIn("function dmCatalogModels", app)
        self.assertIn("embedding: { def: 'baai/bge-m3'", app)
        self.assertIn("image: { def: 'openai/gpt-5.4-image-2'", app)
        docs = self._read("web_ui/static/js/documents.js")
        self.assertIn("defaultModel('embedding')", docs)


class QuranFontsTests(unittest.TestCase):
    """خطوط القرآن الكريم برواياتها مدمجة وتتصدر قوائم الخطوط قبل
    خطوط جوجل بأسمائها العربية، وأوزان كل خط هي ما يعرض عند اختياره."""

    QURAN_FILES = {
        "hafs.ttf": "KFGQPC Hafs V3",
        "hafs-nastaliq.otf": "KFGQPC Nastaleeq",
        "warsh.ttf": "KFGQPC Warsh V3",
        "qalun.ttf": "KFGQPC Qalun V3",
        "shubah.ttf": "KFGQPC Shubah V3",
        "bazzi.ttf": "KFGQPC Bazzi V3",
        "susi.ttf": "KFGQPC Susi V3",
        "duri.ttf": "KFGQPC Douri Uthmanic Script",
    }

    def test_quran_font_files_exist(self):
        base = os.path.join(ROOT, "web_ui/static/fonts/quran")
        for name in self.QURAN_FILES:
            path = os.path.join(base, name)
            self.assertTrue(os.path.isfile(path), name)
            self.assertGreater(os.path.getsize(path), 100_000, name)

    def test_quran_catalog_matches_files_and_precedes_google(self):
        with open(os.path.join(ROOT, "web_ui/static/js/app.js"), encoding="utf-8") as fh:
            app = fh.read()
        self.assertIn("const QURAN_FONT_CATALOG", app)
        self.assertIn("خطوط القرآن الكريم", app)
        for family in self.QURAN_FILES.values():
            self.assertIn(family, app)
        for label in ("حفص عن عاصم", "ورش عن نافع المدني", "قالون عن نافع المدني",
                      "شعبة عن عاصم الكوفي", "البزي عن ابن كثير المكي",
                      "السوسي عن أبي عمرو البصري", "الدوري عن أبي عمرو البصري"):
            self.assertIn(label, app)
        # المجموعة تُزرع قبل مجموعة جوجل في بانِيات القوائم الثلاث
        self.assertGreaterEqual(app.count("appendQuranFontGroup(select)"), 3)
        self.assertIn("quran:", app)
        self.assertIn("fontChoiceWeights", app)
        self.assertIn("syncPrintWeightOptions", app)


class WebRefArrowTests(unittest.TestCase):
    """مراجع الويب في المحادثة: نص المرجع بلا رابط، والسهم المائل ↗
    في نهايته وحده هو الرابط، والروابط الداخلية لا تُمس."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_web_ref_arrow_wiring(self):
        chat = self._read("web_ui/static/js/chat.js")
        self.assertIn("function _webRefArrows", chat)
        self.assertIn('class="web-ref-arrow"', chat)
        self.assertIn("webRefs: true", chat)
        css = self._read("web_ui/static/css/claude_theme.css")
        self.assertIn(".web-ref-arrow", css)


class VoiceRecordingTests(unittest.TestCase):
    """مايك المحادثة: تسجيل بموجات مهتزة وإيقاف/إرسال/مسح، والنسخ
    عبر Gemini 4 Neon في نقطة خادم واحدة، ثم النص سؤالًا للنموذج."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_mic_ui_next_to_globe(self):
        index = self._read("web_ui/templates/index.html")
        globe = index.index('id="chatWebSearchBtn"')
        mic = index.index('id="chatMicBtn"')
        self.assertGreater(mic, globe, "المايك بجانب الكرة الأرضية")
        for el in ("voiceRecordBar", "voiceWave", "voiceRecordTime",
                   "voiceStopBtn", "voiceSendBtn", "voiceDiscardBtn"):
            self.assertIn(el, index, el)
        css = self._read("web_ui/static/css/claude_theme.css")
        self.assertIn("@keyframes voiceWaveDance", css)
        self.assertIn(".voice-record-bar", css)

    def test_voice_logic_and_endpoint(self):
        chat = self._read("web_ui/static/js/chat.js")
        for fn in ("toggleVoiceRecording", "stopVoiceRecording",
                   "discardVoiceRecording", "_transcribeVoiceBlob"):
            self.assertIn(fn, chat, fn)
        self.assertIn("/api/chat/transcribe", chat)
        srv = self._read("web_ui/server.py")
        self.assertIn('TRANSCRIBE_MODEL = "google/gemini-4-neon"', srv)
        self.assertIn('@app.post("/api/chat/transcribe")', srv)
        self.assertIn('"input_audio"', srv)


class CompareChatBoxTests(unittest.TestCase):
    """تبويب المقارنة: لا حاويات قديمة أسفل أعمدة الأجوبة، بل مربع
    حوار المحادثة نفسه، والسؤال/الرفع/اختيار المجموعات يذهب للنموذجين."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_compare_uses_chat_box_clone(self):
        index = self._read("web_ui/templates/index.html")
        pane = index[index.index('id="paneCompare"'):index.index('id="paneArchive"')]
        self.assertNotIn("compare-composer", pane)
        self.assertNotIn("compareContextSelect", pane)
        self.assertNotIn("compare-template-row", pane)
        self.assertIn('id="compareInput" class="chat-textarea"', pane)
        self.assertIn("compareFileUploadInput", pane)
        self.assertIn("compareGroupChecklistItems", pane)
        self.assertIn('id="compareSendBtn" onclick="submitCompareQuestion()"', pane)

    def test_compare_logic_sends_to_both_models(self):
        src = self._read("web_ui/static/js/compare.js")
        for fn in ("handleCompareFileSelected", "renderCompareAttachmentsPreview",
                   "toggleCompareGroupsDropdown", "toggleCompareGroup",
                   "compareChosenGroups", "compareMergedAgents",
                   "handleCompareInputKey", "stopCompareGeneration"):
            self.assertIn(fn, src, fn)
        self.assertIn("compareAttachments", src)
        self.assertIn("/api/chat/upload", src)


class BridgeSpeedContractTests(unittest.TestCase):
    """سرعة البحث على منهج الشاملة: فهرسهم الجاهز بجسر واحد دائم
    الإحماء حيث الكلفة أغلى من التوازي، وصيغة بحث واحدة ذكية،
    ومقاطع من حقول الفهرس المخزنة دون فتح ملفات صفحات."""

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_single_bridge_on_windows_and_low_ram(self):
        src = self._read("web_ui/shamela_search.py")
        self.assertIn('os.name == "nt"', src)
        self.assertIn("ALMOGHNI_BRIDGE_WORKERS", src)

    def test_smart_single_query_mode(self):
        src = self._read("web_ui/shamela_search.py")
        self.assertIn('mode == "smart"', src)
        srv = self._read("web_ui/server.py")
        self.assertIn('_m = "smart" if mode == "phrase" else mode', srv)

    def test_snippets_from_index_not_page_files(self):
        srv = self._read("web_ui/server.py")
        seg = srv[srv.index("def _shamela_bridge_candidates"):srv.index("def _fts_candidates")]
        self.assertNotIn("get_page", seg,
                         "بناء المرشحين من الجسر لا يفتح ملفات صفحات")
        self.assertIn('h.get("snippet")', seg)


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
