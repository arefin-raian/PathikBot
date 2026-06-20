"""
Logsheet Generator  –  v5 (dual-format + BOTH)
================================================
Generates all 28 required logsheet .docx AND/OR .odt variations from the
matching template in the project's templates/ folder.
On startup the script asks which format to use (docx / odt / both).

Usage
-----
    python scripts/template_variant_generator.py

Template files (from project root):
    templates/Logsheet_Template.docx
    templates/Logsheet_Template.odt

Generated files (28 each, n4e = 0..6, T = 1..4):
    DOCX → template_variants/DOCX/3HE_3PET{T}_0EST.docx    (and variants)

    ODT  → template_variants/ODT/3HE_3PET{T}_0EST.odt      (and variants)
──────────────────────────────────────────────────────────────────────────────
DOCX approach (unchanged from v3)
──────────────────────────────────────────────────────────────────────────────
Work entirely at the raw byte level on word/document.xml:
  • Extract each direct child of <w:body> by byte-level tag scanning.
  • Map each inter-table gap to its correct original spacer paragraph so
    that all tblPr / tblpPr / tblBorders / tblLayout / tblGrid / tcPr
    properties are preserved byte-for-byte from the template.
  • Reorder the Total row inside the 3PET table by swapping <w:tr> byte
    slices.
  • The bookmark spacer (child [2]) is used at most once; plain spacers
    (no bookmark) are used for all additional gaps, preventing duplicate
    w:id="0" schema violations.

Template DOCX body layout (12 children):
  [0]  p      heading
  [1]  tbl    3HE  (8 rows, inline)
  [2]  p      bookmark spacer  (_GoBack, id=0 — used exactly once)
  [3]  tbl    4E   (6 rows, floating via tblpPr)
  [4]  p      plain spacer
  [5]  tbl    3PET (6 rows, floating)
  [6]  p      tab spacer 1
  [7]  tbl    dummy (5 rows, floating)
  [8]  p      tab spacer 2
  [9]  tbl    0EST summary (7 rows, inline)
  [10] p      tiny spacer
  [11] sectPr

──────────────────────────────────────────────────────────────────────────────
ODT approach (v5 — inline tables)
──────────────────────────────────────────────────────────────────────────────
The updated ODT template lays out all five tables INLINE (no draw:frame
floating tables and no _GoBack bookmark), separated by empty spacer
paragraphs — structurally identical to the DOCX template. Work at the
string level on content.xml.

Template ODT office:text layout (12 children):
  [0]  text:sequence-decls   (keep verbatim)
  [1]  text:p                heading
  [2]  table:table           Table1 = 3HE   (8 rows, inline)
  [3]  text:p                spacer (P15)
  [4]  table:table           Table2 = 4E    (inline)
  [5]  text:p                spacer (P15)
  [6]  table:table           Table3 = 3PET  (6 rows, inline)
  [7]  text:p                spacer (P19)
  [8]  table:table           Table4 = dummy (inline)
  [9]  text:p                spacer (P19)
  [10] table:table           Table5 = 0EST summary (7 rows, inline)
  [11] text:p                trailing (P23)

When n4e > 1, each extra 4E copy is the Table2 element duplicated with a
unique table:name (Table2_2, Table2_3, …). All table:style-name
references are shared with the original — a single auto-style definition
may be referenced by any number of tables in ODF, so no style cloning is
required.

The Total row in Table3 (3PET) is identified by the absence of any
column-specific cell style (Table3.C–L) and reordered by swapping raw
<table:table-row> string slices.
"""

import re
import sys
import zipfile
from pathlib import Path


# ══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════════

def read_zip(path: Path) -> dict:
    out = {}
    with zipfile.ZipFile(path, "r") as z:
        for name in z.namelist():
            out[name] = z.read(name)
    return out


def write_zip(path: Path, files: dict):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)


def all_specs():
    specs = []
    for n4e in range(7):       # 0 .. 6
        for t in range(1, 5):  # T1 .. T4
            if n4e == 0:
                stem = f"3HE_3PET{t}_0EST"
            elif n4e == 1:
                stem = f"3HE_4E_3PET{t}_0EST"
            else:
                stem = f"3HE_4E.{n4e}_3PET{t}_0EST"
            specs.append((stem, n4e, t))
    return specs


# ══════════════════════════════════════════════════════════════════════════════
# DOCX engine  (raw-bytes, word/document.xml)
# ══════════════════════════════════════════════════════════════════════════════

def _find_tag_end(xml: bytes, start: int) -> int:
    i, in_quote = start + 1, None
    while i < len(xml):
        c = xml[i:i+1]
        if in_quote:
            if c == in_quote: in_quote = None
        else:
            if c in (b'"', b"'"): in_quote = c
            elif c == b'>': return i
        i += 1
    raise ValueError(f"Unclosed tag at {start}")


def _find_closing_tag(xml: bytes, tag_name: bytes, open_pos: int) -> int:
    close_tag   = b'</' + tag_name + b'>'
    open_prefix = b'<'  + tag_name
    depth, i = 0, open_pos
    while i < len(xml):
        if xml[i:i+1] == b'<':
            if xml[i:i+2] == b'</':
                if xml[i:i+len(close_tag)] == close_tag:
                    depth -= 1
                    if depth == 0:
                        return i + len(close_tag)
                i = xml.index(b'>', i) + 1
                continue
            if xml[i:i+len(open_prefix)] == open_prefix:
                nc = xml[i+len(open_prefix):i+len(open_prefix)+1]
                if nc in (b'>', b' ', b'\t', b'\r', b'\n', b'/'):
                    te = _find_tag_end(xml, i)
                    if xml[te-1:te] != b'/':
                        depth += 1
                    i = te + 1
                    continue
            i = _find_tag_end(xml, i) + 1
        else:
            i += 1
    raise ValueError(f"No closing </{tag_name.decode()}> from {open_pos}")


def _extract_body_children(xml: bytes) -> list:
    body_start = xml.index(b'<w:body>') + len(b'<w:body>')
    body_end   = xml.rindex(b'</w:body>')
    inner      = xml[body_start:body_end]
    results, i = [], 0
    while i < len(inner):
        if inner[i:i+1] in (b' ', b'\t', b'\r', b'\n'):
            i += 1; continue
        if inner[i:i+1] != b'<':
            i += 1; continue
        j = i + 1
        while j < len(inner) and inner[j:j+1] not in (b' ', b'>', b'\t', b'\r', b'\n', b'/'):
            j += 1
        tag_name = inner[i+1:j]
        te = _find_tag_end(inner, i)
        if inner[te-1:te] == b'/':
            results.append({'kind': 'other', 'bytes': inner[i:te+1]})
            i = te + 1
            continue
        end = _find_closing_tag(inner, tag_name, i)
        kind = {'w:tbl': 'tbl', 'w:p': 'p', 'w:sectPr': 'sectPr'}.get(
            tag_name.decode('utf-8', 'replace'), 'other')
        results.append({'kind': kind, 'bytes': inner[i:end]})
        i = end
    return results


def _is_total_row(row_bytes: bytes) -> bool:
    return b'w:val="60"' in row_bytes or b"w:val='60'" in row_bytes


def _extract_tr_positions(tbl: bytes) -> list:
    positions, i = [], 0
    while True:
        pos = tbl.find(b'<w:tr ', i)
        if pos == -1: pos = tbl.find(b'<w:tr>', i)
        if pos == -1: break
        end = _find_closing_tag(tbl, b'w:tr', pos)
        positions.append((pos, end))
        i = end
    return positions


def _reorder_total_row_docx(tbl: bytes, target_pos: int) -> bytes:
    tr_pos = _extract_tr_positions(tbl)
    if len(tr_pos) < 6: return tbl
    data = tr_pos[2:6]
    total_idx = next((i for i, (s, e) in enumerate(data) if _is_total_row(tbl[s:e])), None)
    if total_idx is None: return tbl
    target_idx = target_pos - 1
    if total_idx == target_idx: return tbl
    rows = [tbl[s:e] for s, e in data]
    total_row = rows.pop(total_idx)
    rows.insert(target_idx, total_row)
    pre  = tbl[:data[0][0]]
    post = tbl[data[-1][1]:]
    return pre + b''.join(rows) + post


def build_docx(tpl_xml: bytes, n4e: int, total_pos: int) -> bytes:
    """Return new word/document.xml bytes for the given variant."""
    children = _extract_body_children(tpl_xml)
    assert len(children) == 12, (
        f"Expected 12 body children, got {len(children)}. Template may have changed.")

    b_heading      = children[0]['bytes']
    b_3HE          = children[1]['bytes']
    b_spacer_bm    = children[2]['bytes']   # bookmark spacer — use at most once
    b_4E           = children[3]['bytes']
    b_spacer_plain = children[4]['bytes']   # plain spacer — safe to repeat
    b_3PET         = children[5]['bytes']
    b_spacer_tab1  = children[6]['bytes']
    b_dummy        = children[7]['bytes']
    b_spacer_tab2  = children[8]['bytes']
    b_0EST         = children[9]['bytes']
    b_tiny         = children[10]['bytes']
    b_sect         = children[11]['bytes']

    b_3PET_fixed = _reorder_total_row_docx(b_3PET, total_pos)

    parts = [b_heading, b_3HE]
    if n4e == 0:
        parts.append(b_spacer_plain)
    else:
        parts += [b_spacer_bm, b_4E]
        for _ in range(n4e - 1):
            parts += [b_spacer_plain, b_4E]
        parts.append(b_spacer_plain)
    parts += [b_3PET_fixed, b_spacer_tab1, b_dummy, b_spacer_tab2, b_0EST, b_tiny, b_sect]

    body_open  = tpl_xml.index(b'<w:body>') + len(b'<w:body>')
    body_close = tpl_xml.rindex(b'</w:body>')
    preamble   = tpl_xml[:body_open]
    postamble  = tpl_xml[body_close:]
    return preamble + b''.join(parts) + postamble


def generate_docx(template_path: Path, out_dir: Path):
    print(f"Reading template: {template_path}")
    tpl_files = read_zip(template_path)
    tpl_xml   = tpl_files["word/document.xml"]
    specs     = all_specs()
    print(f"Generating {len(specs)} .docx files into '{out_dir}/' ...\n")
    ok = 0
    for stem, n4e, t in specs:
        out_path = out_dir / f"{stem}.docx"
        try:
            new_xml   = build_docx(tpl_xml, n4e, t)
            new_files = dict(tpl_files)
            new_files["word/document.xml"] = new_xml
            write_zip(out_path, new_files)
            print(f"  OK  {out_path.name}")
            ok += 1
        except Exception as exc:
            print(f"  ERR {out_path.name}  —  {exc}")
            import traceback; traceback.print_exc()
    print(f"\nDone. {ok}/{len(specs)} files written.")


# ══════════════════════════════════════════════════════════════════════════════
# ODT engine  (string-level, content.xml)
# ══════════════════════════════════════════════════════════════════════════════

def _extract_odt_text_children(xml: str) -> list:
    """
    Return list of (tag_name, raw_str) for every direct child of <office:text>.
    Handles arbitrary nesting by tracking open/close tag depth.
    """
    ot_start = xml.find('<office:text')
    ot_inner_start = xml.find('>', ot_start) + 1
    ot_end = xml.find('</office:text>')
    inner  = xml[ot_inner_start:ot_end]

    children, i = [], 0
    while i < len(inner):
        if inner[i] != '<':
            i += 1; continue
        j = i + 1
        while j < len(inner) and inner[j] not in ' >\t\n/':
            j += 1
        tag_name = inner[i+1:j]
        if tag_name.startswith('/'):
            i = inner.index('>', i) + 1; continue
        # find end of opening tag
        gt, k, iq = i, i+1, None
        while k < len(inner):
            c = inner[k]
            if iq:
                if c == iq: iq = None
            else:
                if c in ('"', "'"): iq = c
                elif c == '>': gt = k; break
            k += 1
        if inner[gt-1] == '/':          # self-closing
            children.append((tag_name, inner[i:gt+1]))
            i = gt + 1; continue
        close = f'</{tag_name}>'
        opfx  = f'<{tag_name}'
        depth, p, found = 1, gt+1, False
        while p < len(inner):
            nc = inner.find('<', p)
            if nc == -1: break
            if inner[nc:nc+len(close)] == close:
                depth -= 1
                if depth == 0:
                    end = nc + len(close)
                    children.append((tag_name, inner[i:end]))
                    i = end; found = True; break
                p = nc + len(close)
            elif inner[nc:nc+len(opfx)] == opfx and \
                 inner[nc+len(opfx):nc+len(opfx)+1] in ('>', ' ', '\t', '\n', '/'):
                gt2, kk, iq2 = nc, nc+1, None
                while kk < len(inner):
                    cc = inner[kk]
                    if iq2:
                        if cc == iq2: iq2 = None
                    else:
                        if cc in ('"', "'"): iq2 = cc
                        elif cc == '>': gt2 = kk; break
                    kk += 1
                if inner[gt2-1] != '/': depth += 1
                p = gt2 + 1
            else:
                p = nc + 1
        if not found: i += 1
    return children


def _is_total_row_odt(row: str) -> bool:
    """Total row cells all use Table3.A1 style; data rows use per-column
    styles (Table3.C*, Table3.D*, etc.). Check that no cell uses a
    column-specific style. Exclude header (Table3.1) and sub-header (Table3.2)
    rows which also use only Table3.A1."""
    if re.search(r'table:style-name="Table3\.[12]"', row):
        return False
    return not re.search(r'table:style-name="Table3\.[C-L]\d"', row)


def _reorder_total_row_odt(tbl: str, target_pos: int) -> str:
    """
    Reorder data rows in the ODT 3PET table (Table3) so the Total row is at
    target_pos (1-based within the 3 data rows, i.e. rows 3–5 overall).
    ODT 3PET has 6 rows: row 0 = table-header-rows (Table3.1),
    row 1 = sub-header (Table3.2), rows 2-4 = data, row 5 = total.
    """
    parts = tbl.split('<table:table-row')
    # parts[0] = preamble before first row
    # parts[1..N] = each row (starting with ' ' or attributes)
    if len(parts) < 7: return tbl   # need preamble + 6 rows

    # The last part contains the total row content followed by </table:table>
    # (and possibly trailing whitespace). Extract the closing tag so it
    # stays at the end after reordering.
    last_part = parts[-1]
    ci = last_part.rfind('</table:table>')
    if ci == -1:
        return tbl
    table_close = last_part[ci:]
    parts[-1] = last_part[:ci]

    header_parts = parts[:3]           # preamble + rows 0 & 1 (header, sub-header)
    data_parts   = parts[3:7]          # rows 2,3,4,5 (data1, data2, data3, total)
    total_idx = next((i for i, r in enumerate(data_parts) if _is_total_row_odt(r)), None)
    if total_idx is None:
        return tbl

    target_idx = target_pos - 1
    if total_idx == target_idx:
        return '<table:table-row'.join(header_parts + data_parts) + table_close

    total_row = data_parts.pop(total_idx)
    data_parts.insert(target_idx, total_row)

    return '<table:table-row'.join(header_parts + data_parts) + table_close


def _clone_4e_table(tbl_4e: str, copy_index: int) -> str:
    """
    Clone the inline 4E table (Table2) for copy number `copy_index`
    (2-based: 2 = second copy).

    Only the table's own identifier (table:name) is made unique so that
    multiple 4E copies don't collide. All table:style-name references
    (Table2, Table2.A, Table2.A1, …) are shared with the original copy —
    a single auto-style definition may be referenced by any number of
    tables in ODF, so no style cloning is required.

    table:name appears exactly once per table (on the <table:table>
    element itself), so a single targeted replace is sufficient.
    """
    return tbl_4e.replace(
        'table:name="Table2"', f'table:name="Table2_{copy_index}"', 1)


def build_odt(tpl_content: str, n4e: int, total_pos: int) -> str:
    """Return new content.xml string for the given variant.

    The updated ODT template lays out all five tables INLINE (no
    draw:frame floating tables), separated by empty spacer paragraphs —
    structurally identical to the DOCX template. The 12 office:text
    children are:

      [0]  text:sequence-decls
      [1]  text:p      heading
      [2]  table:table Table1 = 3HE   (inline)
      [3]  text:p      spacer (P15)
      [4]  table:table Table2 = 4E    (inline)
      [5]  text:p      spacer (P15)
      [6]  table:table Table3 = 3PET  (inline)
      [7]  text:p      spacer (P19)
      [8]  table:table Table4 = dummy (inline)
      [9]  text:p      spacer (P19)
      [10] table:table Table5 = 0EST summary (inline)
      [11] text:p      trailing (P23)
    """
    children = _extract_odt_text_children(tpl_content)
    assert len(children) == 12, (
        f"Expected 12 office:text children, got {len(children)}. "
        f"Template may have changed.")

    seq_decls = children[0][1]    # text:sequence-decls
    heading   = children[1][1]    # text:p heading
    tbl_3HE   = children[2][1]    # table:table Table1
    spacer_a  = children[3][1]    # text:p spacer (3HE ↔ 4E area)
    tbl_4E    = children[4][1]    # table:table Table2
    spacer_b  = children[5][1]    # text:p spacer (4E ↔ 3PET)
    tbl_3PET  = children[6][1]    # table:table Table3
    spacer_c  = children[7][1]    # text:p spacer (3PET ↔ dummy)
    tbl_dummy = children[8][1]    # table:table Table4
    spacer_d  = children[9][1]    # text:p spacer (dummy ↔ 0EST)
    tbl_0EST  = children[10][1]   # table:table Table5
    trailing  = children[11][1]   # text:p trailing

    # Reorder the Total row inside the 3PET table to the target position.
    tbl_3PET_fixed = _reorder_total_row_odt(tbl_3PET, total_pos)

    # Assemble office:text inner content (mirrors the DOCX body layout).
    parts = [seq_decls, heading, tbl_3HE]
    if n4e == 0:
        parts.append(spacer_a)                       # one spacer, no 4E table
    else:
        parts += [spacer_a, tbl_4E]                  # first 4E copy (Table2)
        for copy_idx in range(2, n4e + 1):           # extra copies, unique names
            parts += [spacer_a, _clone_4e_table(tbl_4E, copy_idx)]
        parts.append(spacer_b)                       # spacer before 3PET
    parts += [tbl_3PET_fixed, spacer_c, tbl_dummy, spacer_d, tbl_0EST, trailing]

    new_text_inner = ''.join(parts)

    # Splice the rebuilt inner content back into office:text.
    ot_tag_start   = tpl_content.find('<office:text')
    ot_inner_start = tpl_content.find('>', ot_tag_start) + 1
    ot_inner_end   = tpl_content.find('</office:text>')
    return (tpl_content[:ot_inner_start]
            + new_text_inner
            + tpl_content[ot_inner_end:])


def generate_odt(template_path: Path, out_dir: Path):
    print(f"Reading template: {template_path}")
    tpl_files   = read_zip(template_path)
    tpl_content = tpl_files["content.xml"].decode('utf-8')
    specs       = all_specs()
    print(f"Generating {len(specs)} .odt files into '{out_dir}/' ...\n")
    ok = 0
    for stem, n4e, t in specs:
        out_path = out_dir / f"{stem}.odt"
        try:
            new_content = build_odt(tpl_content, n4e, t)
            new_files   = dict(tpl_files)
            new_files["content.xml"] = new_content.encode('utf-8')
            write_zip(out_path, new_files)
            print(f"  OK  {out_path.name}")
            ok += 1
        except Exception as exc:
            print(f"  ERR {out_path.name}  —  {exc}")
            import traceback; traceback.print_exc()
    print(f"\nDone. {ok}/{len(specs)} files written.")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def ask_format() -> str:
    """Prompt the user to choose .docx, .odt, or both."""
    script_dir = Path(__file__).resolve().parent
    templates_dir = script_dir.parent / "templates"
    docx_path = templates_dir / "Logsheet_Template.docx"
    odt_path  = templates_dir / "Logsheet_Template.odt"

    docx_exists = docx_path.exists()
    odt_exists  = odt_path.exists()

    if not docx_exists and not odt_exists:
        print("ERROR: Neither template found in:")
        print(f"  {docx_path}")
        print(f"  {odt_path}")
        sys.exit(1)

    print("Logsheet Generator")
    print("==================")
    print()

    if docx_exists and odt_exists:
        print("Both templates were found:")
        print("  [1] Logsheet_Template.docx  ->  generate .docx files")
        print("  [2] Logsheet_Template.odt   ->  generate .odt  files")
        print("  [3] BOTH                     ->  generate both formats")
        print()
        while True:
            choice = input("Which format? Enter 1, 2, or 3: ").strip()
            if choice == '1': return 'docx'
            if choice == '2': return 'odt'
            if choice == '3': return 'both'
            print("  Please enter 1, 2, or 3.")
    elif docx_exists:
        print("Found: Logsheet_Template.docx  (no .odt template present)")
        print("Generating .docx files.")
        return 'docx'
    else:
        print("Found: Logsheet_Template.odt  (no .docx template present)")
        print("Generating .odt files.")
        return 'odt'


def main():
    script_dir = Path(__file__).resolve().parent
    templates_dir = script_dir.parent / "templates"
    root_dir = script_dir.parent

    fmt = ask_format()
    print()

    docx_out = root_dir / "template_variants" / "DOCX"
    odt_out  = root_dir / "template_variants" / "ODT"

    if fmt in ('docx', 'both'):
        docx_out.mkdir(parents=True, exist_ok=True)
        generate_docx(templates_dir / "Logsheet_Template.docx", docx_out)

    if fmt in ('odt', 'both'):
        odt_out.mkdir(parents=True, exist_ok=True)
        generate_odt(templates_dir / "Logsheet_Template.odt", odt_out)


if __name__ == "__main__":
    main()
