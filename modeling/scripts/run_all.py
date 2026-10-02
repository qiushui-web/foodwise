# -*- coding: utf-8 -*-
# run_all.py v3 - ASCII safe, subprocess-based pipeline
from __future__ import annotations
import sys
import time
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKDIR = SCRIPT_DIR.parent
PY = sys.executable
STEPS = [
    "02_build_pretrain_features",
    "03_train_pretrain_lgbm",
    "04_build_finetune_features",
    "05_finetune_and_backtest",
    "06_export_for_java",
    "07_validate_kaggle",   # 真实Kaggle食堂数据外部验证
    "12_campus_rolling_baseline",
    "10_data_quality_audit",
    "13_verify_java_artifacts",
]

def run_step(name):
    script = SCRIPT_DIR / (name + ".py")
    if not script.exists():
        raise FileNotFoundError(str(script))
    r = subprocess.run([PY, str(script)], cwd=str(WORKDIR))
    if r.returncode != 0:
        raise RuntimeError(name + " failed with exit " + str(r.returncode))

def main():
    t0 = time.time()
    sep = "=" * 70
    print(sep)
    print("FoodWise Modeling Pipeline (subprocess v3)")
    print(" Python : " + PY)
    print(" Workdir: " + str(WORKDIR))
    print(sep)
    ok = 0; fail = 0; order = []
    for i, mod in enumerate(STEPS, 1):
        print("\n[Step {}/{}] {}".format(i, len(STEPS), mod))
        t1 = time.time()
        try:
            run_step(mod)
            dt = time.time() - t1
            print("[OK] Step {} done in {:.1f}s".format(i, dt))
            ok += 1
            order.append("OK  {} {:.1f}s".format(mod, dt))
        except Exception as e:
            dt = time.time() - t1
            print("[FAIL] Step {} after {:.1f}s: {}".format(i, dt, e))
            fail += 1
            order.append("FAIL {} {}".format(mod, e))
            break
    total = time.time() - t0
    print("\n" + sep)
    print("SUMMARY: {}/{} OK, {} FAIL, {:.1f}s total".format(ok, len(STEPS), fail, total))
    for line in order:
        print("   - " + line)
    OUT = WORKDIR / "data" / "03_output"
    print("\nKEY OUTPUTS:")
    for name in ["pretrain_metrics.json","campus_backtest_report.json","feature_importance.csv","kaggle_validation_report.json","data_quality_report.json","DATA_VERSION.json"]:
        p = OUT / name
        if p.exists():
            print("   [OK] {} ({} bytes)".format(name, p.stat().st_size))
        else:
            print("   [MISSING] {}".format(name))
    print(sep)
    sys.exit(0 if fail == 0 else 1)

if __name__ == "__main__":
    main()
