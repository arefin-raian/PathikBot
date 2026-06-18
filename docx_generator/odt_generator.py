"""
docx_generator/odt_generator.py — lxml-based ODT logsheet generator
============================================================
Populates pre-built ODT template variants from template_variants/ODT/
with real entry data. All Bengali text is converted to Bijoy encoding
(SutonnyMJ font). Used as intermediate format for PDF conversion.

Usage from bot:
    from docx_generator.odt_generator import generate_for_user
    out_path = generate_for_user(user_id, entries, month, year,
                                  tpl_dir=Path("template_variants/ODT"),
                                  out_dir=Path("output/ODT"))
"""

import calendar
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from lxml import etree
from docx_generator.bijoy_converter import convert_to_bijoy

NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_TEXT  = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_OFFICE= "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
NS_FO    = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
NS_DRAW  = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
NS_SVG   = "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
NS_XLINK = "http://www.w3.org/1999/xlink"

TAG_TABLE  = f"{{{NS_TABLE}}}table"
TAG_TR     = f"{{{NS_TABLE}}}table-row"
TAG_TC     = f"{{{NS_TABLE}}}table-cell"
TAG_CTC    = f"{{{NS_TABLE}}}covered-table-cell"
TAG_P      = f"{{{NS_TEXT}}}p"
TAG_SPAN   = f"{{{NS_TEXT}}}span"
TAG_FRAME  = f"{{{NS_DRAW}}}frame"
TAG_IMG    = f"{{{NS_DRAW}}}image"

SPAN_STYLE = "T2"

# Bijoy-encoded labels prefixed to each header cell (parallel to docx_generator).
HEADER_LABELS = {
    "company":     "‡Kv¤úvbxi bvg: ",
    "depot":       "wW‡cvi bvg: ",
    "motorcycle":  "gvUi mvB‡K‡ji eªvÛ: ",
    "name":        "Awdmv‡ii bvg: ",
    "designation": "c`ex: ",
}


def _set_odt_header_cell(cell, label_bijoy: str, value_unicode):
    """Overlay a header cell with `<label><bijoy(value)>` while preserving the
    paragraph style. No-op when value is empty so the template default survives.
    Uses the web converter when available (matches distributor handling)."""
    if not value_unicode:
        return
    try:
        from docx_generator.web_converter import convert_unicode_to_bijoy
        value_bijoy = convert_unicode_to_bijoy(value_unicode)
    except Exception:
        value_bijoy = convert_to_bijoy(value_unicode)
    paras = cell.findall(TAG_P)
    if not paras:
        return
    p = paras[0]
    # Capture existing span style so the font (SutonnyMJ) is preserved.
    style = SPAN_STYLE
    existing = p.findall(TAG_SPAN)
    if existing:
        s0 = existing[0].attrib.get(f"{{{NS_TEXT}}}style-name")
        if s0:
            style = s0
    for s in existing:
        p.remove(s)
    if p.text:
        p.text = ""
    p.append(make_span_text(f"{label_bijoy}{value_bijoy}", style))


BIJOY_MONTHS = {
    1:"Rvbyqvwi", 2:"†deªæqvwi", 3:"gvP©", 4:"GwcÖj",
    5:"†g",       6:"Ryb",       7:"RyjvB", 8:"AvMó",
    9:"†m‡Þ¤^i", 10:"A‡±vei", 11:"b‡f¤^i", 12:"wW‡m¤^i",
}

MONTHS_EN = {
    1:"January", 2:"February", 3:"March", 4:"April",
    5:"May", 6:"June", 7:"July", 8:"August",
    9:"September", 10:"October", 11:"November", 12:"December",
}

FALLBACK_BIJOY = (
    'vB AvwjKvj wewPevi gvbyl KzovB'
)


def make_span_text(bijoy_text: str, style: str = SPAN_STYLE):
    el = etree.Element(TAG_SPAN, attrib={f"{{{NS_TEXT}}}style-name": style})
    el.text = bijoy_text
    return el


def set_cell_simple(cell, bijoy_text: str, style: str = SPAN_STYLE):
    paras = cell.findall(TAG_P)
    for p in paras:
        spans = p.findall(TAG_SPAN)
        for s in spans:
            p.remove(s)
        # If the paragraph has text directly (not in span), clear it
        if p.text and p.text.strip():
            p.text = ""
    # Set text in first paragraph
    if paras:
        p = paras[0]
        existing_spans = p.findall(TAG_SPAN)
        if existing_spans:
            existing_spans[0].text = bijoy_text
            existing_spans[0].attrib[f"{{{NS_TEXT}}}style-name"] = style
        else:
            p.append(make_span_text(bijoy_text, style))


def set_cell_runs(cell, bijoy_texts: list, style: str = SPAN_STYLE):
    paras = cell.findall(TAG_P)
    for p in paras:
        spans = p.findall(TAG_SPAN)
        for s in spans:
            p.remove(s)
    if not paras:
        return
    p = paras[0]
    for t in bijoy_texts:
        if t:
            p.append(make_span_text(t, style))


def set_multi_paragraph_cell(cell, bijoy_texts: list, style: str = SPAN_STYLE):
    paras = cell.findall(TAG_P)
    old_style = None
    for p in paras:
        if old_style is None:
            old_style = p.attrib.get(f"{{{NS_TEXT}}}style-name")
        cell.remove(p)
    for t in bijoy_texts:
        if t:
            attrib = {}
            if old_style:
                attrib[f"{{{NS_TEXT}}}style-name"] = old_style
            p = etree.SubElement(cell, TAG_P, attrib=attrib)
            p.append(make_span_text(t, style))


def get_cell_text(cell):
    paras = cell.findall(TAG_P)
    parts = []
    for p in paras:
        spans = p.findall(TAG_SPAN)
        for s in spans:
            if s.text:
                parts.append(s.text)
        if p.text:
            parts.append(p.text)
    return " ".join(parts)


def get_data_tables(children):
    result = []
    for tag, data in children:
        if tag == "table:table":
            if "µwgK bs" in etree.tostring(data, encoding="unicode"):
                result.append(data)
        elif tag == "text:p":
            frames = data.findall(f".//{{{NS_DRAW}}}frame")
            for frame in frames:
                tbls = frame.findall(TAG_TABLE)
                for tbl in tbls:
                    xml_str = etree.tostring(tbl, encoding="unicode")
                    if "µwgK bs" in xml_str or "µwgK bs" in xml_str:
                        result.append(tbl)
    return result


def get_summary_table(children):
    for tag, data in children:
        if tag == "table:table":
            xml_str = etree.tostring(data, encoding="unicode")
            if "†gvU" in xml_str or "‡gvU" in xml_str:
                return data
    return None


def get_data_rows(tbl, header_count):
    rows = tbl.findall(TAG_TR)
    result = []
    for row in rows[header_count:]:
        xml_str = etree.tostring(row, encoding="unicode")
        if ("‡gvU" in xml_str or "†gvU" in xml_str) and "=" in xml_str:
            continue
        # ODT marks total rows with text:style-name="T17" (30pt font)
        if "T17" in xml_str:
            continue
        result.append(row)
    return result


def get_total_row(tbl, skip=1):
    rows = tbl.findall(TAG_TR)
    for row in rows[skip:]:
        xml_str = etree.tostring(row, encoding="unicode")
        if ("‡gvU" in xml_str or "†gvU" in xml_str) and "=" in xml_str:
            return row
        if "T17" in xml_str:
            return row
    return None


def get_total_row_across(data_tbls, max_idx=None):
    if max_idx is None:
        max_idx = len(data_tbls) - 1
    for ti in range(max_idx, -1, -1):
        skip = 5 if ti == 0 else 1
        tr = get_total_row(data_tbls[ti], skip)
        if tr is not None:
            return tr
    if max_idx != len(data_tbls) - 1:
        for ti in range(len(data_tbls) - 1, max_idx, -1):
            skip = 5 if ti == 0 else 1
            tr = get_total_row(data_tbls[ti], skip)
            if tr is not None:
                return tr
    return None


def fmt_taka(amount) -> str:
    if not amount:
        return ""
    return f"{int(amount):,}/-"


def fmt_num(value) -> str:
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else format(value, "f").rstrip("0").rstrip(".")
    return str(value)


def fmt_amount(value) -> str:
    return f"{int(value):,}" if isinstance(value, float) and value.is_integer() else f"{value:,}"


def template_stem(n: int) -> str:
    if not (3 <= n <= 30):
        raise ValueError(f"Entry count {n} out of range 3-30")
    remaining  = n - 3
    n4e        = remaining // 4
    pet        = remaining % 4
    total_pos  = pet + 1
    if n4e == 0:   return f"3HE_3PET{total_pos}_0EST"
    if n4e == 1:   return f"3HE_4E_3PET{total_pos}_0EST"
    return f"3HE_4E.{n4e}_3PET{total_pos}_0EST"


def fill_header(tbl0, month: int, year: int, prefs: dict | None = None):
    last_day = calendar.monthrange(year, month)[1]
    rows = tbl0.findall(TAG_TR)

    # Row 0, Cell 2 — month/year ("gv‡mi bvg: */**** Bs")
    r0c = rows[0].findall(f".//{TAG_TC}")
    spans = r0c[2].findall(f".//{TAG_SPAN}")
    for s in spans:
        if s.text and s.text.strip():
            s.text = f" gv‡mi bvg: {BIJOY_MONTHS[month]}/{year} Bs "
            break

    # Row 1, Cell 3 — date ("ZvwiL: **/**/**** Bs")
    r1c = rows[1].findall(f".//{TAG_TC}")
    spans2 = r1c[3].findall(f".//{TAG_SPAN}")
    for s in spans2:
        if s.text and s.text.strip():
            s.text = f"ZvwiL: {last_day:02d}/{month:02d}/{year} Bs "
            break

    # ── Per-user header overrides. Missing prefs keep the template defaults.
    p = prefs or {}
    if len(r0c) >= 1:
        _set_odt_header_cell(r0c[0], HEADER_LABELS["company"], p.get("header_company"))
    if len(r1c) >= 2:
        _set_odt_header_cell(r1c[0], HEADER_LABELS["depot"], p.get("header_depot"))
        _set_odt_header_cell(r1c[1], HEADER_LABELS["motorcycle"], p.get("header_motorcycle"))
    if len(rows) >= 3:
        r2c = rows[2].findall(f".//{TAG_TC}")
        if len(r2c) >= 2:
            _set_odt_header_cell(r2c[0], HEADER_LABELS["name"], p.get("header_name"))
            _set_odt_header_cell(r2c[1], HEADER_LABELS["designation"], p.get("header_designation"))


def fill_row(row, entry: dict):
    cells = [c for c in row.iterchildren() if c.tag in (TAG_TC, TAG_CTC)]
    # Filter to only actual table-cell elements
    cells = [c for c in row.findall(TAG_TC)]

    n = len(cells)

    if n >= 12:
        set_cell_simple(cells[0], f"{entry['serial']:02d}")
        set_cell_simple(cells[1], entry['date_str'])
        set_multi_paragraph_cell(cells[2], entry['distributors_runs'])
        set_cell_simple(cells[3], fmt_num(entry['odo_start']))
        set_cell_simple(cells[4], fmt_num(entry['odo_end']))
        set_cell_simple(cells[5], "00" if entry['total_km'] == 0 else fmt_num(entry['total_km']))

        if entry.get('petrol_liters', 0) > 0:
            set_cell_runs(cells[6], [str(int(entry['petrol_liters'])), " wjUvi"])
            set_cell_simple(cells[7], fmt_taka(entry['petrol_cost']))

        set_cell_simple(cells[8], fmt_taka(entry.get('mobil_cost', 0)))
        set_cell_simple(cells[9], fmt_taka(entry.get('da_amount', 0)))
        set_cell_simple(cells[10], fmt_taka(entry['total_cost']))

        mb = entry.get('manager_bijoy')
        if mb:
            if entry['entry_type'] == 'MONTHLY_MEETING':
                set_cell_simple(cells[11], "gvwmK wgwUs")
            else:
                set_cell_simple(cells[11], mb)

    elif n >= 10:
        set_cell_simple(cells[0], f"{entry['serial']:02d}")
        set_cell_simple(cells[1], entry['date_str'])
        set_multi_paragraph_cell(cells[2], entry['distributors_runs'])
        set_cell_simple(cells[3], "00" if entry['total_km'] == 0 else fmt_num(entry['total_km']))

        if entry.get('petrol_liters', 0) > 0:
            set_cell_runs(cells[4], [str(int(entry['petrol_liters'])), " wjUvi"])
            set_cell_simple(cells[5], fmt_taka(entry['petrol_cost']))

        set_cell_simple(cells[6], fmt_taka(entry.get('mobil_cost', 0)))
        set_cell_simple(cells[7], fmt_taka(entry.get('da_amount', 0)))
        set_cell_simple(cells[8], fmt_taka(entry['total_cost']))

        mb = entry.get('manager_bijoy')
        if mb:
            if entry['entry_type'] == 'MONTHLY_MEETING':
                set_cell_simple(cells[9], "gvwmK wgwUs")
            else:
                set_cell_simple(cells[9], mb)


def fill_total_row(total_row, entries):
    cells = total_row.findall(TAG_TC)
    total_km  = sum(e.get('total_km', 0) for e in entries)
    total_l   = sum(e.get('petrol_liters', 0) for e in entries)
    total_pet = sum(e.get('petrol_cost', 0) for e in entries)
    total_mob = sum(e.get('mobil_cost', 0) for e in entries)
    total_da  = sum(e.get('da_amount', 0) for e in entries)
    total_oth = sum(e.get('transport_fee', 0) for e in entries)
    grand     = total_pet + total_mob + total_da + total_oth

    if len(cells) >= 12:
        set_cell_runs(cells[5], [fmt_num(total_km), " wK:wg:"])
        set_cell_runs(cells[6], [str(int(total_l)), " wjUvi"])
        set_cell_simple(cells[7], fmt_taka(total_pet))
        set_cell_simple(cells[8], fmt_taka(total_mob))
        set_cell_simple(cells[9], fmt_taka(total_da))
        set_cell_simple(cells[10], f"{fmt_amount(grand)}/-")
    else:
        set_cell_runs(cells[4], [fmt_num(total_km), " wK:wg:"])
        lparts = []
        if total_l:  lparts += [str(int(total_l)), " wjUvi"]
        ps = fmt_taka(total_pet)
        if ps:       lparts.append(ps)
        if lparts:   set_cell_runs(cells[5], lparts)
        set_cell_simple(cells[6], fmt_taka(total_mob))
        set_cell_simple(cells[7], fmt_taka(total_da))
        set_cell_simple(cells[8], f"{fmt_amount(grand)}/-")


def fill_summary(summary_tbl, entries):
    rows = summary_tbl.findall(TAG_TR)

    total_tours   = len(entries)
    friday_tours  = sum(1 for e in entries if datetime.strptime(e['date'],'%Y-%m-%d').weekday() == 4)
    meeting_count = sum(1 for e in entries if e.get('entry_type') == 'MONTHLY_MEETING')
    mgr_tours     = sum(1 for e in entries if e.get('others_designation') and e['entry_type'] == 'REGULAR')
    under50       = sum(1 for e in entries if e.get('total_km', 0) < 50 and e['entry_type'] == 'REGULAR')
    net_tours     = max(0, total_tours - friday_tours - meeting_count)

    first_odo = entries[0]['odo_start']
    last_odo  = entries[-1]['odo_end']
    total_l   = sum(e.get('petrol_liters', 0) for e in entries)
    total_pet = sum(e.get('petrol_cost', 0) for e in entries)
    total_mob = sum(e.get('mobil_cost', 0) for e in entries)
    total_da  = sum(e.get('da_amount', 0) for e in entries)
    total_oth = sum(e.get('transport_fee', 0) for e in entries)
    grand     = total_pet + total_mob + total_da + total_oth
    fri_txt   = "bvB" if friday_tours == 0 else f"{friday_tours:02d}"

    def vc(ri):
        return rows[ri].findall(TAG_TC)

    c = vc(0)
    if len(c) >= 5:
        set_cell_runs(c[1], [f"{total_tours:02d}", " wU"])
        set_cell_runs(c[4], [str(int(total_l)), " wjUvi"])

    c = vc(1)
    if len(c) >= 4:
        set_cell_simple(c[1], fri_txt)
        set_cell_simple(c[3], f"({fmt_num(last_odo)}-{fmt_num(first_odo)}) wKwg")

    c = vc(2)
    if len(c) >= 4:
        set_cell_runs(c[1], [f"{meeting_count:02d}", " wU"])
        set_cell_runs(c[3], [fmt_amount(total_pet), " UvKv"])

    c = vc(3)
    if len(c) >= 4:
        set_cell_runs(c[1], [f"{mgr_tours:02d}", " wU"])
        set_cell_runs(c[3], [fmt_amount(total_mob), " UvKv"])

    c = vc(4)
    if len(c) >= 4:
        set_cell_simple(c[1], f"{under50:02d} wU")
        set_cell_runs(c[3], [fmt_amount(total_da), " UvKv"])

    c = vc(5)
    if len(c) >= 4:
        set_cell_runs(c[1], [f"{net_tours:02d}", " wU"])
        set_cell_runs(c[3], [fmt_amount(total_oth), " UvKv"])

    c = vc(6)
    if len(c) >= 4:
        set_cell_runs(c[3], [fmt_amount(grand), " UvKv"])


def _convert_entry(entry: dict, serial: int) -> dict:
    d = datetime.strptime(entry['date'], '%Y-%m-%d')
    date_str = f"{d.day:02d}/{d.month:02d}/{str(d.year)[2:]}"

    result = {
        'serial': serial,
        'date_str': date_str,
        'odo_start': entry['odo_start'],
        'odo_end': entry['odo_end'],
        'total_km': entry.get('total_km', 0),
        'petrol_liters': entry.get('petrol_liters', 0),
        'petrol_cost': entry.get('petrol_cost', 0),
        'mobil_cost': entry.get('mobil_cost', 0),
        'da_amount': entry.get('da_amount', 0),
        'transport_fee': entry.get('transport_fee', 0),
        'total_cost': entry['total_cost'],
        'entry_type': entry['entry_type'],
        'date': entry['date'],
    }

    if entry['entry_type'] == 'MONTHLY_MEETING':
        venue_b = convert_to_bijoy(entry.get('venue', ''))
        fee = int(entry.get('transport_fee', 0))
        transport_label_b = convert_to_bijoy("যাতায়াত ও আসা যাওয়ার ভাড়া")
        transport_b = f"{transport_label_b} = {fee}/-"
        result['distributors_runs'] = [venue_b, transport_b]
        result['manager_bijoy'] = "gvwmK wgwUs"
    else:
        raw_names = entry.get('distributors_raw', [])
        MESSRS_VARIANTS = ('মেসার্স ', 'মেসার্স', 'messrs ', 'messrs')
        unicode_lines = []
        for name in raw_names:
            clean = name.split("(")[0].split("（")[0].split("{")[0].strip()
            lower = clean.lower()
            for variant in MESSRS_VARIANTS:
                if lower.startswith(variant.lower()):
                    clean = clean[len(variant):].strip()
                    break
            unicode_lines.append('মেসার্স ' + clean + '|')
        full_unicode_block = '\n'.join(unicode_lines)
        try:
            from docx_generator.web_converter import convert_unicode_to_bijoy
            full_bijoy_block = convert_unicode_to_bijoy(full_unicode_block)
            result['distributors_runs'] = full_bijoy_block.split('\n')
        except Exception:
            MESSRS_BIJOY = convert_to_bijoy('মেসার্স') + ' '
            bijoy_runs = []
            for line in unicode_lines:
                clean = line.replace('মেসার্স ', '', 1).rstrip('|')
                bijoy_runs.append(MESSRS_BIJOY + convert_to_bijoy(clean) + "|")
            result['distributors_runs'] = bijoy_runs

        mgr = entry.get('others_designation', '')
        from docx_generator.english_transliteration import transliterate_english_to_bangla
        result['manager_bijoy'] = convert_to_bijoy(transliterate_english_to_bangla(mgr)) if mgr else ""

    return result


def generate_for_user(
    user_id: int,
    entries: list,
    month: int,
    year: int,
    tpl_dir: Path = Path("template_variants/ODT"),
    out_dir: Path = Path("output/ODT"),
    prefs: dict | None = None,
) -> str:
    n = len(entries)
    if n < 3:
        raise ValueError(f"Entry count {n} is less than minimum 3")
    if n > 30:
        raise ValueError(f"Entry count {n} exceeds maximum 30")

    stem = template_stem(n)
    tpl_path = Path(tpl_dir) / f"{stem}.odt"
    if not tpl_path.exists():
        raise FileNotFoundError(f"ODT template not found: {tpl_path}")

    work_dir = tempfile.mkdtemp(prefix="logsheet_odt_")
    try:
        with zipfile.ZipFile(tpl_path, "r") as z:
            z.extractall(work_dir)

        content_path = os.path.join(work_dir, "content.xml")
        tree = etree.parse(content_path)
        root = tree.getroot()

        # Find office:body > office:text
        body_el = root.find(f"{{{NS_OFFICE}}}body")
        if body_el is None:
            raise RuntimeError("No <office:body> found in content.xml")
        text_el = body_el.find(f"{{{NS_OFFICE}}}text")
        if text_el is None:
            raise RuntimeError("No <office:text> found in content.xml")

        # Collect direct children of office:text
        children = list(text_el)

        # Find all tables including those inside frames
        data_tbls = []
        summary_tbl = None
        for child in children:
            if child.tag == TAG_TABLE:
                xml_str = etree.tostring(child, encoding="unicode")
                if "µwgK bs" in xml_str:
                    data_tbls.append(child)
                elif "†gvU" in xml_str or "‡gvU" in xml_str:
                    summary_tbl = child
            elif child.tag == TAG_P:
                frames = child.findall(f".//{TAG_FRAME}")
                for frame in frames:
                    tbls = frame.findall(f".//{TAG_TABLE}")
                    for tbl in tbls:
                        xml_str = etree.tostring(tbl, encoding="unicode")
                        if "µwgK bs" in xml_str:
                            data_tbls.append(tbl)

        if not data_tbls:
            raise RuntimeError("No data tables found in ODT template")

        conv_entries = [_convert_entry(e, i + 1) for i, e in enumerate(entries)]

        fill_header(data_tbls[0], month, year, prefs)

        # Compute dynamic capacities from actual table structures
        caps = []
        for pi, tbl in enumerate(data_tbls):
            hdr = 5 if pi == 0 else 1
            data_rows = get_data_rows(tbl, hdr)
            caps.append(len(data_rows))

        # Split entries by capacities
        remaining = list(conv_entries)
        pages = []
        for cap in caps:
            pages.append(remaining[:cap])
            remaining = remaining[cap:]

        for pi, page_entries in enumerate(pages):
            tbl = data_tbls[pi]
            hdr = 5 if pi == 0 else 1
            data_rows = get_data_rows(tbl, hdr)
            for i, entry in enumerate(page_entries):
                if i < len(data_rows):
                    fill_row(data_rows[i], entry)

        last_data_page = max((i for i, p in enumerate(pages) if p), default=0)
        total_row = get_total_row_across(data_tbls, max_idx=last_data_page)
        if total_row is not None:
            fill_total_row(total_row, conv_entries)

        if summary_tbl is not None:
            fill_summary(summary_tbl, entries)

        xml_bytes = etree.tostring(
            tree,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=False,
            doctype=None,
        )
        # Replace lxml's single-quoted XML declaration with double-quoted version
        declaration = b'<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_bytes = declaration + xml_bytes.split(b"?>", 1)[1].lstrip(b"\n")
        # Strip loext namespace (Aspose.Words parser can't handle it)
        import re as _re
        xml_str = xml_bytes.decode("UTF-8")
        # Remove xmlns:loext="..." declaration
        xml_str = _re.sub(r'\s+xmlns:loext="[^"]*"', "", xml_str)
        # Remove any loext:attr="..." on elements
        xml_str = _re.sub(r'\s+loext:[a-zA-Z_-]+="[^"]*"', "", xml_str)
        xml_bytes = xml_str.encode("UTF-8")
        with open(content_path, "wb") as f:
            f.write(xml_bytes)

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"Logsheet - {MONTHS_EN[month]}'{year}.odt"

        if output_path.exists():
            output_path.unlink()

        with zipfile.ZipFile(str(output_path), "w", zipfile.ZIP_DEFLATED) as zout:
            # mimetype must be first, stored uncompressed (ODF spec)
            mimetype_path = os.path.join(work_dir, "mimetype")
            if os.path.exists(mimetype_path):
                zout.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            for dirpath, _, files in os.walk(work_dir):
                for fname in files:
                    if fname == "mimetype":
                        continue
                    fpath = os.path.join(dirpath, fname)
                    arcname = os.path.relpath(fpath, work_dir)
                    zout.write(fpath, arcname)

        return str(output_path)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
