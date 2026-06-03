"""
Logsheet DOCX Generator
Clones Logsheet_Template.docx and fills it with entry data.
Uses direct XML manipulation via lxml — no python-docx.
"""

import zipfile, os, shutil, copy, re
from lxml import etree
from datetime import date

# ─────────────────────────────────────────────
# NAMESPACES
# ─────────────────────────────────────────────
W  = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# ─────────────────────────────────────────────
# UNICODE → BIJOY CONVERSION
# A minimal hand-rolled mapping sufficient for this document.
# Replace with a full library (bijoy-converter, avro, etc.) for production.
# ─────────────────────────────────────────────
UNI_TO_BIJOY = {
    # vowels / matras
    'অ':'A','আ':'Av','ই':'B','ঈ':'C','উ':'D','ঊ':'E','ঋ':'F','এ':'G','ঐ':'H','ও':'I','ঔ':'J',
    'া':'v','ি':'w','ী':'x','ু':'y','ূ':'~','ৃ':'…','ে':'†','ৈ':'‡','ো':'†v','ৌ':'†Š',
    # consonants
    'ক':'K','খ':'L','গ':'M','ঘ':'N','ঙ':'O','চ':'P','ছ':'Q','জ':'R','ঝ':'S','ঞ':'T',
    'ট':'U','ঠ':'V','ড':'W','ঢ':'X','ণ':'Y','ত':'Z','থ':'_','দ':'`','ধ':'a','ন':'b',
    'প':'c','ফ':'d','ব':'e','ভ':'f','ম':'g','য':'h','র':'i','ল':'j','শ':'k','ষ':'l',
    'স':'m','হ':'n','ড়':'o','ঢ়':'p','য়':'q','ৎ':'r','ং':'s','ঃ':'t','ঁ':'u',
    # hasanta / virama
    '্':'',
    # conjuncts (common ones used in this document)
    'ক্ষ':'¶','জ্ঞ':'·','ত্র':'Î','ক্র':'µ','গ্র':'MÖ','প্র':'cÖ',
    # numbers (Bengali → ASCII, doc uses ASCII digits)
    '০':'0','১':'1','২':'2','৩':'3','৪':'4','৫':'5','৬':'6','৭':'7','৮':'8','৯':'9',
    # punctuation
    '।':'|','৷':'|',
}

def unicode_to_bijoy(text: str) -> str:
    """
    Convert Unicode Bengali string to Bijoy (SutonnyMJ) encoding.
    For this test we use pre-converted Bijoy strings directly, so this
    function is kept simple. Replace with a full library in production.
    """
    # If text is already ASCII (Bijoy-encoded), pass through
    try:
        text.encode('ascii')
        return text
    except UnicodeEncodeError:
        pass

    result = []
    i = 0
    while i < len(text):
        # Try two-char conjuncts first
        if i + 1 < len(text):
            pair = text[i:i+2]
            if pair in UNI_TO_BIJOY:
                result.append(UNI_TO_BIJOY[pair])
                i += 2
                continue
        c = text[i]
        result.append(UNI_TO_BIJOY.get(c, c))
        i += 1
    return ''.join(result)


# ─────────────────────────────────────────────
# XML HELPERS
# ─────────────────────────────────────────────
# Standard run properties used throughout the data area
STD_RPR = (
    f'<w:rPr xmlns:w="{W}">'
    f'<w:rFonts w:ascii="SutonnyMJ" w:hAnsi="SutonnyMJ" w:cs="SutonnyMJ"/>'
    f'<w:b/><w:sz w:val="32"/><w:szCs w:val="32"/>'
    f'</w:rPr>'
)

def make_run(bijoy_text: str) -> etree._Element:
    """Create a <w:r> with SutonnyMJ bold formatting."""
    safe = (bijoy_text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))
    # Preserve leading/trailing spaces
    space_attr = ' xml:space="preserve"' if (bijoy_text.startswith(' ') or bijoy_text.endswith(' ')) else ''
    xml = (f'<w:r xmlns:w="{W}">'
           f'{STD_RPR}'
           f'<w:t{space_attr}>{safe}</w:t>'
           f'</w:r>')
    return etree.fromstring(xml)


def get_para(cell: etree._Element) -> etree._Element:
    """Return the <w:p> inside a <w:tc>."""
    return cell.find(f'{{{W}}}p')


def clear_runs(cell: etree._Element):
    """Remove all existing <w:r> runs from the paragraph in a cell."""
    para = get_para(cell)
    for r in para.findall(f'{{{W}}}r'):
        para.remove(r)
    return para


def set_cell(cell: etree._Element, bijoy_text: str):
    """Put a single run of text into a cell, clearing what was there."""
    para = clear_runs(cell)
    if bijoy_text:
        para.append(make_run(bijoy_text))


def set_cell_runs(cell: etree._Element, bijoy_texts: list):
    """Put multiple runs into a cell (e.g. distributor names, or '43 wjUvi')."""
    para = clear_runs(cell)
    for t in bijoy_texts:
        if t:
            para.append(make_run(t))


# ─────────────────────────────────────────────
# TABLE DETECTION
# ─────────────────────────────────────────────
def is_data_table(tbl: etree._Element) -> bool:
    return 'µwgK bs' in etree.tostring(tbl, encoding='unicode')


def get_total_row(tbl: etree._Element):
    """Return the TOTAL row element, or None."""
    for row in tbl.findall(f'{{{W}}}tr'):
        xml = etree.tostring(row, encoding='unicode')
        if '‡gvU' in xml and '=' in xml:
            return row
    return None


def get_empty_data_rows(tbl: etree._Element, header_count: int) -> list:
    """Return data rows (not header, not total)."""
    rows = tbl.findall(f'{{{W}}}tr')
    result = []
    for row in rows[header_count:]:
        xml = etree.tostring(row, encoding='unicode')
        if '‡gvU' in xml and '=' in xml:
            continue   # skip total row
        result.append(row)
    return result


# ─────────────────────────────────────────────
# HEADER FIELDS
# ─────────────────────────────────────────────
BIJOY_MONTHS = {
    1:'Rvbyqvwi', 2:'†deªæqvwi', 3:'gvP©', 4:'GwcÖj',
    5:'†g', 6:'Ryb', 7:'RyjvB', 8:'AvMó', 9:'†m‡Þ¤^i',
    10:'A‡±vei', 11:'b‡f¤^i', 12:'wW‡m¤^i'
}

def update_header(tbl0: etree._Element, month: int, year: int):
    """
    Table 0 has 5 header rows (0-4).
    Row 0, Cell 1: 'gv‡mi bvg: */****  Bs'  → replace run 1 with ' ‡g/2026'
    Row 1, Cell 2: 'ZvwiL: **/**/**** Bs'   → replace runs 1-3 with actual date
    """
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    rows = tbl0.findall(f'{{{W}}}tr')

    # ── Month name cell (Row 0, Cell 1) ──
    r0_cells = rows[0].findall(f'.//{{{W}}}tc')
    month_cell = r0_cells[1]
    para = get_para(month_cell)
    runs = para.findall(f'{{{W}}}r')
    # runs[0] = 'gv‡mi bvg:'  (keep)
    # runs[1] = ' */****'      (replace)
    # runs[2] = ' Bs'          (keep)
    if len(runs) >= 2:
        t_el = runs[1].find(f'{{{W}}}t')
        if t_el is not None:
            bijoy_month = BIJOY_MONTHS.get(month, str(month))
            t_el.text = f' {bijoy_month}/{year}'
            t_el.set(XML_SPACE, 'preserve')

    # ── Date cell (Row 1, Cell 2) ──
    r1_cells = rows[1].findall(f'.//{{{W}}}tc')
    date_cell = r1_cells[2]
    para2 = get_para(date_cell)
    runs2 = para2.findall(f'{{{W}}}r')
    # runs2[0]='ZvwiL: '  runs2[1]='**'  runs2[2]='/'  runs2[3]='**/****'  runs2[4]=' Bs'
    # Replace runs 1, 2, 3 with a single run containing the full date
    for r in runs2[1:4]:
        para2.remove(r)
    new_run = make_run(f'{last_day:02d}/{month:02d}/{year}')
    # Insert after run[0]
    runs2_remaining = para2.findall(f'{{{W}}}r')
    if runs2_remaining:
        runs2_remaining[0].addnext(new_run)
    else:
        para2.append(new_run)


# ─────────────────────────────────────────────
# FILL ONE ENTRY ROW
# ─────────────────────────────────────────────
def fill_row(row: etree._Element, entry: dict):
    """
    Fill a 12-cell data row with an entry dict.
    Cell indices:
      0=serial  1=date  2=distributors  3=odo_start  4=odo_end
      5=total_km  6=liters+unit  7=petrol_cost  8=mobile
      9=da  10=total  11=with_manager
    """
    cells = row.findall(f'.//{{{W}}}tc')

    # 0 – serial
    set_cell(cells[0], f"{entry['serial']:02d}")

    # 1 – date  DD/MM/YY
    d = entry['date']
    set_cell(cells[1], f"{d.day:02d}/{d.month:02d}/{str(d.year)[2:]}")

    # 2 – distributor names (one run per name, already in Bijoy)
    set_cell_runs(cells[2], entry['distributor_bijoy'])

    # 3 & 4 – odometer
    set_cell(cells[3], str(entry['odo_start']))
    set_cell(cells[4], str(entry['odo_end']))

    # 5 – total km
    km = entry['odo_end'] - entry['odo_start']
    set_cell(cells[5], f"{km:02d}" if km == 0 else str(km))

    # 6 – liters + unit label (two runs if petrol, empty otherwise)
    if entry.get('petrol_liters', 0) > 0:
        set_cell_runs(cells[6], [str(int(entry['petrol_liters'])), 'wjUvi'])
        set_cell(cells[7], fmt_taka(entry['petrol_cost']))
    # else both cells stay empty

    # 8 – mobile
    if entry.get('mobile', 0) > 0:
        set_cell(cells[8], fmt_taka(entry['mobile']))

    # 9 – DA
    if entry.get('da', 0) > 0:
        set_cell(cells[9], fmt_taka(entry['da']))

    # 10 – total
    set_cell(cells[10], fmt_taka(entry['total']))

    # 11 – with manager / monthly meeting
    if entry.get('entry_type') == 'MEETING':
        set_cell_runs(cells[11], ['gvwmK', 'wgwUs'])
    elif entry.get('manager_desig'):
        set_cell(cells[11], unicode_to_bijoy(entry['manager_desig']))


# ─────────────────────────────────────────────
# FILL TOTAL ROW
# ─────────────────────────────────────────────
def fill_total_row(total_row: etree._Element, entries: list):
    cells = total_row.findall(f'.//{{{W}}}tc')
    total_km      = sum(e['odo_end'] - e['odo_start'] for e in entries)
    total_liters  = sum(e.get('petrol_liters', 0) for e in entries)
    total_petrol  = sum(e.get('petrol_cost', 0) for e in entries)
    total_mobile  = sum(e.get('mobile', 0) for e in entries)
    total_da      = sum(e.get('da', 0) for e in entries)
    total_other   = sum(e.get('transport_fee', 0) for e in entries)
    grand_total   = total_petrol + total_mobile + total_da + total_other

    if len(cells) >= 12:
        # Data-row-like structure — direct index mapping
        set_cell_runs(cells[5], [str(total_km), 'wK:wg:'])
        set_cell_runs(cells[6], [str(int(total_liters)), 'wjUvi'])
        set_cell(cells[7], fmt_taka(total_petrol))
        set_cell(cells[8], fmt_taka(total_mobile))
        set_cell(cells[9], fmt_taka(total_da))
        set_cell(cells[10], f"{grand_total:,}/")
    else:
        # Merged total row — 10 cells with gridSpan/vMerge
        # cell[4]  → logical col 5 (total_km)
        # cell[5]  → logical cols 6-7 (liters + petrol, merged)
        # cell[6]  → logical col 8 (mobile)
        # cell[7]  → logical col 9 (DA)
        # cell[8]  → logical col 10 (grand total)
        set_cell_runs(cells[4], [str(total_km), 'wK:wg:'])
        parts = []
        if total_liters:
            parts.extend([str(int(total_liters)), 'wjUvi'])
        petrol_text = fmt_taka(total_petrol)
        if petrol_text:
            parts.append(petrol_text)
        if parts:
            set_cell_runs(cells[5], parts)
        set_cell(cells[6], fmt_taka(total_mobile))
        set_cell(cells[7], fmt_taka(total_da))
        set_cell(cells[8], f"{grand_total:,}/")


# ─────────────────────────────────────────────
# FILL SUMMARY TABLE
# ─────────────────────────────────────────────
def fill_summary(summary_tbl: etree._Element, entries: list):
    rows = summary_tbl.findall(f'{{{W}}}tr')

    total_tours   = len(entries)
    friday_tours  = sum(1 for e in entries if e['date'].weekday() == 4)
    meetings      = sum(1 for e in entries if e.get('entry_type') == 'MEETING')
    mgr_tours     = sum(1 for e in entries if e.get('manager_desig'))
    under50       = sum(1 for e in entries
                        if (e['odo_end'] - e['odo_start']) < 50
                        and e.get('entry_type') != 'MEETING')
    net_tours     = total_tours - friday_tours - meetings

    first_odo     = entries[0]['odo_start']
    last_odo      = entries[-1]['odo_end']
    total_km      = last_odo - first_odo
    total_liters  = sum(e.get('petrol_liters', 0) for e in entries)
    total_petrol  = sum(e.get('petrol_cost', 0) for e in entries)
    total_mobile  = sum(e.get('mobile', 0) for e in entries)
    total_da      = sum(e.get('da', 0) for e in entries)
    total_other   = sum(e.get('transport_fee', 0) for e in entries)
    grand_total   = total_petrol + total_mobile + total_da + total_other

    friday_text = 'bvB' if friday_tours == 0 else f'{friday_tours:02d}'

    def val_cells(row_idx):
        return rows[row_idx].findall(f'.//{{{W}}}tc')

    # Row 0: total tours | total liters
    c = val_cells(0)
    set_cell_runs(c[1], [f'{total_tours}', ' wU'])
    set_cell_runs(c[4], [f'{int(total_liters)}', ' wjUvi'])

    # Row 1: friday tours | km range
    c = val_cells(1)
    set_cell(c[1], friday_text)
    # km range cell currently has 2 runs: '(00-00' and ') wKwg'
    # Replace them with single run
    set_cell(c[4], f'({last_odo}-{first_odo}) wKwg')

    # Row 2: monthly meetings | petrol expense
    c = val_cells(2)
    set_cell_runs(c[1], [f'{meetings:02d}', ' wU'])
    set_cell_runs(c[4], [f'{total_petrol:,}', ' UvKv'])

    # Row 3: manager tours | mobile expense
    c = val_cells(3)
    set_cell_runs(c[1], [f'{mgr_tours:02d}', ' wU'])
    set_cell_runs(c[4], [f'{total_mobile:,}', ' UvKv'])

    # Row 4: <50km tours | DA expense
    c = val_cells(4)
    set_cell(c[1], f'{under50:02d} wU')
    set_cell_runs(c[4], [f'{total_da:,}', ' UvKv'])

    # Row 5: net tours | other expense
    c = val_cells(5)
    set_cell_runs(c[1], [f'{net_tours}', ' wU'])
    set_cell_runs(c[4], [f'{total_other:,}', ' UvKv'])

    # Row 6: grand total
    c = val_cells(6)
    set_cell_runs(c[4], [f'{grand_total:,}', ' UvKv'])


# ─────────────────────────────────────────────
# FORMATTING HELPERS
# ─────────────────────────────────────────────
def fmt_taka(amount: int) -> str:
    if amount == 0:
        return ''
    return f"{amount:,}/-"


# ─────────────────────────────────────────────
# MAIN GENERATOR
# ─────────────────────────────────────────────
def generate(template_path: str, output_path: str,
             month: int, year: int, entries: list):
    """
    Clone template → fill entries → save to output_path.

    entries: list of dicts (see TEST DATA below for schema)
    """
    import calendar

    # 1. Clone
    shutil.copy(template_path, output_path)

    # 2. Unzip
    work_dir = output_path + '_work'
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir)
    with zipfile.ZipFile(output_path, 'r') as z:
        z.extractall(work_dir)

    doc_path = os.path.join(work_dir, 'word', 'document.xml')
    tree = etree.parse(doc_path)
    root = tree.getroot()
    body = root.find(f'{{{W}}}body')

    all_tables = body.findall(f'{{{W}}}tbl')
    data_tables = [t for t in all_tables if is_data_table(t)]
    # data_tables[0]: type-1 page (5 header rows + 3 data rows)
    # data_tables[1]: type-2 page (2 header rows + 4 data rows)
    # data_tables[2]: type-3 page (2 header rows + 1 data row + TOTAL + 2 empty)
    # data_tables[3]: type-4 overflow page (keep empty, template placeholder)

    non_data = [t for t in all_tables if not is_data_table(t)]
    summary_tbl = non_data[0]   # always the last table

    # 3. Header (month name + date)
    update_header(data_tables[0], month, year)

    # 4. Distribute entries across pages
    # Page capacities
    P1_CAP = 3    # type-1 page
    P2_CAP = 4    # type-2 pages (cloned)
    # Last page (type-3) can hold 1–4 entries before the TOTAL row

    pages = []
    if len(entries) <= P1_CAP:
        pages.append(entries[:])
    else:
        pages.append(entries[0:P1_CAP])
        rest = entries[P1_CAP:]
        while len(rest) > P2_CAP:
            pages.append(rest[:P2_CAP])
            rest = rest[P2_CAP:]
        pages.append(rest)  # last page (1–4 entries + TOTAL)

    middle_pages_needed = len(pages) - 2  # exclude first and last
    if len(pages) == 1:
        # All entries fit on page 1, we still need a "last" page for the TOTAL
        middle_pages_needed = 0
        # treat pages[0] as both first and last
        last_page_entries = pages[0]
        pages = [pages[0], []]  # last page is empty, total still needed
        middle_pages_needed = 0

    # 5. Clone type-2 table for each middle page
    type2_template = data_tables[1]
    type3_table    = data_tables[2]

    type3_idx = list(body).index(type3_table)

    new_middle_tables = []
    for _ in range(middle_pages_needed):
        new_tbl = copy.deepcopy(type2_template)
        body.insert(type3_idx, new_tbl)
        type3_idx += 1
        new_middle_tables.append(new_tbl)

    # Re-collect data tables after insertions
    all_tables_now = body.findall(f'{{{W}}}tbl')
    data_tables_now = [t for t in all_tables_now if is_data_table(t)]
    # After insertion:
    # data_tables_now[0]           = type-1 page
    # data_tables_now[1 .. 1+N-1] = cloned middle pages (N = middle_pages_needed)
    # data_tables_now[1+N]         = type-3 page (last data page)
    # data_tables_now[1+N+1]       = type-4 overflow (keep empty)

    # 6. Fill each page
    for page_idx, page_entries in enumerate(pages):
        tbl = data_tables_now[page_idx]

        if page_idx == 0:
            header_count = 5   # type-1 has 5 header rows
        else:
            header_count = 2   # all others have 2 header rows

        empty_rows = get_empty_data_rows(tbl, header_count)

        for i, entry in enumerate(page_entries):
            if i < len(empty_rows):
                fill_row(empty_rows[i], entry)

    # 7. Handle TOTAL row in last data page (type-3 table)
    last_page_idx = len(pages) - 1
    last_tbl = data_tables_now[last_page_idx]
    total_row = get_total_row(last_tbl)

    if total_row is not None:
        last_page_entries = pages[last_page_idx]
        n_entries_last = len(last_page_entries)

        # Current position of total row
        tbl_children = list(last_tbl)
        cur_idx = tbl_children.index(total_row)
        # Desired position: 2 header rows + n_entries_last data rows
        desired_idx = 2 + n_entries_last
        if cur_idx != desired_idx:
            last_tbl.remove(total_row)
            last_tbl.insert(desired_idx, total_row)

        fill_total_row(total_row, entries)

    # 8. Summary table
    fill_summary(summary_tbl, entries)

    # 9. Save XML
    tree.write(doc_path, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 10. Repack
    os.remove(output_path)
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, files in os.walk(work_dir):
            for fname in files:
                fpath = os.path.join(dirpath, fname)
                arcname = os.path.relpath(fpath, work_dir)
                z.write(fpath, arcname)

    shutil.rmtree(work_dir)
    print(f"✓ Written: {output_path}")


# ─────────────────────────────────────────────
# TEST DATA — 8 entries (June 2026)
# Distributor names already in Bijoy encoding (copied from example).
# In production the bot stores Unicode and converts at generation time.
#
# Page distribution with 8 entries:
#   Page 1 (type-1): entries 01–03  (3 entries)
#   Page 2 (type-2): entries 04–07  (4 entries, cloned)
#   Page 3 (type-3): entry  08      (1 entry + TOTAL row)
#   Page 4 (type-4): empty overflow (template placeholder, untouched)
#   Page 5 (summary): statistics
# → Total: exactly 4 filled pages + summary = all 4 page types visible
# ─────────────────────────────────────────────
TEST_ENTRIES = [
    {
        'serial': 1,
        'date': date(2026, 6, 2),
        'distributor_bijoy': [
            '‡gmvm© gv evevi †`vqv †UªWvm©|',
            '‡gmvm© ‡LvKb †UªWvm©|',
            '‡gmvm© Lv‡jK G›UvicÖvBR|',
            '‡gmvm© kvnv`vZ †UªWvm©|',
            '‡gmvm© kwdKzj GÛ eªv`vm©|',
            '‡gmvm© kwn`yj †UªWvm©|',
        ],
        'odo_start': 60000,
        'odo_end':   60091,
        'petrol_liters': 10,
        'petrol_cost': 1357,   # 10 × 135.70
        'mobile': 560,
        'da': 200,
        'transport_fee': 0,
        'total': 2117,         # 1357+560+200
        'entry_type': 'REGULAR',
    },
    {
        'serial': 2,
        'date': date(2026, 6, 3),
        'distributor_bijoy': [
            '‡gmvm© gv‡qi †`vqv †UªWvm©|',
            '‡gmvm© gvnwdRyi ingvb †UªWvm©|',
            '‡gmvm© fvB fvB †UªWvm©|',
            '‡gmvm© Ig †UªWvm©|',
        ],
        'odo_start': 60091,
        'odo_end':   60186,
        'petrol_liters': 0,
        'petrol_cost': 0,
        'mobile': 0,
        'da': 200,
        'transport_fee': 0,
        'total': 200,
        'entry_type': 'REGULAR',
    },
    {
        'serial': 3,
        'date': date(2026, 6, 5),
        'distributor_bijoy': [
            '‡gmvm© kwdKzj GÛ eªv`vm©|',
            '‡gmvm© iwngv G›UvicÖvBR|',
            '‡gmvm© kvwšÍ K…wl fvÛvi|',
        ],
        'odo_start': 60186,
        'odo_end':   60273,
        'petrol_liters': 0,
        'petrol_cost': 0,
        'mobile': 0,
        'da': 200,
        'transport_fee': 0,
        'total': 200,
        'entry_type': 'REGULAR',
    },
    # ── Page 2 (type-2, cloned) ──────────────────────────────
    {
        'serial': 4,
        'date': date(2026, 6, 7),
        'distributor_bijoy': [
            '‡gmvm© kvnv`vZ †UªWvm©|',
            '‡gmvm© fvB fvB †UªWvm©|',
            '‡gmvm© Lv‡jK G›UvicÖvBR|',
            '‡gmvm© kwn`yj †UªWvm©|',
            '‡gmvm© gv evevi †`vqv †UªWvm©|',
        ],
        'odo_start': 60273,
        'odo_end':   60356,
        'petrol_liters': 10,
        'petrol_cost': 1357,
        'mobile': 0,
        'da': 200,
        'transport_fee': 0,
        'total': 1557,
        'entry_type': 'REGULAR',
    },
    {
        'serial': 5,
        'date': date(2026, 6, 9),
        'distributor_bijoy': [
            '‡gmvm© gv‡qi †`vqv †UªWvm©|',
            '‡gmvm© fvB fvB †UªWvm©|',
            '‡gmvm© kwdKzj GÛ eªv`vm©|',
            '‡gmvm© ‡LvKb †UªWvm©|',
        ],
        'odo_start': 60356,
        'odo_end':   60449,
        'petrol_liters': 0,
        'petrol_cost': 0,
        'mobile': 0,
        'da': 200,
        'transport_fee': 0,
        'total': 200,
        'entry_type': 'REGULAR',
    },
    {
        'serial': 6,
        'date': date(2026, 6, 11),
        'distributor_bijoy': [
            '‡gmvm© gv evevi †`vqv †UªWvm©|',
            '‡gmvm© Lv‡jK G›UvicÖvBR|',
            '‡gmvm© kvwšÍ K…wl fvÛvi|',
            '‡gmvm© wjcb †UªWvm©|',
        ],
        'odo_start': 60449,
        'odo_end':   60537,
        'petrol_liters': 0,
        'petrol_cost': 0,
        'mobile': 560,
        'da': 200,
        'transport_fee': 0,
        'total': 760,
        'entry_type': 'REGULAR',
    },
    {
        'serial': 7,
        'date': date(2026, 6, 14),
        'distributor_bijoy': [
            '‡gmvm© fvB fvB †UªWvm©|',
            '‡gmvm© gvnwdRyi ingvb †UªWvm©|',
            '‡gmvm© kÖvebx †UªWvm©|',
        ],
        'odo_start': 60537,
        'odo_end':   60622,
        'petrol_liters': 10,
        'petrol_cost': 1357,
        'mobile': 0,
        'da': 200,
        'transport_fee': 0,
        'total': 1557,
        'entry_type': 'REGULAR',
    },
    # ── Page 3 (type-3, last data page + TOTAL) ──────────────
    {
        'serial': 8,
        # Monthly meeting entry — service center trip
        'date': date(2026, 6, 18),
        'distributor_bijoy': [
            'iscyi †mjm †m›Uvi|',
            '†Wvgvi nB‡Z iscyi †mjm †m›Uvi evm I A‡Uv‡Z hvZvqvZ fvov=460/-',
        ],
        'odo_start': 60622,
        'odo_end':   60622,   # same (no bike used)
        'petrol_liters': 0,
        'petrol_cost': 0,
        'mobile': 0,
        'da': 0,
        'transport_fee': 460,
        'total': 460,
        'entry_type': 'MEETING',
    },
]


# ─────────────────────────────────────────────
# VERIFY CALCULATIONS
# ─────────────────────────────────────────────
def verify(entries):
    print("\n── Verification ─────────────────────────")
    total_km     = entries[-1]['odo_end'] - entries[0]['odo_start']
    total_liters = sum(e.get('petrol_liters', 0) for e in entries)
    total_petrol = sum(e.get('petrol_cost',  0) for e in entries)
    total_mobile = sum(e.get('mobile',       0) for e in entries)
    total_da     = sum(e.get('da',           0) for e in entries)
    total_other  = sum(e.get('transport_fee',0) for e in entries)
    grand        = total_petrol + total_mobile + total_da + total_other

    for e in entries:
        km    = e['odo_end'] - e['odo_start']
        calc  = e.get('petrol_cost',0) + e.get('mobile',0) + e.get('da',0) + e.get('transport_fee',0)
        ok    = '✓' if calc == e['total'] else f'✗ (stored={e["total"]}, calc={calc})'
        print(f"  Entry {e['serial']:02d} | {e['date']} | {km:3d}km | {fmt_taka(e['total']):>10s} {ok}")

    print(f"\n  Total km     : {total_km}")
    print(f"  Total liters : {int(total_liters)} L")
    print(f"  Petrol cost  : {fmt_taka(total_petrol)}")
    print(f"  Mobile       : {fmt_taka(total_mobile)}")
    print(f"  DA           : {fmt_taka(total_da)}")
    print(f"  Other        : {fmt_taka(total_other)}")
    print(f"  Grand total  : {fmt_taka(grand)}")
    tours     = len(entries)
    meetings  = sum(1 for e in entries if e.get('entry_type')=='MEETING')
    fridays   = sum(1 for e in entries if e['date'].weekday()==4)
    net       = tours - meetings - fridays
    print(f"\n  Total tours    : {tours}")
    print(f"  Meetings       : {meetings}")
    print(f"  Friday tours   : {fridays}")
    print(f"  Net tours      : {net}")
    print("─────────────────────────────────────────\n")


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    TEMPLATE = r'c:\Users\Admin\Documents\PathikBot\templates\Logsheet_Template.docx'
    OUTPUT   = r'c:\Users\Admin\Documents\PathikBot\outputs\Logsheet_June_2026_Test.docx'

    verify(TEST_ENTRIES)

    generate(
        template_path = TEMPLATE,
        output_path   = OUTPUT,
        month         = 6,
        year          = 2026,
        entries       = TEST_ENTRIES,
    )
