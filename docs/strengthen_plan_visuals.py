from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from docx import Document
from docx.oxml.ns import qn
from zipfile import ZipFile,ZIP_DEFLATED
import runpy,math,json,re

ROOT=Path(__file__).resolve().parents[2]
ns=runpy.run_path(str(Path(__file__).with_name('upgrade_plan_visuals.py')))
C=ns['C']; old=ns['AS']; AS=old/'strong';AS.mkdir(exist_ok=True)
INK='#122f3c';BLUE='#095978';TEAL='#147e78';ORANGE='#c7653e';MUTE='#586c76';LIGHT='#edf3f5';LINE='#d3e0e5'
F=ns['F']; names=[]
def save(c,n):
 c.im.save(AS/n,dpi=(360,360));names.append(n)
def label(c,x,y,t,n=46,col=INK):c.txt(x,y,t,n,col)
def badge(c,x,y,num,col=BLUE):
 c.d.ellipse((x-49,y-49,x+49,y+49),fill=col);label(c,x,y,str(num),45,'white')
def icon(c,x,y,k,col=BLUE):
 c.d.ellipse((x-96,y-96,x+96,y+96),fill=LIGHT);c.icon(x,y,k,col)

# A continuous operational ribbon with a clear visual rhythm.
c=C(760)
items=[('首批备餐','pot'),('需求校准','chart'),('分批补餐','pot'),('停止制作','check'),('剩余处置','check')]
for i,(t,k) in enumerate(items):
 x=240+i*480; col=BLUE if i<3 else TEAL
 icon(c,x,175,k,col)
 if i<4:c.arrow((x+125,175),(x+355,175),LINE,8)
 c.d.rounded_rectangle((x-200,350,x+200,495),radius=12,fill=col)
 label(c,x,422,t,55,'white');badge(c,x,350,i+1,col)
 label(c,x,605,['历史与校历','实际客流','制作周期','截止时点','安全确认'][i],43,MUTE)
save(c,'image4.png')

# Paid roles are spatially different from the delivery relationship.
c=C(820)
for x,y,t,k,col in [(290,215,'档口经营者','pot',BLUE),(290,620,'食堂运营方','person',TEAL),(2090,410,'学生','person',BLUE)]:
 icon(c,x,y-45,k,col);label(c,x,y+105,t,56,col)
c.d.rounded_rectangle((840,235,1570,585),radius=30,fill=BLUE)
label(c,1205,360,'经营减损服务',70,'white');label(c,1205,470,'记录 · 建议 · 复盘',43,'#d7e9f0')
for a,b,t,x,y,col in [((440,230),(820,345),'付费与确认',630,200,BLUE),((440,595),(820,490),'准入与授权',620,635,TEAL),((1590,410),(1910,410),'预约与核销',1750,335,BLUE)]:
 c.arrow(a,b,col,8);label(c,x,y,t,41,col)
save(c,'image31.png')

# A disciplined two-stage quantitative comparison with direct values and difference.
c=C(1060)
for x,t,col in [(680,'基线期',BLUE),(1210,'策略期',TEAL)]:
 c.d.rectangle((x-155,50,x-95,83),fill=col);label(c,x+25,67,t,44)
for i,(t,a,b) in enumerate([('备餐量',2847,2643),('售出量',2473,2501),('剩余量',374,142)]):
 y=225+i*285
 label(c,205,y+45,t,57);c.line([(410,y+165),(2120,y+165)],LINE,3)
 for j,(v,col) in enumerate([(a,BLUE),(b,TEAL)]):
  yy=y+j*85;xx=430+v/3000*1570
  c.d.rounded_rectangle((430,yy,xx,yy+48),radius=5,fill=col);label(c,xx+85,yy+23,str(v),49,col)
label(c,2210,997,'单位：份',36,MUTE);save(c,'image54.png')

# A single common 0–100% scale, avoiding misleading independent lengths.
c=C(1140)
for x,t,col in [(740,'基线期',BLUE),(1330,'策略期',TEAL)]:
 c.d.ellipse((x-150,40,x-120,70),fill=col);label(c,x,57,t,45)
for i,(t,a,b) in enumerate([('剩余率',13.136635054,5.372682558),('售罄率',86.86336495,94.62731744),('MAPE',7.670803478,3.269500375)]):
 y=215+i*300;label(c,220,y+45,t,59)
 for tick in [0,25,50,75,100]:
  x=500+tick/100*1550;c.line([(x,y-35),(x,y+155)],LINE,2)
  if i==2:label(c,x,y+207,f'{tick}%',33,MUTE)
 for j,(v,col) in enumerate([(a,BLUE),(b,TEAL)]):
  yy=y+j*95;xx=500+v/100*1550;c.line([(500,yy),(xx,yy)],col,14);c.d.ellipse((xx-15,yy-15,xx+15,yy+15),fill=col)
  label(c,xx+87,yy,f'{v:.1f}%',49,col)
label(c,2210,1055,'0—100%',35,MUTE);save(c,'image55.png')

# Financial scenario uses confident typography and a conspicuous zero baseline.
c=C(1040);x0,x1=240,2260;zero=810;scale=16
for v in [0,10,20,30,40]:
 y=zero-v*scale;c.line([(x0,y),(x1,y)],LINE,3 if v else 6);label(c,140,y,str(v),38,MUTE)
label(c,140,65,'万元',39,MUTE)
for i,(a,b) in enumerate([(1.8,-1.4),(11,.25),(35,9.2)]):
 x=570+i*690
 for j,(v,col) in enumerate([(a,BLUE),(b,ORANGE)]):
  xx=x+j*175;y=zero-v*scale;c.d.rectangle((xx,min(y,zero),xx+135,max(y,zero)),fill=col)
  label(c,xx+67,y+(-40 if v>=0 else 44),str(v),51,col)
 label(c,x+150,945,f'第{i+1}年',49)
for x,t,col in [(930,'营业收入',BLUE),(1590,'营业利润',ORANGE)]:
 c.d.rectangle((x-200,55,x-145,94),fill=col);label(c,x,75,t,46)
save(c,'image38.png')

# Replace generated circle only after inspection; deterministic fallback stays available.
gen=old/'strong_loop_generated.png'
if gen.exists():
 im=Image.open(gen).convert('RGB');im.save(AS/'image16.png',dpi=(360,360));names.append('image16.png')

src=ROOT/'计划书/食刻有数_AIC算法创新赛计划书_视觉重设计版.docx'
out=ROOT/'计划书/食刻有数_AIC算法创新赛计划书_视觉强化版.docx'
d=Document(src)
for p in d.paragraphs:
 bs=p._p.xpath('.//*[local-name()="blip"]')
 if bs:
  name=Path(d.part.rels[bs[0].get(qn('r:embed'))].target_ref).name
  if name in names:
   im=Image.open(AS/name);cx=int(6.05*914400);cy=int(cx*im.height/im.width)
   for el in p._p.xpath('.//*[local-name()="extent" or local-name()="ext"]'):
    if el.get('cx'):el.set('cx',str(cx));el.set('cy',str(cy))
 if '三项指标采用独立且从零起始的刻度' in p.text:
  p.text=p.text.replace('三项指标采用独立且从零起始的刻度；仅在同一指标内比较两阶段，不跨指标比较图形长度。','三项指标统一采用0—100%的刻度，各指标分别比较两阶段；售罄率与剩余率互为补充，MAPE表示模拟台账的预测误差。')
d.save(out)
with ZipFile(out) as z:data={n:z.read(n) for n in z.namelist()}
for n in names:data['word/media/'+n]=(AS/n).read_bytes()
with ZipFile(out,'w',ZIP_DEFLATED) as z:
 for n,b in data.items():z.writestr(n,b)
print(out)
(AS/'manifest.json').write_text(json.dumps({'changed':names},ensure_ascii=False,indent=2),encoding='utf-8')
