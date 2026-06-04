"""
populate_logsheet.py
====================
Generates a filled logsheet DOCX by:
  1. Asking how many entries to generate (3–30)
  2. Asking the month and year (header fields only)
  3. Auto-selecting the correct pre-generated template
  4. Populating it with believable sample data
  5. Writing the output next to this script

Usage:
    python populate_logsheet.py

Requirements:
    pip install lxml

Directory layout expected (run from project root):
    generated_logsheets/   ← pre-generated templates from generate_logsheets.py
    data/distributors.json ← list of distributor name strings (optional)
"""

import json
import os
import random
import shutil
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

# ── lxml import ───────────────────────────────────────────────────────────────
try:
    from lxml import etree
except ImportError:
    print("ERROR: lxml is not installed.  Run:  pip install lxml")
    sys.exit(1)

# ── Namespaces ────────────────────────────────────────────────────────────────
W         = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# ── Bijoy month names ─────────────────────────────────────────────────────────
BIJOY_MONTHS = {
    1:"Rvbyqvwi", 2:"†deªæqvwi", 3:"gvP©", 4:"GwcÖj",
    5:"†g",       6:"Ryb",       7:"RyjvB", 8:"AvMó",
    9:"†m‡Þ¤^i", 10:"A‡±vei", 11:"b‡f¤^i", 12:"wW‡m¤^i",
}

# ── Minimal Unicode → Bijoy converter ────────────────────────────────────────
_U2B = {
    "অ":"A","আ":"Av","ই":"B","ঈ":"C","উ":"D","ঊ":"E","ঋ":"F",
    "এ":"G","ঐ":"H","ও":"I","ঔ":"J",
    "া":"v","ি":"w","ী":"x","ু":"y","ূ":"~","ৃ":"…","ে":"†",
    "ৈ":"‡","ো":"†v","ৌ":"†Š",
    "ক":"K","খ":"L","গ":"M","ঘ":"N","ঙ":"O","চ":"P","ছ":"Q",
    "জ":"R","ঝ":"S","ঞ":"T","ট":"U","ঠ":"V","ড":"W","ঢ":"X",
    "ণ":"Y","ত":"Z","থ":"_","দ":"`","ধ":"a","ন":"b","প":"c",
    "ফ":"d","ব":"e","ভ":"f","ম":"g","য":"h","র":"i","ল":"j",
    "শ":"k","ষ":"l","স":"m","হ":"n","ড়":"o","ঢ়":"p","য়":"q",
    "ৎ":"r","ং":"s","ঃ":"t","ঁ":"u","্":"",
    "ক্ষ":"¶","জ্ঞ":"·","ত্র":"Î","ক্র":"µ","গ্র":"MÖ","প্র":"cÖ",
    "০":"0","১":"1","২":"2","৩":"3","৪":"4",
    "৫":"5","৬":"6","৭":"7","৮":"8","৯":"9",
    "।":"|",
}

def uni_to_bijoy(text: str) -> str:
    try:
        text.encode("ascii"); return text
    except UnicodeEncodeError:
        pass
    result, i = [], 0
    while i < len(text):
        if i + 1 < len(text) and text[i:i+2] in _U2B:
            result.append(_U2B[text[i:i+2]]); i += 2; continue
        result.append(_U2B.get(text[i], text[i])); i += 1
    return "".join(result)


# ── Formatting ────────────────────────────────────────────────────────────────
def fmt_taka(amount) -> str:
    if not amount:
        return ""
    return f"{int(amount):,}/-"


# ── XML run helpers ───────────────────────────────────────────────────────────
STD_RPR = (
    f'<w:rPr xmlns:w="{W}">'
    f'<w:rFonts w:ascii="SutonnyMJ" w:hAnsi="SutonnyMJ" w:cs="SutonnyMJ"/>'
    f'<w:b/><w:sz w:val="32"/><w:szCs w:val="32"/>'
    f'</w:rPr>'
)

def _run(bijoy_text: str) -> etree._Element:
    safe = bijoy_text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    sp   = ' xml:space="preserve"' if bijoy_text[:1]==" " or bijoy_text[-1:]==" " else ""
    return etree.fromstring(
        f'<w:r xmlns:w="{W}">{STD_RPR}<w:t{sp}>{safe}</w:t></w:r>'
    )

def _para(cell): return cell.find(f"{{{W}}}p")

def _clear(cell):
    p = _para(cell)
    for r in p.findall(f"{{{W}}}r"): p.remove(r)
    return p

def set_cell(cell, text: str):
    p = _clear(cell)
    if text: p.append(_run(text))

def set_runs(cell, texts: list):
    p = _clear(cell)
    for t in texts:
        if t: p.append(_run(t))


# ── Template selection ────────────────────────────────────────────────────────
def template_stem(n: int) -> str:
    """Return the filename stem for n entries (3–30)."""
    if not (3 <= n <= 30):
        raise ValueError(f"Entry count {n} out of range 3–30.")
    remaining  = n - 3
    n4e        = remaining // 4     # number of 4E middle pages
    pet        = remaining % 4      # regular entries on the 3PET page (0-3)
    total_pos  = pet + 1            # T1..T4  (T1 = 0 before total, T4 = 3 before)
    if n4e == 0:   return f"3HE_3PET{total_pos}_0EST"
    if n4e == 1:   return f"3HE_4E_3PET{total_pos}_0EST"
    return f"3HE_4E.{n4e}_3PET{total_pos}_0EST"


# ── Distributor loading ───────────────────────────────────────────────────────
FALLBACK_DIST_BIJOY = [
    "‡gmvm© gv evevi †`vqv †UªWvm©",
    "‡gmvm© †LvKb †UªWvm©",
    "‡gmvm© Lv‡jK G›UvicÖvBR",
    "‡gmvm© kvnv`vZ †UªWvm©",
    "‡gmvm© kwdKzj GÛ eªv`vm©",
    "‡gmvm© kwn`yj †UªWvm©",
    "‡gmvm© gv‡qi †`vqv †UªWvm©",
    "‡gmvm© gvnwdRyi ingvb †UªWvm©",
    "‡gmvm© fvB fvB †UªWvm©",
    "‡gmvm© Ig †UªWvm©",
    "‡gmvm© iwngv G›UvicÖvBR",
    "‡gmvm© kvwšÍ K…wl fvÛvi",
    "‡gmvm© wjcb †UªWvm©",
    "‡gmvm© kÖvebx †UªWvm©",
    "‡gmvm© ivmj †UªWvm©",
]

def load_dist_pool(data_dir: Path) -> list:
    path = data_dir / "distributors.json"
    if not path.exists():
        return FALLBACK_DIST_BIJOY
    with open(path, encoding="utf-8") as f:
        names = json.load(f)
    # names is a list of strings (Unicode Bengali)
    # Convert to Bijoy
    return [uni_to_bijoy(n) for n in names] if names else FALLBACK_DIST_BIJOY


# ── Sample data generation ────────────────────────────────────────────────────
PETROL_PRICE   = 140.70
MOBIL_PRICE    = 560.00
DA_AMOUNT      = 200
TRANSPORT_FEE  = 460
STARTING_ODO   = 51000

MEETING_VENUE_B    = "iscyi †mjm †m›Uvi|"
MEETING_COST_TMPL  = "†Wvgvi nB‡Z iscyi †mjm †m›Uvi evm I A‡Uv‡Z hvZvqvZ fvov={fee}/-"

def pick_dist(pool, rng):
    k = rng.randint(4, 6)
    return [f"{n}|" for n in rng.choices(pool, k=k)]

def generate_entries(n: int, month: int, year: int, pool: list) -> list:
    import calendar
    rng = random.Random(year * 100 + month)
    days_in_month = calendar.monthrange(year, month)[1]

    # Pick n distinct days, sorted
    all_days = list(range(1, days_in_month + 1))
    rng.shuffle(all_days)
    entry_days = sorted(all_days[:n])

    # Meeting goes roughly in the second half
    meeting_idx = rng.randint(n // 2, max(n // 2, n - 3)) if n >= 4 else None

    entries = []
    odo = STARTING_ODO

    for i, day in enumerate(entry_days):
        serial = i + 1
        edate  = date(year, month, day)
        is_mtg = (meeting_idx is not None and i == meeting_idx)

        if is_mtg:
            e = _meeting(serial, edate, odo)
        else:
            e = _regular(serial, edate, odo, pool, rng, entries)
            odo = e["odo_end"]
        entries.append(e)

    return entries


def _regular(serial, edate, odo_start, pool, rng, prev):
    km = rng.randint(60, 115)
    odo_end = odo_start + km

    km_so_far = sum(e["odo_end"] - e["odo_start"] for e in prev if e["entry_type"]=="REGULAR")
    give_petrol = (km_so_far % 480 < km) or serial == 1
    petrol_l    = round(rng.uniform(8, 12)) if give_petrol else 0
    petrol_cost = round(petrol_l * PETROL_PRICE) if petrol_l else 0

    give_mobil = km_so_far > 0 and km_so_far % 1000 < km
    mobil_l    = 1 if give_mobil else 0
    mobil_cost = round(mobil_l * MOBIL_PRICE) if mobil_l else 0

    total = petrol_cost + mobil_cost + DA_AMOUNT

    return {
        "serial":       serial,
        "date":         edate,
        "entry_type":   "REGULAR",
        "odo_start":    odo_start,
        "odo_end":      odo_end,
        "petrol_liters":petrol_l,
        "petrol_cost":  petrol_cost,
        "mobil_liters": mobil_l,
        "mobil_cost":   mobil_cost,
        "da":           DA_AMOUNT,
        "transport_fee":0,
        "total_cost":   total,
        "distributors": pick_dist(pool, rng),
        "manager_bijoy":"",
    }


def _meeting(serial, edate, odo):
    fee = TRANSPORT_FEE
    return {
        "serial":       serial,
        "date":         edate,
        "entry_type":   "MONTHLY_MEETING",
        "odo_start":    odo,
        "odo_end":      odo,
        "petrol_liters":0,
        "petrol_cost":  0,
        "mobil_liters": 0,
        "mobil_cost":   0,
        "da":           0,
        "transport_fee":fee,
        "total_cost":   fee,
        "distributors": [MEETING_VENUE_B, MEETING_COST_TMPL.format(fee=fee)],
        "manager_bijoy":"gvwmK wgwUs",
    }


# ── Table helpers ─────────────────────────────────────────────────────────────
def is_data_table(tbl):
    return "µwgK bs" in etree.tostring(tbl, encoding="unicode")

def get_total_row(tbl):
    for row in tbl.findall(f"{{{W}}}tr"):
        x = etree.tostring(row, encoding="unicode")
        if ("‡gvU" in x or "†gvU" in x) and "=" in x and "wK:wg" in x:
            return row
    return None

def get_data_rows(tbl, header_count):
    rows = tbl.findall(f"{{{W}}}tr")
    result = []
    for row in rows[header_count:]:
        x = etree.tostring(row, encoding="unicode")
        if ("‡gvU" in x or "†gvU" in x) and "=" in x and "wK:wg" in x:
            continue
        result.append(row)
    return result


# ── Fill functions ────────────────────────────────────────────────────────────
def fill_row(row, entry):
    cells = row.findall(f".//{{{W}}}tc")
    if len(cells) < 12:
        return
    d   = entry["date"]
    km  = entry["odo_end"] - entry["odo_start"]

    set_cell (cells[0],  f"{entry['serial']:02d}")
    set_cell (cells[1],  f"{d.day:02d}/{d.month:02d}/{str(d.year)[2:]}")
    set_runs (cells[2],  entry["distributors"])
    set_cell (cells[3],  str(entry["odo_start"]))
    set_cell (cells[4],  str(entry["odo_end"]))
    set_cell (cells[5],  "00" if km == 0 else str(km))

    if entry["petrol_liters"] > 0:
        set_runs(cells[6], [str(int(entry["petrol_liters"])), "wjUvi"])
        set_cell(cells[7], fmt_taka(entry["petrol_cost"]))
    else:
        set_cell(cells[6], ""); set_cell(cells[7], "")

    set_cell(cells[8],  fmt_taka(entry["mobil_cost"]))
    set_cell(cells[9],  fmt_taka(entry["da"]))
    set_cell(cells[10], fmt_taka(entry["total_cost"]))

    if entry["entry_type"] == "MONTHLY_MEETING":
        set_runs(cells[11], ["gvwmK", "wgwUs"])
    elif entry.get("manager_bijoy"):
        set_cell(cells[11], entry["manager_bijoy"])
    else:
        set_cell(cells[11], "")


def fill_total_row(total_row, entries):
    cells      = total_row.findall(f".//{{{W}}}tc")
    total_km   = sum(e["odo_end"] - e["odo_start"] for e in entries)
    total_l    = sum(e["petrol_liters"] for e in entries)
    total_pet  = sum(e["petrol_cost"] for e in entries)
    total_mob  = sum(e["mobil_cost"] for e in entries)
    total_da   = sum(e["da"] for e in entries)
    total_oth  = sum(e["transport_fee"] for e in entries)
    grand      = total_pet + total_mob + total_da + total_oth

    if len(cells) >= 12:
        set_runs(cells[5],  [str(total_km), "wK:wg:"])
        set_runs(cells[6],  [str(int(total_l)), "wjUvi"])
        set_cell(cells[7],  fmt_taka(total_pet))
        set_cell(cells[8],  fmt_taka(total_mob))
        set_cell(cells[9],  fmt_taka(total_da))
        set_cell(cells[10], f"{grand:,}/")
    else:
        set_runs(cells[4], [str(total_km), "wK:wg:"])
        lparts = []
        if total_l:  lparts += [str(int(total_l)), "wjUvi"]
        ps = fmt_taka(total_pet)
        if ps:       lparts.append(ps)
        if lparts:   set_runs(cells[5], lparts)
        set_cell(cells[6], fmt_taka(total_mob))
        set_cell(cells[7], fmt_taka(total_da))
        set_cell(cells[8], f"{grand:,}/")


def fill_header(tbl0, month: int, year: int):
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    rows     = tbl0.findall(f"{{{W}}}tr")

    # Row 0, Cell 1 — month/year
    r0c = rows[0].findall(f".//{{{W}}}tc")
    para = _para(r0c[1])
    runs = para.findall(f"{{{W}}}r")
    if len(runs) >= 2:
        t = runs[1].find(f"{{{W}}}t")
        if t is not None:
            t.text = f" {BIJOY_MONTHS[month]}/{year}"
            t.set(XML_SPACE, "preserve")

    # Row 1, Cell 2 — date range
    r1c  = rows[1].findall(f".//{{{W}}}tc")
    para2 = _para(r1c[2])
    runs2 = para2.findall(f"{{{W}}}r")
    for r in runs2[1:4]:
        para2.remove(r)
    new_run = _run(f"{last_day:02d}/{month:02d}/{year}")
    remaining = para2.findall(f"{{{W}}}r")
    if remaining:
        remaining[0].addnext(new_run)
    else:
        para2.append(new_run)


def fill_summary(summary_tbl, entries):
    rows = summary_tbl.findall(f"{{{W}}}tr")

    total_tours   = len(entries)
    friday_tours  = sum(1 for e in entries if e["date"].weekday() == 4)
    meeting_count = sum(1 for e in entries if e["entry_type"] == "MONTHLY_MEETING")
    mgr_tours     = sum(1 for e in entries if e.get("manager_bijoy") and e["entry_type"] == "REGULAR")
    regular       = [e for e in entries if e["entry_type"] == "REGULAR"]
    under50       = sum(1 for e in regular if (e["odo_end"] - e["odo_start"]) < 50)
    net_tours     = max(0, total_tours - friday_tours - meeting_count)

    first_odo = entries[0]["odo_start"]
    last_odo  = entries[-1]["odo_end"]
    total_l   = sum(e["petrol_liters"] for e in entries)
    total_pet = sum(e["petrol_cost"]   for e in entries)
    total_mob = sum(e["mobil_cost"]    for e in entries)
    total_da  = sum(e["da"]            for e in entries)
    total_oth = sum(e["transport_fee"] for e in entries)
    grand     = total_pet + total_mob + total_da + total_oth
    fri_txt   = "bvB" if friday_tours == 0 else f"{friday_tours:02d}"

    def vc(ri): return rows[ri].findall(f".//{{{W}}}tc")

    c = vc(0); set_runs(c[1], [str(total_tours), " wU"]);  set_runs(c[4], [str(int(total_l)), " wjUvi"])
    c = vc(1); set_cell(c[1], fri_txt);                    set_cell(c[4], f"({last_odo}-{first_odo}) wKwg")
    c = vc(2); set_runs(c[1], [f"{meeting_count:02d}", " wU"]); set_runs(c[4], [f"{total_pet:,}", " UvKv"])
    c = vc(3); set_runs(c[1], [f"{mgr_tours:02d}", " wU"]);     set_runs(c[4], [f"{total_mob:,}", " UvKv"])
    c = vc(4); set_cell(c[1], f"{under50:02d} wU");             set_runs(c[4], [f"{total_da:,}", " UvKv"])
    c = vc(5); set_runs(c[1], [str(net_tours), " wU"]);         set_runs(c[4], [f"{total_oth:,}", " UvKv"])
    c = vc(6); set_runs(c[4], [f"{grand:,}", " UvKv"])


# ── Namespace fix: splice original opening tag back in ───────────────────────
def _fix_namespace_header(generated_xml_bytes: bytes, _unused=None) -> bytes:
    """
    lxml strips unused namespace declarations when serialising.
    This causes Word to report schema errors because mc:Ignorable still
    references w14, w15, w16se, wp14 which are no longer declared.

    Fix: inject the four missing namespace declarations directly after
    '<w:document ' in the generated XML.  This is simpler and more reliable
    than swapping the entire opening tag, because the template files
    themselves only carry the reduced namespace set.
    """
    # The four prefixes referenced in mc:Ignorable but stripped by lxml
    INJECT = (
        b'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        b'xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml" '
        b'xmlns:w16se="http://schemas.microsoft.com/office/word/2015/wordml/symex" '
        b'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
    )
    marker = b"<w:document "
    pos = generated_xml_bytes.find(marker)
    if pos == -1:
        return generated_xml_bytes   # not found — return unchanged
    insert_at = pos + len(marker)
    return generated_xml_bytes[:insert_at] + INJECT + generated_xml_bytes[insert_at:]


# ── Main generator ────────────────────────────────────────────────────────────
def generate(template_path: str, output_path: str, month: int, year: int, entries: list):
    work_dir = tempfile.mkdtemp(prefix="logsheet_")
    try:
        # Unpack template
        with zipfile.ZipFile(template_path, "r") as z:
            z.extractall(work_dir)

        doc_path   = os.path.join(work_dir, "word", "document.xml")
        tree       = etree.parse(doc_path)
        body       = tree.getroot().find(f"{{{W}}}body")

        # Collect tables
        all_tbls   = body.findall(f"{{{W}}}tbl")
        data_tbls  = [t for t in all_tbls if is_data_table(t)]
        summary_tbl = all_tbls[-1]

        # Fill header (3HE table)
        fill_header(data_tbls[0], month, year)

        # Distribute entries across pages
        # Page 0 (3HE): 3 entries, Pages 1..N-2 (4E): 4 each, Page N-1 (3PET): rest
        remaining = list(entries)
        pages = []
        pages.append(remaining[:3]);  remaining = remaining[3:]
        for _ in range(len(data_tbls) - 2):
            pages.append(remaining[:4]); remaining = remaining[4:]
        pages.append(remaining)

        # Fill data rows
        for pi, page_entries in enumerate(pages):
            tbl       = data_tbls[pi]
            hdr_count = 5 if pi == 0 else 2
            data_rows = get_data_rows(tbl, hdr_count)
            for i, entry in enumerate(page_entries):
                if i < len(data_rows):
                    fill_row(data_rows[i], entry)

        # Fill total row in last data table
        total_row = get_total_row(data_tbls[-1])
        if total_row is not None:
            fill_total_row(total_row, entries)

        # Fill summary table
        fill_summary(summary_tbl, entries)

        # Write modified XML
        tree.write(doc_path, xml_declaration=True, encoding="UTF-8", standalone=True)

        # Read lxml output and fix namespace declarations
        with open(doc_path, "rb") as f:
            generated_xml = f.read()
        fixed_xml = _fix_namespace_header(generated_xml)
        with open(doc_path, "wb") as f:
            f.write(fixed_xml)

        # Repack
        if os.path.exists(output_path):
            os.remove(output_path)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for dirpath, _, files in os.walk(work_dir):
                for fname in files:
                    fpath   = os.path.join(dirpath, fname)
                    arcname = os.path.relpath(fpath, work_dir)
                    zout.write(fpath, arcname)

        print(f"✓  Written: {output_path}")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ── Validation ────────────────────────────────────────────────────────────────
def validate(path: str) -> bool:
    try:
        with zipfile.ZipFile(path, "r") as z:
            xml = z.read("word/document.xml")
        # Check namespace declarations match mc:Ignorable
        root = etree.fromstring(xml)
        ns_map = root.nsmap
        ignorable = root.get(
            "{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable", ""
        )
        missing = [pfx for pfx in ignorable.split() if pfx not in ns_map]
        if missing:
            print(f"  ✗  Namespace issues (undeclared Ignorable prefixes): {missing}")
            return False
        return True
    except Exception as e:
        print(f"  ✗  Validation error: {e}")
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────
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
    print("=" * 60)
    print("  Logsheet Sample Data Generator")
    print("=" * 60)

    script_dir = Path(__file__).resolve().parent.parent
    tpl_dir    = script_dir / "generated_logsheets"

    if not tpl_dir.exists():
        print(f"\nERROR: 'generated_logsheets/' not found at:\n  {tpl_dir}")
        print("Run generate_logsheets.py first.")
        sys.exit(1)

    data_dir  = script_dir / "data"
    pool      = load_dist_pool(data_dir)
    print(f"\n  Loaded {len(pool)} distributor names.")

    print()
    n       = ask_int("  How many entries? (3–30): ", 3, 30)
    month   = ask_int("  Month? (1–12): ", 1, 12)
    year    = ask_int("  Year? (e.g. 2026): ", 2000, 2100)

    stem     = template_stem(n)
    tpl_path = tpl_dir / f"{stem}.docx"
    if not tpl_path.exists():
        print(f"\nERROR: Template not found:\n  {tpl_path}")
        sys.exit(1)

    month_en = date(year, month, 1).strftime("%B")
    out_name = f"Logsheet_{month_en}_{year}_{n}entries.docx"
    out_path = str(script_dir / out_name)

    print(f"\n  Template  : {stem}.docx")
    print(f"  Output    : {out_name}")
    print()

    entries = generate_entries(n, month, year, pool)

    print("  Entry summary:")
    for e in entries:
        km  = e["odo_end"] - e["odo_start"]
        tag = "MTG" if e["entry_type"] == "MONTHLY_MEETING" else "REG"
        print(f"    [{tag}] {e['serial']:02d}  {e['date']}  {km:>3}km  "
              f"total={e['total_cost']:>5,}  {len(e['distributors'])} dist.")
    grand = sum(e["total_cost"] for e in entries)
    print(f"\n  Grand total: {grand:,} BDT\n")

    generate(str(tpl_path), out_path, month, year, entries)

    if validate(out_path):
        print("✓  Schema validation passed — no namespace issues.")
    else:
        print("✗  Schema issues detected (file may still open in Word).")


if __name__ == "__main__":
    main()
