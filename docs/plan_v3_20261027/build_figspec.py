# -*- coding: utf-8 -*-
"""把图表作图方案 Markdown 渲染为与计划书同一排版体系的 DOCX。"""
import os
import re
import sys

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor, Twips

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_v3 import (  # noqa: E402
    HEI, LATIN, CN, TEXT_W, add_field, build_styles, page_setup,
    scale_table_width, set_run_fonts, set_table_borders,
)

MD = r"E:\食刻有数\计划书\计划书版本\图表作图方案_整合优化版_20261027.md"
OUT = r"E:\食刻有数\计划书\计划书版本\图表作图方案_整合优化版_20261027.docx"


def add_inline(p, text, size=11, base_bold=False):
    """处理 **加粗** 与 `等宽` 标记。"""
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = p.add_run(part[2:-2])
            set_run_fonts(r, CN, LATIN, size, True)
        elif part.startswith("`") and part.endswith("`"):
            r = p.add_run(part[1:-1])
            set_run_fonts(r, "Consolas", "Consolas", size - 0.5, False)
        else:
            r = p.add_run(part)
            set_run_fonts(r, CN, LATIN, size, base_bold)


def main():
    lines = open(MD, encoding="utf-8").read().split("\n")
    doc = Document()
    page_setup(doc)
    build_styles(doc)

    # 页脚页码
    fp = doc.sections[0].footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = fp.add_run("— ")
    set_run_fonts(r1, CN, LATIN, 9)
    add_field(fp, "PAGE")
    r2 = fp.add_run(" —")
    set_run_fonts(r2, CN, LATIN, 9)

    i = 0
    first_h1 = True
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln or ln.strip() == "---":
            i += 1
            continue
        if ln.startswith("# "):
            p = doc.add_paragraph(ln[2:], style="Heading 1")
            if first_h1:
                p.paragraph_format.page_break_before = False
                first_h1 = False
        elif ln.startswith("## "):
            doc.add_paragraph(ln[3:], style="Heading 2")
        elif ln.startswith("### "):
            h = doc.add_paragraph()
            h.paragraph_format.space_before = Pt(9)
            h.paragraph_format.space_after = Pt(4)
            h.paragraph_format.keep_with_next = True
            add_inline(h, ln[4:], 12, True)
            for run in h.runs:
                run.font.name = LATIN
                rpr = run._element.get_or_add_rPr()
                rf = rpr.find(qn("w:rFonts"))
                if rf is None:
                    rf = OxmlElement("w:rFonts")
                    rpr.append(rf)
                rf.set(qn("w:eastAsia"), HEI)
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                raw = lines[i].strip().strip("|")
                cells = [c.strip() for c in raw.split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if not rows:
                continue
            ncol = max(len(r) for r in rows)
            table = doc.add_table(rows=len(rows), cols=ncol)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for ri, row in enumerate(rows):
                for ci in range(ncol):
                    cell = table.rows[ri].cells[ci]
                    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    p = cell.paragraphs[0]
                    p.style = doc.styles["表头文字"] if ri == 0 else doc.styles["表内文字"]
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    txt = row[ci] if ci < len(row) else ""
                    add_inline(p, txt, 9.5, ri == 0)
            # 按内容长度分配列宽（首列图号窄，名称列宽）
            weights = []
            for ci in range(ncol):
                longest = max(len(r[ci]) if ci < len(r) else 0 for r in rows)
                weights.append(max(11, min(38, longest)))
            total_w = sum(weights)
            widths = [max(1300, int(TEXT_W * w / total_w)) for w in weights]
            widths[-1] += TEXT_W - sum(widths)
            grid = table._tbl.tblGrid
            for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
                gc.set(qn("w:w"), str(w))
            for row in table.rows:
                for cell, w in zip(row.cells, widths):
                    cell.width = Twips(w)
            scale_table_width(table)
            set_table_borders(table)
            tr_pr = table.rows[0]._tr.get_or_add_trPr()
            tr_pr.append(OxmlElement("w:tblHeader"))
            for row in table.rows:
                row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            continue
        elif ln.startswith("- "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.0)
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, ln[2:])
        elif re.match(r"^\d+\. ", ln):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.first_line_indent = Cm(-0.6)
            p.paragraph_format.space_after = Pt(2)
            add_inline(p, ln)
        elif ln.startswith("**") and ln.endswith("**"):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.keep_with_next = True
            add_inline(p, ln, 11, True)
        else:
            add_inline(doc.add_paragraph(), ln)
        i += 1

    doc.save(OUT)
    print("saved", OUT, "paras", len(doc.paragraphs), "tables", len(doc.tables))


if __name__ == "__main__":
    main()