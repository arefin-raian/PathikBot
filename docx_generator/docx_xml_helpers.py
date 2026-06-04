from lxml import etree
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import copy

def clone_table(table, parent):
    """Clone a table and append it to the parent."""
    new_table_xml = copy.deepcopy(table._tbl)
    parent.append(new_table_xml)
    return new_table_xml

def add_page_break(doc):
    """Add a page break to the document."""
    doc.add_page_break()

def set_cell_text(cell, text, font_name="SutonnyMJ", font_size=None, bold=False):
    """Set text in a cell with specific font."""
    # Clear existing paragraphs
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(text)
    run.font.name = font_name
    # Critical for SutonnyMJ to work correctly in Word
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run._element.rPr.rFonts.set(qn('w:ascii'), font_name)
    run._element.rPr.rFonts.set(qn('w:hAnsi'), font_name)
    
    if font_size:
        run.font.size = font_size
    if bold:
        run.bold = bold
    return run

def clear_table_data(table, start_row=1):
    """Clear all text from a table starting from a specific row."""
    for row in table.rows[start_row:]:
        for cell in row.cells:
            cell.text = ""
