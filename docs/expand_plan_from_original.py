from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pathlib import Path
import shutil

SRC = Path('计划书/计划书pro10.docx')
OUT = Path('计划书/食刻有数_商业计划书_扩充修订版.docx')
doc = Document(SRC)

def set_font(run, size=10.5, bold=False, color=None):
    run.font.name = 'Microsoft YaHei'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    run.font.size = Pt(size); run.bold = bold
    if color: run.font.color.rgb = RGBColor.from_string(color)

def shade(cell, fill):
    shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill)
    cell._tc.get_or_add_tcPr().append(shd)

def border(cell, edge, val='single', sz='8', color='1F5D73'):
    tcPr = cell._tc.get_or_add_tcPr(); borders = tcPr.first_child_found_in('w:tcBorders')
    if borders is None:
        borders = OxmlElement('w:tcBorders'); tcPr.append(borders)
    tag = 'w:' + edge; el = borders.find(qn(tag))
    if el is None: el = OxmlElement(tag); borders.append(el)
    el.set(qn('w:val'), val); el.set(qn('w:sz'), sz); el.set(qn('w:color'), color)

def three_line_table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = ''
        r = c.paragraphs[0].add_run(h); set_font(r, 9, True, 'FFFFFF')
        shade(c, '1F5D73'); c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        border(c, 'top', sz='14'); border(c, 'bottom', sz='8')
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ''
            p = cells[i].paragraphs[0]; p.paragraph_format.space_after = Pt(0)
            r = p.add_run(str(value)); set_font(r, 9)
            border(cells[i], 'top', val='nil'); border(cells[i], 'bottom', val='nil')
    for c in t.rows[-1].cells: border(c, 'bottom', sz='14')
    doc.add_paragraph().paragraph_format.space_after = Pt(3)
    return t

def heading(text, level=1):
    p = doc.add_heading(text, level=level); p.paragraph_format.keep_with_next = True; return p

def para(text):
    p = doc.add_paragraph(); p.paragraph_format.first_line_indent = Pt(20)
    p.paragraph_format.line_spacing = 1.35; p.paragraph_format.space_after = Pt(6)
    p.add_run(text); return p

def bullet(text):
    p = doc.add_paragraph(style='List Bullet'); p.paragraph_format.space_after = Pt(3); p.add_run(text)

def number(text):
    p = doc.add_paragraph(); p.paragraph_format.left_indent = Pt(20); p.paragraph_format.first_line_indent = Pt(-20); p.paragraph_format.space_after = Pt(3); p.add_run(text)

def page_break(): doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

def add_picture(path, caption, width=6.1):
    if Path(path).exists():
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(path, width=Inches(width))
        c = doc.add_paragraph(caption); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if c.runs: set_font(c.runs[0], 9, False, '666666'); c.runs[0].italic = True

# Update running header to the current, concise project name while retaining original page fields.
for sec in doc.sections:
    for p in sec.header.paragraphs:
        if p.text.strip():
            p.text = '食刻有数｜高校食堂经营减损与备餐决策服务'
            for r in p.runs: set_font(r, 9, False, '666666')
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

page_break()
heading('版本校准与省赛评审补充', 1)
para('本补充部分用于将原计划书的完整业务内容与当前可运行项目、数据证据和省赛评审要求统一。原正文保留 13 章结构和原有论证深度；本补充只新增当前版本必须明确的定位、数据治理、图表证据、产品边界和评审口径。')
three_line_table(['校准项','本版统一表述','证据或限制'], [
('项目定位','面向高校食堂档口的低改造成本经营减损与备餐决策 SaaS','不替代 POS，不替代食品安全责任'),
('已完成能力','可运行产品原型、经营台账、需求判断、优惠、核销、反馈和复盘流程','以源码、接口和页面为证据'),
('经营数据','14个营业日、4类档口、7个菜品、98条记录','经营测算样本，不等于现场试点'),
('模型指标','基线期与策略期的阶段回测结果','需固定数据版本、窗口和计算公式'),
('商业化','定价和三年收入为情景测算','需以真实订单、续费和交付工时核验'),
('知识产权','申请材料与软件证据已准备','登记证书状态按实际材料表述'),
])

heading('一、项目定位升级：从功能集合到经营决策链', 2)
para('本项目的核心不是“有多少页面”或“使用了多少模型”，而是把高校食堂档口的一组连续经营动作连接起来：经营数据采集、需求区间判断、首批备餐、二次补餐、停止制作、剩余登记、安全限时处置、订单核销和经营复盘。评委在阅读时应能回答三个问题：谁在什么时间做什么决定，系统提供了什么证据，结果如何回到下一周期。')
three_line_table(['用户','现场任务','系统输出','最终确认人'], [
('档口经营者','决定首批备餐、补餐和停做','需求区间、风险提示、行动参考','档口负责人'),
('食堂运营方','审核准入、责任和异常','授权汇总、阶段报告、审计记录','运营方负责人'),
('学生','选择安全、透明的限时餐品','数量、价格、取餐点、截止时间和核销凭证','学生确认取餐'),
('项目团队','维护数据、模型和服务流程','数据字典、模型卡、SOP、复盘模板','项目负责人'),
])
add_picture('计划书/figures/fig_operating_loop.png', '图补-1 经营数据到现场动作的闭环与责任边界')

heading('二、现有经营样本的证据分层', 2)
para('原计划书中的经营结果必须按证据强度分层。14个营业日、98条记录能够支持字段定义、指标复算和页面流程验证，但不能替代经授权档口试点。公开数据和跨域数据可以支持变量选择与方法开发，但不能直接推出河北高校档口的经营成效。只有连续授权台账、经营者确认和完整成本记录，才能支撑现场改善、付费和复制性结论。')
three_line_table(['数据层','可以回答的问题','不能直接回答的问题','计划书使用方式'], [
('公开政策与研究','为什么值得解决、变量为何合理','项目是否已产生现场效果','背景和方法依据'),
('团队经营测算','字段、公式和产品流程能否贯通','是否适用于所有高校档口','图表和方法回测'),
('合成/预训练数据','模型开发和冷启动如何进行','河北现场迁移效果','研发辅助材料'),
('授权试点数据','经营者是否采纳、成本是否下降','跨区域长期规模化','成效、付费和复制证据'),
])
add_picture('计划书/figures/fig_stage_comparison.png', '图补-2 阶段数量对比：少备餐、售出基本稳定、剩余量下降')
add_picture('计划书/figures/fig_metric_rates.png', '图补-3 阶段指标对比：剩余率、售罄率与预测误差')

heading('三、图表使用规范与评委阅读路径', 2)
para('本版图表按“先结论、再证据、后边界”的顺序使用。柱状图回答数量是否变化，趋势图回答变化是否贯穿整个观察窗口，阶段指标图直接给出剩余率、售罄率和 MAPE，闭环图回答数据如何进入经营动作，竞争象限只说明切入逻辑，不宣称竞品的定量排名。')
three_line_table(['图表','主问题','读图结论','必须保留的边界'], [
('阶段数量对比','备餐、售出、剩余发生了什么变化？','备餐量和剩余量下降，售出量接近','阶段测算，不等于因果证明'),
('14日趋势','变化是否只来自某一天？','策略期剩余量整体较低','阶段划分不是随机实验'),
('阶段指标','评委最关心的率和误差是多少？','剩余率下降、售罄率上升、MAPE下降','需结合缺货、毛利和工时'),
('经营闭环','产品如何形成持续改进？','结果回写下一周期','平台不替代食品安全责任'),
('竞争象限','项目从哪里切入？','低改造成本、经营闭环是切入点','不是市场份额或功能排名'),
])
add_picture('计划书/figures/fig_daily_trend.png', '图补-4 14个营业日经营数量趋势：阶段边界与数据来源已标注')
add_picture('计划书/figures/fig_competitor_quadrant.png', '图补-5 竞争定位示意：低改造成本与经营闭环能力')

heading('四、产品功能的完成度分级', 2)
para('为避免评委将“方案描述”误认为“已交付能力”，本版将功能分为已运行、流程验证和后续适配三类。计划书正文中的措辞应与以下等级一致。')
three_line_table(['等级','能力','可使用的表述','不可使用的表述'], [
('已运行','经营驾驶舱、档口菜品、备餐规则、反馈、复盘、接口和权限框架','已形成可运行原型或接口流程','已经在多校区稳定部署'),
('流程验证','限时优惠、匿名核销、模型回退、审计链路','已完成流程设计与原型验证','已经产生确定的现场节省金额'),
('后续适配','POS/Excel接入、刷卡聚合、OCR、语音、小程序、多租户','列入试点或商业化路线','当前版本已经交付'),
])

heading('五、评委可能追问与答辩准备', 2)
three_line_table(['评委追问','建议回答重点','需要携带的证据'], [
('98条记录是真实试点吗？','说明它是经营测算样本，用于复算和方法回测；真实授权试点待补','CSV、字段说明、样本范围和数据声明'),
('为什么剩余率下降就能说明有效？','不能单独说明；还要同时核对售罄、缺货、毛利、工时和经营者确认','指标表、缺货记录、成本台账、复盘表'),
('模型比简单基线更好吗？','只在固定窗口和统一口径下比较；复杂模型连续失准时回退基线','模型卡、回测脚本、版本和窗口'),
('食品安全谁负责？','档口和运营方负责状态确认与最终销售，平台只做规则提示、限时和留痕','责任清单、下架规则、异常日志'),
('为什么客户会付费？','从低成本单档口诊断切入，以可核对的经营改善和少录入换取续费','试点SOP、单位经济表、付费记录'),
('与POS或ERP有什么不同？','不替代交易系统，聚焦备餐、剩余处置和复盘动作','替代方案比较表、闭环图'),
])

heading('六、当前版本的试点验收标准', 2)
number('完成书面授权，明确档口、运营方、项目团队的数据范围、责任人和保存期限。')
number('连续记录5—7天基线，运行7—14天策略；保持相近星期结构并记录天气、校历和异常事件。')
number('同时记录备餐、售出、剩余、优惠、核销、单位成本、原价销售、操作时长、缺货和建议采纳。')
number('阶段复盘同时检查剩余率、售罄率、毛利、数据完整率和经营者确认，不用单一指标宣布成功。')
number('只有在数据连续、责任清晰、经营者愿意使用且贡献毛利为正时，才进入同食堂复制。')

heading('七、版本交付检查清单', 2)
three_line_table(['检查项','本版状态','提交前动作'], [
('章节完整性','原13章正文保留，新增校准补充','核对目录页码和章节编号'),
('页眉页脚','沿用原计划书版式并统一项目简称','核对每节页眉和页码字段'),
('三线表','原正文表格保留，新增表格使用三线表','检查跨页表头和行拆分'),
('图表','新增数据图、流程图和竞争定位图','检查图题、来源、单位和边界声明'),
('数据口径','已区分测算、回测、试点和商业情景','提交前逐项核对数字来源'),
('敏感信息','未加入本机绝对路径和密钥','检查正文、页眉和附录'),
])

heading('八、项目特有的建模与智能体联合调度', 2)
para('食刻有数的智能体不是替代预测模型的“聊天入口”，而是围绕训练模型做独立复核、经营解释和异常提示。系统先由规则引擎与 LightGBM 并行给出需求判断，再将结构化事实包交给智能体生成可读说明；事实包中的数字来自系统字段，受到数字白名单约束，智能体无权修改备餐量、金额、风险等级或最终经营动作。这样既保留模型的可复现性，也让档口负责人能够理解“为什么这样建议”。')
add_picture('计划书/figures/fig_data_model_agent_pipeline.png', '图补-6 多源数据—模型—智能体联合调度架构')
three_line_table(['环节','项目实现','输出与责任边界'], [
('双引擎预测','规则引擎 + LightGBM；当前系统口径为 0.6×模型 + 0.4×规则，模型未就绪时回退规则','输出 sold_qty 需求区间、首批备餐和补餐参考；不直接下单'),
('确定性复核','ModelCrossCheckService 对比规则预测、LGBM预测、近7日历史区间和模型状态','输出分歧度、区间命中、模型就绪等机读检查项，始终可用'),
('智能体解释','ZhipuAiService 接收结构化事实包，独立给出区间与 caution/agree/disagree 判断','输出解释、风险提示和复核意见；外部调用失败时不影响确定性校验'),
('经营建议','IntelligentDecisionService 汇总事实、原因、动作和警示并留痕','档口负责人确认首批、补餐、停做、优惠与食品安全状态'),
])
para('项目采用“训练模型负责预测、智能体负责旁路复核”的职责分离。智能体没有写入备餐量、价格、风险或食品安全状态的权限；外部大模型 API Key 未配置、调用超时或返回格式异常时，系统仍能够依靠规则引擎、历史区间和模型状态完成确定性校验。该边界是项目可信度的重要组成，而不是对大模型能力的泛化宣传。')

heading('九、多源数据体系与数据治理', 2)
para('项目数据按来源、用途和证据强度分层管理。数据流水线遵循“01_raw 原始数据 → 02_processed 处理数据 → 03_output 指标与预测 → src/main/resources/modeling Java运行产物”的路径；每次提交以 DATA_VERSION.json 的哈希清单核对训练文件、特征列和 Java 加载模型的一致性。正式试点前，必须将授权档口新增数据纳入同一字典和版本链路。')
three_line_table(['数据层','当前材料','可支持的结论','不可直接支持的结论'], [
('公开/跨域数据','university_food_waste、gylaf_campus、kaggle_food_demand、kaggle_cc0、reduce_foodwaste 等公开或授权材料','变量设计、预训练、跨域方法比较','河北高校档口的现场改善金额'),
('项目测算台账','14个营业日、4类档口、7个菜品、98条记录；模型卡标记为 simulation','字段贯通、页面流程、阶段回测和图表复算','真实试点成效、长期稳定性'),
('派生与预测字段','prepare_qty、waste_pieces、waste_rate、lag/rolling 特征及模型输出','明确计算口径、复现模型输入输出','将派生值当作原始观测'),
('授权试点数据','待按档口、日期、责任人和保存期限补充','验证采纳率、缺货、毛利、工时和续费','跨学校规模化效果'),
])
para('现有材料曾出现 SmartBite 合成数据、公开数据集和“全真实、零模拟”等不同表述，也出现不同样本量与指标口径。正式提交时统一以 DATA_VERSION.json、MODEL_CARD.md、数据字典和可复现实验结果为准；未完成统一前，本计划书不把冲突数字写成确定事实，也不以单个 MAPE 数字代替经营改善。')
three_line_table(['字段/指标','口径','使用限制'], [
('sold_qty','实际售出份数或订单销量；用于需求预测评估','必须标注观察窗口、拆分方式和缺失处理'),
('pred_waste','模型或规则对浪费量的估计；与 sold_qty 分开记录','不得与销量误差混算，也不得直接等同真实浪费称重'),
('leftover_qty','备餐量减售出量的经营台账字段','需说明是否含退回、报损和未记录部分'),
('MAPE/WAPE/sMAPE/RMSLE/MAE','按统一窗口和分母规则复算并保留脚本','模型指标不等于经营改善，须结合缺货、毛利和工时'),
])

heading('十、从数据到经营建议的可复现链路', 2)
para('建模采用“预训练—校园场景微调—滚动回测—Java导出—运行时复核”的链路。预训练阶段吸收团餐、校园和天气促销数据的共性关系；校园场景微调使用带场景字段的数据；滚动回测按时间顺序逐日预测，避免把未来信息泄漏到训练集；导出后由纯 Java LightGBM 推理，按固定 24 维特征顺序构造输入，并用 Python/Java 结果一致性文件核验。')
three_line_table(['模型层','输入特征或方法','输出','验收方式'], [
('规则基线','近7日销量、星期、天气、考试周、活动等可解释因子','规则预测与风险提示','与历史区间、业务规则逐项核对'),
('LightGBM','24维固定顺序特征：lag、rolling、天气、星期、校历/考试、活动、价格、成本、品类、促销等','sold_qty 预测与特征贡献','滚动回测；模型文件、特征列和哈希一致'),
('LSTM对照','时序序列建模方案，用于方法对照而非默认上线','对照预测误差','统一窗口、指标、缺失处理和计算脚本'),
('联合调度','当前实现口径：0.6×LightGBM + 0.4×规则；异常时回退规则','需求区间、首批备餐、补餐参考','检查模型状态、分歧度、历史区间和人工确认'),
])
para('模型只预测 sold_qty；浪费量、剩余量和经营改善必须分别定义。MAE、WAPE、sMAPE、RMSLE 等指标用于比较预测误差，不能直接解释为“节省了多少食材”或“降低了多少成本”。计划书中的阶段图展示的是当前经营测算样本的变化；真实成效需要新增授权台账、成本与工时记录以及经营者确认后再计算。')
three_line_table(['复现节点','保留材料','评委可核验的问题'], [
('数据版本','DATA_VERSION.json、数据字典、原始/处理/输出目录说明','这组数字来自哪个版本，是否可重算？'),
('模型版本','模型卡、特征列、LightGBM文件、回测报告','训练、验证和运行时输入是否一致？'),
('运行时版本','Java推理类、双引擎接口、回退逻辑','模型不可用或外部调用失败时是否仍可运行？'),
('经营复盘','采纳反馈、异常记录、缺货/毛利/工时字段','建议是否真的被执行，下一周期如何调整？'),
])

# Make the new section title visible in the TOC-like body even when the original TOC is field-based.
OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(OUT)
