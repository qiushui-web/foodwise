from pathlib import Path
from docx import Document
from collections import Counter
import json,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(r'E:/食刻有数'); out=root/'项目代码/docs/plan_20261109'
p=root/'计划书/计划书pro10.docx'; d=Document(p)
lines=[]
for s in d.sections:
 lines.append('SECTION '+str({k:round(getattr(s,k).cm,3) if getattr(s,k) is not None else None for k in ['page_width','page_height','top_margin','bottom_margin','left_margin','right_margin','header_distance','footer_distance']}))
for name,n in Counter(p.style.name for p in d.paragraphs).most_common(15):
 st=d.styles[name]; f=st.font; pf=st.paragraph_format
 lines.append(str((name,n,f.name,f.size.pt if f.size else None,pf.line_spacing,pf.space_before,pf.space_after,pf.first_line_indent,pf.alignment)))
 samples=[p for p in d.paragraphs if p.style.name==name and p.text.strip()][:3]
 for p in samples:
  lines.append(str({'text':p.text[:110],'ppr':str(p._p.pPr.xml if p._p.pPr is not None else ''),'runs':[(r.text[:25],r.font.name,r.font.size.pt if r.font.size else None,r._r.xml.split('<w:t')[0][-700:]) for r in p.runs[:2]]}))
for s in d.sections[:2]:
 for label,part in [('header',s.header),('footer',s.footer)]:
  lines.append(label+': '+str([(p.text,p._p.xml[:2000]) for p in part.paragraphs]))
lines.append('TABLES '+str(len(d.tables)))
for t in d.tables[:2]:lines.append(t._tbl.xml[:5000])
(out/'pro10_style_audit.txt').write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines[:12]))
sys.path.insert(0,str(root/'项目代码/docs/plan_v3_20261027'))
import content_1,content_2,content_3
(out/'existing_blocks.json').write_text(json.dumps(content_1.BLOCKS+content_2.BLOCKS+content_3.BLOCKS,ensure_ascii=False,indent=1),encoding='utf-8')
for name in ['食刻有数_商业计划书_扩充修订版.docx','食刻有数_商业计划书_70页参赛版.docx','食刻有数_AIC算法创新赛计划书_内容充实与视觉统一版.docx']:
 paths=list((root/'计划书/历史资料').rglob(name))
 if paths:
  x=Document(paths[0]); text='\n'.join(p.text for p in x.paragraphs if p.text.strip())
  (out/(name+'.txt')).write_text(text,encoding='utf-8');print(name,len(text),len(x.tables),len(x.inline_shapes))
