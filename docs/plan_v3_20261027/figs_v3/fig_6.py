# -*- coding: utf-8 -*-
"""图5-5 试点路径；图6-1 转化漏斗；图6-2 竞争定位；图7-1 付费与角色；图8-1 部署泳道；图10-1 甘特。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_lib import (ACCENT, BORDER, GRAY, INK, LIGHT, LIGHT2, PRIMARY, SECOND, W,
                     WHITE, Fig, render)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
GRID = "#E6EBF1"


def fig_5_5():
    h = 226
    f = Fig(W, h)
    stages = [
        ("单档口影子运行", "只记录不建议", "2—3 周"),
        ("小范围并跑", "建议与实做并行", "3—4 周"),
        ("单档口试点", "建议直接进备餐单", "4—6 周"),
        ("单校复制", "多档口、复盘入例会", "1 学期"),
    ]
    x = 14
    w = 108
    for i, (name, sub, dur) in enumerate(stages):
        f.rect(x, 60, w, 56, WHITE, BORDER, 6, 1.0)
        f.text(x + w / 2, 80, name, 10.2, INK, bold=True)
        f.text(x + w / 2, 96, sub, 8.2, GRAY)
        f.text(x + w / 2, 110, dur, 8.2, SECOND)
        if i < 3:
            f.arrow(x + w + 2, 88, x + w + 12, 88, PRIMARY, 1.0)
        x += w + 14

    # 门槛与退出
    y = 140
    f.path("M14,132 L486,132", BORDER, 0.8, "3 2", head=False)
    f.text(20, 152, "每级门槛（不达标停在本级，不进下一级）", 8.6, PRIMARY, anchor="start", bold=True)
    gates = ["连续 10 个营业日记录完整", "建议采纳率 ≥ 60%", "无食品安全与投诉事件", "校方书面同意扩面"]
    for i, g in enumerate(gates):
        cx = 16 + i * 119
        f.rect(cx, 160, 112, 22, LIGHT, BORDER, 4, 0.8)
        f.text(cx + 56, 174, g, 7.6, INK)
    f.text(250, 206, "第 1 级只读书不写字：把台账补齐，不改变任何人的动作", 8.6, GRAY)
    return f, h


def fig_6_1():
    h = 214
    f = Fig(W, h)
    cx = 186
    rows = [
        ("接触人数（估算，非实测）", "—", 220, LIGHT2),
        ("进入演示", "约 40%", 172, LIGHT),
        ("完成影子运行", "约 15%", 120, "#DCE7F1"),
        ("进入付费试点", "约 6%", 74, "#C6D8E8"),
    ]
    y = 26
    for name, rate, w, fill in rows:
        f.raw(f'<rect x="{cx - w / 2}" y="{y}" width="{w}" height="34" fill="{fill}" stroke="{BORDER}" stroke-width="0.9"/>')
        f.text(cx, y + 22, name, 9.0, INK)
        if rate != "—":
            f.text(cx + w / 2 + 8, y + 22, rate, 9.0, PRIMARY, anchor="start")
        y += 40

    f.rect(346, 26, 142, 118, WHITE, BORDER, 5, 0.9)
    f.text(356, 44, "单校可用规模", 8.8, PRIMARY, anchor="start", bold=True)
    for i, t in enumerate(["档口 4 个（现网实测）", "日均台账 7 条", "订阅 99—199 元/月", "客单价 1800—2500 元"]):
        f.text(356, 62 + i * 19, t, 7.6, INK, anchor="start")

    f.rect(346, 152, 142, 42, "#FBF1F1", ACCENT, 5, 0.9)
    f.text(356, 168, "验收口径：台账完整率", 7.4, ACCENT, anchor="start")
    f.text(356, 182, "与采纳率，不以人数计", 7.4, ACCENT, anchor="start")

    f.text(250, 206, "漏斗是获客假设，不是统计结果；任何一档填实数字前都标“待验证”", 8.6, GRAY)
    return f, h

def fig_6_2():
    h = 248
    f = Fig(W, h)
    cx, cy = 250, 122
    x0, x1, y0, y1 = 60, 442, 44, 200

    f.path(f"M{x0},{cy} L{x1},{cy}", "#B9C6D4", 1.0, head=False)
    f.path(f"M{cx},{y0} L{cx},{y1}", "#B9C6D4", 1.0, head=False)
    f.text(x1, cy - 9, "决策深度 →", 8.0, GRAY, anchor="end")
    f.text(cx + 6, y0 + 10, "↑ 与校园经营的贴合度", 8.0, GRAY, anchor="start")

    quads = [
        (64, 56, "记录型：智慧食堂硬件、POS", "start", GRAY),
        (438, 56, "决策型：本项目", "end", PRIMARY),
        (64, 192, "报表型：通用 BI、Excel 台账", "start", GRAY),
        (438, 192, "流程型：社会餐饮排班、采购 SaaS", "end", GRAY),
    ]
    for x, y, t, anc, col in quads:
        f.text(x, y, t, 8.0, col, anchor=anc, bold=(col == PRIMARY))

    # 本项目标记
    px, py = 330, 92
    f.raw(f'<circle cx="{px}" cy="{py}" r="7" fill="{PRIMARY}"/>')
    f.raw(f'<circle cx="{px}" cy="{py}" r="13" fill="none" stroke="{PRIMARY}" stroke-width="0.8" stroke-opacity="0.35"/>')
    f.text(px + 18, py - 4, "食刻有数", 10.4, PRIMARY, bold=True, anchor="start")
    f.text(px + 18, py + 12, "中档口 · 备餐量", 8.0, PRIMARY, anchor="start")
    f.text(px + 18, py + 26, "区间＋成本＋约束，可重放", 7.4, GRAY, anchor="start")

    # 竞品落点
    f.raw(f'<circle cx="150" cy="88" r="4" fill="{GRAY}"/>')
    f.text(150, 76, "智慧食堂", 7.6, GRAY)
    f.raw(f'<circle cx="300" cy="158" r="4" fill="{GRAY}"/>')
    f.text(300, 174, "餐饮 SaaS", 7.6, GRAY)

    f.text(250, 216, "坐标是相对判断，不是打分；没有任何一处写“已优于竞品”", 8.4, GRAY)
    f.text(250, 232, "本图只说明一件事：我们把资源压在“备餐量”这一个决策上，并且把它做到可核对", 8.4, GRAY)
    return f, h

def fig_7_1():
    h = 200
    f = Fig(W, h)
    boxes = [
        ("学校／后勤", "采购与准入", "按校立项或年度服务采购", "买“可核对的减损与合规记录”", ACCENT),
        ("档口经营者", "订阅制", "99—199 元/月 · 档口", "买“明天备多少”的一个答案", PRIMARY),
        ("平台运营", "服务费", "按服务档口数结算", "承担交付与运维，收服务费", SECOND),
    ]
    x = 14
    for name, mode, price, why, col in boxes:
        f.rect(x, 28, 152, 104, WHITE, col, 6, 1.1)
        f.text(x + 76, 50, name, 10.4, INK, bold=True)
        f.text(x + 76, 70, mode, 9.4, col, bold=True)
        f.text(x + 76, 88, price, 7.8, GRAY)
        f.text(x + 76, 104, why, 7.8, INK)
        f.text(x + 76, 122, "尚未签约", 7.8, ACCENT)
        x += 162

    f.path("M14,152 L486,152", BORDER, 0.8, "3 2", head=False)
    f.text(250, 170, "收入结构按“档口订阅为主、学校项目为辅”设计；三项都还没签，正文只写假设与验证方式", 8.6, GRAY)
    f.text(250, 188, "不承诺分成比例，不写“已获投资”，不把意向当订单", 8.6, GRAY)
    return f, h

def fig_8_1():
    h = 262
    f = Fig(W, h)
    lanes = ["校方", "食堂运营方", "档口", "项目组"]
    ys = [34, 76, 118, 160]
    tx0, tw = 88, 56

    # 周次网格
    for w in range(0, 7):
        x = tx0 + w * tw
        f.path(f"M{x},26 L{x},204", GRID, 0.6, head=False)
        f.text(x, 20, f"W{w}", 7.4, GRAY)

    for i, (name, y) in enumerate(zip(lanes, ys)):
        f.rect(10, y, 64, 34, LIGHT if i % 2 == 0 else WHITE, BORDER, 4, 0.8)
        f.text(42, y + 21, name, 9.0, PRIMARY, bold=True)

    tasks = [
        (0, 0.0, 1.4, "立项与授权", "书面同意"),
        (0, 5.0, 1.3, "中期评估", ""),
        (1, 0.4, 1.8, "开放台账接口", ""),
        (1, 4.4, 1.0, "异常处置", ""),
        (2, 1.0, 1.4, "历史台账整理", ""),
        (2, 2.7, 1.4, "影子运行", ""),
        (2, 4.4, 1.4, "并跑校验", ""),
        (3, 0.0, 1.2, "环境部署", ""),
        (3, 1.3, 1.4, "模型接入", ""),
        (3, 3.4, 2.8, "复盘例会", "每两周"),
    ]
    for lane, start, span, name, note in tasks:
        x = tx0 + start * tw
        w = span * tw
        f.raw(f'<rect x="{x}" y="{ys[lane] + 4}" width="{w}" height="26" rx="4" fill="{SECOND}" fill-opacity="0.15" stroke="{SECOND}" stroke-width="0.9"/>')
        f.text(x + w / 2, ys[lane] + 21, name, 7.8, INK)
        if note:
            f.text(x + w + 4, ys[lane] + 21, note, 7.0, GRAY, anchor="start")

    f.text(250, 218, "泳道只写谁在什么时候做什么；对外承诺以校方书面节点为准，未排期的不写死日期", 8.4, GRAY)
    f.text(250, 236, "横轴为相对周次（W0 起），不代表已经排定", 8.4, GRAY)
    return f, h


def fig_10_1():
    h = 246
    f = Fig(W, h)
    tx0, tw = 132, 66
    for i in range(6):
        x = tx0 + i * tw
        f.path(f"M{x},32 L{x},188", GRID, 0.6, head=False)
        if i < 5:
            f.text(x + tw / 2, 24, f"T{i + 1}", 7.8, GRAY)

    rows = [
        ("已完成", 0.0, 1.4, PRIMARY, "代码与文档"),
        ("进行中", 0.9, 1.6, SECOND, "计划书整合"),
        ("里程碑", 2.6, 0.0, ACCENT, "提交"),
        ("待启动", 3.2, 1.6, GRAY, "校级准入"),
    ]
    for i, (lane, start, span, col, label) in enumerate(rows):
        y = 44 + i * 36
        f.text(122, y + 16, lane, 8.6, INK, anchor="end")
        x = tx0 + start * tw
        if span == 0:
            f.raw('<path d="M{x},{yy} l10,10 l-10,10 l-10,-10 z" fill="{col}"/>'.format(x=x, yy=y + 6, col=col))
            f.text(x + 16, y + 20, label, 8.0, ACCENT, anchor="start")
        else:
            w = span * tw
            f.raw(f'<rect x="{x}" y="{y + 4}" width="{w}" height="24" rx="4" fill="{col}" fill-opacity="0.18" stroke="{col}" stroke-width="1.0"/>')
            f.text(x + w / 2, y + 20, label, 8.0, INK)

    f.path(f"M{tx0},188 L{tx0 + 5 * tw},188", "#8FA3B8", 0.9, head=False)
    f.text(tx0 + 1 * tw, 200, "提交前", 7.6, GRAY)
    f.text(tx0 + 4 * tw, 200, "提交后", 7.6, GRAY)
    f.text(250, 220, "相对时间轴：T1—T3 为提交前，T4—T5 为提交后；不写具体日期", 8.4, GRAY)
    f.text(250, 236, "“待启动”指尚未获得校方书面同意，不是已经排期", 8.4, GRAY)
    return f, h

def main():
    for name, fn in (("图5-5", fig_5_5), ("图6-1", fig_6_1), ("图6-2", fig_6_2),
                     ("图7-1", fig_7_1), ("图8-1", fig_8_1), ("图10-1", fig_10_1)):
        f, h = fn()
        render(f.html(), os.path.join(OUT, name + ".png"), W, h, OUT)
        print("ok", name)


if __name__ == "__main__":
    main()