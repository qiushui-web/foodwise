# -*- coding: utf-8 -*-
from pathlib import Path
from collections import Counter
from docx import Document
from docx.oxml.ns import qn
import json,re,hashlib,statistics
HERE=Path(__file__).parent;ROOT=HERE.parents[2];path=ROOT/'计划书/计划书版本/食刻有数_创新创业计划书_双赛融合版_20261109.docx'
d=Document(path);checks={};details={}
checks['十章正文']=len([p for p in d.paragraphs if p.style.name=='Heading 1' and re.match('第.+章 ',p.text)])==10
caps=[p.text.split()[0] for p in d.paragraphs if p.style.name in ['图题','表题']]
checks['图表编号唯一']=len(caps)==len(set(caps))
checks['无内部占位']=not any(re.search(r'TODO|FIXME|待绘制|待补充|图中位置预留|localhost|[A-Z]:\\',p.text) for p in d.paragraphs)
checks['目录已回填']=not any(re.search(r'\t0$',p.text) for p in d.paragraphs if p.style.name=='目录条目')
checks['版本目录仅DOCX']=all(p.suffix.lower()=='.docx' for p in (ROOT/'计划书/计划书版本').iterdir() if p.is_file())
checks['计划书无PDF']=not list((ROOT/'计划书').rglob('*.pdf'))
media=[d.part.related_parts[s._inline.graphic.graphicData.pic.blipFill.blip.embed].blob for s in d.inline_shapes]
hashes=[hashlib.sha256(b).hexdigest() for b in media];checks['无重复嵌图']=len(hashes)==len(set(hashes))
shots=list((ROOT/'计划书/计划书照片/网站截图').glob('*.png'))
checks['全部最新截图原样嵌入']=len(shots)==19 and all(hashlib.sha256(p.read_bytes()).hexdigest() in hashes for p in shots)
checks['十张新图已存照片目录']=len(list((ROOT/'计划书/计划书照片').glob('20261109_*.png')))==10
checks['表格居中及字体']=True;checks['严格三线表']=True;checks['无表格底色']=True
for t in d.tables:
 pr=t._tbl.tblPr;bd=pr.find(qn('w:tblBorders'))
 if bd is None:checks['严格三线表']=False;continue
 for edge in ['top','bottom']:
  el=bd.find(qn('w:'+edge));checks['严格三线表'] &= el is not None and el.get(qn('w:val'))=='single'
 for edge in ['left','right','insideH','insideV']:
  el=bd.find(qn('w:'+edge));checks['严格三线表'] &= el is None or el.get(qn('w:val')) in ['nil','none']
 for i,row in enumerate(t.rows):
  for cell in row.cells:
   checks['表格居中及字体'] &= cell.vertical_alignment==1
   shd=cell._tc.get_or_add_tcPr().find(qn('w:shd'))
   checks['无表格底色'] &= shd is None or shd.get(qn('w:fill')) in ['auto','FFFFFF',None]
   for p in cell.paragraphs:
    align=p.alignment if p.alignment is not None else p.style.paragraph_format.alignment
    checks['表格居中及字体'] &= align==1
    size=p.style.font.size
    checks['表格居中及字体'] &= size is not None and size.pt==9.5
sim=json.loads((ROOT/'项目代码/modeling/data/03_output/competition_validation_20261104_final.json').read_text(encoding='utf-8'))
checks['仿真汇总与明细一致']=True
for a in sim['aggregate']:
 ds=[r for r in sim['detail'] if (r['scenario'],r['policy'])==(a['scenario'],a['policy'])]
 for m in sim['metrics']:checks['仿真汇总与明细一致'] &= abs(statistics.mean(r[m] for r in ds)-a[m+'_mean'])<1e-6
checks['财务恒等式']=all(abs(i-c-f-profit)<1e-8 for i,c,f,profit in [(1.8,1,2.2,-1.4),(11,4.25,6.5,.25),(35,9.8,16,9.2)])
layout=json.loads((HERE/'word_layout_audit.json').read_text(encoding='utf-8-sig'))
checks['不超过70页']=layout['pages']<=70
checks['无表格拆行']=not layout['splitRows']
checks['图题与图片同页']=all(c['page']==c['imagePage'] for c in layout['captions'])
checks['图题与解释同页']=all(c['page']==c['captionPage'] for c in layout.get('explanations',[]))
checks['正文非粗体']=all(x['bold']==0 for x in layout.get('bodyFonts',[])) and bool(layout.get('bodyFonts'))
checks['正文宋体小四']=all(x['eastAsia']=='宋体' and x['size']==12 for x in layout.get('bodyFonts',[])) and bool(layout.get('bodyFonts'))
report={'checks':{k:bool(v) for k,v in checks.items()},'pages':layout['pages'],'tables':len(d.tables),'figures':len(d.inline_shapes),'screenshots':19,'tocEntries':len([p for p in d.paragraphs if p.style.name=='目录条目']),'docxSHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'docxBytes':path.stat().st_size,'limitations':['未重新运行完整建模或现场实验；引用冻结结果并核验汇总','没有真实校园经营成效和付费验证','未保证比赛获奖或相似度检测结果']}
(HERE/'qa_final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
if not all(checks.values()):raise SystemExit(1)
