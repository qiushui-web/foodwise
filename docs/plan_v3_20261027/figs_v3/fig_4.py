# -*- coding: utf-8 -*-
"""图4-1 数据流；图4-2 引擎与证据链；图4-4 系统分层。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_lib import (ACCENT, BORDER, GRAY, INK, LIGHT, LIGHT2, PRIMARY, SECOND, W,
                     WHITE, Fig, render)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def fig_4_1():
    h = 214
    f = Fig(W, h)
    segs = [
        ("台账", "日期·餐次·菜品", "ledger.csv", "原始记录"),
        ("特征", "滞后·星期·天气", "features.parquet", "清洗后"),
        ("模型", "分位＋CQR 校准", "model.joblib", "可训练"),
        ("区间", "80% 参考区间", "metrics.json", "可解释"),
        ("决策", "临界比＋约束", "decision.json", "可重放"),
    ]
    w, gap = 80, 14
    x0 = 14
    centers = []
    for i, (name, sub, out, _) in enumerate(segs):
        x = x0 + i * (w + gap)
        centers.append(x + w / 2)
        f.rect(x, 54, w, 46, WHITE, BORDER, 6, 1.0)
        f.text(x + w / 2, 74, name, 11.2, INK, bold=True)
        f.text(x + w / 2, 89, sub, 7.8, GRAY)
        f.text(x + w / 2, 116, out, 7.8, SECOND)
        if i < 4:
            f.arrow(x + w + 2, 77, x + w + gap - 2, 77, PRIMARY, 1.0)

    # 兜底旁路
    f.rect(200, 146, 116, 24, "#FBF1F1", ACCENT, 4, 0.9, "4 3")
    f.text(258, 162, "规则基线（兜底）", 8.6, ACCENT)
    f.path(f"M{centers[2]},100 L{centers[2]},146", ACCENT, 0.9, "4 3", head=False)
    f.path("M316,158 L480,158 L480,77 L473,77", ACCENT, 0.9, "4 3")

    f.path("M14,182 L486,182", BORDER, 0.8, "3 2", head=False)
    for cx, (_, _, _, lab) in zip(centers, segs):
        f.text(cx, 198, lab, 8.6, GRAY)

    f.text(250, 30, "每一段都有可打开的产物文件；校验不通过时走兜底旁路，而不是继续往下走", 9.0, GRAY)
    return f, h


def fig_4_2():
    h = 268
    f = Fig(W, h)
    f.rect(10, 26, 150, 116, LIGHT2, BORDER, 6, 0.9)
    f.text(85, 44, "离线（Python）", 9.4, PRIMARY, bold=True)
    for i, t in enumerate(["训练分位模型", "分层 CQR 校准", "导出指标 JSON", "写 manifest（sha256）"]):
        f.rect(22, 54 + i * 21, 126, 17, WHITE, BORDER, 3, 0.8)
        f.text(85, 66 + i * 21, t, 8.4, INK)

    f.raw(f'<path d="M250,72 L282,100 L250,128 L218,100 z" fill="{WHITE}" stroke="{PRIMARY}" stroke-width="1.1"/>')
    f.text(250, 104, "启动校验", 9.0, PRIMARY, bold=True)
    f.text(250, 62, "类型·哈希·版本", 8.2, GRAY)

    f.rect(330, 26, 160, 116, WHITE, BORDER, 6, 0.9)
    f.text(410, 44, "在线（Java）", 9.4, PRIMARY, bold=True)
    eng = [("calibrated-quantile", "默认"), ("quantile", "对照"), ("rule", "兜底")]
    for i, (e, tag) in enumerate(eng):
        f.rect(340, 54 + i * 28, 140, 22, WHITE if i else LIGHT, PRIMARY if i == 0 else BORDER, 4, 1.0 if i == 0 else 0.8)
        f.text(408, 69 + i * 28, e, 8.2, PRIMARY if i == 0 else INK)
        f.text(472, 69 + i * 28, tag, 7.8, GRAY, anchor="end")

    f.path("M160,100 L214,100", PRIMARY, 1.0)
    f.path("M284,100 L338,100", PRIMARY, 1.0)
    f.text(187, 92, "产物＋清单", 8.0, GRAY)
    f.text(311, 92, "通过", 8.2, PRIMARY)

    # 拒绝分支：直接落到 rule 行
    f.path("M250,128 L250,150 L340,150 L340,124", ACCENT, 1.0)
    f.text(258, 145, "拒绝 → 直接用 rule", 8.4, ACCENT, anchor="start")

    # 证据链
    f.rect(10, 176, 480, 66, WHITE, BORDER, 6, 0.9)
    f.text(22, 194, "证据链：写记录 → 重放重算 → 逐字段比对", 9.0, PRIMARY, anchor="start", bold=True)
    chain = [("决策记录 /api/v1/decisions", 122), ("重放 /{id}/replay", 118), ("逐字段比对", 86)]
    x = 22
    for i, (t, wid) in enumerate(chain):
        f.rect(x, 204, wid, 22, LIGHT, BORDER, 4, 0.8)
        f.text(x + wid / 2, 218, t, 8.0, INK)
        if i < 2:
            f.arrow(x + wid + 2, 215, x + wid + 12, 215, PRIMARY, 0.9)
        x += wid + 14
    f.path(f"M{x - 14},215 L{x + 2},215", BORDER, 0.9, "3 2", head=False)
    f.rect(x + 6, 198, 74, 18, WHITE, BORDER, 3, 0.8)
    f.text(x + 43, 211, "一致", 8.0, PRIMARY)
    f.rect(x + 6, 220, 74, 18, "#FBF1F1", ACCENT, 3, 0.8)
    f.text(x + 43, 233, "差异 → 报警", 8.0, ACCENT)

    f.text(250, 258, "不做静默降级：任一环节不通过，页面上必须看得到降级后的引擎名与原因", 8.8, GRAY)
    return f, h


def fig_4_4():
    h = 236
    f = Fig(W, h)
    layers = [
        ("表现层", "Vue 3 · TypeScript · Vite", "SPA /app/**　单页部署，含证据与复现页"),
        ("接口层", "Spring Boot 3 · Java 21", "REST /api/v1　鉴权、留痕、幂等"),
        ("模型层", "三档引擎 ＋ 清单门禁", "默认校准档，失败退回规则基线"),
        ("数据层", "H2 / MySQL ＋ Flyway", "迁移失败即中止启动，不半启动"),
    ]
    y = 22
    for i, (name, tech, note) in enumerate(layers):
        f.rect(20, y, 406, 40, LIGHT if i % 2 == 0 else WHITE, BORDER, 5, 0.9)
        f.text(36, y + 17, name, 10.6, PRIMARY, anchor="start", bold=True)
        f.text(36, y + 32, tech, 8.4, GRAY, anchor="start")
        f.text(412, y + 24, note, 8.2, INK, anchor="end")
        if i < 3:
            f.arrow(223, y + 40, 223, y + 47, PRIMARY, 0.9)
        y += 48

    f.rect(438, 20, 52, 86, LIGHT2, BORDER, 5, 0.8, "3 2")
    f.text(464, 42, "离线", 8.6, PRIMARY, bold=True)
    f.text(464, 58, "训练与", 7.8, GRAY)
    f.text(464, 70, "产物导出", 7.8, GRAY)
    f.path("M438,64 L428,64 L428,132 L420,132", PRIMARY, 0.9, "4 3")

    f.rect(20, 212, 470, 26, WHITE, BORDER, 4, 0.8)
    f.text(28, 229, "单一可部署包　·　端口 8089　·　profile：local / local-persistent / mysql", 8.4, INK, anchor="start")
    return f, h


def main():
    for name, fn in (("图4-1", fig_4_1), ("图4-2", fig_4_2), ("图4-4", fig_4_4)):
        f, h = fn()
        render(f.html(), os.path.join(OUT, name + ".png"), W, h, OUT)
        print("ok", name)


if __name__ == "__main__":
    main()