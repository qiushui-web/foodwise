from pathlib import Path
from copy import deepcopy
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

SRC = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_商业计划书_最终统一版.docx')
OUT = (Path(__file__).resolve().parents[2] / '计划书/食刻有数_商业计划书_10章精简规划版.docx')
doc = Document(SRC)

def para_text(node):
    return ''.join(node.itertext()) if hasattr(node, 'itertext') else ''

def heading_nodes():
    return [n for n in list(doc.element.body) if n.tag == qn('w:p')]

def find_para(needle, last=False):
    matches = [p for p in doc.paragraphs if needle in p.text]
    return matches[-1] if last and matches else (matches[0] if matches else None)

def rewrite_heading(old, new):
    p = find_para(old)
    if not p: return
    p.text = new
    p.style = doc.styles['Heading 1'] if new[:2] == '第' and '章' in new else doc.styles['Heading 2']
    p.paragraph_format.keep_with_next = True

def remove_range(start_text, end_text, keep_start=False, keep_end=True):
    body = doc.element.body
    nodes = list(body)
    start = next((i for i,n in enumerate(nodes) if start_text in para_text(n)), None)
    end = next((i for i,n in enumerate(nodes) if i > (start or -1) and end_text in para_text(n)), None)
    if start is None or end is None: return
    for n in nodes[start + (0 if keep_start else 1): end + (0 if keep_end else 1)]:
        body.remove(n)

def move_range(start_text, end_text, before_text):
    body = doc.element.body
    nodes = list(body)
    start = next((i for i,n in enumerate(nodes) if start_text in para_text(n)), None)
    end = next((i for i,n in enumerate(nodes) if i > (start or -1) and end_text in para_text(n)), None)
    target = next((i for i,n in enumerate(nodes) if before_text in para_text(n)), None)
    if None in (start,end,target): return
    block = nodes[start:end]
    for n in block: body.remove(n)
    target_node = next(n for n in list(body) if before_text in para_text(n))
    idx = list(body).index(target_node)
    for offset,n in enumerate(block): body.insert(idx+offset,n)

# 1. Rename the core chapters to the ten-chapter competition structure.
rename = {
    '第一章 项目概述': '第一章 项目概述',
    '第二章 行业环境与政策分析': '第二章 用户痛点与需求验证',
    '第三章 经营痛点与需求分析': None,
    '第四章 市场调研与客户核对': None,
    '第五章 目标市场与竞争定位': '第六章 市场与竞争定位',
    '第六章 服务模式与经营流程': '第三章 产品方案与使用流程',
    '第七章 数字平台与交互设计': None,
    '第八章 数据分析与需求预测': '第四章 技术与数据可行性',
    '第九章 商业模式与定价设计': '第七章 商业模式与财务计划',
    '第十章 市场推广与客户拓展': None,
    '第十一章 运营交付与团队组织': '第八章 运营实施与团队分工',
    '第十二章 财务预测与资金规划': None,
    '第十三章 风险管控与实施规划': '第九章 风险控制与合规',
}
for old,new in rename.items():
    if new: rewrite_heading(old,new)

# 2. Merge redundant chapters into the nearest decision section.
# Keep evidence-bearing paragraphs but remove repeated chapter title blocks.
for old in ['第三章 经营痛点与需求分析','第四章 市场调研与客户核对','第七章 数字平台与交互设计','第十章 市场推广与客户拓展','第十二章 财务预测与资金规划']:
    p=find_para(old)
    if p:
        p.text=''
        p.style=doc.styles['Normal']

# 3. Remove internal process headings and empty/duplicated headings.
for p in list(doc.paragraphs):
    if p.text.strip() in ('评委追问与答辩准备','版本交付检查清单','图表使用规范与评委阅读路径','版本校准与省赛评审补充'):
        p._element.getparent().remove(p._element)

# 4. Move the four evidence blocks into Chapter 4 and rename as compact subsections.
for old,new in {
    '8.8 经营闭环与责任边界':'4.1 数据来源与经营闭环',
    '8.9 建模与智能体联合调度':'4.2 需求预测与智能体复核',
    '8.10 数据来源与治理':'4.3 数据治理与安全边界',
    '8.11 验证方法与试点边界':'5.1 当前测算与试点边界',
}.items(): rewrite_heading(old,new)

# 5. Condense obvious developer-facing technology wording in body prose.
replacements = {
    'Spring Boot':'后端服务', 'MySQL数据库':'经营数据表', 'Thymeleaf':'管理端页面',
    'ECharts':'经营图表', 'Java推理':'上线推理', 'DATA_VERSION.json':'数据版本记录',
    'MODEL_CARD.md':'模型说明', 'ModelCrossCheckService':'确定性校验模块',
    'ZhipuAiService':'智能体复核服务', 'IntelligentDecisionService':'经营建议模块',
    'foodwise_operations.csv':'项目经营台账',
}
for p in doc.paragraphs:
    if p.text:
        old=p.text
        for a,b in replacements.items(): old=old.replace(a,b)
        if old != p.text: p.text=old

# 6. Normalize heading numbering for the compact edition.
for p in doc.paragraphs:
    if p.style and p.style.name == 'Heading 2' and p.text.strip():
        p.paragraph_format.keep_with_next = True

doc.save(OUT)
print(OUT)
