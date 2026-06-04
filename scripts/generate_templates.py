"""
Logsheet Generator  –  v2 (schema-clean)
=========================================
Generates all 28 required logsheet .docx variations from the template.

Root cause of the Word schema error in v1
------------------------------------------
Python's ElementTree.tostring() strips namespace declarations that aren't
directly used by serialised elements.  The template root has:
    mc:Ignorable="w14 w15 w16se wp14"
but after ET round-tripping those four prefix declarations were gone from
<w:document>, making the Ignorable attribute reference undeclared namespaces.

Fix
---
Never re-serialise the root element with ET.  Instead, work at the raw-bytes
level:
  1. Read the template XML bytes verbatim.
  2. Locate each body child (paragraph / table / sectPr) by scanning the bytes
     to find their start/end positions.
  3. Build the desired body by concatenating the raw byte slices in the new
     order (deep-copying table/paragraph chunks as many times as needed).
  4. Splice the new body back between the original XML header
     (<?xml…?><w:document …>) and the closing </w:document>.

This guarantees that the namespace declarations, mc:Ignorable, standalone="yes",
encoding declaration, line-endings, and every other byte outside <w:body>…
</w:body> are identical to the original template.

The only structural change inside a 3PET table is to move the Total <w:tr>
element to the desired data-row position — again done at the raw-bytes level.

Template body layout (verified by inspection)
---------------------------------------------
The template's <w:body> contains these direct children, in order:

  [p0]   heading paragraph          "মোটর সাইকেল লগশিট"
  [tbl0] 3HE page table             8 rows  (3 info-header + 2 col-header + 3 data)
  [p1]   spacer paragraph
  [tbl1] 4E page table              6 rows  (2 col-header + 4 data)
  [p2]   spacer paragraph
  [tbl2] 3PET page table            6 rows  (2 col-header + 3 empty + 1 Total=T4)
  [p3]   spacer paragraph
  [tbl3] 0EST dummy-entry table     5 rows  (2 col-header + 3 empty data)
  [p4]   spacer paragraph
  [tbl4] 0EST summary table         7 rows
  [p5]   tiny spacer paragraph
  [sectPr]

Generated files (28 total, n4e = 0..6, T = 1..4):
  n4e=0:  3HE_3PET{T}_0EST
  n4e=1:  3HE_4E_3PET{T}_0EST
  n4e=2:  3HE_4E.2_3PET{T}_0EST
  …
  n4e=6:  3HE_4E.6_3PET{T}_0EST
"""

import re
import sys
import zipfile
from pathlib import Path


# ─── ZIP helpers ──────────────────────────────────────────────────────────────

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


# ─── Raw-XML byte-level helpers ───────────────────────────────────────────────

def find_tag_end(xml: bytes, start: int) -> int:
    """
    Given the position of a '<' that starts an opening tag, return the index
    of the '>' that closes it (handling quoted attribute values).
    """
    i = start + 1
    in_quote = None
    while i < len(xml):
        c = xml[i:i+1]
        if in_quote:
            if c == in_quote:
                in_quote = None
        else:
            if c in (b'"', b"'"):
                in_quote = c
            elif c == b'>':
                return i
        i += 1
    raise ValueError(f"Unclosed tag starting at {start}")


def find_closing_tag(xml: bytes, tag_name: bytes, open_pos: int) -> int:
    """
    Starting from open_pos (the '<' of the opening tag), find the matching
    closing tag and return the index just AFTER the '>'.

    Handles nesting by counting open/close tags with the same name.
    """
    close_tag = b'</' + tag_name + b'>'
    open_tag_prefix = b'<' + tag_name  # could be followed by '>' or ' ' or '\r' or '\n'

    depth = 0
    i = open_pos

    while i < len(xml):
        if xml[i:i+1] == b'<':
            # Self-closing?  Skip for depth counting; self-closing tags don't affect depth.
            # Check for closing tag first
            if xml[i:i+2] == b'</':
                if xml[i:i+len(close_tag)] == close_tag:
                    depth -= 1
                    if depth == 0:
                        return i + len(close_tag)
                # skip to end of this closing tag
                gt = xml.index(b'>', i)
                i = gt + 1
                continue
            # Opening tag with our name?
            if xml[i:i+len(open_tag_prefix)] == open_tag_prefix:
                next_ch = xml[i+len(open_tag_prefix):i+len(open_tag_prefix)+1]
                if next_ch in (b'>', b' ', b'\t', b'\r', b'\n', b'/'):
                    # It's our tag — find where the opening tag ends
                    tag_end = find_tag_end(xml, i)
                    if xml[tag_end-1:tag_end] == b'/':
                        # self-closing — depth unchanged
                        pass
                    else:
                        depth += 1
                    i = tag_end + 1
                    continue
            # Some other tag — skip to '>'
            gt = find_tag_end(xml, i)
            i = gt + 1
        else:
            i += 1

    raise ValueError(f"Could not find closing </{tag_name.decode()}> starting from {open_pos}")


def extract_body_children_bytes(xml: bytes) -> list:
    """
    Parse the raw bytes of a word/document.xml and return a list of dicts,
    one per direct child of <w:body>:

        {
          "kind":  "tbl" | "p" | "sectPr" | "other",
          "bytes": bytes,   # raw bytes of this element incl. tags
        }

    We do NOT parse into an element tree; we work on raw bytes so that
    re-serialisation is byte-for-byte identical to the original.
    """
    # Find <w:body>
    body_open_start = xml.index(b'<w:body>')
    body_content_start = body_open_start + len(b'<w:body>')

    # Find </w:body>
    body_close_start = xml.rindex(b'</w:body>')

    body_content = xml[body_content_start:body_close_start]

    results = []
    i = 0
    while i < len(body_content):
        # Skip whitespace / text between elements
        c = body_content[i:i+1]
        if c in (b' ', b'\t', b'\r', b'\n'):
            i += 1
            continue
        if c != b'<':
            i += 1
            continue

        # What tag is this?
        if body_content[i:i+8] == b'<w:tbl>':
            tag_name = b'w:tbl'
        elif body_content[i:i+3] == b'<w:':
            # Extract tag name
            space_or_gt = len(body_content)
            for ch in (b' ', b'>', b'\t', b'\r', b'\n', b'/'):
                pos = body_content.find(ch, i+1)
                if pos != -1:
                    space_or_gt = min(space_or_gt, pos)
            tag_name = body_content[i+1:space_or_gt]
        else:
            i += 1
            continue

        # Find where this element ends
        tag_end_pos = find_tag_end(body_content, i)
        # Self-closing?
        if body_content[tag_end_pos-1:tag_end_pos] == b'/':
            el_bytes = body_content[i:tag_end_pos+1]
            end_pos = tag_end_pos + 1
        else:
            end_pos = find_closing_tag(body_content, tag_name, i)
            el_bytes = body_content[i:end_pos]

        if tag_name == b'w:tbl':
            kind = 'tbl'
        elif tag_name == b'w:p':
            kind = 'p'
        elif tag_name == b'w:sectPr':
            kind = 'sectPr'
        else:
            kind = 'other'

        results.append({'kind': kind, 'bytes': el_bytes})
        i = end_pos

    return results


# ─── Total-row detection and reordering (bytes level) ────────────────────────

def is_total_row_bytes(row_bytes: bytes) -> bool:
    """A Total row has a <w:sz w:val="60"/> run property."""
    return b'w:val="60"' in row_bytes or b"w:val='60'" in row_bytes


def extract_tr_elements(tbl_bytes: bytes) -> list:
    """
    Return list of (start, end) byte positions (relative to tbl_bytes)
    for each <w:tr>…</w:tr> in the table.
    """
    positions = []
    i = 0
    while True:
        pos = tbl_bytes.find(b'<w:tr ', i)
        if pos == -1:
            pos = tbl_bytes.find(b'<w:tr>', i)
        if pos == -1:
            break
        end = find_closing_tag(tbl_bytes, b'w:tr', pos)
        positions.append((pos, end))
        i = end
    return positions


def reorder_data_rows_bytes(tbl_bytes: bytes, target_pos: int) -> bytes:
    """
    In a 3PET table, move the Total row so it becomes data-row number
    target_pos (1-based, 1=first data row, 4=last data row).

    Data rows are the 3rd through 6th <w:tr> elements (index 2..5).
    Returns the modified table bytes.
    """
    tr_positions = extract_tr_elements(tbl_bytes)

    # data rows: indices 2, 3, 4, 5  (0-based)
    if len(tr_positions) < 6:
        return tbl_bytes  # not a 3PET table shape

    data_tr = tr_positions[2:6]

    # Find the Total row among data rows
    total_idx = None
    for i, (s, e) in enumerate(data_tr):
        if is_total_row_bytes(tbl_bytes[s:e]):
            total_idx = i
            break

    if total_idx is None:
        return tbl_bytes  # nothing to reorder

    target_idx = target_pos - 1  # 0-based

    if total_idx == target_idx:
        return tbl_bytes  # already correct

    # Extract the raw bytes for each of the 4 data rows
    row_bytes_list = [tbl_bytes[s:e] for (s, e) in data_tr]

    # Rearrange: pull out total row, insert at target
    total_row_b = row_bytes_list.pop(total_idx)
    row_bytes_list.insert(target_idx, total_row_b)

    # Rebuild the table bytes:
    # everything before first data row  +  new data rows  +  everything after last data row
    pre  = tbl_bytes[:data_tr[0][0]]
    post = tbl_bytes[data_tr[-1][1]:]

    return pre + b''.join(row_bytes_list) + post


# ─── Document builder ─────────────────────────────────────────────────────────

def build_document_bytes(tpl_xml: bytes, n4e: int, total_pos: int) -> bytes:
    """
    Build and return new word/document.xml bytes for a document with:
      1× 3HE page
      n4e× 4E pages
      1× 3PET page with Total at total_pos (1-4)
      1× 0EST page (dummy-entry table + summary table)

    The XML header (declaration + <w:document …> with all namespace attrs)
    and the closing </w:document> are taken byte-for-byte from the template.
    """
    children = extract_body_children_bytes(tpl_xml)

    # Identify template children by index
    # Structure: p0 tbl0 p1 tbl1 p2 tbl2 p3 tbl3 p4 tbl4 p5 sectPr
    tbls   = [c for c in children if c['kind'] == 'tbl']
    paras  = [c for c in children if c['kind'] == 'p']
    sects  = [c for c in children if c['kind'] == 'sectPr']

    assert len(tbls) == 5, f"Expected 5 tables in template, found {len(tbls)}"

    b_3HE    = tbls[0]['bytes']
    b_4E     = tbls[1]['bytes']
    b_3PET   = tbls[2]['bytes']
    b_dummy  = tbls[3]['bytes']
    b_0EST   = tbls[4]['bytes']

    b_heading = paras[0]['bytes']
    b_spacer  = paras[1]['bytes']  # between-table spacer
    b_tiny    = paras[-1]['bytes'] # end spacer
    b_sect    = sects[0]['bytes']  if sects else b''

    # Reorder Total row in 3PET table
    b_3PET_reordered = reorder_data_rows_bytes(b_3PET, total_pos)

    # Build new body content
    parts = []
    parts.append(b_heading)
    parts.append(b_3HE)
    for _ in range(n4e):
        parts.append(b_spacer)
        parts.append(b_4E)
    parts.append(b_spacer)
    parts.append(b_3PET_reordered)
    parts.append(b_spacer)
    parts.append(b_dummy)
    parts.append(b_spacer)
    parts.append(b_0EST)
    parts.append(b_tiny)
    parts.append(b_sect)

    new_body_content = b''.join(parts)

    # Extract the template's XML preamble (everything up to and including <w:body>)
    body_open_start  = tpl_xml.index(b'<w:body>')
    body_close_start = tpl_xml.rindex(b'</w:body>')
    doc_close_start  = tpl_xml.rindex(b'</w:document>')

    preamble  = tpl_xml[:body_open_start + len(b'<w:body>')]  # incl. <w:body>
    postamble = tpl_xml[body_close_start:]                    # </w:body></w:document>

    return preamble + new_body_content + postamble


# ─── File specs ───────────────────────────────────────────────────────────────

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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    script_dir = Path(__file__).resolve().parent.parent
    template_path = script_dir / "templates" / "Logsheet_Template.docx"
    if not template_path.exists():
        print(f"ERROR: '{template_path}' not found.")
        print("Place 'Logsheet_Template.docx' in templates/ folder.")
        sys.exit(1)

    out_dir = script_dir / "generated_logsheets"
    out_dir.mkdir(exist_ok=True)

    print(f"Reading template: {template_path}")
    tpl_files = read_zip(template_path)
    tpl_xml   = tpl_files["word/document.xml"]

    specs = all_specs()
    print(f"Generating {len(specs)} files into '{out_dir}/' ...\n")

    ok_count = 0
    for stem, n4e, t in specs:
        out_path = out_dir / f"{stem}.docx"
        try:
            new_xml   = build_document_bytes(tpl_xml, n4e, t)
            new_files = dict(tpl_files)
            new_files["word/document.xml"] = new_xml
            write_zip(out_path, new_files)
            print(f"  OK  {out_path.name}")
            ok_count += 1
        except Exception as exc:
            print(f"  ERR {out_path.name}  —  {exc}")
            import traceback; traceback.print_exc()

    print(f"\nDone. {ok_count}/{len(specs)} files written to '{out_dir}/'.")


if __name__ == "__main__":
    main()