#!/usr/bin/env python3
"""مولّد وورد عبر Aspose.Words — عملية مستقلة على Python 3.13.

المكتبة الأولى (بناء OOXML في server.py) تبقى كما هي؛ هذا المسار يُستدعى
منها عند وجود بيئة aspose-venv، ويسقط إليها إن تعذّر.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

CENTER_KINDS = {
    "title", "meta", "bismillah", "biblioTitle", "tocTitle",
    "partTitle", "chapter", "chapterLabel", "chapterName",
}
BREAK_KINDS = {"biblioTitle", "tocTitle", "chapter", "partTitle"}
KEEP_KINDS = {"chapter", "partTitle"}
HEADING_STYLE_KEYS = {
    "title": "title", "meta": "meta", "h": "h", "biblioTitle": "h",
    "biblioItem": "biblio", "tocTitle": "h", "partTitle": "h",
    "chapter": "h", "chapterLabel": "h", "chapterName": "h",
}


def _style_of(styles: dict, key: str, fallback: dict) -> dict:
    out = dict(fallback or {})
    st = styles.get(key) if isinstance(styles, dict) else None
    if isinstance(st, dict):
        for k in ("font", "size", "weight", "color", "lh"):
            if st.get(k) not in (None, ""):
                out[k] = st[k]
    return out


def _is_bold(style: dict, extra: bool = False) -> bool:
    if extra:
        return True
    weight = (style or {}).get("weight")
    if isinstance(weight, (int, float)) and weight >= 600:
        return True
    if isinstance(weight, str) and weight.isdigit() and int(weight) >= 600:
        return True
    if isinstance(weight, str) and weight.lower() in ("bold", "bolder"):
        return True
    return False


def _size(style: dict, default: float = 12.0) -> float:
    try:
        return float((style or {}).get("size") or default)
    except Exception:
        return default


def _try_license(aw) -> None:
    candidates = [
        (os.environ.get("ALMOGHNI_ASPOSE_LICENSE") or "").strip(),
        str(Path.home() / "Library/Application Support/Almoghni/Aspose.Words.Python.NET.lic"),
        str(Path.home() / "Library/Application Support/Almoghni/Aspose.Words.lic"),
        str(Path.home() / "AppData/Roaming/Almoghni/Aspose.Words.lic"),
    ]
    for path in candidates:
        if path and Path(path).is_file():
            aw.License().set_license(path)
            return


def _apply_font(builder, style: dict, bold: bool = False, italic: bool = False, size: float | None = None):
    font = builder.font
    font.clear_formatting()
    name = str((style or {}).get("font") or "Amiri")
    sz = float(size) if size is not None else _size(style)
    is_bold = _is_bold(style, extra=bold)
    font.name = name
    font.name_ascii = name
    font.name_bi = name
    font.name_far_east = name
    font.bidi = True
    font.complex_script = True
    font.locale_id = 1025
    font.locale_id_bi = 1025
    font.size = sz
    font.size_bi = sz
    font.bold = is_bold
    font.bold_bi = is_bold
    font.italic = bool(italic)
    font.italic_bi = bool(italic)
    color = str((style or {}).get("color") or "").lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", color or ""):
        try:
            import aspose.pydrawing as drawing
            r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
            font.color = drawing.Color.from_argb(r, g, b)
        except Exception:
            pass


def _footnote_text(note) -> str:
    if not isinstance(note, dict):
        return " "
    parts = []
    for run in note.get("runs") or []:
        if isinstance(run, dict) and run.get("t"):
            parts.append(str(run["t"]))
    return "".join(parts).strip() or " "


def _write_runs(builder, aw, runs, base: dict, styles: dict, footnotes: list):
    fn_count = len(footnotes)
    for run in runs or []:
        if not isinstance(run, dict):
            continue
        text = str(run.get("t") or "")
        cls = run.get("cls")
        if cls == "chapterLabel":
            style = dict(base)
            style["size"] = max(11.0, round(_size(style, 16) * 0.65, 1))
        elif cls in ("quran", "hadith", "quote"):
            style = _style_of(styles, cls, base)
        else:
            style = base
        _apply_font(builder, style, bold=bool(run.get("b")), italic=bool(run.get("i")))
        if text:
            for ti, tseg in enumerate(text.split("\t")):
                if ti:
                    builder.write("\t")
                for i, seg in enumerate(tseg.split("\n")):
                    if i:
                        builder.insert_break(aw.BreakType.LINE_BREAK)
                    if seg:
                        builder.write(seg)
        fn = run.get("fn")
        if isinstance(fn, int) and 0 <= fn < fn_count:
            _apply_font(builder, base)
            builder.write("(")
            builder.insert_footnote(aw.notes.FootnoteType.FOOTNOTE, _footnote_text(footnotes[fn]))
            builder.write(")")


def _prepare_chapter_runs(block: dict) -> dict:
    chap_runs = []
    for run in block.get("runs") or []:
        if not isinstance(run, dict):
            continue
        parts = str(run.get("t") or "").split("\n", 1)
        chap_runs.append({**run, "t": parts[0], "cls": "chapterLabel"})
        if len(parts) > 1 and parts[1]:
            chap_runs.append({**run, "t": "\n" + parts[1]})
    if not chap_runs:
        return block
    out = dict(block)
    out["runs"] = chap_runs
    return out


def _apply_para(builder, aw, kind: str, body: dict, page_break: bool):
    pf = builder.paragraph_format
    pf.clear_formatting()
    pf.bidi = True
    pf.alignment = (
        aw.ParagraphAlignment.CENTER if kind in CENTER_KINDS else aw.ParagraphAlignment.JUSTIFY
    )
    pf.line_spacing_rule = aw.LineSpacingRule.MULTIPLE
    pf.line_spacing = 12
    pf.space_after = 3
    pf.space_before = 0
    pf.first_line_indent = 15 if kind == "p" else 0
    pf.keep_together = kind in KEEP_KINDS
    pf.keep_with_next = kind == "h"
    pf.page_break_before = bool(page_break or kind in BREAK_KINDS)
    if kind == "h":
        pf.space_before = min(30, max(10, _size(body)))
        pf.space_after = 3
    elif kind in ("chapter", "chapterLabel", "partTitle"):
        pf.space_before = 0
        pf.space_after = 4


def _write_toc_table(builder, aw, items: list, styles: dict, body: dict, known: set):
    table = builder.start_table()
    for it in items:
        try:
            lvl = max(1, min(3, int(it.get("lvl") or 1)))
        except Exception:
            lvl = 1
        bm = re.sub(r"[^A-Za-z0-9_]", "", str(it.get("bookmark") or ""))[:40]
        text = "".join(str(r.get("t") or "") for r in (it.get("runs") or []) if isinstance(r, dict))
        builder.insert_cell()
        builder.cell_format.preferred_width = aw.tables.PreferredWidth.from_percent(90)
        builder.cell_format.borders.line_style = aw.LineStyle.NONE
        pf = builder.paragraph_format
        pf.clear_formatting()
        pf.bidi = True
        pf.alignment = aw.ParagraphAlignment.RIGHT
        pf.line_spacing_rule = aw.LineSpacingRule.MULTIPLE
        pf.line_spacing = 12
        pf.space_after = 2
        pf.space_before = 0
        pf.right_indent = (lvl - 1) * 15
        _apply_font(builder, body)
        builder.write(text)
        builder.insert_cell()
        builder.cell_format.preferred_width = aw.tables.PreferredWidth.from_percent(10)
        builder.cell_format.borders.line_style = aw.LineStyle.NONE
        pf = builder.paragraph_format
        pf.clear_formatting()
        pf.bidi = True
        pf.alignment = aw.ParagraphAlignment.CENTER
        pf.line_spacing_rule = aw.LineSpacingRule.MULTIPLE
        pf.line_spacing = 12
        _apply_font(builder, body)
        if bm and bm in known:
            builder.insert_field(f"PAGEREF {bm} \\h")
        else:
            builder.write("-")
        builder.end_row()
    table.preferred_width = aw.tables.PreferredWidth.from_percent(100)
    table.allow_auto_fit = False
    table.bidi = True
    table.clear_borders()
    builder.end_table()


def _strip_trailing_empty(doc) -> None:
    try:
        body = doc.first_section.body
        last = body.last_paragraph
        if last is not None and not (last.get_text() or "").strip():
            last.remove()
    except Exception:
        pass


def _patch_update_fields(path: str) -> None:
    import io
    import zipfile
    src = Path(path).read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src), "r") as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/settings.xml":
                xml = data.decode("utf-8")
                if "updateFields" not in xml:
                    xml = re.sub(
                        r"(<w:settings\b[^>]*>)",
                        r'\1<w:updateFields w:val="true"/>',
                        xml,
                        count=1,
                    )
                data = xml.encode("utf-8")
            zout.writestr(item.filename, data)
    Path(path).write_bytes(buf.getvalue())


def build_docx(payload: dict, out_path: str) -> None:
    import aspose.words as aw

    _try_license(aw)
    styles = payload.get("styles") or {}
    blocks = payload.get("blocks") or []
    footnotes = payload.get("footnotes") or []
    total_chars = sum(
        len(str(r.get("t") or ""))
        for b in blocks if isinstance(b, dict)
        for r in (b.get("runs") or []) if isinstance(r, dict)
    )
    if len(blocks) > 6000 or len(footnotes) > 6000 or total_chars > 5_000_000:
        raise ValueError("payload too large")
    body = _style_of(styles, "body", {"font": "Amiri", "size": 12, "weight": 400})
    fn_style = _style_of(styles, "fn", {"font": body.get("font") or "Amiri", "size": 10, "weight": 400})

    doc = aw.Document()
    builder = aw.DocumentBuilder(doc)

    ps = doc.first_section.page_setup
    ps.paper_size = aw.PaperSize.A4
    ps.top_margin = aw.ConvertUtil.millimeter_to_point(20)
    ps.bottom_margin = aw.ConvertUtil.millimeter_to_point(24)
    ps.left_margin = aw.ConvertUtil.millimeter_to_point(18)
    ps.right_margin = aw.ConvertUtil.millimeter_to_point(18)
    ps.bidi = True
    ps.rtl_gutter = True

    try:
        normal = doc.styles.get_by_style_identifier(aw.StyleIdentifier.NORMAL)
        normal.font.name = body.get("font") or "Amiri"
        normal.font.name_bi = body.get("font") or "Amiri"
        normal.font.bidi = True
        normal.font.size = _size(body)
        normal.font.size_bi = _size(body)
        normal.font.locale_id_bi = 1025
        normal.paragraph_format.bidi = True
        normal.paragraph_format.alignment = aw.ParagraphAlignment.JUSTIFY
        normal.paragraph_format.line_spacing_rule = aw.LineSpacingRule.MULTIPLE
        normal.paragraph_format.line_spacing = 12
    except Exception:
        pass
    try:
        fn_s = doc.styles.get_by_style_identifier(aw.StyleIdentifier.FOOTNOTE_TEXT)
        fn_s.font.name = fn_style.get("font") or "Amiri"
        fn_s.font.name_bi = fn_style.get("font") or "Amiri"
        fn_s.font.bidi = True
        fn_s.font.size = _size(fn_style, 10)
        fn_s.font.size_bi = _size(fn_style, 10)
        fn_s.paragraph_format.bidi = True
        fn_s.paragraph_format.alignment = aw.ParagraphAlignment.JUSTIFY
    except Exception:
        pass

    restart = str(payload.get("footnote_restart") or "")
    doc.footnote_options.restart_rule = (
        aw.notes.FootnoteNumberingRule.CONTINUOUS
        if restart == "continuous"
        else aw.notes.FootnoteNumberingRule.RESTART_PAGE
    )
    try:
        doc.footnote_options.position = aw.notes.FootnotePosition.BOTTOM_OF_PAGE
    except Exception:
        pass
    doc.footnote_options.number_style = aw.NumberStyle.ARABIC

    known = set()
    for b in blocks:
        if isinstance(b, dict) and str(b.get("kind") or "") != "tocItem":
            nm = re.sub(r"[^A-Za-z0-9_]", "", str(b.get("bookmark") or ""))[:40]
            if nm:
                known.add(nm)

    title = str(payload.get("title") or "").strip()
    if title:
        try:
            doc.built_in_document_properties.title = title
            doc.built_in_document_properties.author = "المغني"
            doc.built_in_document_properties.comments = "almoghni-aspose"
        except Exception:
            pass

    pending_break = False
    biblio_counter = 0
    i = 0
    while i < len(blocks):
        b = blocks[i]
        i += 1
        if not isinstance(b, dict):
            continue
        kind = str(b.get("kind") or "")
        if kind == "pageBreak":
            pending_break = True
            continue
        if kind == "tocItem":
            group = [b]
            while i < len(blocks) and isinstance(blocks[i], dict) and str(blocks[i].get("kind") or "") == "tocItem":
                group.append(blocks[i])
                i += 1
            _write_toc_table(builder, aw, group, styles, body, known)
            pending_break = False
            continue
        if kind == "chapter":
            b = _prepare_chapter_runs(b)
        key = HEADING_STYLE_KEYS.get(kind, "body")
        base = _style_of(styles, key, body)
        _apply_para(builder, aw, kind, body, pending_break)
        if kind == "biblioItem":
            biblio_counter += 1
            num_ar = str(biblio_counter).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
            _apply_font(builder, base)
            builder.write(f"{num_ar}- ")
        bm = re.sub(r"[^A-Za-z0-9_]", "", str(b.get("bookmark") or ""))[:40]
        if bm:
            builder.start_bookmark(bm)
        _write_runs(builder, aw, b.get("runs"), base, styles, footnotes)
        if bm:
            builder.end_bookmark(bm)
        builder.insert_paragraph()
        pending_break = False

    _strip_trailing_empty(doc)
    try:
        doc.update_fields()
        doc.update_page_layout()
    except Exception:
        pass
    doc.save(out_path)
    _patch_update_fields(out_path)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: export_docx_aspose.py input.json output.docx", file=sys.stderr)
        return 2
    payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    build_docx(payload, argv[2])
    out = Path(argv[2])
    if not out.is_file() or out.stat().st_size < 800:
        print("aspose produced empty docx", file=sys.stderr)
        return 1
    print("aspose-words ok", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
