# -*- coding: utf-8 -*-
"""从旧稿中提取“图号 -> 图片文件”的对照，供 v3 重建时复用真实截图。"""
import os
import re
import json

from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table

OLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "生成模板.docx")
OUT = r"E:\食刻有数\项目代码\docs\plan_v3_20261027\shots"
os.makedirs(OUT, exist_ok=True)

d = Document(OLD)
body = d.element.body
kids = list(body.iterchildren())

found = {}
for i, child in enumerate(kids):
    if not child.tag.endswith("}p"):
        continue
    if not child.xpath(".//wp:inline"):
        continue
    # 找紧随其后的图题
    cap = ""
    for j in range(i + 1, min(i + 4, len(kids))):
        nxt = kids[j]
        if nxt.tag.endswith("}p"):
            t = Paragraph(nxt, d).text.strip()
            if re.match(r"^图\s*[0-9A-Za-z]", t):
                cap = t
                break
    if not cap:
        continue
    no = re.match(r"^(图\s*[0-9A-Za-z]+[-–]?[0-9]*)", cap).group(1).replace(" ", "")
    blips = child.xpath(".//a:blip/@r:embed")
    if not blips:
        continue
    part = d.part.related_parts[blips[0]]
    ext = os.path.splitext(part.partname)[1] or ".png"
    fn = os.path.join(OUT, no.replace("–", "-") + ext)
    with open(fn, "wb") as f:
        f.write(part.blob)
    found[no] = {"file": os.path.basename(fn), "bytes": len(part.blob), "caption": cap}

with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
    json.dump(found, f, ensure_ascii=False, indent=2)
for k, v in found.items():
    print(k, v["bytes"], v["caption"][:40])