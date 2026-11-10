# -*- coding: utf-8 -*-
"""删除示意图后重排章内图号，保证从 1 连续。"""
import re

BASE = r"E:\食刻有数\项目代码\docs\plan_v3_20261027"

# 第三章：图3-3 已删除，3-4..3-7 前移一位
MAP = {"图3-4": "图3-3", "图3-5": "图3-4", "图3-6": "图3-5", "图3-7": "图3-6"}

path = BASE + r"\content_1.py"
s = open(path, encoding="utf-8").read()
pat = re.compile("|".join(sorted(MAP, key=len, reverse=True)))
s2, n = pat.subn(lambda m: MAP[m.group(0)], s)
open(path, "w", encoding="utf-8").write(s2)
print("renamed", n, "occurrences")

# 校验连续性
for name in ("content_1.py", "content_2.py", "content_3.py"):
    txt = open(BASE + "\\" + name, encoding="utf-8").read()
    nos = re.findall(r'B\(\("fig", "图(\d+)-(\d+)"', txt)
    from collections import defaultdict
    ch = defaultdict(list)
    for a, b in nos:
        ch[a].append(int(b))
    for k in sorted(ch, key=int):
        v = ch[k]
        expect = list(range(1, len(v) + 1))
        print(name, "ch" + k, v, "OK" if v == expect else "NOT CONTIGUOUS")