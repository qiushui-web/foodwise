# -*- coding: utf-8 -*-
"""数据图：图4-3 覆盖率-宽度权衡；图5-1 区间指标；图5-2 决策指标；图5-3 归因；图9-1 财务情景。

数值全部来自 项目代码/modeling/data/03_output/*.json 与正文表格，不做任何平滑或改写。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_lib import (ACCENT, BORDER, GRAY, INK, LIGHT, LIGHT2, PRIMARY, SECOND, W,
                     WHITE, Fig, render)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
GRID = "#E6EBF1"
BAR = "#A8C0D8"


def axes(f, x0, y0, x1, y1, xticks, yticks, fmt=lambda v: f"{v:g}",
         xlabel="", ylabel="", yside="left"):
    """简易坐标轴：只画左轴刻度线与水平网格。"""
    for v in yticks:
        yy = y1 - (v - yticks[0]) / (yticks[-1] - yticks[0]) * (y1 - y0)
        f.path(f"M{x0},{yy} L{x1},{yy}", GRID, 0.7, head=False)
        f.text(x0 - 8, yy + 3, fmt(v), 7.8, GRAY, anchor="end")
    f.path(f"M{x0},{y0} L{x0},{y1} L{x1},{y1}", "#8FA3B8", 1.0, head=False)
    for v in xticks:
        xx = x0 + (v - xticks[0]) / (xticks[-1] - xticks[0]) * (x1 - x0)
        f.path(f"M{xx},{y1} L{xx},{y1 + 4}", "#8FA3B8", 0.9, head=False)
    if xlabel:
        f.text((x0 + x1) / 2, y1 + 34, xlabel, 8.4, GRAY)
    if ylabel:
        f.text(x0 - 8, y0 - 10, ylabel, 8.4, GRAY, anchor="end")


def fig_4_3():
    h = 232
    f = Fig(W, h)
    rows = [
        ("未校准", 57.7, 0.1278, 29.87, ACCENT),
        ("全局 CQR", 97.4, 0.2966, 19.75, SECOND),
        ("分层 CQR", 96.7, 0.2844, 19.01, PRIMARY),
    ]
    bx0, bx1 = 96, 344

    def px(v):
        return bx0 + v / 100 * (bx1 - bx0)

    f.text(bx0, 34, "实测覆盖率 PICP（%）", 8.2, GRAY, anchor="start")
    f.text(396, 34, "平均宽度／Winkler", 8.2, GRAY, anchor="start")
    f.path(f"M{bx0},44 L{bx0},190", "#8FA3B8", 0.9, head=False)
    for v in (0, 25, 50, 75, 100):
        f.path(f"M{px(v)},42 L{px(v)},44", "#8FA3B8", 0.0, head=False)

    # 90% 目标线
    f.path(f"M{px(90)},44 L{px(90)},196", ACCENT, 0.9, "5 3", head=False)
    f.text(px(90) + 4, 40, "90% 目标", 7.8, ACCENT, anchor="start")

    for i, (name, picp, pinaw, wink, col) in enumerate(rows):
        y = 56 + i * 46
        best = name == "分层 CQR"
        f.text(bx0 - 10, y + 15, name, 9.0, PRIMARY if best else INK, anchor="end", bold=best)
        f.raw(f'<rect x="{bx0}" y="{y}" width="{px(picp) - bx0}" height="22" fill="{col}" fill-opacity="{0.9 if best else 0.55}"/>')
        f.text(px(picp) + 6, y + 15, f"{picp:.1f}%", 8.6, PRIMARY if best else INK, anchor="start", bold=True)
        f.text(396, y + 11, f"宽 {pinaw:.4f}", 7.8, GRAY, anchor="start")
        f.text(396, y + 23, f"Winkler {wink:.2f}", 7.8, GRAY, anchor="start")

    f.text(250, 214, "同一测试集 390 行：校准把覆盖从 57.7% 提到 96.7%，代价是宽度由 0.128 增至 0.284", 8.6, GRAY)
    return f, h

def fig_5_1():
    h = 258
    f = Fig(W, h)
    data = [
        ("未校准", 57.7, 0.128),
        ("全局 CQR", 97.4, 0.297),
        ("分层 CQR", 96.7, 0.284),
        ("分层+ACI", 96.7, 0.285),
        ("滚动", 96.4, 0.285),
        ("滚动+ACI", 95.9, 0.277),
        ("滑窗", 92.6, 0.256),
    ]
    x0, y0, x1, y1 = 58, 46, 452, 186
    bw, gap = 34, 20

    def py(v):
        return y1 - v / 100 * (y1 - y0)

    for v in (0, 25, 50, 75, 100):
        f.path(f"M{x0},{py(v)} L{x1},{py(v)}", GRID, 0.7, head=False)
        f.text(x0 - 8, py(v) + 3, f"{v}", 7.8, GRAY, anchor="end")
    f.path(f"M{x0},{y0} L{x0},{y1} L{x1},{y1}", "#8FA3B8", 1.0, head=False)

    # 90% 名义线
    f.path(f"M{x0},{py(90)} L{x1},{py(90)}", ACCENT, 0.9, "5 3", head=False)
    f.text(x0 + 4, py(90) - 7, "名义覆盖 90%", 8.0, ACCENT, anchor="start")

    pts = []
    for i, (name, picp, pinaw) in enumerate(data):
        x = x0 + 14 + i * (bw + gap)
        top = py(picp)
        best = name == "分层 CQR"
        f.raw(f'<rect x="{x}" y="{top}" width="{bw}" height="{y1 - top}" fill="{PRIMARY if best else BAR}" '
              f'fill-opacity="{0.9 if best else 0.85}" stroke="none"/>')
        f.text(x + bw / 2, top - 5, f"{picp:.1f}", 8.4, PRIMARY if best else INK, bold=best)
        for j, seg in enumerate(name.split("+")):
            f.text(x + bw / 2, y1 + 15 + j * 11, ("+" if j else "") + seg, 7.8, INK)
        pts.append((x + bw / 2, pinaw))

    # PINAW 线（右轴 0–0.32）
    def ry(v):
        return y1 - v / 0.32 * (y1 - y0)
    for i in range(len(pts) - 1):
        f.path(f"M{pts[i][0]},{ry(pts[i][1])} L{pts[i + 1][0]},{ry(pts[i + 1][1])}", ACCENT, 1.0, head=False)
    for cx, v in pts:
        f.raw(f'<circle cx="{cx}" cy="{ry(v)}" r="3.2" fill="{WHITE}" stroke="{ACCENT}" stroke-width="1.2"/>')

    for v in (0.0, 0.16, 0.32):
        f.text(x1 + 6, ry(v) + 3, f"{v:.2f}", 7.2, ACCENT, anchor="start")
    f.text(x0 - 8, y0 - 8, "覆盖率 PICP（%）", 8.2, GRAY, anchor="start")
    f.text(250, 232, "■ 覆盖率 PICP（左轴 0–100%）　○— 平均区间宽度 PINAW（右轴 0–0.32，越低越窄）", 8.2, GRAY)
    f.text(250, 248, "分层 CQR 在覆盖达标的前提下把宽度压到 0.2844；未校准的“窄”是漏出来的", 8.4, GRAY)
    return f, h


def fig_5_2():
    """最新观察受限策略仿真：把低剩余与高缺货同时画出。"""
    h = 340
    f = Fig(W, h)
    scenarios = [
        ("基线", [("历史惯性", 53.495, 5.54, 22.17), ("固定+10%", 48.489, 4.36, 26.50), ("残差分位", 76.707, 2.16, 55.87)]),
        ("校园活动", [("历史惯性", 53.307, 5.52, 21.91), ("固定+10%", 48.219, 4.35, 26.72), ("残差分位", 69.438, 2.22, 50.79)]),
        ("雨天缩放", [("历史惯性", 54.735, 5.66, 21.99), ("固定+10%", 49.018, 4.43, 26.44), ("残差分位", 76.107, 2.21, 55.40)]),
        ("高波动压力", [("历史惯性", 95.016, 5.58, 35.35), ("固定+10%", 88.480, 4.75, 41.07), ("残差分位", 124.791, 2.55, 64.31)]),
    ]
    left, top, panel_w, panel_h, gap_x, gap_y = 18, 30, 226, 130, 12, 14
    for pi, (scenario, rows) in enumerate(scenarios):
        col, row = pi % 2, pi // 2
        x0 = left + col * (panel_w + gap_x)
        y0 = top + row * (panel_h + gap_y)
        f.text(x0 + 4, y0 + 10, scenario, 9.2, PRIMARY if pi == 0 else INK, anchor="start", bold=True)
        f.text(x0 + 90, y0 + 10, "regret/100", 7.4, GRAY, anchor="start")
        f.text(x0 + 168, y0 + 10, "余%", 7.4, GRAY)
        f.text(x0 + 203, y0 + 10, "缺%", 7.4, GRAY)
        f.path(f"M{x0},{y0 + 16} L{x0 + panel_w},{y0 + 16}", BORDER, 0.7, head=False)
        for v in (0, 60, 120):
            gx = x0 + 94 + v / 150 * 66
            f.path(f"M{gx},{y0 + 19} L{gx},{y0 + 121}", GRID, 0.6, head=False)
        for i, (name, regret, waste, stockout) in enumerate(rows):
            yy = y0 + 37 + i * 27
            bx = x0 + 94
            bh = max(0, regret) / 150 * 66
            col = PRIMARY if name == "固定+10%" else (ACCENT if name == "残差分位" else BAR)
            f.text(x0 + 4, yy + 8, ["历史惯性", "固定 +10%", "残差分位"][i], 8.0, INK)
            f.raw(f'<rect x="{bx}" y="{yy}" width="{bh}" height="13" fill="{col}" fill-opacity="0.9"/>')
            f.text(x0 + 164, yy + 10, f"{waste:.2f}", 7.6, GRAY)
            f.text(x0 + 203, yy + 10, f"{stockout:.2f}", 7.6, ACCENT if stockout > 40 else GRAY)
            f.text(bx + bh + 4, yy + 10, f"{regret:.1f}", 7.4, col, anchor="start", bold=(name == "固定+10%"))
    f.text(250, 326, "每情景 20 个随机种子、每次 90 天；三项均为合成仿真指标，不是校园实测", 8.2, GRAY)
    return f, h


def fig_5_3():
    h = 236
    f = Fig(W, h)
    x0, x1, y = 62, 452, 100
    lo, hi = -12.0, 4.0

    def px(v):
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    f.path(f"M{x0},{y} L{x1},{y}", "#8FA3B8", 1.0, head=False)
    for v in (-12, -10, -8, -6, -4, -2, 0, 2, 4):
        f.path(f"M{px(v)},{y} L{px(v)},{y + 4}", "#8FA3B8", 0.8, head=False)
        f.text(px(v), y + 15, f"{v}", 7.8, GRAY)
    f.text((x0 + x1) / 2, y + 28, "每百份剩余率变化（百分点）", 8.2, GRAY)
    f.path(f"M{px(0)},{y - 30} L{px(0)},{y + 4}", GRAY, 0.9, "4 3", head=False)

    est, se = -9.31, 1.34
    a, b = est - 1.96 * se, est + 1.96 * se
    f.raw(f'<line x1="{px(a)}" y1="{y}" x2="{px(b)}" y2="{y}" stroke="{PRIMARY}" stroke-width="2.6"/>')
    for v in (a, b):
        f.path(f"M{px(v)},{y - 7} L{px(v)},{y + 7}", PRIMARY, 1.8, head=False)
    f.raw(f'<circle cx="{px(est)}" cy="{y}" r="5.5" fill="{PRIMARY}"/>')
    f.text(px(est), y - 26, "负对照（期内无干预）", 8.2, GRAY)
    f.text(px(est), y - 12, "−9.31pp（SE 1.34）", 8.6, PRIMARY, bold=True)

    # MDE 标尺
    ym = 56
    f.path(f"M{px(-6.46)},{ym} L{px(0)},{ym}", SECOND, 1.0, head=False)
    for v in (-6.46, 0):
        f.path(f"M{px(v)},{ym - 4} L{px(v)},{ym + 4}", SECOND, 1.0, head=False)
    f.path(f"M{px(0)},{ym + 4} L{px(0)},{y - 32}", BORDER, 0.8, "3 2", head=False)
    f.text(px(-3.2), ym - 9, "本窗口 MDE 6.46pp", 8.2, SECOND)

    # 左：台账事实
    f.rect(10, 138, 268, 62, "#FBF1F1", ACCENT, 5, 0.9)
    f.text(22, 156, "真实台账 14 个营业日，期内无任何干预", 8.2, ACCENT, anchor="start")
    f.text(22, 172, "负对照落在 −9.3pp：趋势估计不可用于宣称效果", 8.2, ACCENT, anchor="start")
    f.text(22, 188, "识别 5pp 效应约需 35 个营业日", 8.2, ACCENT, anchor="start")

    # 右：安慰剂
    f.rect(300, 138, 188, 62, WHITE, BORDER, 5, 0.9)
    f.text(312, 155, "安慰剂误报率（60 次重复）", 8.0, GRAY, anchor="start")
    f.text(312, 172, "ITS　10%", 9.0, INK, anchor="start")
    f.text(394, 172, "BSTS　15%", 9.0, INK, anchor="start")
    f.text(312, 189, "名义 5%；两种方法均偏高", 8.0, ACCENT, anchor="start")

    f.text(250, 224, "一个“显著”的点估计，在没有干预的窗口里只能算偏差，不能当作减损证据", 8.6, GRAY)
    return f, h

def fig_9_1():
    h = 244
    f = Fig(W, h)
    years = ["第 1 年", "第 2 年", "第 3 年"]
    rev = [1.8, 11.0, 35.0]
    prof = [-1.4, 0.25, 9.2]
    x0, y0, x1, y1 = 66, 40, 440, 176

    def py(v):
        return y0 + (40 - v) / 45 * (y1 - y0)

    for v in (-5, 0, 10, 20, 30, 40):
        f.path(f"M{x0},{py(v)} L{x1},{py(v)}", GRID if v else "#8FA3B8", 0.7 if v else 1.0, head=False)
        f.text(x0 - 8, py(v) + 3, f"{v}", 7.8, GRAY, anchor="end")

    for i, (yr, r, p) in enumerate(zip(years, rev, prof)):
        cx = x0 + 70 + i * 118
        f.raw(f'<rect x="{cx - 44}" y="{py(r)}" width="36" height="{py(0) - py(r)}" fill="{BAR}" fill-opacity="0.9"/>')
        f.text(cx - 26, py(r) - 5, f"{r:.1f}", 8.4, INK)
        py0, pp = py(0), py(p)
        top, bot = min(py0, pp), max(py0, pp)
        f.raw(f'<rect x="{cx + 6}" y="{top}" width="36" height="{bot - top}" fill="{PRIMARY if p > 0 else ACCENT}" fill-opacity="0.85"/>')
        f.text(cx + 24, (top - 5) if p > 0 else (bot + 11), f"{p:g}", 8.4, PRIMARY if p > 0 else ACCENT, bold=True)
        f.text(cx, y1 + 16, yr, 8.8, INK)

    f.text(x0 - 8, y0 - 10, "万元", 8.2, GRAY, anchor="end")
    f.raw(f'<rect x="300" y="18" width="10" height="10" fill="{BAR}"/>')
    f.text(316, 26, "营业收入", 8.2, INK, anchor="start")
    f.raw(f'<rect x="376" y="18" width="10" height="10" fill="{PRIMARY}"/>')
    f.text(392, 26, "净利润（亏损标红）", 8.2, INK, anchor="start")

    f.text(250, 206, "情景测算，不是订单；三档分别对应单校跑通、单校复制、区域拓展", 8.4, GRAY)
    f.text(250, 222, "第 2 年利润转正的关键是把单档口服务成本压到 500 元/月以内", 8.4, GRAY)
    return f, h


def main():
    for name, fn in (("图4-3", fig_4_3), ("图5-1", fig_5_1), ("图5-2", fig_5_2),
                     ("图5-3", fig_5_3), ("图9-1", fig_9_1)):
        f, h = fn()
        render(f.html(), os.path.join(OUT, name + ".png"), W, h, OUT)
        print("ok", name)


if __name__ == "__main__":
    main()
