# -*- coding: utf-8 -*-
"""图2-1 营业日四个决策时点；图2-2 三类角色与信息流向。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_lib import (ACCENT, BORDER, GRAY, INK, LIGHT, LIGHT2, PRIMARY, SECOND, W,
                     WHITE, Fig, render)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def fig_2_1():
    h = 224
    f = Fig(W, h)
    f.line(34, 112, 476, 112, "#8FA3B8", 1.2, head=True)

    nodes = [
        (78, "T1 备餐前", "历史台账／当日课表", "给出建议量与首批"),
        (190, "T2 开餐", "上餐进度／实时销量", "触发补餐判断"),
        (302, "T3 高峰", "剩余数量／售卖速度", "决定是否上优惠"),
        (414, "T4 闭餐后", "实际制作／售出剩余", "回填并进入复盘"),
    ]
    for x, tag, info, out in nodes:
        f.rect(x - 50, 30, 100, 42, WHITE, BORDER, 6, 0.9)
        f.text(x, 47, info.split("／")[0], 9.2, INK)
        f.text(x, 61, info.split("／")[1], 9.2, INK)
        f.raw(f'<circle cx="{x}" cy="112" r="5.5" fill="{PRIMARY}"/>')
        f.raw(f'<circle cx="{x}" cy="112" r="10.5" fill="none" stroke="{PRIMARY}" stroke-width="0.8" stroke-opacity="0.3"/>')
        f.text(x, 96, tag, 9.8, PRIMARY, bold=True)
        f.rect(x - 50, 132, 100, 34, LIGHT, BORDER, 6, 0.9)
        f.text(x, 153, out, 9.2, PRIMARY)
        f.line(x, 72, x, 100, BORDER, 0.9)
        f.line(x, 122, x, 131, BORDER, 0.9)

    f.path("M246,18 L246,196", ACCENT, 0.9, "4 3", head=False)
    f.text(243, 14, "此后才有事后结果", 9.2, ACCENT, anchor="end")
    f.text(120, 14, "只用事前可得信息", 9.2, PRIMARY)
    f.text(120, 186, "信息不足时给区间，不给单一答案", 8.8, GRAY)
    f.text(330, 186, "事后信息不得回填到事前建议", 8.8, GRAY)
    f.text(250, 212, "四个时点各自成立；把 T4 的数据提前用于 T1，等于用结果解释决策", 9.2, GRAY)
    return f, h


def fig_2_2():
    h = 280
    f = Fig(W, h)
    f.rect(176, 104, 148, 60, LIGHT, PRIMARY, 7, 1.3)
    f.text(250, 128, "食刻有数平台", 13.0, PRIMARY, bold=True)
    f.text(250, 146, "区间 · 计划 · 记录", 9.2, GRAY)

    f.rect(8, 26, 136, 44, WHITE, BORDER, 6, 1.0)
    f.text(76, 44, "档口负责人", 11.4, INK, bold=True)
    f.text(76, 59, "记录与执行", 9.0, GRAY)

    f.rect(356, 26, 136, 44, WHITE, BORDER, 6, 1.0)
    f.text(424, 44, "食堂运营方", 11.4, INK, bold=True)
    f.text(424, 59, "准入与监督", 9.0, GRAY)

    f.rect(176, 206, 148, 42, WHITE, BORDER, 6, 1.0)
    f.text(250, 224, "学生", 11.4, INK, bold=True)
    f.text(250, 239, "免费使用", 9.0, GRAY)

    # 1 档口 → 平台（台账与结果）
    f.elbow([(144, 48), (250, 48), (250, 102)], PRIMARY, 1.0)
    f.text_outlined(250, 40, "台账 · 成本 · 约束", 8.8, PRIMARY)
    # 2 平台 → 档口（建议）
    f.elbow([(176, 146), (96, 146), (96, 72)], SECOND, 1.0, "4 3", head=True)
    f.text_outlined(150, 142, "建议区间与数量", 8.8, SECOND)
    # 3 运营方 ⇢ 平台（授权与监督）
    f.elbow([(424, 70), (424, 134), (326, 134)], PRIMARY, 1.0, "4 3")
    f.text_outlined(376, 130, "授权·额度·异常", 8.6, PRIMARY)
    # 4 平台 → 学生
    f.line(210, 164, 210, 204, SECOND, 1.0)
    f.text_outlined(204, 190, "餐品与优惠", 8.8, SECOND, anchor="end")
    # 5 学生 → 平台
    f.line(292, 204, 292, 166, SECOND, 1.0, "4 3")
    f.text_outlined(298, 190, "预约·核销", 8.8, SECOND, anchor="start")

    f.text(250, 272, "运营方不替代学校许可或采购程序；学生数据只用于判断优惠是否挤占原价销售", 8.8, GRAY)
    return f, h

def main():
    for name, fn in (("图2-1", fig_2_1), ("图2-2", fig_2_2)):
        f, h = fn()
        render(f.html(), os.path.join(OUT, name + ".png"), W, h, OUT)
        print("ok", name)


if __name__ == "__main__":
    main()