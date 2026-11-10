# -*- coding: utf-8 -*-
"""v3 整合优化版计划书构建脚本。

用法：
    python build_v3.py            # 生成 docx（目录页码为占位 0）
    python fill_toc.py out.docx   # 渲染后回填真实页码
"""
import copy
import json
import os
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor, Twips

import content_1
import content_2
import content_3

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(HERE, "生成模板.docx")
SHOTS = os.path.join(HERE, "shots")
OUT = r"E:\食刻有数\计划书\计划书版本\食刻有数_商业计划书_20261104.docx"

# 新图号 -> 旧稿提取出的截图文件
SHOT_MAP = {
    "图3-2": "图3-1.png",
    "图3-3": "图3-2.png",
    "图3-5": "图3-3.png",
    "图5-4": "图5-2.png",
    "图A-1": "图A-1.png",
    "图A-2": "图A-2.png",
    "图A-3": "图A-3.png",
    "图A-4": "图A-4.png",
    "图A-5": "图A-5.png",
    "图A-6": "图A-6.png",
    "图A-7": "图A-7.png",
}

FIGS = os.path.join(HERE, "figs_v3", "out")

# 图号 -> figs_v3/out 下已绘制的示意图（存在即替换占位框）
FIG_MAP = {
    "图1-1": "图1-1.png",
    "图2-1": "图2-1.png",
    "图2-2": "图2-2.png",
    "图3-1": "图3-1.png",
    "图3-4": "图3-4.png",
    "图3-6": "图3-6.png",
    "图4-1": "图4-1.png",
    "图4-2": "图4-2.png",
    "图4-3": "图4-3.png",
    "图4-4": "图4-4.png",
    "图5-1": "图5-1.png",
    "图5-2": "图5-2.png",
    "图5-3": "图5-3.png",
    "图5-5": "图5-5.png",
    "图6-1": "图6-1.png",
    "图6-2": "图6-2.png",
    "图7-1": "图7-1.png",
    "图8-1": "图8-1.png",
    "图9-1": "图9-1.png",
    "图10-1": "图10-1.png",
}

FIG_W = {"图1-1": 12.0, "图10-1": 11.4}  # 个别图按需收窄，避免章末留白
TEXT_W = 8902  # 15.7cm 版心，单位 twips
CN, LATIN = "宋体", "Times New Roman"
HEI = "黑体"


# --------------------------------------------------------------- 基础工具
def set_run_fonts(rpr_owner, cn=CN, latin=LATIN, size=None, bold=None):
    """给 style 或 run 设置中西文字体。"""
    font = rpr_owner.font
    font.name = latin
    if size is not None:
        font.size = Pt(size)
    if bold is not None:
        font.bold = bold
    rpr = rpr_owner.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), cn)
    rfonts.set(qn("w:cs"), latin)


def first_line_chars(p_style, chars=200):
    ppr = p_style.element.get_or_add_pPr()
    ind = ppr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        ppr.append(ind)
    ind.set(qn("w:firstLineChars"), str(chars))
    ind.set(qn("w:firstLine"), str(int(chars / 100 * 220)))


def keep_with_next(p_style):
    p_style.paragraph_format.keep_with_next = True


def add_field(paragraph, instr, placeholder="1"):
    r = paragraph.add_run()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), instr)
    t = OxmlElement("w:t")
    t.text = placeholder
    r_el = OxmlElement("w:r")
    r_el.append(t)
    fld.append(r_el)
    paragraph._p.append(fld)


def set_cell_shading(cell, hexcolor):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcpr.append(shd)


def set_table_borders(table, top=12, bottom=12, header=6, dashed=False):
    """三线表：上下 1.5pt、表头下 0.75pt，其余为无。"""
    tbl_pr = table._tbl.tblPr
    for tag in ("w:tblBorders",):
        old = tbl_pr.find(qn(tag))
        if old is not None:
            tbl_pr.remove(old)
    borders = OxmlElement("w:tblBorders")
    spec = {
        "top": (top, "single"),
        "left": (0, "none"),
        "bottom": (bottom, "single"),
        "right": (0, "none"),
        "insideH": (0, "none"),
        "insideV": (0, "none"),
    }
    for edge, (sz, val) in spec.items():
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), val)
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tbl_pr.append(borders)
    if dashed:
        return
    # 表头下沿单独加线
    for cell in table.rows[0].cells:
        tcpr = cell._tc.get_or_add_tcPr()
        tcb = OxmlElement("w:tcBorders")
        b = OxmlElement("w:bottom")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), str(header))
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "000000")
        tcb.append(b)
        tcpr.append(tcb)


def scale_table_width(table, total=TEXT_W):
    tbl = table._tbl
    grid = tbl.find(qn("w:tblGrid"))
    cols = grid.findall(qn("w:gridCol")) if grid is not None else []
    widths = [int(c.get(qn("w:w")) or 0) for c in cols]
    if not widths or sum(widths) == 0:
        return
    factor = total / sum(widths)
    new = [max(600, int(w * factor)) for w in widths]
    diff = total - sum(new)
    new[-1] += diff
    for c, w in zip(cols, new):
        c.set(qn("w:w"), str(w))
    for row in table.rows:
        for cell, w in zip(row.cells, new):
            cell.width = Twips(w)
    tbl_pr = table._tbl.tblPr
    tw = tbl_pr.find(qn("w:tblW"))
    if tw is None:
        tw = OxmlElement("w:tblW")
        tbl_pr.append(tw)
    tw.set(qn("w:w"), str(total))
    tw.set(qn("w:type"), "dxa")
    # 去掉浮动表格属性
    for tag in ("w:tblpPr", "w:tblOverlap"):
        el = tbl_pr.find(qn(tag))
        if el is not None:
            tbl_pr.remove(el)


def style_table(table, doc):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    scale_table_width(table)
    set_table_borders(table)
    for i, row in enumerate(table.rows):
        tr_pr = row._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        tr_pr.append(cant)
        if i == 0:
            hdr = OxmlElement("w:tblHeader")
            tr_pr.append(hdr)
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for p in cell.paragraphs:
                p.style = doc.styles["表内文字"] if i else doc.styles["表头文字"]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.12
                p.paragraph_format.first_line_indent = Pt(0)


# --------------------------------------------------------------- 文档骨架
def build_styles(doc):
    normal = doc.styles["Normal"]
    set_run_fonts(normal, CN, LATIN, 11)
    pf = normal.paragraph_format
    pf.line_spacing = 1.4
    pf.space_before = Pt(0)
    pf.space_after = Pt(3)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    first_line_chars(normal)

    specs = [
        ("正文", CN, 11, False, 1.4, 3, "justify", None),
        ("表内文字", CN, 9.5, False, 1.12, 0, "center", None),
        ("表头文字", CN, 9.5, True, 1.12, 0, "center", None),
        ("图题", HEI, 10.5, True, 1.15, 6, "center", None),
        ("表题", HEI, 10.5, True, 1.15, 3, "center", None),
        ("注释", CN, 9.5, False, 1.15, 6, "justify", None),
        ("参考条目", CN, 10.5, False, 1.15, 2, "justify", None),
        ("占位框", CN, 9, False, 1.2, 0, "center", None),
    ]
    for name, cn, size, bold, ls, after, align, _ in specs:
        st = doc.styles.add_style(name, 1)
        st.base_style = doc.styles["Normal"]
        set_run_fonts(st, cn, LATIN, size, bold)
        pf = st.paragraph_format
        pf.line_spacing = ls
        pf.space_before = Pt(0)
        pf.space_after = Pt(after)
        pf.alignment = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
                        "center": WD_ALIGN_PARAGRAPH.CENTER}[align]
        pf.first_line_indent = Pt(0)

    doc.styles["表题"].paragraph_format.keep_with_next = True

    h1 = doc.styles["Heading 1"]
    set_run_fonts(h1, HEI, LATIN, 16, True)
    h1.font.color.rgb = RGBColor(0, 0, 0)
    h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1.paragraph_format.space_before = Pt(12)
    h1.paragraph_format.space_after = Pt(12)
    h1.paragraph_format.line_spacing = 1.2
    h1.paragraph_format.page_break_before = True
    h1.paragraph_format.keep_with_next = True

    h2 = doc.styles["Heading 2"]
    set_run_fonts(h2, HEI, LATIN, 14, True)
    h2.font.color.rgb = RGBColor(0, 0, 0)
    h2.paragraph_format.space_before = Pt(9)
    h2.paragraph_format.space_after = Pt(6)
    h2.paragraph_format.line_spacing = 1.25
    h2.paragraph_format.keep_with_next = True

    cap = doc.styles["题注"] if "题注" in [s.name for s in doc.styles] else None
    toc = doc.styles.add_style("目录条目", 1)
    toc.base_style = doc.styles["Normal"]
    set_run_fonts(toc, CN, LATIN, 11)
    toc.paragraph_format.line_spacing = 1.15
    toc.paragraph_format.space_after = Pt(0)
    toc.paragraph_format.first_line_indent = Pt(0)


def page_setup(doc):
    s = doc.sections[0]
    s.header.is_linked_to_previous = False
    s.footer.is_linked_to_previous = False
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin, s.bottom_margin = Cm(2.54), Cm(2.54)
    s.left_margin, s.right_margin = Cm(2.80), Cm(2.50)
    s.header_distance, s.footer_distance = Cm(1.5), Cm(1.6)


def add_body_section(doc):
    s = doc.add_section(WD_SECTION.NEW_PAGE)
    s.header.is_linked_to_previous = False
    s.footer.is_linked_to_previous = False
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin, s.bottom_margin = Cm(2.54), Cm(2.54)
    s.left_margin, s.right_margin = Cm(2.80), Cm(2.50)
    s.header_distance, s.footer_distance = Cm(1.5), Cm(1.6)
    # 页码从 1 重新编号
    pgnum = OxmlElement("w:pgNumType")
    pgnum.set(qn("w:start"), "1")
    s._sectPr.append(pgnum)
    # 页眉
    hp = s.header.paragraphs[0]
    hp.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = hp.add_run("食刻有数 · 高校食堂精细化经营与食品减损平台")
    set_run_fonts(run, CN, LATIN, 9)
    run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "808080")
    pbdr.append(bottom)
    hp._p.get_or_add_pPr().append(pbdr)
    # 页脚
    fp = s.footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = fp.add_run("— ")
    set_run_fonts(r1, CN, LATIN, 9)
    add_field(fp, "PAGE")
    r2 = fp.add_run(" —")
    set_run_fonts(r2, CN, LATIN, 9)


# --------------------------------------------------------------- 内容构件
def para(doc, text, style="正文"):
    p = doc.add_paragraph(text, style=style)
    return p


def caption(doc, text, kind="图题", no=None):
    if no and text.startswith(no):
        text = text[len(no):].lstrip(" 　")
        text = f"{no} {text}"
    p = doc.add_paragraph(text, style=kind)
    return p


def add_shot(doc, no, path):
    from PIL import Image
    w, h = Image.open(path).size
    base_w = 11.6 if no.startswith("图A-") else 13.6
    width = Cm(base_w)
    height_cm = base_w * h / w
    if height_cm > 10.0:
        width = Cm(base_w * 10.0 / height_cm)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=width)


def add_drawn(doc, no, path, base_w=13.2):
    """插入已绘制的示意图：宽度固定为版心宽 13.2 cm，最高 10.5 cm。"""
    from PIL import Image
    w, h = Image.open(path).size
    width = Cm(base_w)
    height_cm = base_w * h / w
    if height_cm > 10.5:
        width = Cm(base_w * 10.5 / height_cm)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=width)


def add_placeholder(doc, no, kind_text):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    scale_table_width(table)
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "dashed")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "9E9E9E")
        borders.append(el)
    tbl_pr.append(borders)
    row = table.rows[0]
    tr_pr = row._tr.get_or_add_trPr()
    h = OxmlElement("w:trHeight")
    h.set(qn("w:val"), "900")
    h.set(qn("w:hRule"), "atLeast")
    tr_pr.append(h)
    cell = row.cells[0]
    set_cell_shading(cell, "FAFAFA")
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    p.style = doc.styles["占位框"]
    p.paragraph_format.keep_with_next = True
    r = p.add_run(f"【图中位置预留】示意{kind_text}，待绘制｜规格见《图表作图方案》{no}")
    set_run_fonts(r, CN, LATIN, 9)
    r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def insert_rows_before_last(table, rows):
    """在表体最后一行之前插入若干行（复制末行格式），row 数据按列顺序写入。"""
    ref = table.rows[-1]._tr
    for _ in rows:
        ref.addprevious(copy.deepcopy(ref))
    data_rows = table.rows[-len(rows) - 1:-1]
    for row, values in zip(data_rows, rows):
        for cell, val in zip(row.cells, values):
            cell.text = ""
            p = cell.paragraphs[0]
            p.add_run(str(val))


def add_table_from_source(doc, src_doc, idx, cap_no, cap_text, note, extra=None):
    last = doc.element.body[-1]
    if last.tag.endswith("}tbl"):
        sep = doc.add_paragraph()
        sep.paragraph_format.space_after = Pt(0)
        sep.paragraph_format.line_spacing = 0.5
    caption(doc, f"{cap_no} {cap_text}", "表题")
    tbl = src_doc.tables[idx]._tbl
    new_tbl = copy.deepcopy(tbl)
    body = doc.element.body
    sect = body.find(qn("w:sectPr"))
    if sect is not None:
        sect.addprevious(new_tbl)
    else:
        body.append(new_tbl)
    table = doc.tables[-1]
    if isinstance(extra, dict) and "replace" in extra:
        values = extra["replace"]
        template = copy.deepcopy(table.rows[-1]._tr)
        rows = table._tbl.tr_lst
        for tr in rows[1:]:
            table._tbl.remove(tr)
        while len(table.rows) < len(values):
            table._tbl.append(copy.deepcopy(template))
        for row, row_values in zip(table.rows, values):
            if len(row.cells) != len(row_values):
                raise ValueError(f"{cap_no} 列数不匹配：{len(row.cells)} != {len(row_values)}")
            for cell, value in zip(row.cells, row_values):
                cell.text = str(value)
    elif extra:
        insert_rows_before_last(table, extra)
    style_table(table, doc)
    if note:
        para(doc, note, "注释")


def build_toc(doc, entries):
    title = doc.add_paragraph("目　录")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(6)
    title.paragraph_format.space_after = Pt(14)
    r = title.add_run("")
    set_run_fonts(r, HEI, LATIN, 22, True)
    for run in title.runs:
        run.font.size = Pt(22)
        run.font.bold = True
    for level, text, page in entries:
        p = doc.add_paragraph(style="目录条目")
        p.paragraph_format.first_line_indent = Pt(0)
        if level == 2:
            p.paragraph_format.left_indent = Cm(0.74)
        # 右对齐制表位 + 点线
        tabs = p.paragraph_format.tab_stops
        tabs.add_tab_stop(Cm(15.55), alignment=2, leader=1)
        p.add_run(f"{text}\t{page}")
    return title


def toc_entries(blocks):
    out = []
    for b in blocks:
        if b[0] == "abs_h":
            continue
        if b[0] == "h1":
            out.append((1, b[1], 0))
        elif b[0] == "h2":
            out.append((2, b[1], 0))
    return out


# --------------------------------------------------------------- 主流程
def inject_refs(blocks):
    """给每张图/每张表在最近的上一段正文里补一处“（见图X-Y）/（见表X-Y）”。"""
    blocks = list(blocks)
    for i, b in enumerate(blocks):
        if b[0] not in ("fig", "tbl"):
            continue
        no = b[1]          # 形如“图1-1”“表5-4”，已含图/表字，不再加前缀
        ref = f"（见{no}）"
        for j in range(i - 1, -1, -1):
            if blocks[j][0] in ("h1", "h2"):
                break
            if blocks[j][0] != "p":
                continue
            txt = blocks[j][1]
            if no in txt or ref in txt:
                break
            k = txt.rfind("。")
            new = txt[:k] + ref + txt[k:] if k > 0 else txt + ref
            blocks[j] = ("p", new)
            break
    return blocks


def main():
    blocks = inject_refs(content_1.BLOCKS + content_2.BLOCKS + content_3.BLOCKS)
    src = Document(OLD)

    doc = Document()
    page_setup(doc)
    build_styles(doc)

    # ---------------- 封面
    for _ in range(3):
        doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("食刻有数")
    set_run_fonts(r, HEI, LATIN, 36, True)
    st = doc.add_paragraph()
    st.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = st.add_run("高校食堂精细化经营与食品减损平台")
    set_run_fonts(r, HEI, LATIN, 18, False)
    st2 = doc.add_paragraph()
    st2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = st2.add_run("FOODWISE  ·  备餐决策与经营减损服务")
    set_run_fonts(r, CN, LATIN, 12, False)
    for _ in range(4):
        doc.add_paragraph()
    info = [
        ("项目名称", "食刻有数——高校食堂精细化经营与食品减损服务"),
        ("参赛赛道", "大挑战杯（科技发明制作 B 类）· 三创赛常规赛（创业计划赛道）"),
        ("作品形态", "可运行系统 ＋ 研究报告 ＋ 复现包"),
        ("文稿性质", "双赛适配版，数字口径见附录B"),
        ("申报学校／团队", "＿＿＿＿＿＿＿＿＿＿＿＿（按当届报名信息填写）"),
        ("版本日期", "2026 年 11 月 4 日"),
    ]
    tb = doc.add_table(rows=len(info), cols=2)
    tb.alignment = WD_TABLE_ALIGNMENT.CENTER
    scale_table_width(tb, 7600)
    for i, (k, v) in enumerate(info):
        c0, c1 = tb.rows[i].cells
        c0.width, c1.width = Twips(1900), Twips(5700)
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r0 = p0.add_run(k + "：")
        set_run_fonts(r0, HEI, LATIN, 11, True)
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r1 = p1.add_run(v)
        set_run_fonts(r1, CN, LATIN, 11, False)
        for c in (c0, c1):
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    # 封面表无框线
    tbl_pr = tb._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "none")
        el.set(qn("w:sz"), "0")
        borders.append(el)
    tbl_pr.append(borders)

    # ---------------- 摘要页
    doc.add_page_break()
    h = doc.add_paragraph("摘　要", style="Heading 1")
    h.paragraph_format.page_break_before = False
    for b in blocks:
        if b[0] == "abs":
            if b[1].startswith("关键词"):
                para(doc, b[1], "注释")
            else:
                para(doc, b[1])

    # ---------------- 目录页
    doc.add_page_break()
    entries = toc_entries(blocks)
    build_toc(doc, entries)

    # ---------------- 正文
    add_body_section(doc)
    first_h1 = True
    for b in blocks:
        kind = b[0]
        if kind == "h1":
            h = doc.add_paragraph(b[1], style="Heading 1")
            if first_h1:
                h.paragraph_format.page_break_before = False
                first_h1 = False
        elif kind == "abs" or kind == "abs_h":
            continue
        elif kind == "h2":
            doc.add_paragraph(b[1], style="Heading 2")
        elif kind == "p":
            para(doc, b[1])
        elif kind == "ref":
            p = doc.add_paragraph(b[1], style="参考条目")
            p.paragraph_format.left_indent = Cm(0.74)
            p.paragraph_format.first_line_indent = Cm(-0.74)
        elif kind == "note":
            para(doc, b[1], "注释")
        elif kind == "tbl":
            no, cap_text, idx, note = b[1], b[2], b[3], b[4]
            extra = b[5] if len(b) > 5 else None
            add_table_from_source(doc, src, idx, no, cap_text, note, extra)
        elif kind == "fig":
            _, no, cap_text, ftype, spec = b
            if no in SHOT_MAP:
                add_shot(doc, no, os.path.join(SHOTS, SHOT_MAP[no]))
                caption(doc, f"{no} {cap_text}", no=no)
            elif no in FIG_MAP:
                add_drawn(doc, no, os.path.join(FIGS, FIG_MAP[no]), FIG_W.get(no, 13.2))
                caption(doc, f"{no} {cap_text}", no=no)
            else:
                label = {"draw": "图"}.get(ftype, ftype)
                add_placeholder(doc, no, label)
                caption(doc, f"{no} {cap_text}", no=no)

    doc.save(OUT)
    with open(os.path.join(HERE, "toc_entries.json"), "w", encoding="utf-8") as f:
        json.dump([[lv, tx] for lv, tx, _ in entries], f, ensure_ascii=False, indent=1)
    print("saved", OUT)
    print("paras", len(doc.paragraphs), "tables", len(doc.tables), "toc", len(entries))


if __name__ == "__main__":
    main()
