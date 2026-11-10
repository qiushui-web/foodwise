# -*- coding: utf-8 -*-
"""删除指定的示意图块（图号级）。"""
import re

BASE = r"E:\食刻有数\项目代码\docs\plan_v3_20261027"
TARGETS = {
    "content_1.py": ["图1-2", "图3-3"],
    "content_2.py": ["图9-2"],
    "content_3.py": ["图7-2"],
}

for fname, nos in TARGETS.items():
    path = f"{BASE}\\{fname}"
    s = open(path, encoding="utf-8").read()
    for no in nos:
        pat = re.compile('B\\(\\("fig", "' + no + '".*?\\)\\)\\n', re.S)
        s, n = pat.subn("", s)
        print(fname, no, "removed", n)
    open(path, "w", encoding="utf-8").write(s)
print("done")