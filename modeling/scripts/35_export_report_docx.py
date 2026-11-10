"""把研究报告 Markdown 导出为排版规整的 DOCX（挑战杯提交用）。

排版口径与工作区约定一致：A4、宋体 11 磅、1.4 倍行距、段后 3 磅；标题黑体；
表格三线表、9 磅；代码块等宽字体 + 浅底。

用法：
    <bundled python> modeling/scripts/35_export_report_docx.py
需要 python-docx（建模虚拟环境未安装，使用 DSH 自带 Python）。
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "研究报告_食刻有数_v3_20261027.md"
TARGET = ROOT / "docs" / "研究报告_食刻有数_v3_20261027.docx"

SONG = "宋体"
HEI = "黑体"
MONO = "Consolas"


def set_run_font(run, name: str, size: float, bold: bool = False) -> None:
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    fonts.set(qn("w:eastAsia"), name)
    fonts.set(qn("w:ascii"), "Times New Roman" if name == SONG else name)
    fonts.set(qn("w:hAnsi"), "Times New Roman" if name == SONG else name)


def body_format(paragraph, space_after: float = 3.0, first_indent: bool = False) -> None:
    fmt = paragraph.paragraph_format
    fmt.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    fmt.line_spacing = 1.4
    fmt.space_after = Pt(space_after)
    fmt.space_before = Pt(0)
    if first_indent:
        fmt.first_line_indent = Pt(22)


INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\$[^$]+\$)")

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "varepsilon": "ε", "epsilon": "ε",
    "mu": "μ", "sigma": "σ", "rho": "ρ", "kappa": "κ", "Phi": "Φ", "phi": "φ", "theta": "θ",
    "lambda": "λ", "tau": "τ", "pi": "π", "sum": "Σ", "max": "max", "min": "min",
}
SUPERSCRIPTS = {"-1": "⁻¹", "2": "²", "6": "⁶", "*": "*", "-2": "⁻²", "2/9": "⁽²ᐟ⁹⁾"}
SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _read_group(text: str, start: int) -> tuple[str, int]:
    """从 start 处的 `{` 读出配对内容，返回 (内容, 结束位置后一位)。"""
    if start >= len(text) or text[start] != "{":
        return "", start
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
    return text[start + 1:], len(text)


def latex_to_plain(text: str) -> str:
    """把报告里用到的少量 LaTeX 片段转成可读的纯文本（不做真正排版）。"""
    text = text.replace("\\left", "").replace("\\right", "")
    for token in ("\\!", "\\,", "\\;", "\\quad", "\\ "):
        text = text.replace(token, " ")

    # \frac{a}{b} → (a)/(b)，支持嵌套一层
    while "\\frac" in text:
        start = text.index("\\frac")
        numerator, after_num = _read_group(text, start + 5)
        denominator, after_den = _read_group(text, after_num)
        replacement = f"({numerator})/({denominator})"
        text = text[:start] + replacement + text[after_den:]

    # \hat{X} / \tilde{X} → 组合符号
    for command, mark in (("\\hat", "\u0302"), ("\\tilde", "\u0303")):
        while command in text:
            start = text.index(command)
            group, after = _read_group(text, start + len(command))
            text = text[:start] + group + mark + text[after:]

    # \text{...} / \mathbb{1}
    while "\\text" in text:
        start = text.index("\\text")
        group, after = _read_group(text, start + 5)
        text = text[:start] + group + text[after:]
    text = text.replace("\\mathbb{1}", "1")
    text = text.replace("\\bigl\\{", "{").replace("\\bigr\\}", "}")
    text = text.replace("\\{", "{").replace("\\}", "}")
    text = text.replace("\\cdot", "·").replace("\\times", "×").replace("\\approx", "≈")

    # 上下标
    for pattern, superscript in SUPERSCRIPTS.items():
        text = text.replace("^{" + pattern + "}", superscript)
    while "^{" in text:
        start = text.index("^{")
        group, after = _read_group(text, start + 1)
        text = text[:start] + "^(" + group + ")" + text[after:]
    while "_{" in text:
        start = text.index("_{")
        group, after = _read_group(text, start + 1)
        text = text[:start] + "_" + (group.translate(SUBSCRIPT_DIGITS) if group.isdigit() else f"({group})") + text[after:]

    for name, symbol in GREEK.items():
        text = text.replace("\\" + name, symbol)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    return text.replace("$", "").strip()


def smart_quotes(text: str) -> str:
    """把中文语境里的半角引号换成全角，避免 Word 里出现"这样的直引号"。"""
    result: list[str] = []
    opening = True
    for char in text:
        if char == '"':
            result.append("“" if opening else "”")
            opening = not opening
        else:
            result.append(char)
    return "".join(result)


def add_inline(paragraph, text: str, size: float = 11.0, base_bold: bool = False) -> None:
    """处理 **加粗**、`行内代码` 与 $行内公式$。"""
    for token in INLINE.split(text):
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            # 加粗里可能还有 `代码` 或 $公式$，递归处理一层
            add_inline(paragraph, token[2:-2], size=size, base_bold=True)
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, MONO, size - 0.5)
            run.font.color.rgb = RGBColor(0x8B, 0x2E, 0x16)
        elif token.startswith("$") and token.endswith("$") and len(token) > 2:
            run = paragraph.add_run(latex_to_plain(token[1:-1]))
            set_run_font(run, SONG, size)
            run.font.italic = True
        else:
            run = paragraph.add_run(smart_quotes(token))
            set_run_font(run, SONG, size, bold=base_bold)


def add_heading(doc: Document, text: str, level: int) -> None:
    sizes = {1: 16.0, 2: 14.0, 3: 12.0, 4: 11.0}
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    set_run_font(run, HEI, sizes.get(level, 11.0), bold=True)
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(14 if level <= 2 else 10)
    fmt.space_after = Pt(6)
    fmt.keep_with_next = True


def shade(cell, color: str) -> None:
    tc_pr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def three_line_table(table) -> None:
    tbl = table._element
    tbl_pr = tbl.tblPr
    # 行不跨页拆开，且整表尽量不被分页切开，避免页首只剩一行
    for row in table.rows:
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True
    borders = OxmlElement("w:tblBorders")
    for edge, size in (("top", "12"), ("bottom", "12")):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), "000000")
        borders.append(element)
    for edge in ("left", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "none")
        borders.append(element)
    tbl_pr.append(borders)
    # 表头下横线
    header = table.rows[0]
    for cell in header.cells:
        tc_pr = cell._element.get_or_add_tcPr()
        tc_borders = OxmlElement("w:tcBorders")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:color"), "000000")
        tc_borders.append(bottom)
        tc_pr.append(tc_borders)


def add_table(doc: Document, rows: list[list[str]]) -> None:
    header, body = rows[0], rows[1:]
    # 表前的引导句与表格同页，避免"标题孤行"
    if doc.paragraphs and doc.paragraphs[-1].text.strip():
        doc.paragraphs[-1].paragraph_format.keep_with_next = True
    table = doc.add_table(rows=1, cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for index, text in enumerate(header):
        cell = table.rows[0].cells[index]
        cell.text = ""
        paragraph = cell.paragraphs[0]
        add_inline(paragraph, text, size=9.5, base_bold=True)
        shade(cell, "F2F5F6")
    for row in body:
        cells = table.add_row().cells
        for index, text in enumerate(row[: len(header)]):
            cells[index].text = ""
            add_inline(cells[index].paragraphs[0], text, size=9.5)
    apply_column_widths(table, rows)
    three_line_table(table)
    apply_column_widths(table, rows)
    doc.add_paragraph()


def apply_column_widths(table, rows: list[list[str]]) -> None:
    """按每列最长内容分配宽度，避免路径列被挤成竖排单字。"""
    available = 15.8  # cm，A4 减去左右各 2.6cm 页边距
    columns = len(rows[0])
    weights = []
    for index in range(columns):
        longest = max(len(str(row[index])) if index < len(row) else 0 for row in rows)
        weight = max(8, min(longest, 40))
        if index == 0:
            weight *= 1.45  # 首列多为短标签，给足宽度避免"测试对照样本"竖排
        weights.append(weight)
    total = sum(weights)
    widths = [max(2.2, available * weight / total) for weight in weights]
    scale = available / sum(widths)
    widths = [round(width * scale, 2) for width in widths]
    for index, width in enumerate(widths):
        table.columns[index].width = Cm(width)
        for row in table.rows:
            row.cells[index].width = Cm(width)
    # 固定表格布局，否则 Word 会按内容重新分配；tblLayout 必须排在 tblBorders 之前
    tbl_pr = table._element.tblPr
    for existing in tbl_pr.findall(qn("w:tblLayout")):
        tbl_pr.remove(existing)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is not None:
        borders.addprevious(layout)
    else:
        tbl_pr.append(layout)


def add_code_block(doc: Document, lines: list[str]) -> None:
    table = doc.add_table(rows=1, cols=1)
    cell = table.rows[0].cells[0]
    shade(cell, "F4F6F7")
    cell.text = ""
    paragraph = cell.paragraphs[0]
    for index, line in enumerate(lines):
        run = paragraph.add_run(line)
        set_run_font(run, MONO, 9.0)
        if index < len(lines) - 1:
            run.add_break()
    fmt = paragraph.paragraph_format
    fmt.line_spacing = 1.25
    fmt.space_after = Pt(0)
    doc.add_paragraph()


def add_cover(doc: Document, title: str, subtitle: str) -> None:
    for _ in range(4):
        doc.add_paragraph()
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(title)
    set_run_font(run, HEI, 22.0, bold=True)
    paragraph.paragraph_format.space_after = Pt(18)

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(subtitle)
    set_run_font(run, SONG, 12.0)
    paragraph.paragraph_format.space_after = Pt(6)

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("食刻有数（FOODWISE） · 2026 年 10 月")
    set_run_font(run, SONG, 11.0)
    doc.add_page_break()


def parse(markdown: str) -> list[tuple[str, object]]:
    blocks: list[tuple[str, object]] = []
    lines = markdown.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            blocks.append(("code", code))
            index += 1
            continue
        if stripped.startswith("$$"):
            index += 1
            math_lines: list[str] = []
            if stripped.strip("$").strip():
                math_lines.append(stripped.strip("$").strip())
            while index < len(lines) and "$$" not in lines[index]:
                math_lines.append(lines[index].strip())
                index += 1
            index += 1
            blocks.append(("math", " ".join(math_lines)))
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and set(lines[index + 1].strip()) <= set("|-: "):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not set("".join(cells)) <= set("-: "):
                    rows.append(cells)
                index += 1
            blocks.append(("table", rows))
            continue
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            blocks.append((f"h{min(level, 4)}", stripped[level:].strip()))
            index += 1
            continue
        if stripped in ("---", "***"):
            blocks.append(("rule", None))
            index += 1
            continue
        if stripped.startswith(">"):
            blocks.append(("quote", stripped.lstrip("> ").strip()))
            index += 1
            continue
        if re.match(r"^-\s*\[[ xX]\]", stripped):
            blocks.append(("check", re.sub(r"^-\s*\[[ xX]\]\s*", "", stripped)))
            index += 1
            continue
        if re.match(r"^[-*]\s+", stripped):
            blocks.append(("bullet", re.sub(r"^[-*]\s+", "", stripped)))
            index += 1
            continue
        if re.match(r"^\d+\.\s+", stripped):
            blocks.append(("number", stripped))
            index += 1
            continue
        if stripped:
            blocks.append(("para", stripped))
        index += 1
    return blocks


def main() -> int:
    markdown = SOURCE.read_text(encoding="utf-8")
    blocks = parse(markdown)
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.6)
    section.right_margin = Cm(2.6)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    title = "从区间校准到可复核决策"
    subtitle = "高校食堂档口备餐减损的方法、实验与边界"
    add_cover(doc, title, subtitle)
    skipped_title = False

    for kind, value in blocks:
        if kind == "h1":
            if not skipped_title:  # Markdown 一级标题已作为封面
                skipped_title = True
                continue
            add_heading(doc, value, 1)
        elif kind in ("h2", "h3", "h4"):
            add_heading(doc, value, int(kind[1]))
        elif kind == "para":
            paragraph = doc.add_paragraph()
            add_inline(paragraph, value)
            body_format(paragraph, first_indent=True)
        elif kind == "bullet":
            paragraph = doc.add_paragraph(style="List Bullet")
            add_inline(paragraph, value)
            body_format(paragraph, space_after=1.5)
        elif kind == "number":
            paragraph = doc.add_paragraph(style="List Number")
            add_inline(paragraph, value)
            body_format(paragraph, space_after=1.5)
        elif kind == "check":
            paragraph = doc.add_paragraph()
            run = paragraph.add_run("☐ ")
            set_run_font(run, SONG, 11.0)
            add_inline(paragraph, value)
            body_format(paragraph, space_after=1.5)
        elif kind == "quote":
            paragraph = doc.add_paragraph()
            add_inline(paragraph, value)
            body_format(paragraph)
            for run in paragraph.runs:
                run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        elif kind == "code":
            add_code_block(doc, value)
        elif kind == "math":
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(latex_to_plain(str(value)))
            set_run_font(run, SONG, 11.0)
            run.font.italic = True
            fmt = paragraph.paragraph_format
            fmt.space_before = Pt(6)
            fmt.space_after = Pt(8)
        elif kind == "table":
            add_table(doc, value)
        elif kind == "rule":
            doc.add_page_break()

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    doc.save(TARGET)
    print(f"wrote {TARGET}")
    print(f"paragraphs={len(doc.paragraphs)} tables={len(doc.tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())