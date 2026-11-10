"""外部效度（一）：芬兰学校食堂 154 个营业日的备餐过剩实测。

数据没有提供"备餐份数"，只有三样东西：厨房与服务环节浪费（KSW，kg）、餐盘浪费（PW，kg）、
就餐人数（DINERS）。所以这个实验回答的不是"我们的建议量对不对"，而是三个更前置的问题：

1. 备餐过剩在真实食堂里到底有多大？（人均克数、占全部浪费的比例）
2. 它跟就餐人数有没有稳定关系？（如果我们连"人多就多备"都解释不了，模型就不用谈了）
3. 食堂在做干预期时，过剩量会不会动？（动多少，决定我们后 35 天实验的效应量是否现实）

xlsx 用标准库解析：venv 里没有 openpyxl，且不该为读一个表装依赖。
"""

from __future__ import annotations

import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / "数据来源" / "Finland_school_food_waste_2024_2025" / "Food waste data school Finland 2024-2025.xlsx"
OUT = ROOT / "modeling" / "data" / "03_output" / "external_finland.json"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXCEL_EPOCH = date(1899, 12, 30)
INTERVENTION_DAYS = 20


def read_xlsx(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in shared]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    table: list[dict[str, str]] = []
    for row in sheet.findall(".//" + NS + "row"):
        cells: dict[str, str] = {}
        for cell in row.findall(NS + "c"):
            column = "".join(ch for ch in cell.get("r", "") if ch.isalpha())
            value = cell.find(NS + "v")
            if value is None or not column:
                continue
            text = value.text or ""
            if cell.get("t") == "s":
                text = strings[int(text)]
            cells[column] = text
        if cells:
            table.append(cells)
    header = table[0]
    frame = pd.DataFrame(table[1:])
    frame.columns = [header.get(column, column) for column in frame.columns]
    return frame


def build_frame(path: Path) -> pd.DataFrame:
    raw = read_xlsx(path)
    frame = pd.DataFrame({
        "date": [EXCEL_EPOCH + timedelta(days=int(float(value))) for value in raw["DATE"]],
        "menu": pd.to_numeric(raw["MENU"], errors="coerce"),
        "ksw_kg": pd.to_numeric(raw["KSW kg"], errors="coerce"),
        "pw_kg": pd.to_numeric(raw["PW kg"], errors="coerce"),
        "diners": pd.to_numeric(raw["DINERS"], errors="coerce"),
    })
    frame = frame.dropna(subset=["date", "diners", "pw_kg"]).reset_index(drop=True)
    frame["ksw_kg"] = frame["ksw_kg"].fillna(frame["ksw_kg"].median())
    frame["weekday"] = pd.to_datetime(frame["date"]).dt.dayofweek
    frame["total_waste_kg"] = frame["ksw_kg"] + frame["pw_kg"]
    frame["ksw_per_diner_g"] = frame["ksw_kg"] * 1000 / frame["diners"]
    frame["pw_per_diner_g"] = frame["pw_kg"] * 1000 / frame["diners"]
    return frame


def summarize(frame: pd.DataFrame) -> dict:
    kitchen_share = float(frame["ksw_kg"].sum() / frame["total_waste_kg"].sum())
    correlation = float(np.corrcoef(frame["diners"], frame["ksw_kg"])[0, 1])
    split = len(frame) - INTERVENTION_DAYS
    before, during = frame.iloc[:split], frame.iloc[split:]
    weekday = (frame.groupby("weekday")["ksw_per_diner_g"].mean().round(2).to_dict())
    return {
        "days": int(len(frame)),
        "date_from": frame["date"].min().isoformat(),
        "date_to": frame["date"].max().isoformat(),
        "diners_mean": round(float(frame["diners"].mean()), 1),
        "ksw_kg_per_day": round(float(frame["ksw_kg"].mean()), 2),
        "pw_kg_per_day": round(float(frame["pw_kg"].mean()), 2),
        "ksw_per_diner_g": round(float(frame["ksw_per_diner_g"].mean()), 1),
        "pw_per_diner_g": round(float(frame["pw_per_diner_g"].mean()), 1),
        "kitchen_share_of_waste": round(kitchen_share, 4),
        "corr_diners_ksw": round(correlation, 3),
        "ksw_cv": round(float(frame["ksw_kg"].std() / frame["ksw_kg"].mean()), 3),
        "weekday_ksw_per_diner_g": {str(int(k)): v for k, v in weekday.items()},
        "intervention": {
            "days": INTERVENTION_DAYS,
            "ksw_per_diner_g_before": round(float(before["ksw_per_diner_g"].mean()), 1),
            "ksw_per_diner_g_during": round(float(during["ksw_per_diner_g"].mean()), 1),
            "change_pct": round(float(during["ksw_per_diner_g"].mean() / before["ksw_per_diner_g"].mean() - 1), 4),
            "pw_per_diner_g_change_pct": round(float(during["pw_per_diner_g"].mean() / before["pw_per_diner_g"].mean() - 1), 4),
        },
    }


def run() -> dict:
    frame = build_frame(RAW)
    payload = {
        "dataset": "Finland_school_food_waste_2024_2025",
        "source_file": RAW.name,
        "license": "CC BY 4.0",
        "units": {"ksw_kg": "厨房与服务环节浪费（≈备餐过剩）", "pw_kg": "餐盘浪费", "diners": "就餐人数"},
        "summary": summarize(frame),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(OUT.with_suffix(".csv"), index=False, encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))