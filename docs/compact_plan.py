from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from lxml import etree
from copy import deepcopy
import zipfile
import tempfile

SRC = Path('计划书/计划书pro10.docx')
OUT = Path('计划书/食刻有数_商业计划书_精简参赛版.docx')
doc = Document(SRC)

def body_text(node):
    if node.tag == qn('w:p'):
        return Paragraph(node, doc).text
    return ''.join(node.itertext()) if hasattr(node, 'itertext') else ''

def remove_body_range(start_text, end_text):
    """Remove body blocks from a heading through the block before end_text."""
    body = doc.element.body
    children = list(body)
    starts = [i for i, n in enumerate(children) if start_text in body_text(n)]
    start = starts[-1] if starts else None
    ends = [i for i, n in enumerate(children) if end_text in body_text(n) and (start is None or i > start)]
    end = ends[0] if ends else None
    if start is None or end is None:
        return
    for node in children[start:end]:
        body.remove(node)

def remove_chapter7_images():
    """Keep Chapter 7 prose but remove repeated UI screenshots and their captions."""
    body = doc.element.body
    children = list(body)
    starts = [i for i, n in enumerate(children) if '第七章' in body_text(n)]
    start = starts[-1] if starts else None
    ends = [i for i, n in enumerate(children) if '第八章' in body_text(n) and (start is None or i > start)]
    end = ends[0] if ends else None
    if start is None or end is None:
        return
    for node in children[start:end]:
        txt = body_text(node)
        if '图7-' in txt or b'w:drawing' in etree.tostring(node):
            body.remove(node)

def remove_subsection_range(start_text, end_text):
    """Trim a dense explanatory block while keeping the following heading."""
    body = doc.element.body
    children = list(body)
    starts = [i for i, n in enumerate(children) if start_text in body_text(n)]
    start = starts[-1] if starts else None
    ends = [i for i, n in enumerate(children) if end_text in body_text(n) and (start is None or i > start)]
    end = ends[0] if ends else None
    if start is None or end is None:
        return
    for node in children[start:end]:
        body.remove(node)

def detach_references():
    body = doc.element.body
    children = list(body)
    starts = [i for i, n in enumerate(children) if '参考文献' in body_text(n)]
    if not starts:
        return []
    start = starts[-1]
    refs = [deepcopy(n) for n in children[start:] if n.tag != qn('w:sectPr')]
    for node in children[start:]:
        if node.tag != qn('w:sectPr'):
            body.remove(node)
    return refs

# Formal submissions keep conclusions and evidence, while raw survey/interview
# instruments and repeated product screenshots remain in the project archive.
remove_body_range('附录A', '参考文献')
# Keep the core findings and screenshots, but remove long methodological and
# scenario narratives that are better kept in the project evidence archive.
remove_subsection_range('4.2 档口经营者访谈方案设计', '5.1 目标客户筛选条件')
remove_subsection_range('5.3 现有经营方式与替代方案', '6.1 数据采集与经营闭环')
remove_subsection_range('12.4 敏感性与现金流分析', '13.1 风险识别与处置')
reference_nodes = detach_references()
# Interface screenshots are retained as product evidence; page reduction is
# handled by removing raw research instruments and redundant narrative instead.

def set_font(run, size=12, bold=False, color=None, name='SimSun'):
    run.font.name = name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)

def shade(cell, fill):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    cell._tc.get_or_add_tcPr().append(shd)

def border(cell, edge, val='single', sz='8', color='1F5D73'):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.first_child_found_in('w:tcBorders')
    if borders is None:
        borders = OxmlElement('w:tcBorders')
        tcPr.append(borders)
    tag = 'w:' + edge
    el = borders.find(qn(tag))
    if el is None:
        el = OxmlElement(tag)
        borders.append(el)
    el.set(qn('w:val'), val)
    el.set(qn('w:sz'), sz)
    el.set(qn('w:color'), color)

def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ''
        r = c.paragraphs[0].add_run(h)
        set_font(r, 10, True, 'FFFFFF', 'Microsoft YaHei')
        shade(c, '1F5D73')
        c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        border(c, 'top', sz='14')
        border(c, 'bottom', sz='8')
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ''
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(str(value))
            set_font(r, 10, False, None, 'SimSun')
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if len(str(value)) > 16 else WD_ALIGN_PARAGRAPH.CENTER
            border(cells[i], 'top', val='nil')
            border(cells[i], 'bottom', val='nil')
    for c in t.rows[-1].cells:
        border(c, 'bottom', sz='14')
    for row in t.rows:
        trPr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement('w:cantSplit')
        trPr.append(cant_split)
        if row is t.rows[0]:
            tbl_header = OxmlElement('w:tblHeader')
            tbl_header.set(qn('w:val'), 'true')
            trPr.append(tbl_header)
    # Keep all added tables compact and visually consistent with pro10.
    for row in t.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            mar = tcPr.first_child_found_in('w:tcMar')
            if mar is None:
                mar = OxmlElement('w:tcMar'); tcPr.append(mar)
            for edge in ('top', 'start', 'bottom', 'end'):
                el = mar.find(qn('w:' + edge))
                if el is None:
                    el = OxmlElement('w:' + edge); mar.append(el)
                el.set(qn('w:w'), '90'); el.set(qn('w:type'), 'dxa')
    doc.add_paragraph().paragraph_format.space_after = Pt(3)

def heading(text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True

def para(text):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(20)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    p.add_run(text)
    for r in p.runs:
        set_font(r, 12, False, None, 'SimSun')

def picture(path, caption, width=6.1):
    if Path(path).exists():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(path, width=Inches(width))
        c = doc.add_paragraph(caption)
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if c.runs:
            set_font(c.runs[0], 9, False, '666666')
            c.runs[0].italic = True

for sec in doc.sections:
    for p in sec.header.paragraphs:
        if p.text.strip():
            p.text = '食刻有数｜高校食堂经营减损与备餐决策服务'
            for r in p.runs:
                set_font(r, 9, False, '666666', 'Microsoft YaHei')
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
heading('项目定位与经营闭环', 1)
para('食刻有数面向高校食堂档口，连接经营数据、需求判断、分批备餐、剩余处置与复盘反馈，帮助经营者在不替换现有交易系统的前提下减少过量备餐和无效操作。系统给出需求区间与行动参考，首批备餐、补餐、停做和食品安全状态由档口负责人确认。')
table(['参与方', '核心任务', '系统输出', '责任边界'], [
    ('档口经营者', '备餐、补餐、停做与剩余登记', '需求区间、风险提示、行动参考', '确认现场动作与餐品状态'),
    ('食堂运营方', '授权、异常和周期复盘', '汇总看板、审计记录、复盘指标', '确认经营规则与数据范围'),
    ('学生', '选择限时餐品并完成取餐', '数量、价格、截止时间、核销凭证', '确认订单和取餐'),
])
picture('计划书/figures/fig_operating_loop.png', '图补-1 经营数据到现场动作的闭环与责任边界')

heading('建模与智能体联合调度', 1)
para('系统采用规则判断与机器学习模型双重预测。当前实现以模型结果为主、规则结果为辅；模型未就绪时回退规则判断。模型负责预测售出量，智能体只读取结构化事实，负责独立复核、经营解释和异常提示，不得修改备餐量、金额、风险等级或最终经营动作。')
picture('计划书/figures/fig_data_model_agent_pipeline.png', '图补-2 多源数据—模型—智能体联合调度架构')
table(['环节', '实现方式', '输出与边界'], [
    ('需求预测', '规则引擎 + LightGBM；固定特征顺序', '需求区间、首批备餐与补餐参考'),
    ('确定性校验', '对比规则预测、模型预测、近7日历史区间和模型状态', '输出分歧度与区间命中，始终可用'),
    ('智能体复核', '结构化事实字段约束；外部调用失败自动降级', '输出解释和一致性判断，不写回经营数值'),
    ('经营确认', '档口负责人确认建议、餐品状态与限时动作', '形成采纳反馈和下一周期复盘记录'),
])
para('系统先检查模型结果与规则判断、历史经营范围是否一致，再生成原因说明和异常提示。外部智能服务未启用或调用异常时，确定性校验仍可独立运行，经营建议仍由档口负责人确认。')

heading('数据来源与治理', 1)
para('数据按来源和证据强度分层，并通过“原始数据—统一特征—模型结果—经营复盘”管理。正式试点数据需取得档口授权，记录来源、日期、责任人和保存期限；每个版本均保留数据字典、模型说明和指标计算记录。')
table(['数据层', '当前材料', '用途与限制'], [
    ('公开/跨域数据', 'university_food_waste、gylaf_campus、kaggle_food_demand、kaggle_cc0、reduce_foodwaste', '支持变量设计与预训练，不能直接推出本地现场成效'),
    ('项目经营台账', '14个营业日、4类档口、7个菜品、98条记录，模型卡标记为 simulation', '支持流程、字段和回测复算，不替代授权试点'),
    ('派生/预测字段', 'prepare_qty、waste_pieces、waste_rate、lag/rolling 与模型输出', '用于建模和复现，不当作原始观测'),
    ('授权试点数据', '按档口和周期新增采集', '验证采纳、缺货、毛利、工时和续费'),
])
para('现有材料中的数据集名称及样本量存在版本差异，正式提交以统一的数据版本、模型说明、数据字典和指标计算记录为准。计划书不把不同版本的指标并列为确定事实。')
table(['指标', '统一口径', '使用边界'], [
    ('sold_qty', '实际售出份数或订单销量', '用于需求预测评估'),
    ('pred_waste', '模型或规则对浪费量的估计', '不与销量误差混算，不等同称重结果'),
    ('leftover_qty', '备餐量减售出量的台账字段', '需说明退回、报损和漏记范围'),
    ('MAE/WAPE/sMAPE/RMSLE/MAPE', '固定窗口、分母和缺失处理后复算', '预测误差不等于经营改善'),
])

heading('验证方法与试点边界', 1)
para('建模流程为预训练、校园场景适配、滚动回测和上线验证。模型综合使用历史销量、天气、星期、校历/考试、活动、价格、成本、品类和促销等信息。滚动回测按时间顺序逐日预测，避免未来信息泄漏；上线前对训练结果、运行结果和指标计算进行一致性核对。')
table(['模型层', '主要输入', '验证方式'], [
    ('规则基线', '近7日销量、星期、天气、考试周、活动', '历史区间与业务规则核对'),
    ('机器学习模型', '历史销量、天气、校历、活动、价格、成本和品类等特征', '滚动回测与运行结果核对'),
    ('LSTM对照', '时序序列', '统一窗口和指标进行方法对照'),
    ('联合调度', '模型预测、规则预测、历史区间和人工确认', '异常时回退规则并保留复核记录'),
])
picture('计划书/figures/fig_stage_comparison.png', '图补-3 经营测算阶段数量对比')
picture('计划书/figures/fig_metric_rates.png', '图补-4 阶段指标对比：剩余率、售罄率与预测误差')
para('当前14天台账用于流程和回测管线验证，不能替代真实档口试点。真实成效需在授权数据中同时记录备餐、售出、剩余、缺货、优惠、单位成本、操作时长和建议采纳，并结合经营者确认计算。')

for node in reference_nodes:
    doc.element.body.append(deepcopy(node))

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
# The template stores the total-page value as literal text in one footer
# textbox; update that display after the final render count is known.
tmp = OUT.with_suffix('.tmp.docx')
with zipfile.ZipFile(OUT, 'r') as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.startswith('word/footer') and item.filename.endswith('.xml'):
            data = data.replace(b'<w:t>69</w:t>', b'<w:t>68</w:t>')
        zout.writestr(item, data)
tmp.replace(OUT)
print(OUT)
