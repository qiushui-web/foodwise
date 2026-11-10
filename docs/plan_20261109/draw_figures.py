# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon, Circle
from matplotlib import font_manager
ROOT=Path(r'E:/食刻有数');HERE=Path(__file__).parent;OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
font_manager.fontManager.addfont('C:/Windows/Fonts/simhei.ttf')
plt.rcParams.update({'font.family':'SimHei','font.size':15,'axes.unicode_minus':False,'svg.fonttype':'none','savefig.facecolor':'white'})
BLUE='#285E82';TEAL='#328E96';ORANGE='#C78743';INK='#203748';MUTED='#566D7C';PALE='#EDF4F8';LIGHT='#D1E0E9'
def canvas(w=10,h=4):
 f,a=plt.subplots(figsize=(w,h));a.set_xlim(0,10);a.set_ylim(0,h);a.axis('off');return f,a
def text(a,x,y,s,size=15,color=INK,**kw):a.text(x,y,s,ha='center',va='center',fontsize=size,color=color,**kw)
def box(a,x,y,w,h,s,color=BLUE,fill=PALE,size=15):
 a.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.025,rounding_size=.09',edgecolor=color,facecolor=fill,linewidth=1.3));text(a,x+w/2,y+h/2,s,size)
def arrow(a,x,y,x2,y2,color=BLUE,rad=0):a.add_patch(FancyArrowPatch((x,y),(x2,y2),arrowstyle='-|>',mutation_scale=13,lw=1.5,color=color,connectionstyle=f'arc3,rad={rad}'))
def save(f,name):
 f.savefig(OUT/name,dpi=240,bbox_inches='tight',pad_inches=.18);f.savefig(OUT/(name.replace('.png','.svg')),bbox_inches='tight',pad_inches=.18);plt.close(f)
f,a=canvas(h=3.6)
for x,y,s,c in [(0.3,2.1,'经营记录',BLUE),(3.2,2.1,'备餐建议',BLUE),(6.3,2.1,'人工确认',TEAL),(6.3,.45,'执行与盘点',TEAL),(3.2,.45,'经营复盘',BLUE)]:box(a,x,y,2.1,.8,s,c)
arrow(a,2.45,2.5,3.15,2.5);arrow(a,5.35,2.5,6.25,2.5);arrow(a,7.35,2.05,7.35,1.3);arrow(a,6.25,.85,5.35,.85);arrow(a,3.15,.85,1.35,2.05,rad=-.35)
box(a,8.8,.45,.85,2.45,'余量\n\n处置',ORANGE,'#FBF3E8',12);arrow(a,8.45,.85,8.75,.85,ORANGE)
save(f,'loop.png')
f,a=canvas(h=3.7)
text(a,1,3.22,'历史参考',14);text(a,4.7,3.22,'现场条件',14);text(a,8.65,3.22,'人工决定',14)
box(a,.15,1.3,1.75,1.15,'参考数量\n与范围');
for i,s in enumerate(['库存与产能','整批与时间']):box(a,3.45,2.1-i*1.35,2.5,.85,s,TEAL)
arrow(a,1.95,1.9,3.4,2.5);arrow(a,1.95,1.9,3.4,1.2);arrow(a,6,2.5,7.35,1.9);arrow(a,6,1.2,7.35,1.9)
box(a,7.4,1.3,2.35,1.15,'确认或调整\n首批 / 补餐',ORANGE,'#FBF3E8');save(f,'constraints.png')
f,a=canvas(h=3.8)
box(a,.2,1.3,2.15,1.15,'授权快照\n台账 / 计划\n经营复盘');box(a,3.45,1.3,2.2,1.15,'确定性计算\n数量与成本',TEAL);box(a,6.75,1.3,2.65,1.15,'只读解释\n依据与人工下一步')
arrow(a,2.4,1.9,3.4,1.9);arrow(a,5.7,1.9,6.7,1.9)
text(a,4.55,.45,'可选语言摘要',11,MUTED);arrow(a,5.65,.5,7.45,1.25,TEAL,rad=.1)
save(f,'advisor.png')
f,a=plt.subplots(figsize=(9.8,3.7));x=np.linspace(0,10,100);d=15+6*x+9*np.sin(x*.5);a.plot(x,d,color=BLUE,lw=2.2,label='需求（示意）');a.plot(x,np.minimum(d,42),color=ORANGE,lw=2.3,ls='--',label='可观测销量（示意）');a.axhline(42,color=TEAL,lw=1.3,ls=':');a.text(.25,43.2,'可售供给',color=TEAL);a.fill_between(x,42,d,where=d>42,color=LIGHT,alpha=.7);a.set_xlabel('需求变化（示意）');a.set_ylabel('数量（示意）');a.set_xticks([]);a.set_yticks([]);a.legend(frameon=False,loc='upper left');a.spines[['top','right']].set_visible(False);save(f,'censoring.png')
f,a=canvas(h=2.4)
start=.4;total=9.2
for n,s,c in [(25,'训练\n25日',BLUE),(10,'调参\n10日',TEAL),(5,'校准\n5日',ORANGE),(20,'测试\n20日','#527793')]:
 w=total*n/60;a.add_patch(Rectangle((start,.8),w,1.0,facecolor=c,edgecolor='white',lw=2));text(a,start+w/2,1.3,s,12,'white');start+=w
arrow(a,.4,.4,9.65,.4);text(a,5,.1,'按全局日期向前',11);save(f,'split.png')
f,a=canvas(h=5.1)
for y,label,detail,c in [(3.9,'使用界面','Vue 3 · TypeScript',BLUE),(2.7,'经营业务','Java 21 · Spring Boot',BLUE),(1.5,'记录与修订','JDBC · Flyway · H2 / MySQL',TEAL)]:
 a.add_patch(Rectangle((.35,y),6.0,.85,facecolor=PALE,edgecolor=c,lw=1.3));text(a,1.55,y+.425,label,13);text(a,4.55,y+.425,detail,12)
arrow(a,3.4,3.85,3.4,3.6);arrow(a,3.4,2.65,3.4,2.4)
box(a,7.3,2.7,2.25,1.55,'离线研究\nPython\n公开回测 / 仿真',ORANGE,'#FBF3E8',12);arrow(a,7.25,3.1,6.4,3.1,ORANGE)
text(a,8.4,2.15,'评估后接入',11,MUTED);f.set_size_inches(10,3.6);a.set_ylim(1.2,4.95);save(f,'architecture.png')
f,a=canvas(h=4.4)
xs=[2.55,5.3,8.05]
for x,s in zip(xs,['营业前','营业中','闭餐后']):text(a,x,4.05,s,13)
for y,label in [(3.0,'负责人'),(1.9,'当班人员'),(.8,'团队')]:
 a.add_patch(Rectangle((.1,y-.4),9.7,.85,facecolor=PALE if y!=1.9 else '#F5F8FA',edgecolor='none'));text(a,.7,y,label,11)
for x,y,s in [(2.55,3,'确认计划'),(5.3,1.9,'执行与暂记'),(8.05,1.9,'盘点与去向'),(8.05,3,'核对复盘'),(2.55,.8,'准备与培训'),(5.3,.8,'异常支持')]:text(a,x,y,s,12)
arrow(a,3.45,2.9,4.45,2.0);arrow(a,6.15,1.9,7.2,1.9);arrow(a,8.05,2.25,8.05,2.65);arrow(a,3.45,.8,4.45,.8)
f.set_size_inches(10,3.4);a.set_ylim(.25,4.4);save(f,'swimlane.png')
sim=json.loads((ROOT/'项目代码/modeling/data/03_output/competition_validation_20261104_final.json').read_text(encoding='utf-8'))
scenarios=['baseline','rain_shock','campus_event','high_volatility'];labels=['基线','降雨冲击','校园活动','高波动'];policies=[('inertia','惯性备餐',BLUE,'o'),('safety','固定增加10%',TEAL,'s'),('model','残差分位',ORANGE,'D')];agg={(v['scenario'],v['policy']):v for v in sim['aggregate']}
f,a=plt.subplots(figsize=(10,6));ys=np.arange(4)
for i,(key,label,col,marker) in enumerate(policies):
 rows=[agg[s,key] for s in scenarios];means=np.array([r['regret_per_100_mean'] for r in rows]);lo=np.array([r['regret_per_100_p05'] for r in rows]);hi=np.array([r['regret_per_100_p95'] for r in rows]);y=ys+(i-1)*.21
 a.errorbar(means,y,xerr=[means-lo,hi-means],fmt=marker,color=col,capsize=3,label=label,markersize=6)
 for v,yy in zip(means,y):a.text(v+2,yy-.055,f'{v:.1f}',fontsize=13,color=col)
a.set_yticks(ys,labels);a.invert_yaxis();a.set_xlim(0,180);a.set_xlabel('regret/100（原实验归一化口径）');a.grid(axis='x',color='#E0E7EC');a.set_axisbelow(True);a.spines[['top','right','left']].set_visible(False);a.legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,1.13),ncol=3);save(f,'simulation.png')
f,a=plt.subplots(figsize=(9,2.7));a.barh([0],[850],color=ORANGE,label='可变交付成本');a.barh([0],[1350],left=[850],color=BLUE,label='贡献毛利');a.text(425,0,'850',color='white',ha='center',va='center',fontsize=16);a.text(1525,0,'1350',color='white',ha='center',va='center',fontsize=16);a.set_xlim(0,2300);a.set_ylim(-.65,.65);a.set_yticks([]);a.set_xlabel('元 / 档口·年');a.spines[['top','right','left']].set_visible(False);a.legend(frameon=False,ncol=2,loc='upper center',bbox_to_anchor=(.5,1.24));save(f,'unit_economics.png')
f,a=plt.subplots(figsize=(9.7,4.4));x=np.arange(3);inc=[1.8,11,35];cost=[3.2,10.75,25.8];profit=[-1.4,.25,9.2]
for ofs,vals,col,label in [(-.25,inc,BLUE,'营业收入'),(0,cost,TEAL,'总成本'),(.25,profit,ORANGE,'营业利润')]:
 bars=a.bar(x+ofs,vals,width=.23,color=col,label=label)
 for b,v in zip(bars,vals):a.text(b.get_x()+b.get_width()/2,v+(.65 if v>=0 else -1.6),f'{v:g}',ha='center',fontsize=13)
a.axhline(0,color=INK,lw=1);a.set_ylim(-5,40);a.set_xticks(x,['第一年','第二年','第三年']);a.set_ylabel('万元');a.grid(axis='y',color='#E5EBEF');a.set_axisbelow(True);a.spines[['top','right']].set_visible(False);a.legend(frameon=False,ncol=3,loc='upper left');save(f,'finance.png')
print('10 figures rendered to',OUT)
