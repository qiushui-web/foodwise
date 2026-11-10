# -*- coding: utf-8 -*-
"""图1-1 短保餐品的剩余与缺货双重损失。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_lib import (ACCENT, BORDER, GRAY, INK, LIGHT, LIGHT2, PRIMARY, SECOND, W,
                     WHITE, Fig, render)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def build():
    h = 258
    f = Fig(W, h)

    # 中心决策节点
    f.rect(175, 100, 150, 46, LIGHT, PRIMARY, 7, 1.2)
    f.text(250, 119, "备餐量决策", 13.5, PRIMARY, bold=True)
    f.text(250, 135, "一天一次 · 闭餐前不可逆", 9.3, GRAY)

    # 左链（过量侧）
    left = [("备餐过量", None), ("闭餐剩余", None), ("折价/报损", None), ("毛利损失", None)]
    ys = [24, 68, 112, 156]
    for i, ((t, s), y) in enumerate(zip(left, ys)):
        last = i == len(left) - 1
        f.box(8, y, 152, 30, t, s, "#FBF1F1" if last else WHITE, ACCENT if last else BORDER,
              ACCENT if last else INK, 11.5, bold=last)
    for i in range(3):
        f.arrow(84, ys[i] + 30, 84, ys[i + 1] - 1, PRIMARY if i < 2 else ACCENT, 1.0)

    # 右链（不足侧）
    right = ["备餐不足", "高峰售罄", "流失销售", "口碑损失"]
    for i, (t, y) in enumerate(zip(right, ys)):
        last = i == len(right) - 1
        f.box(340, y, 152, 30, t, None, "#FBF1F1" if last else WHITE, ACCENT if last else BORDER,
              ACCENT if last else INK, 11.5, bold=last)
    for i in range(3):
        f.arrow(416, ys[i] + 30, 416, ys[i + 1] - 1, PRIMARY if i < 2 else ACCENT, 1.0)

    # 决策 → 两侧
    f.elbow([(175, 112), (168, 112), (168, 39), (161, 39)], PRIMARY, 1.0)
    f.elbow([(325, 112), (332, 112), (332, 39), (339, 39)], PRIMARY, 1.0)

    # 约束总线
    f.path("M100,201 L400,201", BORDER, 0.9, "4 3", head=False)
    f.line(250, 201, 250, 147, PRIMARY, 0.9, "4 3")
    chips = ["保质期以小时计", "就餐时段集中", "单餐菜品有限"]
    xs = [66, 178, 290]
    for x, c in zip(xs, chips):
        f.rect(x, 210, 116, 22, WHITE, BORDER, 5, 0.9, "0")
        f.text(x + 58, 225, c, 9.6, INK)
        f.path(f"M{x + 58},210 L{x + 58},201", BORDER, 0.9, "4 3", head=False)

    f.text(250, 250, "两者并存，不是二选一；同一决策同时决定两侧损失", 9.4, GRAY)
    return f, h


fig_1_1 = build


def main():
    f, h = build()
    png = os.path.join(OUT, "图1-1.png")
    render(f.html(), png, W, h, OUT)
    print("ok", png)


if __name__ == "__main__":
    main()