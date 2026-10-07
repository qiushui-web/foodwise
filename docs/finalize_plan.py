from pathlib import Path
from copy import deepcopy
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = Path('计划书/食刻有数_商业计划书_70页参赛版.docx')
OUT = Path('计划书/食刻有数_商业计划书_最终统一版.docx')
doc = Document(SRC)

def set_run(run, size=12, name='SimSun', bold=None, color=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), name)
    run.font.size = Pt(size)
    if bold is not None: run.bold = bold
    if italic is not None: run.italic = italic
    if color: run.font.color.rgb = RGBColor.from_string(color)

def text(node):
    return ''.join(node.itertext()) if hasattr(node, 'itertext') else ''

def insert_heading_before(anchor, title):
    body = doc.element.body
    for node in list(body):
        if anchor in text(node):
            p = doc.add_heading(title, level=1)._element
            body.remove(p)
            body.insert(list(body).index(node), p)
            return

def set_repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    if trPr.find(qn('w:tblHeader')) is None:
        trPr.append(OxmlElement('w:tblHeader'))

def set_cant_split(row):
    trPr = row._tr.get_or_add_trPr()
    if trPr.find(qn('w:cantSplit')) is None:
        trPr.append(OxmlElement('w:cantSplit'))

# Restore the two chapter labels omitted in the compressed draft.
insert_heading_before('5.1 目标客户筛选条件', '第五章 目标市场与竞争定位')
insert_heading_before('13.1 风险识别与处置', '第十三章 风险管控与实施规划')

# Normalize paragraph typography while preserving the template's heading hierarchy.
for p in doc.paragraphs:
    style = p.style.name if p.style else ''
    s = p.text.strip()
    if style.startswith('Heading'):
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(6)
        for r in p.runs: set_run(r, 18 if style == 'Heading 1' else 16, 'SimHei', True)
    elif style in ('下标', 'Caption') or s.startswith(('图', '表')):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(6)
        for r in p.runs: set_run(r, 9, 'Microsoft YaHei', False, '666666', True)
    elif s:
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(6)
        if not style.startswith('List'):
            p.paragraph_format.first_line_indent = Pt(24)
        for r in p.runs: set_run(r, 12, 'SimSun')
    else:
        p.paragraph_format.space_after = Pt(0)

# Tables: readable 10 pt body, centered short fields, left aligned explanations,
# repeated header and no row splitting across pages.
for table in doc.tables:
    for ri, row in enumerate(table.rows):
        set_cant_split(row)
        if ri == 0: set_repeat_header(row)
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            for p in cell.paragraphs:
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                if len(p.text.strip()) <= 16:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    set_run(r, 10 if ri else 10, 'Microsoft YaHei' if ri == 0 else 'SimSun', ri == 0, 'FFFFFF' if ri == 0 else None)

# Keep the running header concise and consistent with the project name.
for sec in doc.sections:
    for p in sec.header.paragraphs:
        if p.text.strip():
            p.text = '食刻有数｜高校食堂经营减损与备餐决策服务'
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for r in p.runs: set_run(r, 9, 'Microsoft YaHei', False, '666666')

# Remove empty paragraphs immediately before a page break; preserve intentional
# spacing in the cover, TOC and section boundaries.
for p in list(doc.paragraphs):
    if not p.text.strip() and p._p.getnext() is not None:
        nxt = p._p.getnext()
        if nxt.tag == qn('w:p') and nxt.find('.//' + qn('w:br')) is not None:
            p._element.getparent().remove(p._element)

doc.save(OUT)
print(OUT)
