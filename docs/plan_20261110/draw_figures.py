# -*- coding: utf-8 -*-
from pathlib import Path
import json,shutil,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle,Rectangle,FancyArrowPatch,Arc
HERE=Path(__file__).parent;ROOT=HERE.parents[2];OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
font_manager.fontManager.addfont('C:/Windows/Fonts/simhei.ttf')
plt.rcParams.update({'font.family':['Times New Roman','SimHei'],'font.size':15,'axes.unicode_minus':False,'svg.fonttype':'none','savefig.facecolor':'white','axes.edgecolor':'#9AA5AF','axes.labelcolor':'#222222','xtick.color':'#646C74','ytick.color':'#222222'})
BLUE='#285E82';GRAY='#9AA5AF';INK='#222222';MUTED='#646C74';ORANGE='#C78743';PALE='#F3F6F8';LIGHT='#DDE5EB'
SIM=ROOT/'项目代码/modeling/data/03_output/competition_validation_20261104_final.json'
PUB=ROOT/'项目代码/modeling/data/03_output/competition-public-data/competition-public-data-20261104-final/summary.json'
sim=json.loads(SIM.read_text(encoding='utf-8'));public=json.loads(PUB.read_text(encoding='utf-8'))['runs']['external_zurich']['result']
provenance={}
def canvas(h=3.5):
 f,a=plt.subplots(figsize=(8.8,h));a.set_xlim(0,10);a.set_ylim(0,h);a.axis('off');return f,a
def txt(a,x,y,s,size=15,color=INK,ha='center',**kw):return a.text(x,y,s,fontsize=size,color=color,ha=ha,va='center',**kw)
def arrow(a,x,y,u,v,col=BLUE,style='-',rad=0):
 a.add_patch(FancyArrowPatch((x,y),(u,v),arrowstyle='-|>',lw=1.35,color=col,mutation_scale=13,linestyle=style,connectionstyle=f'arc3,rad={rad}'))
def icon(a,x,y,kind,color=BLUE,r=.28):
 # Meaningful line symbols retain shape cues in grayscale.
 a.add_patch(Circle((x,y),r,facecolor='white',edgecolor=color,lw=1.5))
 if kind=='check':a.plot([x-r*.5,x-r*.1,x+r*.55],[y,y-r*.35,y+r*.4],c=color,lw=1.7)
 elif kind=='chart':
  for dx,h in [(-.13,.12),(0,.23),(.13,.34)]:a.plot([x+dx,x+dx],[y-.17,y-.17+h],c=color,lw=2.4)
 elif kind=='plate':
  a.add_patch(Arc((x,y),r*1.25,r*.8,theta1=180,theta2=360,color=color,lw=1.4));a.plot([x-r*.7,x+r*.7],[y,y],c=color,lw=1.4);a.plot([x,x],[y+.03,y+.15],c=color,lw=1.2)
 elif kind=='person':
  a.add_patch(Circle((x,y+.09),r*.23,fill=False,edgecolor=color,lw=1.3));a.add_patch(Arc((x,y-.13),r*.9,r*.9,theta1=0,theta2=180,color=color,lw=1.4))
 else:
  a.add_patch(Rectangle((x-.12,y-.16),.24,.32,fill=False,edgecolor=color,lw=1.2))
  a.plot([x-.07,x+.07],[y+.05,y+.05],c=color,lw=1.1);a.plot([x-.07,x+.07],[y-.04,y-.04],c=color,lw=1.1)
def save(f,name,source='项目业务与研究方案；结构化绘制'):
 f.savefig(OUT/(name+'.png'),dpi=280,bbox_inches='tight',pad_inches=.15)
 f.savefig(OUT/(name+'.svg'),bbox_inches='tight',pad_inches=.15);plt.close(f)
 provenance[name]={'source':source,'generated_image_api':False}
def axes(a):
 a.spines[['top','right']].set_visible(False);a.spines[['bottom','left']].set_color(LIGHT);a.tick_params(length=0,pad=8);a.set_axisbelow(True)

f,a=plt.subplots(figsize=(8.8,3.6));x=np.array([0,1,2,3,4,5]);d=np.array([0,.19,.38,.57,.76,.95]);supply=.57
a.plot(x,d,c=BLUE,lw=2.2,label='需求');a.plot(x,np.minimum(d,supply),c=ORANGE,lw=2,ls='--',label='观测销量')
a.fill_between(x,supply,d,where=d>=supply,color=PALE)
a.annotate('售罄后无法直接观测的需求',xy=(4.1,.68),xytext=(2.2,.94),fontsize=14,arrowprops={'arrowstyle':'-','color':MUTED},color=INK)
a.text(.05,supply+.035,'可售供给上限',fontsize=14,color=MUTED);a.axhline(supply,c=GRAY,lw=1,ls=':');a.scatter([3],[supply],s=45,c=ORANGE,zorder=5)
a.set_xlabel('潜在需求增加 →',labelpad=10);a.set_ylabel('数量关系');a.set_xticks([]);a.set_yticks([]);a.set_ylim(-.03,1.09);a.legend(frameon=False,loc='lower right');axes(a);save(f,'censoring','概念机制：Y=min(D,A)，非观测数据')

f,a=canvas(3.6)
for x,label,sub,kind in [(1.4,'开餐前','核对参考 · 确认计划','doc'),(5,'营业中','执行调整 · 保留记录','plate'),(8.6,'收餐后','盘点去向 · 核对复盘','chart')]:
 icon(a,x,2.35,kind,r=.38);txt(a,x,3.16,label,17);txt(a,x,1.47,sub,14)
arrow(a,1.85,2.35,4.54,2.35);arrow(a,5.45,2.35,8.13,2.35)
arrow(a,8.6,.65,1.4,.65,col=GRAY);txt(a,5,.35,'完整记录进入下一餐参考',14,MUTED)
for x,s in [(1.4,'负责人确认'),(5,'当班人员回传'),(8.6,'负责人复核')]:txt(a,x,1.0,s,13,MUTED)
save(f,'journey')

f,a=canvas(5.6)
# A branched method diagram, with research outputs visibly separated from operation.
a.add_patch(Rectangle((2.6,3.65),4.8,1.65,facecolor=PALE,edgecolor='none'))
txt(a,3.8,4.88,'需求分位',16,BLUE);txt(a,3.8,4.29,'历史特征与校准',13,MUTED)
txt(a,6.1,4.88,'成本与可行数量',16,BLUE);txt(a,6.1,4.29,'过量 / 不足 / 批次',13,MUTED)
arrow(a,4.65,4.87,5.17,4.87,col=GRAY,style='--')
for x,label,detail,kind in [(1,'经营记录','销量 · 售罄 · 去向','doc'),(3.6,'历史参考','已知日期与条件','chart'),(6.2,'可执行安排','库存 · 产能 · 批量','plate'),(8.8,'人工确认','计划与实际分别留存','check')]:
 icon(a,x,2.1,kind,ORANGE if x>8 else BLUE,r=.32);txt(a,x,2.88,label,16);txt(a,x,1.38,detail,12.5)
for x1,x2 in [(1.38,3.2),(4,5.8),(6.6,8.4)]:arrow(a,x1,2.1,x2,2.1)
arrow(a,1.1,2.52,2.9,4.75,col=GRAY,style='--');arrow(a,6.2,3.85,6.2,3.14,col=GRAY,style='--')
arrow(a,8.8,.64,1,.64,col=GRAY);txt(a,5,.26,'执行回传与复盘',14,MUTED)
save(f,'pipeline')

f,a=canvas(3.7)
txt(a,.05,3.22,'ZHAW',15,ha='left');txt(a,.05,1.95,'FreshRetailNet',15,ha='left');txt(a,.05,.7,'芬兰学校记录',15,ha='left')
start=2.6;total=7.15
for n,label,col in [(25,'训练 25日',BLUE),(10,'调参 10日','#657F93'),(5,'校准\n5日',ORANGE),(20,'测试 20日',INK)]:
 w=total*n/60;a.plot([start,start+w],[3.2,3.2],c=col,lw=5,solid_capstyle='butt');txt(a,start+w/2,2.82,label,12.8);start+=w
a.plot([2.6,7.7],[1.96,1.96],c=BLUE,lw=3);a.plot([8.05,9.75],[1.96,1.96],c=GRAY,lw=3)
txt(a,5.1,1.58,'原训练期内抽样与调参',13.5);txt(a,8.88,1.58,'原评测期',13.5)
a.plot([2.6,9.75],[.7,.7],c=GRAY,lw=2);txt(a,6.1,.3,'155日分项分析；保留缺失',13.5)
save(f,'split','数据集与建模方案_20261109；各行不共用日期尺度')

names={'gbdt':'梯度提升','mean_roll7':'7日均值','same_weekday_median':'同星期中位数','median_roll7':'7日中位数','yesterday':'前一营业日'}
keys=['gbdt','mean_roll7','same_weekday_median','median_roll7','yesterday']
f,a=plt.subplots(figsize=(8.8,3.9));vals=[public['methods'][k]['wape']*100 for k in keys];y=np.arange(5)
a.hlines(y,0,vals,color=LIGHT,lw=2);a.scatter(vals,y,s=95,c=[BLUE]+[GRAY]*4,zorder=3)
for yy,v in zip(y,vals):a.text(v+1,yy,f'{v:.2f}%',va='center',fontsize=14,color=INK)
a.set_yticks(y,[names[k] for k in keys]);a.invert_yaxis();a.set_xlim(0,54);a.set_xlabel('WAPE（%）',labelpad=10);a.set_xticks([0,10,20,30,40,50]);a.grid(axis='x',color=PALE);axes(a);save(f,'wape',str(PUB.relative_to(ROOT)))

policies=[('inertia','惯性备餐',GRAY,'o'),('safety','固定增加10%','#657F93','s'),('model','残差分位',BLUE,'D')]
scenarios=['baseline','rain_shock','campus_event','high_volatility'];slabels=['基线','降雨冲击','校园活动','高波动'];agg={(v['scenario'],v['policy']):v for v in sim['aggregate']}
f,a=plt.subplots(figsize=(8.8,5.2))
for j,(key,name,col,m) in enumerate(policies):
 for i,sc in enumerate(scenarios):
  r=agg[sc,key];yy=i+(j-1)*.22;mean=r['regret_per_100_mean']
  a.plot([r['regret_per_100_p05'],r['regret_per_100_p95']],[yy,yy],c=col,lw=1.6)
  a.scatter([mean],[yy],c=col,marker=m,s=46,label=name if i==0 else None,zorder=3)
  a.text(r['regret_per_100_p95']+2.4,yy,f'{mean:.1f}',fontsize=12.5,va='center',color=INK)
a.set_yticks(np.arange(4),slabels);a.invert_yaxis();a.set_xlim(0,185);a.set_xlabel('额外损失 / 100（原实验归一化口径）',labelpad=10);a.grid(axis='x',color=PALE);a.legend(frameon=False,ncol=3,loc='upper center',bbox_to_anchor=(.5,1.13),fontsize=12.8);axes(a);save(f,'simulation',str(SIM.relative_to(ROOT)))

f,a=plt.subplots(figsize=(8.8,4.7))
for k,name,c,m in policies:
 rows=[v for v in sim['detail'] if v['scenario']=='baseline' and v['policy']==k]
 x=np.array([r['waste_rate']*100 for r in rows]);y=np.array([r['stockout_rate']*100 for r in rows])
 a.scatter(x,y,s=35,facecolor='none',edgecolor=c,marker=m,alpha=.75)
 a.scatter([x.mean()],[y.mean()],s=135,c=c,marker=m,label=name,edgecolor='white',linewidth=.8,zorder=4)
a.set_xlabel('剩余率（%）',labelpad=10);a.set_ylabel('缺货频率（%）',labelpad=10);a.set_xlim(0,6.5);a.set_ylim(0,70);a.grid(c=PALE);a.legend(frameon=False,ncol=3,loc='upper center',bbox_to_anchor=(.5,1.15),fontsize=12.8);axes(a);save(f,'tradeoff',str(SIM.relative_to(ROOT))+'；仅baseline明细，未新增数据')

f,a=canvas(3.8)
icon(a,1.3,1.9,'person',r=.55);icon(a,8.7,1.9,'doc',r=.55);txt(a,1.3,.95,'档口经营者',16);txt(a,8.7,.95,'食刻有数团队',16)
for y,label,direction in [(3.2,'经营记录与人工确认',1),(2.17,'建档 · 备餐参考 · 周期复盘',-1),(1.14,'约定范围的服务费用',1)]:
 if direction==1:arrow(a,2.2,y,7.8,y,col=GRAY if y>3 else BLUE)
 else:arrow(a,7.8,y,2.2,y)
 txt(a,5,y+.25,label,14.5)
save(f,'business')

f,a=canvas(4.1)
for x,label,sub in [(1,'确认准入','范围与责任'),(3.55,'完成建档','单位与记录'),(6.0,'影子运行','核对建议与原计划')]:
 icon(a,x,2.4,'check' if x<4 else 'chart',r=.3);txt(a,x,3.15,label,16);txt(a,x,1.72,sub,13)
for x1,x2 in [(1.36,3.2),(3.9,5.65)]:arrow(a,x1,2.4,x2,2.4)
arrow(a,6.4,2.4,7.1,2.4)
from matplotlib.patches import Polygon
a.add_patch(Polygon([[7.2,2.4],[7.9,3.05],[8.6,2.4],[7.9,1.75]],fill=False,edgecolor=BLUE,lw=1.4));txt(a,7.9,2.4,'可试用？',13.5)
arrow(a,8.65,2.4,9.7,2.4);txt(a,9.35,3.08,'限定试用',14.5);txt(a,9.15,2.66,'是',12,MUTED)
arrow(a,7.9,1.7,7.9,.8,col=ORANGE);txt(a,8.15,1.22,'否',12,MUTED);txt(a,6,.4,'调整记录或服务范围；必要时暂停',13.5,MUTED)
save(f,'delivery')

f,a=plt.subplots(figsize=(8.8,4.1));labels=['营业收入','可变交付','固定费用','营业利润'];bottom=[0,6.75,.25,0];height=[11,4.25,6.5,.25];cols=[BLUE,GRAY,GRAY,ORANGE]
for i,(b,h,c) in enumerate(zip(bottom,height,cols)):
 a.bar(i,h,bottom=b,width=.54,color=c)
 label=['11.00','−4.25','−6.50','0.25'][i];a.text(i,b+h+.25,label,ha='center',fontsize=15,color=INK)
 if i<3:a.plot([i+.28,i+.72],[([11,6.75,.25][i])]*2,c=GRAY,lw=1,ls=':')
a.set_xticks(range(4),labels);a.set_ylabel('万元');a.set_ylim(0,12.5);a.grid(axis='y',color=PALE);axes(a);save(f,'waterfall','规划测算：50×2200−50×850−65000=2500元')

f,a=plt.subplots(figsize=(8.8,3.7));labels=['基准情景','付费档口 −20%','年均价格 −10%','单位交付成本 +20%'];vals=[2500,-11000,-8500,-6000];yy=np.arange(4)
a.hlines(yy,0,vals,color=[BLUE,GRAY,GRAY,GRAY],lw=2);a.scatter(vals,yy,c=[BLUE,GRAY,GRAY,GRAY],s=80,zorder=4)
for y,v in zip(yy,vals):a.text(v,y-.17,f'{v:+,}' if v<0 else f'{v:,}',ha='center',va='center',fontsize=14)
a.set_yticks(yy,labels);a.invert_yaxis();a.axvline(0,c=LIGHT,lw=1);a.set_xlim(-12500,6800);a.set_xlabel('营业利润（元）',labelpad=10);a.grid(axis='x',color=PALE);axes(a);save(f,'sensitivity','规划单因素敏感性；档口40，价格1980，单位成本1020分别计算')

f,a=canvas(4.4)
labels=['研究准备','数据核对','首轮试用','验证复盘','审慎复制'];subs=['分源与基线','单位与授权','记录与操作','效果与成本','付款与交付']
for i,(l,s) in enumerate(zip(labels,subs)):
 y=3.9-i*.82;col=ORANGE if i==4 else BLUE
 a.scatter([.65],[y],s=65,c=col,zorder=3)
 if i<4:a.plot([.65,.65],[y-.1,y-.72],c=LIGHT,lw=1.5)
 txt(a,1.05,y,l,16,ha='left');a.plot([3.1,4.2],[y,y],c=LIGHT,lw=1);txt(a,4.5,y,s,14,ha='left')
txt(a,8.2,3.5,'推进依据',15,BLUE);txt(a,8.2,2.35,'授权\n记录\n效果\n交付',14,MUTED,linespacing=1.7)
save(f,'roadmap')

photos=ROOT/'计划书/计划书照片'
for p in OUT.glob('*.png'):shutil.copy2(p,photos/('20261110_'+p.name))
(HERE/'figure_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
print(len(provenance),'figures')
