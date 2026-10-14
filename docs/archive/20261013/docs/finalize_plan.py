from pathlib import Path
from copy import deepcopy
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
import zipfile

SRC = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_商业计划书_70页参赛版.docx')
OUT = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_商业计划书_最终统一版.docx')
doc = Document(SRC)
# The body section was marked as a new page in addition to the TOC's own
# pagination, producing one empty page. A continuous section keeps the
# template header/footer while allowing the first chapter to begin on the
# next available page.
if len(doc.sections) >= 3:
    doc.sections[2].start_type = WD_SECTION.CONTINUOUS

def text(node):
    return ''.join(node.itertext()) if hasattr(node, 'itertext') else ''

def move_supplement_into_chapter8():
    """Move the four late-added evidence sections into Chapter 8."""
    body = doc.element.body
    nodes = list(body)
    starts = ['项目定位与经营闭环', '建模与智能体联合调度', '数据来源与治理', '验证方法与试点边界']
    start_nodes = []
    for label in starts:
        found = next((n for n in nodes if label in text(n)), None)
        if found is not None:
            start_nodes.append(found)
    heading_nodes = [n for n in nodes if n.tag == qn('w:p') and n.find('.//' + qn('w:pStyle')) is not None]
    target = next((n for n in heading_nodes if '第九章' in text(n)), None)
    reference = next((n for n in reversed(heading_nodes) if '参考文献' in text(n)), None)
    if len(start_nodes) != 4 or target is None or reference is None:
        return
    selected = []
    for idx, node in enumerate(start_nodes):
        begin = nodes.index(node)
        end = nodes.index(start_nodes[idx + 1]) if idx + 1 < len(start_nodes) else nodes.index(reference)
        selected.extend(nodes[begin:end])
    for node in selected:
        body.remove(node)
    insert_at = list(body).index(target)
    for offset, node in enumerate(selected):
        body.insert(insert_at + offset, node)
    # Make the moved blocks read as evidence/modeling subsections rather than
    # an appendix added after the conclusion.
    labels = {
        '项目定位与经营闭环': '8.8 经营闭环与责任边界',
        '建模与智能体联合调度': '8.9 建模与智能体联合调度',
        '数据来源与治理': '8.10 数据来源与治理',
        '验证方法与试点边界': '8.11 验证方法与试点边界',
    }
    for node in selected:
        if node.tag == qn('w:p'):
            p = Paragraph(node, doc)
            for old, new in labels.items():
                if old in p.text:
                    p.text = new
                    p.style = doc.styles['Heading 2']
                    break

move_supplement_into_chapter8()

def set_run(run, size=12, name='SimSun', bold=None, color=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), name)
    run.font.size = Pt(size)
    if bold is not None: run.bold = bold
    if italic is not None: run.italic = italic
    if color: run.font.color.rgb = RGBColor.from_string(color)

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
        p.paragraph_format.keep_together = True
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

# The compressed draft left a redundant page break after the abstract, which
# rendered as a page containing only the running header and footer.
for i, p in enumerate(list(doc.paragraphs)):
    if p._p.xpath('.//w:br[@w:type="page"]') and i > 0:
        prev = doc.paragraphs[i - 1].text
        if '14个营业日' in prev or '14��营业日' in prev:
            for br in p._p.xpath('.//w:br[@w:type="page"]'):
                br.getparent().remove(br)

# Refresh the static TOC entries to the final rendered chapter starts. The
# document uses page numbering that begins with the first chapter (cover,
# abstract and TOC are unnumbered).
toc_pages = {
    '第一章': '8', '第二章': '11', '第三章': '16', '第四章': '19',
    '第五章': '20', '第六章': '27', '第七章': '32', '第八章': '39',
    '第九章': '48', '第十章': '53', '第十一章': '55',
    '第十二章': '58', '第十三章': '60', '参考文献': '68',
}
for p in doc.paragraphs:
    if p.style and p.style.name == 'toc 1' and '\t' in p.text:
        title = p.text.split('\t', 1)[0]
        if title.startswith(('附录A', '附录B', '附录C', '附录D')):
            p._element.getparent().remove(p._element)
            continue
        for key, page in toc_pages.items():
            if title.startswith(key):
                p.text = title + '\t' + page
                for r in p.runs: set_run(r, 12, 'SimSun')
                break

doc.save(OUT)
# The template footer contains a literal total-page field. Update only footer
# text after rendering so it matches the compact final edition.
tmp = OUT.with_suffix('.tmp.docx')
with zipfile.ZipFile(OUT, 'r') as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.startswith('word/footer') and item.filename.endswith('.xml'):
            data = data.replace(b'<w:t>63</w:t>', b'<w:t>68</w:t>')
        zout.writestr(item, data)
tmp.replace(OUT)
print(OUT)
