import csv
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path("E:/食刻有数")
out = root / "计划书" / "figures"
out.mkdir(parents=True, exist_ok=True)
font_path = "C:/Windows/Fonts/msyh.ttc"
font_b = ImageFont.truetype(font_path, 30)
font_m = ImageFont.truetype(font_path, 22)
font_s = ImageFont.truetype(font_path, 17)
teal, navy, coral, mint, gray, white = "#1F5D73", "#174C5A", "#D66A4A", "#5BAA9B", "#60737B", "#FFFFFF"
with open(root / "src/main/resources/data/foodwise_operations_14d.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
for r in rows:
    if r.get("phase") not in ("基线期", "策略期"):
        r["phase"] = "基线期" if "baseline" in str(r.get("phase","")).lower() else "策略期"
stages = {"基线期": defaultdict(int), "策略期": defaultdict(int)}
daily = defaultdict(lambda: defaultdict(int))
for r in rows:
    for k in ["prepared_qty", "sold_qty", "leftover_qty"]:
        stages[r["phase"]][k] += int(r[k])
        daily[r["business_date"]][k] += int(r[k])

def canvas(w=1500, h=800):
    return Image.new("RGB", (w, h), "#F7FAFA")
def text(d, xy, s, f=font_s, fill=navy):
    d.text(xy, s, font=f, fill=fill, anchor="ma")

im = canvas(1600, 920); d = ImageDraw.Draw(im); text(d, (800, 45), "阶段对比：少备餐，售出基本稳定，剩余量下降", font_b)
left, bottom, right, top, maxv = 150, 665, 1450, 155, 3200
for v in range(0, 3500, 500):
    y = bottom - (bottom-top)*v/maxv
    d.line((left, y, right, y), fill="#D9E5E7", width=2); text(d, (55, y), str(v), font_s, gray)
labels = [("备餐量", "prepared_qty", teal), ("售出量", "sold_qty", mint), ("剩余量", "leftover_qty", coral)]
for i, phase in enumerate(["基线期", "策略期"]):
    cx = 430 + i*600; text(d, (cx, 710), phase, font_m)
    for j, (lab, k, col) in enumerate(labels):
        x = cx-150+j*110; val = stages[phase][k]; y = bottom-(bottom-top)*val/maxv
        d.rectangle((x, y, x+70, bottom), fill=col); text(d, (x+35, y-22), str(val), font_s); text(d, (x+35, 740), lab, font_s, gray)
d.line((left, top, left, bottom), fill=navy, width=3); d.line((left, bottom, right, bottom), fill=navy, width=3)
text(d,(800,770),"数量（份）；样本：14个营业日、4类档口、7个菜品、98条记录",font_s,gray)
text(d,(430,825),"剩余率 13.8% → 6.0%",font_m,coral)
text(d,(1080,825),"售罄率 86.2% → 94.0%",font_m,mint)
text(d,(800,875),"说明：阶段测算与方法回测，不等同于授权档口现场干预成效。",font_s,gray)
im.save(out/"fig_stage_comparison.png")

# Stage rates and error comparison
im = canvas(1600, 900); d = ImageDraw.Draw(im); text(d, (800, 45), "阶段指标：剩余率下降，售罄率上升，MAPE下降", font_b)
left, bottom, right, top, maxv = 150, 650, 1450, 150, 100
for v in range(0, 110, 20):
    y = bottom-(bottom-top)*v/maxv; d.line((left,y,right,y),fill="#D9E5E7",width=2); text(d,(65,y),str(v),font_s,gray)
metrics = [("剩余率", "leftover_qty", "prepared_qty", coral), ("售罄率", "sold_qty", "prepared_qty", mint)]
for i, (lab, num, den, col) in enumerate(metrics):
    for j, phase in enumerate(["基线期", "策略期"]):
        rate = stages[phase][num] / stages[phase][den] * 100; x = 330+i*520+j*130
        y = bottom-(bottom-top)*rate/maxv; d.rectangle((x,y,x+78,bottom),fill=col); text(d,(x+39,y-24),f"{rate:.1f}%",font_s); text(d,(x+39,700),phase,font_s,gray)
    text(d,(590+i*520,760),lab,font_m,col)
    if lab == "剩余率": text(d,(590+i*520,810),"下降 7.8 个百分点",font_s,gray)
    else: text(d,(590+i*520,810),"提高 7.8 个百分点",font_s,gray)
d.line((left,top,left,bottom),fill=navy,width=3); d.line((left,bottom,right,bottom),fill=navy,width=3)
text(d,(800,865),"MAPE：8.9% → 4.5%，为同一经营测算样本的阶段回测结果。",font_s,gray)
im.save(out/"fig_metric_rates.png")

im = canvas(1600, 920); d = ImageDraw.Draw(im); text(d, (800, 45), "14 个营业日：备餐、售出与剩余的变化", font_b)
dates = sorted(daily); left, bottom, right, top, maxv = 130, 680, 1400, 150, 700
for v in range(0, 800, 100):
    y = bottom-(bottom-top)*v/maxv; d.line((left,y,right,y),fill="#D9E5E7",width=2); text(d,(55,y),str(v),font_s,gray)
colors = {"prepared_qty": teal, "sold_qty": mint, "leftover_qty": coral}
for idx,(k,col) in enumerate(colors.items()):
    pts=[]
    for i,date in enumerate(dates):
        x=left+(right-left)*i/(len(dates)-1); y=bottom-(bottom-top)*daily[date][k]/maxv; pts.append((x,y))
    d.line(pts,fill=col,width=5)
    for x,y in pts: d.ellipse((x-6,y-6,x+6,y+6),fill=col)
    text(d,(1180,80+idx*28),{"prepared_qty":"备餐量","sold_qty":"售出量","leftover_qty":"剩余量"}[k],font_s,col)
x=left+(right-left)*7/(len(dates)-1); d.line((x,top,x,bottom),fill=gray,width=3); text(d,(x+45,125),"策略期开始",font_s,gray)
for i,date in enumerate(dates):
    x=left+(right-left)*i/(len(dates)-1); text(d,(x,705),date[5:],font_s,gray)
d.line((left,top,left,bottom),fill=navy,width=3); d.line((left,bottom,right,bottom),fill=navy,width=3)
text(d,(800,770),"纵轴：数量（份）｜横轴：营业日｜虚线：策略期起点",font_s,gray)
text(d,(800,825),"解读：策略期剩余量整体较低，售出量保持接近；该图展示变化，不单独证明因果效果。",font_s,gray)
text(d,(800,875),"数据来源：foodwise_operations_14d.csv；阶段划分沿用原始 phase 字段。",font_s,gray)
im.save(out/"fig_daily_trend.png")

im = canvas(1700,720); d = ImageDraw.Draw(im); text(d,(850,40),"从数据到经营动作：可追踪闭环与责任边界",font_b)
nodes=[("经营数据\\n采集",70,220,teal),("需求区间\\n预测",350,220,navy),("分批备餐\\n人工确认",630,220,mint),("剩余登记\\n安全判断",910,220,coral),("限时优惠\\n订单核销",1190,220,"#8D6E63")]
for label,x,y,col in nodes:
    d.rounded_rectangle((x,y,x+210,y+100),radius=18,fill=white,outline=col,width=5)
    lines=label.split("\\n"); text(d,(x+105,y+35),lines[0],font_m,col); text(d,(x+105,y+72),lines[1],font_m,col)
for i in range(len(nodes)-1):
    x=nodes[i][1]+210; y=270; d.line((x,y,x+70,y),fill=gray,width=5); d.polygon([(x+70,y),(x+52,y-11),(x+52,y+11)],fill=gray)
d.rounded_rectangle((590,440,1110,535),radius=18,fill=white,outline=navy,width=5); text(d,(850,487),"经营复盘 → 反馈下一周期",font_m,navy)
d.line((1295,320,1295,487),fill=gray,width=4); d.line((1295,487,1110,487),fill=gray,width=4); d.polygon([(1110,487),(1128,476),(1128,498)],fill=gray)
d.line((590,487,175,487),fill=gray,width=4); d.line((175,487,175,320),fill=gray,width=4); d.polygon([(175,320),(164,338),(186,338)],fill=gray)
text(d,(175,125),"档口/运营方：输入与确认",font_s,gray); text(d,(1295,125),"学生：获取优惠与核销",font_s,gray); text(d,(850,585),"平台：计算、提示、留痕；不替代食品安全责任",font_s,gray)
text(d,(850,650),"闭环图展示业务关系，不表示所有模块已经完成现场部署。",font_s,gray)
im.save(out/"fig_operating_loop.png")

# Competitive positioning quadrant
im = canvas(1500, 900); d = ImageDraw.Draw(im); text(d,(750,45),'竞争定位：低改造成本与经营闭环能力',font_b)
left,bottom,right,top=180,700,1360,150
d.line((left,top,left,bottom),fill=navy,width=4); d.line((left,bottom,right,bottom),fill=navy,width=4)
text(d,(130,135),'经营闭环能力 ↑',font_s,gray); text(d,(1250,755),'改造成本 →',font_s,gray)
for x in [480,780,1080]: d.line((x,top,x,bottom),fill='#D9E5E7',width=2)
for y in [290,430,570]: d.line((left,y,right,y),fill='#D9E5E7',width=2)
pts=[('经验/纸笔',330,560,gray),('Excel台账',520,500,gray),('POS/收银',880,420,navy),('餐饮ERP',1120,300,navy),('优惠平台',1040,540,'#8D6E63'),('食刻有数',690,270,coral)]
for lab,x,y,col in pts:
    d.ellipse((x-14,y-14,x+14,y+14),fill=col); text(d,(x,y-38),lab,font_s,col)
text(d,(750,820),'位置用于说明产品切入逻辑，不是对竞品功能和市场份额的定量排名。',font_s,gray)
im.save(out/"fig_competitor_quadrant.png")

# Data/model/agent pipeline
im = canvas(1800, 900); d = ImageDraw.Draw(im); text(d,(900,45),'多源数据—模型—智能体联合调度架构',font_b)
layers=[
    ('01_raw｜原始数据', ['高校浪费实测','高校交易+天气','团餐需求','零售+天气','减损基准'], teal, 90),
    ('02_processed｜统一特征', ['24维特征','滞后/滚动销量','天气/校历/活动','价格/成本/品类'], navy, 300),
    ('03_output｜模型产物', ['LightGBM高校模型','规则基线','回测报告','特征重要性'], mint, 510),
    ('线上联合调度', ['规则引擎兜底','LGBM预测与归因','确定性校验','智能体旁路复核'], coral, 720),
]
for title, items, col, y in layers:
    d.rounded_rectangle((80,y,1720,y+125),radius=20,fill=white,outline=col,width=5)
    text(d,(300,y+30),title,font_m,col)
    for i,item in enumerate(items):
        x=470+i*240; d.rounded_rectangle((x,y+17,x+215,y+103),radius=12,fill='#F3F8F8',outline='#C7DADC',width=2); text(d,(x+107,y+60),item,font_s,navy)
    if y < 720:
        d.line((900,y+125,900,y+205),fill=gray,width=4); d.polygon([(900,y+205),(889,y+187),(911,y+187)],fill=gray)
text(d,(900,875),'智能体只读取结构化事实，负责独立复核与经营解释；训练模型拥有最终预测主权。',font_s,gray)
im.save(out/"fig_data_model_agent_pipeline.png")
print(out)
