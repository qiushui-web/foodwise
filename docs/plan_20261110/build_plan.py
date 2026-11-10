# -*- coding: utf-8 -*-
from pathlib import Path
import sys,json,shutil
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image
HERE=Path(__file__).parent.resolve();ROOT=HERE.parents[2]
import content
BLOCKS=content.BLOCKS
OUT=ROOT/'计划书/计划书版本/食刻有数_创新创业计划书_图文重设计版_20261110.docx'
PHOTOS=ROOT/'计划书/计划书照片';SHOTS=PHOTOS/'网站截图'
FONT='Times New Roman'
def fonts(owner,cn='宋体',size=12,bold=False):
 owner.font.name=FONT;owner.font.size=Pt(size);owner.font.bold=bold;owner.font.color.rgb=RGBColor(0,0,0)
 rpr=owner.element.get_or_add_rPr();rf=rpr.find(qn('w:rFonts'))
 if rf is None:rf=OxmlElement('w:rFonts');rpr.insert(0,rf)
 for k,v in [('ascii',FONT),('hAnsi',FONT),('eastAsia',cn),('cs',FONT)]:rf.set(qn('w:'+k),v)
 for k in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme']:
  rf.attrib.pop(qn('w:'+k),None)
def style(d,name,cn,size,bold,line,before,after,align,indent=0,keep=False):
 s=d.styles[name] if name in d.styles else d.styles.add_style(name,1)
 fonts(s,cn,size,bold);f=s.paragraph_format;f.line_spacing=line;f.space_before=Pt(before);f.space_after=Pt(after);f.alignment=align;f.first_line_indent=Pt(indent);f.keep_with_next=keep;f.widow_control=True
 return s
def setup(s):
 s.page_width=Cm(21);s.page_height=Cm(29.7);s.top_margin=Cm(2.5);s.bottom_margin=Cm(2.3);s.left_margin=Cm(2.7);s.right_margin=Cm(2.4);s.header_distance=Cm(1.2);s.footer_distance=Cm(1.2)
def field(p,instr):
 f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),instr);r=OxmlElement('w:r');rp=OxmlElement('w:rPr');rf=OxmlElement('w:rFonts')
 for k,v in [('ascii',FONT),('hAnsi',FONT),('eastAsia','宋体')]:rf.set(qn('w:'+k),v)
 rp.append(rf);sz=OxmlElement('w:sz');sz.set(qn('w:val'),'18');rp.append(sz);r.append(rp);t=OxmlElement('w:t');t.text='1';r.append(t);f.append(r);p._p.append(f)

def headerfooter(s):
 s.header.is_linked_to_previous=False;s.footer.is_linked_to_previous=False
 hp=s.header.paragraphs[0];hp.alignment=WD_ALIGN_PARAGRAPH.CENTER
 hp.paragraph_format.first_line_indent=Pt(0);hp.paragraph_format.space_before=Pt(0);hp.paragraph_format.space_after=Pt(6);hp.paragraph_format.line_spacing=1
 fonts(hp.add_run('食刻有数—高校食堂精细化经营与食品减损平台'),size=9)
 borders=OxmlElement('w:pBdr');b=OxmlElement('w:bottom')
 for k,v in [('val','single'),('sz','6'),('color','8B8B8B'),('space','2')]:b.set(qn('w:'+k),v)
 borders.append(b);hp._p.get_or_add_pPr().append(borders)
 fp=s.footer.paragraphs[0];fp.alignment=WD_ALIGN_PARAGRAPH.CENTER
 fp.paragraph_format.first_line_indent=Pt(0);fp.paragraph_format.space_before=Pt(0);fp.paragraph_format.space_after=Pt(0);fp.paragraph_format.line_spacing=1
 for t in ['第 ']:fonts(fp.add_run(t),size=9)
 field(fp,'PAGE');fonts(fp.add_run(' 页 共 '),size=9);field(fp,'SECTIONPAGES');fonts(fp.add_run(' 页'),size=9)

def p(d,text,sty='正文'):return d.add_paragraph(text,style=sty)
def keep(p):p.paragraph_format.keep_with_next=True

def make_table(d,b):
 _,no,title,rows,note=b;p(d,f'{no}  {title}','表题');t=d.add_table(rows=0,cols=len(rows[0]));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
 widths=[15.9/len(rows[0])]*len(rows[0])
 if len(widths)==3:widths=[3.0,5.0,7.9]
 if len(widths)==4:widths=[3.7,4.1,4.1,4.0]
 if no in ['表5-2','表5-3','表9-1','表9-2']:widths=[15.9/len(rows[0])]*len(rows[0])
 for col,w in zip(t.columns,widths):col.width=Cm(w)
 pr=t._tbl.tblPr
 tw=pr.find(qn('w:tblW'));tw.set(qn('w:w'),str(int(Cm(15.9).twips)));tw.set(qn('w:type'),'dxa')
 borders=OxmlElement('w:tblBorders')
 for k in ['top','bottom','left','right','insideH','insideV']:
  e=OxmlElement('w:'+k);e.set(qn('w:val'),'single' if k in ['top','bottom'] else 'nil');e.set(qn('w:sz'),'12' if k in ['top','bottom'] else '0');e.set(qn('w:color'),'000000');borders.append(e)
 pr.append(borders);mar=OxmlElement('w:tblCellMar')
 for k,v in [('top',70),('bottom',70),('left',90),('right',90)]:
  el=OxmlElement('w:'+k);el.set(qn('w:w'),str(v));el.set(qn('w:type'),'dxa');mar.append(el)
 pr.append(mar)
 for i,row in enumerate(rows):
  r=t.add_row();trpr=r._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
  if i==0:trpr.append(OxmlElement('w:tblHeader'))
  for cell,text,w in zip(r.cells,row,widths):
   cell.width=Cm(w);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;pa=cell.paragraphs[0];pa.style=d.styles['表头' if i==0 else '表文'];pa.add_run(str(text));pa.paragraph_format.keep_with_next=(len(rows)<=5 and i<len(rows)-1)
   if i==0:
    cb=OxmlElement('w:tcBorders');el=OxmlElement('w:bottom');el.set(qn('w:val'),'single');el.set(qn('w:sz'),'6');el.set(qn('w:color'),'000000');cb.append(el);cell._tc.get_or_add_tcPr().append(cb)
 if note:p(d,note,'来源说明')

def image(d,b):
 kind,no,title,file,desc=b
 path=SHOTS/file if kind=='shot' else HERE/'figures'/file
 if kind=='fig':
  dest=PHOTOS/('20261110_'+file);shutil.copy2(path,dest);path=dest
 w,h=Image.open(path).size;width=15.9;height=width*h/w
 maxh=11.0 if kind=='shot' else 9.6
 if kind=='fig':
  width={'censoring.png':13.5,'journey.png':15.3,'pipeline.png':15.9,'split.png':15.5,'wape.png':14.6,'simulation.png':15.9,'tradeoff.png':14.8,'business.png':14.6,'delivery.png':15.0,'waterfall.png':14.2,'sensitivity.png':15.0,'roadmap.png':15.5}.get(file,15.5)
  height=width*h/w

 if height>maxh:width*=maxh/height
 pa=d.add_paragraph(style='图片');pa.add_run().add_picture(str(path),width=Cm(width));keep(pa)
 p(d,f'{no}  {title}','图题')
 if desc:p(d,desc,'图后说明')

def main():
 d=Document();setup(d.sections[0]);J=WD_ALIGN_PARAGRAPH.JUSTIFY;C=WD_ALIGN_PARAGRAPH.CENTER;L=WD_ALIGN_PARAGRAPH.LEFT
 style(d,'前置标题','黑体',18,True,1.2,2.5,8,C,keep=True)
 style(d,'Normal','宋体',12,False,1.5,0,0,J,24)
 style(d,'正文','宋体',12,False,1.5,0,0,J,24)
 style(d,'Heading 1','黑体',18,True,1.2,2.5,2.5,C,keep=True).paragraph_format.page_break_before=True
 style(d,'Heading 2','黑体',16,True,1.2,2.5,2.5,L,keep=True)
 for n,cn,sz,bd,ln,af,al,ke in [('表文','宋体',9.5,False,1.12,0,C,False),('表头','宋体',9.5,True,1.12,0,C,False),('图题','黑体',10.5,True,1.15,4,C,True),('表题','黑体',10.5,True,1.15,3,C,True),('来源说明','宋体',9.5,False,1.15,6,J,False),('图后说明','宋体',12,False,1.5,4,J,False),('参考条目','宋体',10.5,False,1.3,5,L,False),('图片','宋体',10.5,False,1,3,C,True),('目录条目','宋体',11,False,1.15,2,L,False)]:style(d,n,cn,sz,bd,ln,0,af,al,keep=ke)
 for _ in range(3):d.add_paragraph()
 for txt,size,cn,bd in [('食刻有数',36,'黑体',True),('高校食堂精细化经营与食品减损平台',18,'黑体',False),('FOODWISE',16,'宋体',False)]:
  pa=d.add_paragraph();pa.alignment=C;pa.paragraph_format.first_line_indent=Pt(0);pa.paragraph_format.space_after=Pt(15);fonts(pa.add_run(txt),cn,size,bd)
 for _ in range(2):d.add_paragraph()
 for txt in ['创新创业计划书','备餐决策 · 经营回传 · 食品减损','2026年11月10日']:
  pa=d.add_paragraph();pa.alignment=C;pa.paragraph_format.first_line_indent=Pt(0);pa.paragraph_format.space_after=Pt(15);fonts(pa.add_run(txt),'黑体' if txt=='创新创业计划书' else '宋体',22 if txt=='创新创业计划书' else 12,txt=='创新创业计划书')
 d.add_page_break();pa=p(d,'摘　要','前置标题');pa.paragraph_format.page_break_before=False
 for txt in content.ABSTRACT:p(d,txt)
 p(d,'关键词：高校食堂；备餐决策；售罄截断；经营复盘；食品减损','来源说明')
 d.add_page_break();pa=p(d,'目　录','前置标题');pa.paragraph_format.page_break_before=False
 entries=[]
 for b in BLOCKS:
  if b[0]=='h1' or b[0]=='h2' and not b[1].startswith('A.'):
   entries.append([1 if b[0]=='h1' else 2,b[1]])
 toc=d.add_paragraph()
 r=toc.add_run();begin=OxmlElement('w:fldChar');begin.set(qn('w:fldCharType'),'begin');r._r.append(begin)
 instr=OxmlElement('w:instrText');instr.set(qn('xml:space'),'preserve');instr.text=' TOC \\o "1-2" \\h \\z \\u ';r._r.append(instr)
 sep=OxmlElement('w:fldChar');sep.set(qn('w:fldCharType'),'separate');r._r.append(sep)
 end=OxmlElement('w:fldChar');end.set(qn('w:fldCharType'),'end');r._r.append(end)
 for n in ['TOC 1','TOC 2']:
  st=style(d,n,'宋体',11,n=='TOC 1',1.15,0,2,L)
  st.paragraph_format.left_indent=Cm(.6 if n=='TOC 2' else 0)
  st.paragraph_format.tab_stops.add_tab_stop(Cm(15.8),2,1)
 s=d.add_section(WD_SECTION.NEW_PAGE);setup(s);headerfooter(s);pg=OxmlElement('w:pgNumType');pg.set(qn('w:start'),'1');s._sectPr.append(pg)
 first=True
 for bi,b in enumerate(BLOCKS):
  if b[0]=='h1':
   pa=p(d,b[1],'Heading 1')
   if first:pa.paragraph_format.page_break_before=False;first=False
  elif b[0]=='h2':
   if b[1].startswith('A.'):continue
   p(d,b[1],'Heading 2')
  elif b[0]=='p':p(d,b[1])
  elif b[0]=='table':make_table(d,b)
  elif b[0] in ['fig','shot']:image(d,b)
  elif b[0]=='ref':p(d,b[1],'参考条目')
 for pa in d.paragraphs:
  pa.paragraph_format.widow_control=True
 # 固定中西文默认字体，防止主题改变图表题和页码字体。
 defaults=d.styles.element.find(qn('w:docDefaults'))
 if defaults is not None:
  for rf in defaults.iter(qn('w:rFonts')):
   for k,v in [('ascii',FONT),('hAnsi',FONT),('eastAsia','宋体'),('cs',FONT)]:rf.set(qn('w:'+k),v)
 settings=d.settings.element;upd=OxmlElement('w:updateFields');upd.set(qn('w:val'),'true');settings.append(upd)
 d.save(OUT);(HERE/'toc_entries.json').write_text(json.dumps(entries,ensure_ascii=False,indent=1),encoding='utf-8')
 manifest={'output':str(OUT),'paragraphs':len(d.paragraphs),'tables':len(d.tables),'images':len(d.inline_shapes),'characters':sum(len(p.text) for p in d.paragraphs)+sum(len(c.text) for t in d.tables for r in t.rows for c in r.cells),'chapters':[b[1] for b in BLOCKS if b[0]=='h1'],'toc':len(entries),'no_pdf':True}
 (HERE/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(manifest,ensure_ascii=False))
if __name__=='__main__':main()
