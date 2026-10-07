# -*- coding: utf-8 -*-
import shutil
from pathlib import Path

SRC = Path(r"c:\Users\lenovo\Desktop\商业精英挑战赛\deploy\java_pure")
ROOT = Path(__file__).resolve().parents[1]
DST = ROOT / "src" / "main" / "java" / "org" / "foodwise" / "service"

for name in ["LgbmCampusModel.java", "DualPredictionService.java"]:
    shutil.copy2(SRC / name, DST / name)
    print(f"[COPY] {name}")

gradle = ROOT / "build.gradle"
t = gradle.read_text(encoding="utf-8")
lines = t.splitlines()
out = []
removed = 0
for ln in lines:
    if "com.microsoft.ml.lightgbm" in ln or "lightgbmlib" in ln:
        removed += 1
        print(f"[REMOVE] {ln.strip()}")
        continue
    out.append(ln)
gradle.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"[OK] build.gradle 移除 {removed} 行原生依赖")
