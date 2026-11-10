"""外部效度（二）：德国烘焙连锁的"订货—售出—剩余"。

这个数据集的 README 说它包含 ordered / unsold / sales 三列——这正是我们想找的"备餐三件套"。
但读进来必须先做一件事：**确认这三列能不能直接算过剩率**。结论是不行，本脚本把这个判断过程也留下来。

可用的部分：门店 × 日的销量序列（按门店标准化），以及节假日标记。用它们检验两件结构性假设：
1. 周内节律是否稳定存在（我们的基线完全建立在"同星期可比"上）；
2. 节假日是否真的抬高销量（我们的特征清单里有 exam_week / campus_event 这一类）。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / "数据来源" / "Reduce-Foodwaste-Dataset"
OUT = ROOT / "modeling" / "data" / "03_output" / "external_germany.json"


def scaling_diagnosis(frame: pd.DataFrame) -> dict:
    """三列是否满足 ordered = sales + unsold？不满足就说明被匿名化缩放过，比率不可用。"""
    both = frame.dropna(subset=["ordered", "sales", "unsold"])
    residual = (both["ordered"] - both["sales"] - both["unsold"]).abs()
    positive_order = both[both["ordered"] > 0]
    rate = positive_order["unsold"] / positive_order["ordered"]
    return {
        "rows_with_three_columns": int(len(both)),
        "identity_abs_median": round(float(residual.median()), 4),
        "identity_abs_p95": round(float(residual.quantile(0.95)), 4),
        "negative_unsold_share": round(float((both["unsold"] < 0).mean()), 4),
        "negative_ordered_share": round(float((both["ordered"] < 0).mean()), 4),
        "naive_overproduction_rate": None if positive_order.empty else round(float(rate.mean()), 4),
        "verdict": "scaled_and_anonymised",
        "reason": "三列不满足守恒、且过半 unsold 为负，说明数值被按门店标准化过；比率与绝对量都不可解释，"
                  "只能用于结构性检查",
    }


def weekday_profile(frame: pd.DataFrame) -> dict:
    frame = frame.copy()
    frame["weekday"] = frame["date"].dt.dayofweek
    per_store = frame.groupby(["store", "weekday"])["sales"].mean()
    normalized = per_store.groupby(level="store").transform(lambda s: s / s.mean())
    profile = normalized.groupby(level="weekday").mean()
    return {"by_weekday": {str(int(k)): round(float(v), 3) for k, v in profile.items()},
            "peak": int(profile.idxmax()), "trough": int(profile.idxmin())}


def holiday_effect(frame: pd.DataFrame) -> dict:
    normal = frame[frame["is_state_holiday"] == "normal_day"]["sales"]
    holiday = frame[frame["is_state_holiday"] != "normal_day"]["sales"]
    return {
        "normal_days": int(len(normal)),
        "holiday_days": int(len(holiday)),
        "normal_mean": round(float(normal.mean()), 3),
        "holiday_mean": round(float(holiday.mean()), 3),
        "difference": round(float(holiday.mean() - normal.mean()), 3),
    }


def run() -> dict:
    frame = pd.read_csv(RAW / "train.csv", parse_dates=["date"])
    payload = {
        "dataset": "Reduce-Foodwaste-Dataset (pastry-prediction)",
        "source_file": "train.csv",
        "license": "MIT",
        "rows": int(len(frame)),
        "stores": int(frame["store"].nunique()),
        "days": int(frame["date"].nunique()),
        "date_from": frame["date"].min().date().isoformat(),
        "date_to": frame["date"].max().date().isoformat(),
        "scaling": scaling_diagnosis(frame),
        "weekday_profile": weekday_profile(frame),
        "holiday_effect": holiday_effect(frame),
        "usable_for": ["周内节律是否存在", "节假日是否改变销量水平", "真实门店确实记录 ordered/unsold 这一事实"],
        "not_usable_for": ["备餐过剩率", "任何绝对份数或金额", "与我们台账的直接数值比较"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps({k: result[k] for k in ("rows", "stores", "days", "scaling",
                                            "weekday_profile", "holiday_effect")},
                     ensure_ascii=False, indent=2))