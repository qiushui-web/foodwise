# -*- coding: utf-8 -*-
"""图3-1 七步闭环；图3-4 成本临界比与约束投影；图3-6 两种偏差口径。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_lib import (ACCENT, BORDER, GRAY, INK, LIGHT, LIGHT2, PRIMARY, SECOND, W,
                     WHITE, Fig, render)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def fig_3_1():
    h = 288
    f = Fig(W, h)
    steps = [
        ("建档与准入", "数据字典", False),
        ("台账导入与核对", "清洗台账", False),
        ("营业前需求参考", "参考区间", False),
        ("现场约束与备餐计划", "计划单", False),
        ("执行确认", "确认记录", True),
        ("结果回填", "实际结果", False),
        ("周期复盘", "复盘报告", False),
    ]
    y0, hh, gap = 16, 28, 8
    for i, (name, out, manual) in enumerate(steps):
        y = y0 + i * (hh + gap)
        f.box(44, y, 192, hh, name, None, LIGHT if manual else WHITE,
              BORDER, INK, 11.0)
        f.rect(258, y + 3, 90, hh - 6, LIGHT2, BORDER, 4, 0.8)
        f.text(303, y + hh / 2 + 3.4, out, 9.0, SECOND)
        f.path(f"M236,{y + hh / 2} L256,{y + hh / 2}", BORDER, 0.9, "3 2", head=False)
        if i < len(steps) - 1:
            f.line(140, y + hh, 140, y + hh + gap - 1, PRIMARY, 1.0)

    y5 = y0 + 4 * (hh + gap)
    f.rect(362, y5 + 2, 96, 24, "#FBF1F1", ACCENT, 5, 0.9)
    f.text(410, y5 + 18, "人工确认", 9.4, ACCENT)
    f.text(410, y5 + 38, "采纳／调整／不采纳", 8.2, GRAY)
    f.path(f"M354,{y5 + 14} L360,{y5 + 14}", ACCENT, 0.9, "3 2", head=False)

    y7 = y0 + 6 * (hh + gap)
    y3 = y0 + 2 * (hh + gap)
    f.elbow([(44, y7 + hh / 2), (24, y7 + hh / 2), (24, y3 + hh / 2), (42, y3 + hh / 2)],
            SECOND, 1.0, "5 3")
    f.text(250, h - 10, "七步都留下可核对记录；下一周期从复盘后的建档开始，回环不跳过结果回填", 9.0, GRAY)
    return f, h


def fig_3_4():
    h = 296
    f = Fig(W, h)
    # ① 成本参数 → 临界比
    f.rect(10, 12, 480, 66, WHITE, BORDER, 6, 0.9)
    f.text(26, 32, "① 成本参数与临界比", 9.6, PRIMARY, anchor="start", bold=True)
    params = [("售价 p", "13.0"), ("单位成本 c", "5.2"), ("剩余净损失 o", "1.30"), ("缺货损失 l", "10.14")]
    for i, (k, v) in enumerate(params):
        x = 26 + i * 82
        f.text(x, 50, k, 8.8, GRAY, anchor="start")
        f.text(x, 68, v, 11.2, INK, anchor="start", bold=True)
    f.path("M360,44 L386,44", PRIMARY, 1.0)
    f.rect(390, 24, 92, 38, LIGHT, PRIMARY, 6, 1.0)
    f.text(436, 40, "ρ = 0.886", 11.4, PRIMARY, bold=True)
    f.text(436, 54, "10.14 ÷ 11.44", 7.8, GRAY)

    # ② 区间上取分位
    f.rect(10, 88, 480, 74, WHITE, BORDER, 6, 0.9)
    f.text(26, 106, "② 在参考区间上按 ρ 取分位", 9.6, PRIMARY, anchor="start", bold=True)
    bx0, bx1, by = 66, 330, 140
    f.raw(f'<rect x="{bx0}" y="{by - 3}" width="{bx1 - bx0}" height="6" fill="{SECOND}" fill-opacity="0.30"/>')
    f.line(bx0, by, bx0, by + 7, SECOND, 1.0, head=False)
    f.line(bx1, by, bx1, by + 7, SECOND, 1.0, head=False)
    f.text(bx0, by + 20, "64", 9.6, SECOND, bold=True)
    f.text(bx1, by + 20, "97", 9.6, SECOND, bold=True)
    f.text(bx0, by - 12, "销量参考区间（校准后）", 9.0, SECOND, anchor="start")
    px = 380
    f.raw(f'<circle cx="{px}" cy="{by}" r="6" fill="{PRIMARY}"/>')
    f.text(px, by + 20, "100", 10.2, PRIMARY, bold=True)
    f.text(px, by - 12, "建议量", 8.8, PRIMARY)
    f.text(412, by - 2, "ρ 高于上界时", 8.4, GRAY, anchor="start")
    f.text(412, by + 10, "允许略高于上界", 8.4, GRAY, anchor="start")

    # ③ 约束裁剪
    f.rect(10, 170, 480, 96, WHITE, BORDER, 6, 0.9)
    f.text(26, 188, "③ 约束逐级裁剪为计划量", 9.6, PRIMARY, anchor="start", bold=True)
    f.text(52, 212, "建议量", 8.8, GRAY, anchor="end")
    f.raw(f'<rect x="60" y="198" width="380" height="18" fill="{PRIMARY}" fill-opacity="0.16" stroke="{PRIMARY}" stroke-width="0.9"/>')
    f.text(74, 211, "100", 9.6, PRIMARY, anchor="start", bold=True)
    f.text(52, 244, "计划量", 8.8, GRAY, anchor="end")
    f.raw(f'<rect x="60" y="230" width="312" height="18" fill="{SECOND}" fill-opacity="0.20" stroke="{SECOND}" stroke-width="0.9"/>')
    f.text(74, 243, "首批 82", 9.6, SECOND, anchor="start", bold=True)
    f.raw(f'<rect x="372" y="230" width="68" height="18" fill="{SECOND}" fill-opacity="0.10" stroke="{SECOND}" stroke-width="0.9" stroke-dasharray="3 2"/>')
    f.text(406, 243, "补餐 18", 9.0, SECOND)
    f.text(60, 262, "额度压到 50 时：计划 50，缺口 50；缺口不等于已经发生的缺货", 8.6, ACCENT, anchor="start")

    f.text(250, 288, "临界比决定取哪一分位，约束只削减数量；两者都不改变区间本身", 9.0, GRAY)
    return f, h


def fig_3_6():
    h = 216
    f = Fig(W, h)
    y = 110
    f.line(40, y, 452, y, "#8FA3B8", 1.2, head=False)
    pts = [(96, "预测值"), (188, "已确认计划"), (286, "实际制作"), (392, "实际售出")]
    for x, lab in pts:
        f.raw(f'<circle cx="{x}" cy="{y}" r="5" fill="{PRIMARY}"/>')
        f.text(x, y + 20, lab, 9.6, INK)

    f.path(f"M96,{y - 12} L96,{y - 28} L392,{y - 28} L392,{y - 12}", SECOND, 1.0, head=False)
    f.text(244, y - 34, "预测偏差 ＝ 实际售出 − 预测值", 9.4, SECOND)
    f.path(f"M188,{y + 28} L188,{y + 42} L286,{y + 42} L286,{y + 28}", PRIMARY, 1.0, head=False)
    f.text(237, y + 58, "执行偏差 ＝ 实际制作 − 已确认计划", 9.4, PRIMARY)

    f.rect(300, 20, 190, 44, "#FBF1F1", ACCENT, 6, 0.9)
    f.text(395, 38, "供给受限时：实际售出 ≠ 需求", 9.0, ACCENT)
    f.text(395, 53, "售罄造成的偏差不能算作预测错误", 8.4, ACCENT)
    f.path(f"M392,64 L392,{y - 8}", ACCENT, 0.9, "4 3")
    f.text(250, h - 10, "两个偏差用同一套记录算，却回答不同问题：预测准不准、执行偏没偏", 8.8, GRAY)
    return f, h


def main():
    for name, fn in (("图3-1", fig_3_1), ("图3-4", fig_3_4), ("图3-6", fig_3_6)):
        f, h = fn()
        render(f.html(), os.path.join(OUT, name + ".png"), W, h, OUT)
        print("ok", name)


if __name__ == "__main__":
    main()