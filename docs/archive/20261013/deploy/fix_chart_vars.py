# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "src" / "main" / "resources" / "static" / "build" / "app.js"
t = p.read_text(encoding="utf-8")
reps = [
    ("xAxis: { type: 'category', data: days, axisTick",
     "xAxis: { type: 'category', data: [], axisTick"),
    ("symbolSize: 7, data: actual, lineStyle: { color: colors.green, width: 3 }",
     "symbolSize: 7, data: [], lineStyle: { color: colors.green, width: 3 }"),
    ("symbol: 'none', data: rulePred, lineStyle: { color: colors.gold, width: 2, type: 'dashed' }",
     "symbol: 'none', data: [], lineStyle: { color: colors.gold, width: 2, type: 'dashed' }"),
]
for old, new in reps:
    if new in t:
        print("[SKIP]", new[:40]); continue
    if old not in t:
        print("[MISS]", old[:60]); continue
    t = t.replace(old, new, 1); print("[OK]", new[:60])
p.write_text(t, encoding="utf-8")
print("done")
