"""
docx_generator/generate.py — lxml-based DOCX logsheet generator
=========================================================
Populates pre-built templates from generated_logsheets/ with
real entry data. All Bengali text is converted to Bijoy encoding
(SutonnyMJ font). Zero python-docx dependency.

Usage from bot:
    from generate_logsheet import generate_for_user
    out_path = generate_for_user(user_id, entries, month, year,
                                 tpl_dir=Path("generated_logsheets"),
                                 out_dir=Path("outputs"))

Standalone CLI:
    python generate_logsheet.py
"""

import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    print("ERROR: lxml is not installed.  Run:  pip install lxml")
    sys.exit(1)

from docx_generator.bijoy_converter import convert_to_bijoy

W         = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

BIJOY_MONTHS = {
    1:"Rvbyqvwi", 2:"†deªæqvwi", 3:"gvP©", 4:"GwcÖj",
    5:"†g",       6:"Ryb",       7:"RyjvB", 8:"AvMó",
    9:"†m‡Þ¤^i", 10:"A‡±vei", 11:"b‡f¤^i", 12:"wW‡m¤^i",
}

STD_RPR = (
    f'<w:rPr xmlns:w="{W}">'
    f'<w:rFonts w:ascii="SutonnyMJ" w:hAnsi="SutonnyMJ" w:cs="SutonnyMJ"/>'
    f'<w:b/><w:sz w:val="32"/><w:szCs w:val="32"/>'
    f'</w:rPr>'
)


def make_run(bijoy_text: str):
    safe = bijoy_text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    sp   = ' xml:space="preserve"' if bijoy_text[:1]==" " or bijoy_text[-1:]==" " else ""
    return etree.fromstring(
        f'<w:r xmlns:w="{W}">{STD_RPR}<w:t{sp}>{safe}</w:t></w:r>'
    )


def make_paragraph(bijoy_text: str):
    para = etree.fromstring(f'<w:p xmlns:w="{W}"/>')
    para.append(make_run(bijoy_text))
    return para


def set_multi_paragraph_cell(cell, bijoy_texts: list):
    for para in cell.findall(f"{{{W}}}p"):
        cell.remove(para)
    for text in bijoy_texts:
        if text:
            cell.append(make_paragraph(text))


def set_cell(cell, bijoy_text: str):
    para = cell.find(f"{{{W}}}p")
    for r in para.findall(f"{{{W}}}r"):
        para.remove(r)
    if bijoy_text:
        para.append(make_run(bijoy_text))


def set_runs(cell, bijoy_texts: list):
    para = cell.find(f"{{{W}}}p")
    for r in para.findall(f"{{{W}}}r"):
        para.remove(r)
    for t in bijoy_texts:
        if t:
            para.append(make_run(t))


def fmt_taka(amount) -> str:
    if not amount:
        return ""
    return f"{int(amount):,}/-"


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


def is_data_table(tbl):
    return "µwgK bs" in etree.tostring(tbl, encoding="unicode")


def is_summary_table(tbl):
    return "†gvU Uz¨i msL¨v:" in etree.tostring(tbl, encoding="unicode")


def get_total_row(tbl, skip=2):
    rows = tbl.findall(f"{{{W}}}tr")
    for row in rows[skip:]:
        x = etree.tostring(row, encoding="unicode")
        if ("‡gvU" in x or "†gvU" in x) and "=" in x:
            return row
    return None


def get_total_row_across(data_tbls, max_idx=None):
    if max_idx is None:
        max_idx = len(data_tbls) - 1
    for ti in range(max_idx, -1, -1):
        skip = 5 if ti == 0 else 2
        tr = get_total_row(data_tbls[ti], skip)
        if tr is not None:
            return tr
    if max_idx != len(data_tbls) - 1:
        for ti in range(len(data_tbls) - 1, max_idx, -1):
            skip = 5 if ti == 0 else 2
            tr = get_total_row(data_tbls[ti], skip)
            if tr is not None:
                return tr
    return None


def get_data_rows(tbl, header_count):
    rows = tbl.findall(f"{{{W}}}tr")
    result = []
    for row in rows[header_count:]:
        x = etree.tostring(row, encoding="unicode")
        if ("‡gvU" in x or "†gvU" in x) and "=" in x:
            continue
        result.append(row)
    return result


def fill_header(tbl0, month: int, year: int):
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    rows = tbl0.findall(f"{{{W}}}tr")

    # Row 0, Cell 1 — month/year label
    r0c = rows[0].findall(f".//{{{W}}}tc")
    para = r0c[1].find(f"{{{W}}}p")
    runs = para.findall(f"{{{W}}}r")
    if len(runs) >= 2:
        t_el = runs[1].find(f"{{{W}}}t")
        if t_el is not None:
            t_el.text = f" {BIJOY_MONTHS[month]}/{year}"
            t_el.set(XML_SPACE, "preserve")

    # Row 1, Cell 2 — date range
    r1c = rows[1].findall(f".//{{{W}}}tc")
    para2 = r1c[2].find(f"{{{W}}}p")
    runs2 = para2.findall(f"{{{W}}}r")
    for r in runs2[1:4]:
        para2.remove(r)
    new_run = make_run(f"{last_day:02d}/{month:02d}/{year}")
    remaining = para2.findall(f"{{{W}}}r")
    if remaining:
        remaining[0].addnext(new_run)
    else:
        para2.append(new_run)


def fill_row(row, entry: dict):
    cells = row.findall(f".//{{{W}}}tc")
    n = len(cells)

    # Page-1 tables have 12 cells (includes separate odo_start / odo_end /
    # total_km columns).  Page-2+ tables (4E / 3PET templates) are narrower
    # and only have 10 cells — the three odometer columns are absent.
    # Previously the function returned immediately for n < 12, which meant
    # every distributor name on page 2 onwards was silently never written.

    if n >= 12:
        # ── Full layout (page 1) ──────────────────────────────────────────
        set_cell(cells[0],  f"{entry['serial']:02d}")
        set_cell(cells[1],  entry['date_str'])
        set_multi_paragraph_cell(cells[2],  entry['distributors_runs'])
        set_cell(cells[3],  str(entry['odo_start']))
        set_cell(cells[4],  str(entry['odo_end']))
        set_cell(cells[5],  "00" if entry['total_km'] == 0 else str(entry['total_km']))

        if entry.get('petrol_liters', 0) > 0:
            set_runs(cells[6], [str(int(entry['petrol_liters'])), " wjUvi"])
            set_cell(cells[7], fmt_taka(entry['petrol_cost']))

        set_cell(cells[8],  fmt_taka(entry.get('mobil_cost', 0)))
        set_cell(cells[9],  fmt_taka(entry.get('da_amount', 0)))
        set_cell(cells[10], fmt_taka(entry['total_cost']))

        mb = entry.get('manager_bijoy')
        if mb:
            if entry['entry_type'] == 'MONTHLY_MEETING':
                set_cell(cells[11], "gvwmK wgwUs")
            else:
                set_cell(cells[11], mb)

    elif n >= 10:
        # ── Compact layout (page 2+, no odo columns) ─────────────────────
        set_cell(cells[0],  f"{entry['serial']:02d}")
        set_cell(cells[1],  entry['date_str'])
        set_multi_paragraph_cell(cells[2],  entry['distributors_runs'])
        set_cell(cells[3],  "00" if entry['total_km'] == 0 else str(entry['total_km']))

        if entry.get('petrol_liters', 0) > 0:
            set_runs(cells[4], [str(int(entry['petrol_liters'])), " wjUvi"])
            set_cell(cells[5], fmt_taka(entry['petrol_cost']))

        set_cell(cells[6],  fmt_taka(entry.get('mobil_cost', 0)))
        set_cell(cells[7],  fmt_taka(entry.get('da_amount', 0)))
        set_cell(cells[8],  fmt_taka(entry['total_cost']))

        mb = entry.get('manager_bijoy')
        if mb:
            if entry['entry_type'] == 'MONTHLY_MEETING':
                set_cell(cells[9], "gvwmK wgwUs")
            else:
                set_cell(cells[9], mb)

    # Fewer than 10 cells → unrecognised row shape, skip silently


def fill_total_row(total_row, entries):
    cells = total_row.findall(f".//{{{W}}}tc")
    total_km  = sum(e.get('total_km', 0) for e in entries)
    total_l   = sum(e.get('petrol_liters', 0) for e in entries)
    total_pet = sum(e.get('petrol_cost', 0) for e in entries)
    total_mob = sum(e.get('mobil_cost', 0) for e in entries)
    total_da  = sum(e.get('da_amount', 0) for e in entries)
    total_oth = sum(e.get('transport_fee', 0) for e in entries)
    grand     = total_pet + total_mob + total_da + total_oth

    if len(cells) >= 12:
        set_runs(cells[5],  [str(total_km), " wK:wg:"])
        set_runs(cells[6],  [str(int(total_l)), " wjUvi"])
        set_cell(cells[7],  fmt_taka(total_pet))
        set_cell(cells[8],  fmt_taka(total_mob))
        set_cell(cells[9],  fmt_taka(total_da))
        set_cell(cells[10], f"{grand:,}/-")
    else:
        set_runs(cells[4], [str(total_km), " wK:wg:"])
        lparts = []
        if total_l:  lparts += [str(int(total_l)), " wjUvi"]
        ps = fmt_taka(total_pet)
        if ps:       lparts.append(ps)
        if lparts:   set_runs(cells[5], lparts)
        set_cell(cells[6], fmt_taka(total_mob))
        set_cell(cells[7], fmt_taka(total_da))
        set_cell(cells[8], f"{grand:,}/-")


def fill_summary(summary_tbl, entries):
    rows = summary_tbl.findall(f"{{{W}}}tr")

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
        return rows[ri].findall(f".//{{{W}}}tc")

    c = vc(0); set_runs(c[1], [f"{total_tours:02d}", " wU"]);  set_runs(c[4], [str(int(total_l)), " wjUvi"])
    c = vc(1); set_cell(c[1], fri_txt);                         set_cell(c[4], f"({last_odo}-{first_odo}) wKwg")
    c = vc(2); set_runs(c[1], [f"{meeting_count:02d}", " wU"]); set_runs(c[4], [f"{total_pet:,}", " UvKv"])
    c = vc(3); set_runs(c[1], [f"{mgr_tours:02d}", " wU"]);     set_runs(c[4], [f"{total_mob:,}", " UvKv"])
    c = vc(4); set_cell(c[1], f"{under50:02d} wU");             set_runs(c[4], [f"{total_da:,}", " UvKv"])
    c = vc(5); set_runs(c[1], [f"{net_tours:02d}", " wU"]);     set_runs(c[4], [f"{total_oth:,}", " UvKv"])
    c = vc(6); set_runs(c[4], [f"{grand:,}", " UvKv"])


def _fix_namespace_header(xml_bytes: bytes) -> bytes:
    NEEDED = {
        "w14": b'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"',
        "w15": b'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"',
        "w16se": b'xmlns:w16se="http://schemas.microsoft.com/office/word/2015/wordml/symex"',
        "wp14": b'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"',
    }
    missing = [decl for prefix, decl in NEEDED.items()
               if decl not in xml_bytes]
    if not missing:
        return xml_bytes
    inject = b" ".join(missing) + b" "
    marker = b"<w:document "
    pos = xml_bytes.find(marker)
    if pos == -1:
        return xml_bytes
    insert_at = pos + len(marker)
    return xml_bytes[:insert_at] + inject + xml_bytes[insert_at:]


def validate_docx(path: str) -> bool:
    try:
        with zipfile.ZipFile(path, "r") as z:
            xml = z.read("word/document.xml")
        root = etree.fromstring(xml)
        mc_ns = "http://schemas.openxmlformats.org/markup-compatibility/2006"
        ignorable = root.get(f"{{{mc_ns}}}Ignorable", "")
        missing = [pfx for pfx in ignorable.split() if pfx not in root.nsmap]
        if missing:
            print(f"  Namespace warnings (undeclared Ignorable prefixes): {missing}")
            return False
        return True
    except Exception as e:
        print(f"  Validation error: {e}")
        return False


def _convert_entry(entry: dict, serial: int) -> dict:
    """Convert a bot entry dict to the internal format for fill_row()."""
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
        # FIX: Convert only the Bengali part of the ভাড়া label separately,
        # then append the ASCII number and suffix as plain strings.
        # Previously the whole f-string (Bengali + digits + "/-") was passed
        # to convert_to_bijoy, which caused the ড় in ভাড়া to be mangled by
        # the no-op NFC normalisation bug.  Keeping Bengali and ASCII separate
        # also makes the intent clearer and avoids any future encoding issues.
        transport_label_b = convert_to_bijoy("যাতায়াত ও আসা যাওয়ার ভাড়া")
        transport_b = f"{transport_label_b} = {fee}/-"
        # FIX: Use two separate paragraph entries instead of joining with "|"
        # so set_multi_paragraph_cell() renders them on separate lines in the
        # cell, which matches the visual layout of the original template.
        result['distributors_runs'] = [venue_b, transport_b]
        result['manager_bijoy'] = "gvwmK wgwUs"
    else:
        raw_names = entry.get('distributors_raw', [])
        # The bot inconsistently prepends মেসার্স (Messrs) to distributor
        # names in some entries but omits it in others (typically page 2+).
        # Normalise: strip any existing variant first, then always prepend,
        # so every name in the logsheet gets the prefix uniformly.
        MESSRS_UNICODE = 'মেসার্স'
        MESSRS_VARIANTS = ('মেসার্স ', 'মেসার্স', 'messrs ', 'messrs')
        MESSRS_BIJOY = convert_to_bijoy(MESSRS_UNICODE) + ' '
        bijoy_runs = []
        for name in raw_names:
            clean = name.split("(")[0].split("（")[0].split("{")[0].strip()
            lower = clean.lower()
            for variant in MESSRS_VARIANTS:
                if lower.startswith(variant.lower()):
                    clean = clean[len(variant):].strip()
                    break
            bijoy_runs.append(MESSRS_BIJOY + convert_to_bijoy(clean) + "|")
        result['distributors_runs'] = bijoy_runs

        mgr = entry.get('others_designation', '')
        result['manager_bijoy'] = convert_to_bijoy(mgr) if mgr else ""

    return result


def generate_for_user(
    user_id: int,
    entries: list,
    month: int,
    year: int,
    tpl_dir: Path = Path("generated_logsheets"),
    out_dir: Path = Path("outputs"),
) -> str:
    n = len(entries)
    if n < 3:
        raise ValueError(f"Entry count {n} is less than minimum 3")
    if n > 30:
        raise ValueError(f"Entry count {n} exceeds maximum 30")

    stem = template_stem(n)
    tpl_path = Path(tpl_dir) / f"{stem}.docx"
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tpl_path}")

    work_dir = tempfile.mkdtemp(prefix="logsheet_")
    try:
        with zipfile.ZipFile(tpl_path, "r") as z:
            z.extractall(work_dir)

        doc_path = os.path.join(work_dir, "word", "document.xml")
        tree = etree.parse(doc_path)
        body = tree.getroot().find(f"{{{W}}}body")

        all_tbls = body.findall(f"{{{W}}}tbl")
        data_tbls = [t for t in all_tbls if is_data_table(t)]
        if not data_tbls:
            raise RuntimeError("No data tables found in template")

        summary_tbl = all_tbls[-1]
        conv_entries = [_convert_entry(e, i + 1) for i, e in enumerate(entries)]

        fill_header(data_tbls[0], month, year)

        remaining = list(conv_entries)
        pages = []
        pages.append(remaining[:3]); remaining = remaining[3:]
        for _ in range(len(data_tbls) - 2):
            pages.append(remaining[:4]); remaining = remaining[4:]
        pages.append(remaining)

        for pi, page_entries in enumerate(pages):
            tbl = data_tbls[pi]
            hdr_count = 5 if pi == 0 else 2
            data_rows = get_data_rows(tbl, hdr_count)
            for i, entry in enumerate(page_entries):
                if i < len(data_rows):
                    fill_row(data_rows[i], entry)

        last_data_page = max((i for i, p in enumerate(pages) if p), default=0)
        total_row = get_total_row_across(data_tbls, max_idx=last_data_page)
        if total_row is not None:
            fill_total_row(total_row, conv_entries)

        fill_summary(summary_tbl, entries)

        tree.write(doc_path, xml_declaration=True, encoding="UTF-8", standalone=True)

        with open(doc_path, "rb") as f:
            xml_bytes = f.read()
        fixed = _fix_namespace_header(xml_bytes)
        with open(doc_path, "wb") as f:
            f.write(fixed)

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"Logsheet_{month}_{year}.docx"

        if os.path.exists(str(output_path)):
            os.remove(str(output_path))
        with zipfile.ZipFile(str(output_path), "w", zipfile.ZIP_DEFLATED) as zout:
            for dirpath, _, files in os.walk(work_dir):
                for fname in files:
                    fpath = os.path.join(dirpath, fname)
                    arcname = os.path.relpath(fpath, work_dir)
                    zout.write(fpath, arcname)

        if not validate_docx(str(output_path)):
            pass

        return str(output_path)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def ask_int(prompt, lo, hi):
    while True:
        try:
            v = int(input(prompt).strip())
            if lo <= v <= hi:
                return v
            print(f"  Enter a number between {lo} and {hi}.")
        except ValueError:
            print("  Enter a valid integer.")


def main():
    import calendar
    from datetime import date
    import random

    print("=" * 60)
    print("  Logsheet Generator — Bot Data")
    print("=" * 60)

    script_dir = Path(__file__).parent
    tpl_dir = script_dir / "generated_logsheets"

    if not tpl_dir.exists():
        print(f"ERROR: 'generated_logsheets/' not found at:\n  {tpl_dir}")
        sys.exit(1)

    user_file = script_dir / "data" / "entries_6161189904.json"
    if not user_file.exists():
        print(f"No entry file found at {user_file}")
        sys.exit(1)

    with open(user_file, encoding="utf-8") as f:
        all_entries = json.load(f)

    months_available = set()
    for e in all_entries:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        months_available.add((dt.year, dt.month))

    sorted_months = sorted(months_available, reverse=True)
    print("\n  Available months:")
    for y, m in sorted_months:
        print(f"    {y}-{m:02d}")

    year = ask_int("\n  Year (e.g. 2026): ", 2000, 2100)
    month = ask_int("  Month (1–12): ", 1, 12)

    entries = [e for e in all_entries
               if datetime.strptime(e['date'], '%Y-%m-%d').month == month
               and datetime.strptime(e['date'], '%Y-%m-%d').year == year]

    if len(entries) < 3:
        print(f"\n  Only {len(entries)} entries for {year}-{month:02d}. Need 3–30.")
        sys.exit(1)
    if len(entries) > 30:
        print(f"\n  {len(entries)} entries exceeds max 30. Split by month.")
        sys.exit(1)

    stem = template_stem(len(entries))
    tpl_path = tpl_dir / f"{stem}.docx"
    if not tpl_path.exists():
        print(f"\n  Template not found: {tpl_path}")
        sys.exit(1)

    out_dir = script_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(out_dir / f"Logsheet_{month}_{year}_{len(entries)}entries.docx")

    print(f"\n  Entries : {len(entries)}")
    print(f"  Template: {stem}.docx")
    print(f"  Output  : {output_path}\n")

    try:
        out = generate_for_user(
            user_id=6161189904,
            entries=entries,
            month=month,
            year=year,
            tpl_dir=tpl_dir,
            out_dir=out_dir,
        )
        print(f"  Generated: {out}")
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()