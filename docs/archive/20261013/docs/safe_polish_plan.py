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

def set_run(r, size, font='SimSun', bold=None):
    r.font.name = font
    r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), font)
    r.font.size = Pt(size)
    if bold is not None: r.bold = bold
    r.font.color.rgb = RGBColor(0, 0, 0)

def first_text(node):
    ts = list(node.iter(qn('w:t')))
    return ts[0].text if ts else ''

def move_supplements():
    body = doc.element.body
    nodes = list(body)
    start = next((i for i,n in enumerate(nodes) if first_text(n).startswith('8.8 ')), None)
    end = next((i for i,n in enumerate(nodes) if i > (start or -1) and first_text(n).startswith('第九章') and '\t' in ''.join(n.itertext())), None)
    main8 = max((i for i,n in enumerate(nodes) if first_text(n).startswith('第八章')), default=-1)
    target = next((i for i,n in enumerate(nodes) if i > main8 and first_text(n).startswith('第九章') and '\t' not in ''.join(n.itertext())), None)
    if None in (start, end, target): return
    block = nodes[start:end]
    for n in block: body.remove(n)
    target_node = next((n for n in list(body) if first_text(n).startswith('第九章') and '\t' not in ''.join(n.itertext())), None)
    if target_node is None: return
    idx = list(body).index(target_node)
    for off,n in enumerate(block): body.insert(idx + off, n)

move_supplements()

repl = {'Spring Boot':'后端服务','MySQL数据库':'经营数据表','Thymeleaf':'管理端页面','ECharts':'经营图表','Java推理':'上线推理','DATA_VERSION.json':'数据版本记录','MODEL_CARD.md':'模型说明','foodwise_operations.csv':'项目经营台账'}
for p in doc.paragraphs:
    for r in p.runs:
        for a,b in repl.items():
            if a in r.text: r.text = r.text.replace(a,b)

for p in doc.paragraphs:
    s = p.text.strip(); st = p.style.name if p.style else ''
    if st == 'Heading 1':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True
        for r in p.runs: set_run(r, 16, 'SimHei', True)
    elif st == 'Heading 2':
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT; p.paragraph_format.keep_with_next = True
        for r in p.runs: set_run(r, 14, 'SimHei', True)
    elif st in ('下标','Caption') or s.startswith(('图','表')):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_together = True
        for r in p.runs: set_run(r, 9, 'SimHei', False)
    elif s:
        p.paragraph_format.line_spacing = 1.5; p.paragraph_format.space_after = Pt(6)
        if not st.startswith('List'): p.paragraph_format.first_line_indent = Pt(24)
        for r in p.runs: set_run(r, 11, 'SimSun', False)

for table in doc.tables:
    tblPr = table._tbl.tblPr
    borders = tblPr.first_child_found_in('w:tblBorders')
    if borders is None: borders = OxmlElement('w:tblBorders'); tblPr.append(borders)
    for edge,val,sz in [('top','single','12'),('insideH','nil','0'),('insideV','nil','0'),('bottom','single','12'),('start','nil','0'),('end','nil','0')]:
        el = borders.find(qn('w:'+edge))
        if el is None: el = OxmlElement('w:'+edge); borders.append(el)
        el.set(qn('w:val'),val); el.set(qn('w:sz'),sz); el.set(qn('w:color'),'000000')
    for ri,row in enumerate(table.rows):
        trPr = row._tr.get_or_add_trPr()
        if ri == 0 and trPr.find(qn('w:tblHeader')) is None: trPr.append(OxmlElement('w:tblHeader'))
        if trPr.find(qn('w:cantSplit')) is None: trPr.append(OxmlElement('w:cantSplit'))
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                p.paragraph_format.first_line_indent = Pt(0); p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if ri == 0 or len(p.text.strip()) <= 12 else WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs: set_run(r, 9.5, 'SimSun', ri == 0)

for sec in doc.sections:
    for p in sec.header.paragraphs + sec.footer.paragraphs:
        for r in p.runs: set_run(r, 9, 'SimHei', False)

doc.save(OUT)
# Update the template's literal total-page footer after the new render.
tmp = OUT.with_suffix('.tmp.docx')
with ZipFile(OUT, 'r') as zin, ZipFile(tmp, 'w') as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.startswith('word/footer') and item.filename.endswith('.xml'):
            data = data.replace(b'<w:t>68</w:t>', b'<w:t>59</w:t>')
        zout.writestr(item, data)
tmp.replace(OUT)
print(OUT)
