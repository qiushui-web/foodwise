from pathlib import Path
from zipfile import ZipFile
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_商业计划书_最终统一版.docx')
OUT = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_商业计划书_排版优化版.docx')
doc = Document(SRC)

def node_text(node):
    return ''.join(node.itertext()) if hasattr(node, 'itertext') else ''

def move_supplements_after_chapter8():
    body = doc.element.body
    nodes = list(body)
    start = next((i for i,n in enumerate(nodes) if '8.8 ' in node_text(n)), None)
    end = next((i for i,n in enumerate(nodes) if i > (start or -1) and '8.11 ' in node_text(n)), None)
    chapter9 = next((n for i,n in enumerate(nodes) if i > 100 and '第九章' in node_text(n)), None)
    if start is None or end is None or chapter9 is None:
        return
    # Include the complete 8.11 block up to the next heading/chapter boundary.
    end2 = next((i for i,n in enumerate(nodes) if i > end and '第九章' in node_text(n)), end + 1)
    block = nodes[start:end2]
    for n in block: body.remove(n)
    target = next(n for n in list(body) if '第九章' in node_text(n))
    idx = list(body).index(target)
    for off,n in enumerate(block): body.insert(idx + off, n)

move_supplements_after_chapter8()

def set_run(run, size, font='SimHei', bold=None, color='000000'):
    run.font.name = font
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), font)
    run.font.size = Pt(size)
    if bold is not None: run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)

def set_table_borders(table):
    # Strict three-line table: top rule, header separator, bottom rule.
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = tblPr.first_child_found_in('w:tblBorders')
    if borders is None:
        borders = OxmlElement('w:tblBorders'); tblPr.append(borders)
    for edge, val, sz in [('top','single','12'),('insideH','nil','0'),('insideV','nil','0'),('bottom','single','12'),('start','nil','0'),('end','nil','0')]:
        el = borders.find(qn('w:' + edge))
        if el is None: el = OxmlElement('w:' + edge); borders.append(el)
        el.set(qn('w:val'), val); el.set(qn('w:sz'), sz); el.set(qn('w:color'), '000000')
    if table.rows:
        row = table.rows[0]
        trPr = row._tr.get_or_add_trPr()
        if trPr.find(qn('w:tblHeader')) is None: trPr.append(OxmlElement('w:tblHeader'))
    for row in table.rows:
        trPr = row._tr.get_or_add_trPr()
        if trPr.find(qn('w:cantSplit')) is None: trPr.append(OxmlElement('w:cantSplit'))

# Remove developer-facing implementation language while preserving evidence and limits.
replacements = {
    'Spring Boot': '后端服务', 'MySQL数据库': '经营数据表', 'Thymeleaf': '管理端页面',
    'ECharts': '经营图表', 'Java推理': '上线推理', 'DATA_VERSION.json': '数据版本记录',
    'MODEL_CARD.md': '模型说明', 'ModelCrossCheckService': '确定性校验模块',
    'ZhipuAiService': '智能体复核服务', 'IntelligentDecisionService': '经营建议模块',
    'foodwise_operations.csv': '项目经营台账', 'service class': '服务模块',
}
for p in doc.paragraphs:
    if p.text:
        value = p.text
        for a,b in replacements.items(): value = value.replace(a,b)
        if value != p.text: p.text = value

# Typography and hierarchy.
for p in doc.paragraphs:
    s = p.text.strip()
    style = p.style.name if p.style else ''
    if style == 'Heading 1':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(10)
        for r in p.runs: set_run(r, 16, 'SimHei', True)
    elif style == 'Heading 2':
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(6)
        for r in p.runs: set_run(r, 14, 'SimHei', True)
    elif style in ('下标','Caption') or s.startswith(('图','表')):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_together = True
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(6)
        for r in p.runs: set_run(r, 9, 'SimHei', False)
    elif s:
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        if not style.startswith('List'):
            p.paragraph_format.first_line_indent = Pt(24)
        for r in p.runs: set_run(r, 11, 'SimSun', False)

# Explicit, sequential second-level numbering where the original title lacks it.
chapter = 0
sub = 0
for p in doc.paragraphs:
    if p.style and p.style.name == 'Heading 1' and '章' in p.text:
        chapter += 1; sub = 0
    elif p.style and p.style.name == 'Heading 2':
        sub += 1
        if not any(ch.isdigit() for ch in p.text[:4]):
            p.text = f'{chapter}.{sub} {p.text}'
            for r in p.runs: set_run(r, 14, 'SimHei', True)

# Tables: body and header use Songti; header remains bold and black on white.
for table in doc.tables:
    set_table_borders(table)
    for ri,row in enumerate(table.rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                p.paragraph_format.first_line_indent = Pt(0)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ri == 0 or len(p.text.strip()) <= 12 else WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs: set_run(r, 9.5, 'SimSun', ri == 0)

# Header/footer: black, restrained, consistent.
for sec in doc.sections:
    for p in sec.header.paragraphs + sec.footer.paragraphs:
        for r in p.runs: set_run(r, 9, 'SimHei', False)

doc.save(OUT)
print(OUT)
