"""从芬兰学校食堂 155 天数据里抽出"备餐过剩"的先验分布，供仿真器与报告引用。

字段含义（数据来源 README）：
  KSW kg = 厨房与供餐环节浪费（kg），对应本项目"备餐过剩"
  PW  kg = 餐盘浪费（kg），对应"售出后没吃完"
  DINERS = 当日就餐人数
  MENU   = 25 天滚动菜单编号
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path

import openpyxl

SRC = Path(r"E:\食刻有数\数据来源\Finland_school_food_waste_2024_2025\Food waste data school Finland 2024-2025.xlsx")
OUT = Path("modeling/data/03_output/finland_waste_priors.json")


def load_rows() -> list[dict]:
    book = openpyxl.load_workbook(SRC, data_only=True)
    sheet = book["food waste school meals 2024-25"]
    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        date, menu, ksw, pw, _pw_g, diners, _pw_diner, _ksw_diner = row[:8]
        if not isinstance(date, datetime) or not isinstance(diners, (int, float)) or diners <= 0:
            continue
        if not isinstance(ksw, (int, float)) or not isinstance(pw, (int, float)):
            continue
        rows.append({
            "date": date.date().isoformat(),
            "menu": int(menu) if isinstance(menu, (int, float)) else None,
            "ksw_kg": float(ksw),
            "pw_kg": float(pw),
            "diners": int(diners),
        })
    return sorted(rows, key=lambda item: item["date"])


def summarise(rows: list[dict]) -> dict:
    ksw_per_diner_g = [row["ksw_kg"] * 1000 / row["diners"] for row in rows]
    pw_per_diner_g = [row["pw_kg"] * 1000 / row["diners"] for row in rows]
    total_waste = [row["ksw_kg"] + row["pw_kg"] for row in rows]
    over_share = [row["ksw_kg"] / (row["ksw_kg"] + row["pw_kg"]) for row in rows]
    diners = [row["diners"] for row in rows]
    ksw = [row["ksw_kg"] for row in rows]

    def describe(values: list[float]) -> dict:
        return {
            "mean": round(statistics.fmean(values), 2),
            "median": round(statistics.median(values), 2),
            "sd": round(statistics.pstdev(values), 2),
            "p05": round(sorted(values)[max(0, int(0.05 * len(values)))], 2),
            "p95": round(sorted(values)[min(len(values) - 1, int(0.95 * len(values)))], 2),
        }

    mean_ksw = statistics.fmean(ksw)
    mean_diners = statistics.fmean(diners)
    cov = statistics.fmean(
        (k - mean_ksw) * (d - mean_diners) for k, d in zip(ksw, diners)
    ) / (statistics.pstdev(ksw) * statistics.pstdev(diners))

    baseline = rows[:-20]
    intervention = rows[-20:]

    def ksw_per_diner(subset: list[dict]) -> float:
        return statistics.fmean(row["ksw_kg"] * 1000 / row["diners"] for row in subset)

    return {
        "rows": len(rows),
        "date_min": rows[0]["date"],
        "date_max": rows[-1]["date"],
        "diners": describe(diners),
        "ksw_kg": describe(ksw),
        "ksw_per_diner_g": describe(ksw_per_diner_g),
        "pw_per_diner_g": describe(pw_per_diner_g),
        "total_waste_kg": describe(total_waste),
        "kitchen_share_of_waste": describe(over_share),
        "corr_ksw_diners": round(cov, 3),
        "menu_cycle_days": len({row["menu"] for row in rows if row["menu"]}),
        "baseline_days": len(baseline),
        "intervention_days": len(intervention),
        "ksw_per_diner_g_baseline": round(ksw_per_diner(baseline), 2),
        "ksw_per_diner_g_intervention": round(ksw_per_diner(intervention), 2),
    }


def main() -> int:
    rows = load_rows()
    summary = summarise(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"rows={summary['rows']} {summary['date_min']}..{summary['date_max']}")
    print(f"KSW/diner g: {summary['ksw_per_diner_g']}")
    print(f"PW/diner g:  {summary['pw_per_diner_g']}")
    print(f"kitchen share of waste: {summary['kitchen_share_of_waste']}")
    print(f"corr(KSW, diners) = {summary['corr_ksw_diners']}")
    print(f"baseline vs intervention KSW/diner: "
          f"{summary['ksw_per_diner_g_baseline']} -> {summary['ksw_per_diner_g_intervention']}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())