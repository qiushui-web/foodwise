import zipfile, shutil, tempfile
from pathlib import Path
from lxml import etree

src = Path('计划书/食刻有数_商业计划书_重写版.docx')
tmp = Path(tempfile.mkdtemp())
with zipfile.ZipFile(src) as z: z.extractall(tmp)
media = tmp/'word'/'media'
figs = [
    Path('计划书/figures/fig_operating_loop.png'),
    Path('计划书/figures/fig_daily_trend.png'),
    Path('计划书/figures/fig_stage_comparison.png'),
    Path('计划书/figures/fig_metric_rates.png'),
    Path('计划书/figures/fig_competitor_quadrant.png'),
]
for i, p in enumerate(figs, 1): shutil.copyfile(p, media/f'image{i}.png')
for i in (4,5):
    # remove old extra screenshot payloads; relationships are retained for compatibility
    pass
xml = tmp/'word'/'document.xml'
text = xml.read_text(encoding='utf-8')
repls = {
 '经营驾驶舱产品界面（产品原型证据，不单独证明经营成效）':'经营数据到现场动作的闭环流程（输入、责任和反馈关系）',
 '备餐决策中心（需求区间与经营动作入口）':'经营数据到现场动作的闭环流程（输入、责任和反馈关系）',
 '需求预测分析界面（回测与解释层）':'基线期与策略期的数量对比（14个营业日、98条记录）',
 '减损成效分析界面（指标复盘层）':'14个营业日备餐、售出与剩余趋势（策略期起点以虚线标示）',
 '限时优惠界面（安全确认和数量护栏）':'限时处置在经营闭环中的位置（不替代食品安全责任）',
}
for a,b in repls.items(): text=text.replace(a,b)
# The first replacement is reused by two legacy captions; restore distinct chart captions.
marker = '经营数据到现场动作的闭环流程（输入、责任和反馈关系）'
pos = text.find(marker)
pos2 = text.find(marker, pos + len(marker))
if pos2 >= 0:
    text = text[:pos2] + text[pos2:].replace(marker, '基线期与策略期的数量对比（14个营业日、98条记录）', 1)
text = text.replace('图4-2 基线期与策略期的数量对比（14个营业日、98条记录）', '图4-2 14个营业日经营数量趋势（阶段边界和数据来源见图内）')
text = text.replace('图6-2 14个营业日备餐、售出与剩余趋势（策略期起点以虚线标示）', '图6-2 阶段指标对比（剩余率、售罄率与预测误差）')
text = text.replace('图7-1 限时处置在经营闭环中的位置（不替代食品安全责任）', '图8-1 竞争定位示意（低改造成本与经营闭环能力）')
xml.write_text(text, encoding='utf-8')
out = src.with_name(src.stem+'__图表增强版.docx')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in tmp.rglob('*'):
        if p.is_file(): z.write(p, p.relative_to(tmp))
print(out)
