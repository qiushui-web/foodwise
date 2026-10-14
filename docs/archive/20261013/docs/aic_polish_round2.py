from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_BREAK

SRC = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_AIC算法创新赛计划书_重构版.docx')
OUT = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_AIC算法创新赛计划书_终审优化版.docx')

doc = Document(SRC)
body = doc.element.body

def is_h(p, level=None):
    return p.style and p.style.name == (f'Heading {level}' if level else p.style.name)

def fmt(run, size, font, bold=False):
    run.font.name = font
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), font)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)

paras = list(doc.paragraphs)
heads = [p for p in paras if p.style and p.style.name == 'Heading 1' and '章' in p.text]
if len(heads) != 10:
    raise RuntimeError(f'expected 10 chapters, found {len(heads)}')

# Split the current AI/data chapter at evidence-bearing subsections.
ai_head = heads[3]
market_head = heads[4]
service_original = heads[5]
business_original = heads[6]
ai_h2 = [p for p in doc.paragraphs if p.style and p.style.name == 'Heading 2' and p._p.getparent() is body]
nodes = list(body)
def block_for(anchor, limit):
    ns = list(body); start = ns.index(anchor._p); end = ns.index(limit._p)
    later = [ns.index(p._p) for p in ai_h2 if ns.index(p._p) > start and ns.index(p._p) < end]
    stop = min(later) if later else end
    return ns[start:stop]
market_idx = nodes.index(market_head._p)
evidence_nodes = []
for prefix in ('4.6 ', '4.12 '):
    anchor = next(p for p in ai_h2 if p.text.strip().startswith(prefix))
    # The next chapter boundary is the limit for the last subsection.
    if prefix == '4.12 ':
        limit = market_head
    else:
        limit = next(p for p in ai_h2 if nodes.index(p._p) > nodes.index(anchor._p))
    block = block_for(anchor, limit)
    evidence_nodes.extend(block)
for n in evidence_nodes:
    if n.getparent() is body:
        body.remove(n)

# Insert Chapter 5 immediately before the existing market chapter.
insert = list(body).index(market_head._p)
market_head.text = '第六章 市场与竞争定位'
p5 = doc.add_paragraph(style='Heading 1')
p5.add_run('第五章 实验、试点与阶段证据')
body.remove(p5._p); body.insert(insert, p5._p); insert += 1
for n in evidence_nodes:
    body.insert(insert, n); insert += 1

# Current market chapter becomes Chapter 6; service and business chapters are consolidated into Chapter 7.
heads_now = [p for p in doc.paragraphs if p.style and p.style.name == 'Heading 1' and '章' in p.text]
for p in heads_now:
    if p is p5:
        p.text = '第五章 实验、试点与阶段证据'
    elif p is market_head:
        p.text = '第六章 市场与竞争定位'

# Remove the redundant service chapter heading while retaining its body, moving it before Chapter 7's body.
service_head = service_original
business_head = business_original
nodes = list(body); sidx, bidx = nodes.index(service_head._p), nodes.index(business_head._p)
service_block = nodes[sidx + 1:bidx]
for n in service_block:
    if n.getparent() is body: body.remove(n)
at_service = list(body).index(business_head._p) + 1
for n in service_block:
    body.insert(at_service, n)
    at_service += 1
body.remove(service_head._p)

# Move operational delivery/role subsections to Chapter 8 and milestones/conclusion to Chapter 10.
ops_head = heads[7]
project_head = heads[9]
def move_h2_blocks(prefixes, destination_head, after_existing=False):
    anchors = [p for p in doc.paragraphs if p.style and p.style.name == 'Heading 2' and p.text.strip().startswith(prefixes)]
    collected = []
    for anchor in anchors:
        ns = list(body); start = ns.index(anchor._p)
        later = [ns.index(p._p) for p in doc.paragraphs if p.style and p.style.name in ('Heading 1','Heading 2') and ns.index(p._p) > start]
        stop = min(later) if later else len(ns)
        block = ns[start:stop]
        collected.extend(block)
    for n in collected:
        if n.getparent() is body: body.remove(n)
    ns = list(body); at = ns.index(destination_head._p) + 1
    if after_existing:
        h2s = [p for p in doc.paragraphs if p.style and p.style.name == 'Heading 2' and p._p.getparent() is body and ns.index(p._p) > ns.index(destination_head._p)]
        if h2s:
            at = ns.index(h2s[-1]._p) + 1
            following = [ns.index(p._p) for p in doc.paragraphs if p.style and p.style.name in ('Heading 1','Heading 2') and ns.index(p._p) > at]
            if following: at = min(following)
    for n in collected:
        body.insert(at, n); at += 1

move_h2_blocks(('6.1 ', '6.2 ', '6.3 ', '6.4 ', '6.5 '), ops_head)
move_h2_blocks(('9.7 ', '9.8 '), project_head)
for p in list(doc.paragraphs):
    if p.text.strip().startswith('项目将按“数据接入'):
        p._p.getparent().remove(p._p)

# Remove two high-risk stock-like scene photos; product screenshots and data graphics remain untouched.
rels = doc.part.rels
for p in list(doc.paragraphs):
    blips = p._p.xpath('.//a:blip')
    if not blips:
        continue
    names = []
    for blip in blips:
        rid = blip.get(qn('r:embed'))
        rel = rels.get(rid)
        if rel is not None: names.append(Path(rel.target_ref).name)
    if any(name in ('image5.png', 'image37.jpeg') for name in names):
        nxt = p._p.getnext()
        p._p.getparent().remove(p._p)
        if nxt is not None and ''.join(nxt.itertext()).strip().startswith(('图', '图 ')):
            nxt.getparent().remove(nxt)

# Rename source captions and section-local references into the new chapter numbering.
chapter = 0
sub = 0
caption_counts = {}
ref_map = {}
for p in doc.paragraphs:
    text = p.text.strip()
    style = p.style.name if p.style else ''
    if style == 'Heading 1' and '章' in text:
        chapter += 1; sub = 0
        for r in p.runs: fmt(r, 16, 'SimHei', True)
    elif style == 'Heading 2':
        sub += 1
        raw = text
        if raw and raw.split(' ', 1)[0].replace('.', '').isdigit():
            raw = raw.split(' ', 1)[1] if ' ' in raw else raw
        p.text = f'{chapter}.{sub} {raw}'
        for r in p.runs: fmt(r, 14, 'SimHei', True)
    elif style in ('下标', 'Caption') or text.startswith(('图', '表')):
        # Chapter-local numbering keeps references readable after reordering.
        import re
        m = re.match(r'^(图|表)\s*(?:补-)?(?:\d+[-－]\d+)?\s*(.*)$', text)
        if m:
            kind, rest = m.group(1), m.group(2).strip()
            old = re.match(r'^(图|表)\s*((?:补-)?\d+[-－]\d+|补-\d+)', text)
            key = (chapter, kind); caption_counts[key] = caption_counts.get(key, 0) + 1
            new_label = f'{kind}{chapter}-{caption_counts[key]}'
            if old: ref_map[old.group(1)+old.group(2).replace('－','-')] = new_label
            caption_text = f'{new_label} {rest}'
            if p._p.xpath('.//a:blip'):
                for run in list(p.runs):
                    if not run._r.xpath('.//a:blip'):
                        run._r.getparent().remove(run._r)
                p.add_run(caption_text)
            else:
                p.text = caption_text
        for r in p.runs: fmt(r, 9, 'SimHei')
    elif text and style not in ('toc 1', 'Heading 1'):
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(6)
        for r in p.runs: fmt(r, 11, 'SimSun')

# Update body cross-references in one pass to prevent chained substitutions.
if ref_map:
    import re
    keys = sorted(ref_map, key=len, reverse=True)
    token = re.compile('|'.join(re.escape(k) for k in keys))
    for p in doc.paragraphs:
        if p.style and p.style.name in ('下标','Caption'):
            continue
        if p.text and not p._p.xpath('.//a:blip'):
            p.text = token.sub(lambda m: ref_map[m.group(0)], p.text)

# Explicitly label the remaining public/scene photo as illustrative.
for p in doc.paragraphs:
    if p.text.strip().startswith('图1-1'):
        p.text = '图1-1 高校餐饮经营场景示意图（非项目实拍）'
        for r in p.runs: fmt(r, 9, 'SimHei')

# Start the TOC and main body on separate pages without changing the cover/abstract section.
toc_para = next((p for p in doc.paragraphs if p.text.strip() == '目录'), None)
if toc_para is not None:
    toc_para.paragraph_format.page_break_before = False
chapter_one = next(p for p in doc.paragraphs if p.style and p.style.name == 'Heading 1' and p.text.strip().startswith('第一章'))
chapter_one.paragraph_format.page_break_before = True

# Apply table style constraints.
for table in doc.tables:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in('w:tblBorders')
    if borders is None:
        borders = OxmlElement('w:tblBorders'); tbl_pr.append(borders)
    for edge, value, size in [('top','single','12'),('insideH','nil','0'),('insideV','nil','0'),('bottom','single','12'),('start','nil','0'),('end','nil','0')]:
        e = borders.find(qn('w:'+edge))
        if e is None: e = OxmlElement('w:'+edge); borders.append(e)
        e.set(qn('w:val'), value); e.set(qn('w:sz'), size); e.set(qn('w:color'),'000000')
    for row in table.rows:
        tr = row._tr.get_or_add_trPr()
        if tr.find(qn('w:cantSplit')) is None: tr.append(OxmlElement('w:cantSplit'))
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs: fmt(r, 10, 'SimSun')

settings = doc.settings._element
up = settings.find(qn('w:updateFields'))
if up is None: up = OxmlElement('w:updateFields'); settings.append(up)
up.set(qn('w:val'), 'true')
doc.save(OUT)

# Replace image1 with a public still photo, and remove two high-risk photo assets by dropping their image paragraphs.
with ZipFile(SRC, 'r') as source_zip:
    public = source_zip.read('word/media/image1.jpeg')
tmp = OUT.with_suffix('.tmp.docx')
with ZipFile(OUT, 'r') as zin, ZipFile(tmp, 'w', ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'word/media/image1.jpeg': data = public
        zout.writestr(item, data)
tmp.replace(OUT)
print(OUT)
