from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches,Pt
from docx.oxml.ns import qn
from zipfile import ZipFile,ZIP_DEFLATED
from io import BytesIO
import csv, math,re,json
ROOT=Path(__file__).resolve().parents[2];AS=ROOT/'项目代码/docs/visual_upgrade';AS.mkdir(exist_ok=True)
SRC=ROOT/'计划书/食刻有数_AIC算法创新赛计划书_全面核查修订版.docx';OUT=ROOT/'计划书/食刻有数_AIC算法创新赛计划书_视觉重设计版.docx'
INK='#182e38';BLUE='#126788';TEAL='#287d72';ORANGE='#bd6542';MUTE='#61747b';LIGHT='#eaf2f5';LINE='#cedbe1'
F=lambda n:ImageFont.truetype('C:/Windows/Fonts/simhei.ttf',n)
class C:
 def __init__(self,h):self.im=Image.new('RGB',(2400,h),'white');self.d=ImageDraw.Draw(self.im)
 def txt(self,x,y,t,n=48,col=INK,anchor='mm'):
  lines=t.split('\n');height=len(lines)*(n+14)-14
  for i,line in enumerate(lines):self.d.text((x,y-height/2+i*(n+14)),line,font=F(n),fill=col,anchor='mt' if anchor=='mm' else 'lt')
 def line(self,pts,col=LINE,w=5):self.d.line(pts,fill=col,width=w,joint='curve')
 def arrow(self,a,b,col=BLUE,w=6):
  self.line([a,b],col,w);ang=math.atan2(b[1]-a[1],b[0]-a[0]);self.d.polygon([b,(b[0]-26*math.cos(ang-.45),b[1]-26*math.sin(ang-.45)),(b[0]-26*math.cos(ang+.45),b[1]-26*math.sin(ang+.45))],fill=col)
 def card(self,x,y,w,h,title,sub='',accent=False):
  self.d.rounded_rectangle((x,y,x+w,y+h),radius=22,fill=BLUE if accent else LIGHT)
  self.txt(x+w/2,y+(h*.4 if sub else h/2),title,50,'white' if accent else INK)
  if sub:self.txt(x+w/2,y+h*.75,sub,37,'#dcebf0' if accent else MUTE)
 def icon(self,x,y,kind,col=BLUE):
  d=self.d
  if kind=='data':
   d.rounded_rectangle((x-45,y-55,x+45,y+55),radius=8,outline=col,width=5)
   for yy in [y-25,y,y+25]:d.line((x-25,yy,x+25,yy),fill=col,width=5)
  elif kind=='pot':
   d.arc((x-60,y-35,x+60,y+55),0,180,fill=col,width=6);d.line((x-60,y+10,x+60,y+10),fill=col,width=6);d.line((x-65,y-7,x+65,y-7),fill=col,width=6);d.arc((x-35,y-35,x+35,y+10),180,360,fill=col,width=5)
  elif kind=='check':
   d.ellipse((x-48,y-48,x+48,y+48),outline=col,width=5);d.line((x-26,y,x-4,y+22,x+30,y-22),fill=col,width=7)
  elif kind=='person':
   d.ellipse((x-20,y-47,x+20,y-7),outline=col,width=5);d.arc((x-45,y-2,x+45,y+65),180,360,fill=col,width=6)
  else:
   for k,v in enumerate([35,65,90]):d.rectangle((x-50+k*35,y+45-v,x-30+k*35,y+45),fill=col)
 def save(self,name):self.im.save(AS/name,dpi=(360,360));return name
names=[]
# 1: operational timeline with visible phases, not tiny boxes.
c=C(660);c.line([(180,310),(2210,310)],LINE,12)
for i,(t,sub,icon) in enumerate([('首批备餐','历史与校历','pot'),('需求校准','实际客流','chart'),('分批补餐','制作周期','pot'),('停止制作','截止时点','check'),('剩余处置','安全确认','check')]):
 x=200+i*500;c.d.ellipse((x-62,248,x+62,372),fill=BLUE if i<3 else TEAL);c.txt(x,310,str(i+1),55,'white');c.icon(x,120,icon);c.txt(x,445,t,53);c.txt(x,535,sub,40,MUTE)
names.append(c.save('image4.png'))
# 2: trial duration separate from actions.
c=C(600)
for i,(t,s) in enumerate([('基线记录','5—7天'),('策略运行','7—14天'),('收益复核','同口径比较'),('继续或退出','收益与负担')]):
 x=80+i*590;c.card(x,180,500,240,t,s,accent=i==2);c.txt(x+250,90,f'0{i+1}',72,BLUE); 
 if i<3:c.arrow((x+520,300),(x+568,300))
names.append(c.save('image30.png'))
# 3: model and agent architecture, own lanes and clear roles.
c=C(960);c.card(70,350,400,210,'经营台账','天气与校历')
c.card(620,125,480,185,'演示模型','派生目标');c.card(620,565,480,185,'确定性规则','基线与边界');c.card(1270,350,430,210,'结构化结果','统一数值口径',True)
c.card(1860,125,450,185,'智能体','解释与提示');c.card(1860,565,450,185,'档口负责人','最终确认',True)
for a,b in [((470,455),(620,217)),((470,455),(620,657)),((1100,217),(1270,455)),((1100,657),(1270,455)),((1700,455),(1860,217)),((1700,455),(1860,657)),((2085,310),(2085,560))]:c.arrow(a,b)
# Keep the return path below the nodes; place its label above the line so it does not merge with the arrow.
c.line([(2085,760),(2085,865),(270,865),(270,580)],TEAL,5);c.arrow((270,580),(270,560),TEAL);c.txt(1180,825,'采纳与经营记录回传',38,TEAL)
names.append(c.save('image53.png'))
# 4: actors, paying relationship and permissions; no invented percentages.
c=C(740);c.card(845,260,700,230,'经营减损服务','记录 · 建议 · 复盘',True)
for x,y,t,s,k in [(60,90,'档口经营者','付费与经营确认','pot'),(60,460,'食堂运营方','准入与授权管理','person'),(1790,275,'学生','预约与核销','person')]:
 c.card(x,y,550,180,t,s);c.icon(x+275,y-45,k)
 if x<800:c.arrow((x+555,y+90),(835,375))
 else:c.arrow((1555,375),(1780,y+90))
names.append(c.save('image31.png'))
# 5: renewal decision readable vertical branches.
c=C(830);c.card(60,300,440,190,'触达与诊断');c.arrow((510,395),(620,395));c.card(630,300,470,190,'试用与复核');c.arrow((1110,395),(1220,395));
c.d.polygon([(1420,220),(1620,395),(1420,570),(1220,395)],fill=LIGHT);c.txt(1420,395,'收益与负担\n是否适配？',46)
for y,t,col in [(70,'订阅服务',BLUE),(310,'调整再评估',TEAL),(550,'退出服务',MUTE)]:
 c.line([(1620,395),(1720,395),(1720,y+95),(1800,y+95)],col,5);c.card(1810,y,500,190,t);c.txt(1745,y+55,['是','调整','否'][[70,310,550].index(y)],34,col)
names.append(c.save('image35.png'))
# 6: operational ring with icons and curved circulation.
c=C(1100);cx,cy=1200,540;pts=[]
for i,t in enumerate(['经营记录','需求判断','现场执行','限时处置','周期复盘']):
 a=-math.pi/2+i*2*math.pi/5;x=cx+760*math.cos(a);y=cy+365*math.sin(a);pts.append((x,y));c.d.ellipse((x-170,y-100,x+170,y+100),fill=LIGHT);c.icon(x,y-58,['data','chart','pot','check','chart'][i]);c.txt(x,y+43,t,49)
for i,a in enumerate(pts):
 b=pts[(i+1)%5];vx,vy=b[0]-a[0],b[1]-a[1];L=math.hypot(vx,vy);c.arrow((a[0]+vx*180/L,a[1]+vy*125/L),(b[0]-vx*180/L,b[1]-vy*125/L),TEAL)
c.d.ellipse((1010,400,1390,680),fill=BLUE);c.txt(1200,540,'档口确认',59,'white')
names.append(c.save('image16.png'))
# 7: decision gate = one necessary question, preserve exception.
c=C(820);c.card(70,290,420,190,'预计剩余');c.arrow((500,385),(670,385));c.d.polygon([(920,180),(1170,385),(920,590),(670,385)],fill=LIGHT);c.txt(920,385,'安全与经营\n条件满足？',51)
c.arrow((1180,385),(1360,385),TEAL);c.txt(1270,335,'是',38,TEAL);c.card(1370,275,920,220,'限时发布 → 核销 → 下架','负责人确认',True)
c.arrow((920,595),(920,670),ORANGE);c.txt(980,635,'否',38,ORANGE);c.card(630,680,580,120,'停止发布并记录')
names.append(c.save('image18.png'))
# Dataset exact daily values.
rows=list(csv.DictReader((ROOT/'项目代码/src/main/resources/data/foodwise_operations_14d.csv').open(encoding='utf-8-sig')))
dates=sorted({r['business_date'] for r in rows});daily=[]
for dt in dates:daily.append([sum(int(r[k]) for r in rows if r['business_date']==dt) for k in ['prepared_qty','sold_qty','leftover_qty']])
c=C(870);x0,x1,y0,y1=200,2250,130,680
for v in range(0,501,100):
 y=y1-v/500*(y1-y0);c.line([(x0,y),(x1,y)],LINE,2);c.txt(120,y,str(v),35,MUTE)
c.txt(100,60,'份',36,MUTE)
for j in range(2):
 pts=[(x0+i*(x1-x0)/13,y1-v[j]/500*(y1-y0)) for i,v in enumerate(daily)];c.line(pts,[BLUE,TEAL][j],7)
 for x,y in pts:c.d.ellipse((x-8,y-8,x+8,y+8),fill=[BLUE,TEAL][j])
for i,vs in enumerate(daily):
 x=x0+i*(x1-x0)/13;y=y1-vs[2]/500*(y1-y0);c.d.rectangle((x-23,y,x+23,y1),fill=ORANGE)
 if i%2==0 or i==13:c.txt(x,730,dates[i][5:],34,MUTE)
for x,t,col in [(700,'备餐量',BLUE),(1200,'售出量',TEAL),(1700,'剩余量',ORANGE)]:c.line([(x-120,70),(x-60,70)],col,8);c.txt(x+35,70,t,40)
names.append(c.save('image27.png'))
# comparable category pairs, compact paired horizontal bars with exact labels.
c=C(950);c.txt(610,65,'基线期',44,BLUE);c.txt(1510,65,'策略期',44,ORANGE)
for i,(label,a,b) in enumerate([('备餐量',2847,2643),('售出量',2473,2501),('剩余量',374,142)]):
 y=230+i*270;c.txt(180,y+40,label,50)
 for j,(v,col) in enumerate([(a,BLUE),(b,ORANGE)]):
  yy=y+j*90;c.d.rounded_rectangle((400,yy,400+v/3000*1650,yy+52),radius=7,fill=col);c.txt(460+v/3000*1650,yy+26,str(v),43,col)
c.txt(2220,870,'份',36,MUTE);names.append(c.save('image54.png'))
# Full-width common quantitative chart, each independent metric clearly named.
c=C(930)
for i,(label,a,b,mx) in enumerate([('剩余率',13.136635054,5.372682558,16),('售罄率',86.86336495,94.62731744,100),('MAPE',7.670803478,3.269500375,10)]):
 y=125+i*270;c.txt(210,y+65,label,53)
 for tick in range(5):
  x=540+tick*390;c.line([(x,y-20),(x,y+160)],LINE,2);c.txt(x,y+195,f'{mx*tick/4:g}%',31,MUTE)
 for j,(v,col) in enumerate([(a,BLUE),(b,ORANGE)]):
  yy=y+j*100;xx=540+v/mx*1560;c.line([(540,yy),(xx,yy)],col,14);c.d.ellipse((xx-18,yy-18,xx+18,yy+18),fill=col);c.txt(xx+80,yy,f'{v:.1f}%',42,col)
 for x,t,col in [(880,'基线期',BLUE),(1440,'策略期',ORANGE)]:
  if i==0:c.line([(x-140,35),(x-70,35)],col,10);c.txt(x+20,35,t,39)
names.append(c.save('image55.png'))
# truthful financial bars, tabular values are preserved.
c=C(930)
for v in [-5,0,10,20,30,40]:
 y=740-(v+5)/45*590;c.line([(200,y),(2260,y)],LINE,3 if v else 6);c.txt(115,y,str(v),35,MUTE)
c.txt(110,70,'万元',36,MUTE)
for i,(income,profit) in enumerate([(1.8,-1.4),(11,.25),(35,9.2)]):
 x=560+i*700
 for j,(v,col) in enumerate([(income,BLUE),(profit,ORANGE)]):
  xx=x+j*180;y=740-(v+5)/45*590;zero=740-5/45*590;c.d.rectangle((xx,min(y,zero),xx+125,max(y,zero)),fill=col);c.txt(xx+62,y+(-35 if v>=0 else 45),str(v),44,col)
 c.txt(x+150,845,f'第{i+1}年',46)
for x,t,col in [(1000,'营业收入',BLUE),(1650,'营业利润',ORANGE)]:c.d.rectangle((x-170,53,x-110,90),fill=col);c.txt(x,72,t,43)
names.append(c.save('image38.png'))
# qualitative risk matrix with numbered points and a native body explanation.
c=C(1050);x0,y0,cell=340,120,150
for x in range(5):
 for y in range(5):
  score=(x+1)*(5-y);col='#f1e2d6' if score>=16 else '#e8eff1';c.d.rectangle((x0+x*cell,y0+y*cell,x0+(x+1)*cell,y0+(y+1)*cell),fill=col,outline='white',width=4)
for k,(name,x,y) in enumerate([('食品安全',2,5),('付费验证',4,5),('数据授权',3,4),('交付成本',4,4),('续费',3,3),('预测偏差',3,2)],1):
 xx=x0+(x-.5)*cell;yy=y0+(5-y+.5)*cell;c.d.ellipse((xx-32,yy-32,xx+32,yy+32),fill=BLUE);c.txt(xx,yy,str(k),37,'white');c.d.ellipse((1410-32,180+(k-1)*120-32,1410+32,180+(k-1)*120+32),fill=BLUE);c.txt(1410,180+(k-1)*120,str(k),37,'white');c.txt(1720,180+(k-1)*120,name,48)
for i in range(5):c.txt(x0+(i+.5)*cell,920,str(i+1),36,MUTE);c.txt(260,y0+(i+.5)*cell,str(5-i),36,MUTE)
c.txt(700,1000,'发生可能性（定性等级）',38);c.txt(480,55,'影响程度（定性等级）',36)
names.append(c.save('image43.png'))
# Replace figure payloads, delete only diagrams redundant with tables / prose.
doc=Document(SRC);removed={'image3.png','image6.png','image15.png','image17.png','image19.png','image44.png','image46.png'}
for q in list(doc.paragraphs):
 bs=q._p.xpath('.//*[local-name()="blip"]')
 if not bs:continue
 name=Path(doc.part.rels[bs[0].get(qn('r:embed'))].target_ref).name
 if name in removed:
  nxt=q._p.getnext()
  if nxt is not None and re.match(r'^图\d+-\d+',''.join(nxt.xpath('.//w:t/text()'))):nxt.getparent().remove(nxt)
  q._p.getparent().remove(q._p)
 elif name in names:
  im=Image.open(AS/name);cx=int(6.05*914400);cy=int(cx*im.height/im.width)
  for el in q._p.xpath('.//*[local-name()="extent" or local-name()="ext"]'):
   if el.get('cx'):el.set('cx',str(cx));el.set('cy',str(cy))
  q.paragraph_format.space_before=Pt(8);q.paragraph_format.space_after=Pt(2);q.paragraph_format.keep_with_next=True
counts={};mapping={}
for q in doc.paragraphs:
 m=re.match(r'^图(\d+)-(\d+)\s+(.*)',q.text)
 if m:
  ch,old,title=m.groups();counts[ch]=counts.get(ch,0)+1;new=f'图{ch}-{counts[ch]}';mapping[f'图{ch}-{old}']=new;q.text=new+' '+title.replace('学院[9]','学院[8]')
  for r in q.runs:r.font.name='SimHei';r.font.size=Pt(9);r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'SimHei')
for q in doc.paragraphs:
 if re.match(r'^图\d+-\d+',q.text):continue
 s=re.sub(r'图\s*(\d+-\d+)',lambda m:mapping.get('图'+m[1],m[0]),q.text)
 if s!=q.text:q.text=s
for q in doc.paragraphs:
 if q.text.startswith('图中档口数为市场测算假设'):
  q.text='表6-1中的档口数为市场测算假设，并非已服务客户；长期市场空间不计入已实现收入。'
# Explain differential scales below graph, never in an image banner.
for q in doc.paragraphs:
 if q.text.startswith('图5-2'):
  nxt=q._p.getnext()
  if nxt is not None:
   from docx.text.paragraph import Paragraph
   p=Paragraph(nxt,q._parent);p.text=p.text+' 三项指标采用独立且从零起始的刻度；仅在同一指标内比较两阶段，不跨指标比较图形长度。'
doc.save(OUT)
with ZipFile(OUT) as z:data={n:z.read(n) for n in z.namelist()}
for name in names:data['word/media/'+name]=(AS/name).read_bytes()
with ZipFile(OUT,'w',ZIP_DEFLATED) as z:
 for n,b in data.items():z.writestr(n,b)
(AS/'design-log.json').write_text(json.dumps({'redrawn':names,'removed':sorted(removed),'source':str(SRC),'output':str(OUT)},ensure_ascii=False,indent=2),encoding='utf-8')
print(OUT)
