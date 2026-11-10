"""35 天现场数据的验收脚本：模式、守恒、覆盖、采纳率，一个都不放过。

用法：
    python modeling/scripts/48_validate_pilot.py --ledger <daily_ledger.csv> [--adoption <adoption_log.csv>] [--output <json>]

退出码：0 全部通过（可能有警告）；1 存在阻断性错误。警告不影响退出码，但必须写进周复盘。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = [
    "business_date", "week_index", "condition", "stall_id", "dish_id", "meal_period",
    "price", "unit_cost", "suggested_qty", "adopted", "prepared_qty", "sold_qty",
    "discounted_qty", "leftover_qty",
]
NUMERIC = ["price", "unit_cost", "suggested_qty", "prepared_qty", "sold_qty",
           "discounted_qty", "leftover_qty", "waste_qty", "stockout_minutes"]
TRUE_VALUES = {"y", "yes", "1", "true", "是", "采纳"}
FALSE_VALUES = {"n", "no", "0", "false", "否", "未采纳"}
INTERVENTION = {"a", "干预", "intervention"}
CONTROL = {"b", "对照", "control"}
MAX_DAYS = 35
MIN_DISH_COVERAGE = 20


def parse_bool(value) -> bool | None:
    text = str(value).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def load(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.columns = [column.strip() for column in frame.columns]
    return frame.mask(frame == "")


def validate(ledger: pd.DataFrame, adoption: pd.DataFrame | None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    missing = [column for column in REQUIRED if column not in ledger.columns]
    if missing:
        return {"status": "failed", "errors": [f"缺少必需列: {', '.join(missing)}"],
                "warnings": [], "summary": {"rows": len(ledger)}}

    frame = ledger.copy()
    frame["business_date"] = pd.to_datetime(frame["business_date"], errors="coerce")
    if frame["business_date"].isna().any():
        errors.append(f"{int(frame['business_date'].isna().sum())} 行的 business_date 无法解析")

    for column in NUMERIC:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["waste_qty"] = frame["waste_qty"].fillna(0) if "waste_qty" in frame.columns else 0.0

    for column in ["price", "unit_cost", "suggested_qty", "prepared_qty", "sold_qty",
                   "discounted_qty", "leftover_qty"]:
        bad = frame[column].isna()
        if bad.any():
            errors.append(f"{int(bad.sum())} 行的 {column} 缺失或不是数字")

    negatives = frame[(frame[["prepared_qty", "sold_qty", "discounted_qty", "leftover_qty"]]
                       .fillna(0) < 0).any(axis=1)]
    if len(negatives):
        errors.append(f"{len(negatives)} 行存在负数数量")

    duplicated = frame.duplicated(subset=["business_date", "dish_id", "meal_period"], keep=False)
    if duplicated.any():
        errors.append(f"{int(duplicated.sum())} 行是重复键（同一天同菜品同餐次只能一行；改错请用 revision_of 新增一行）")

    valid = frame.dropna(subset=["prepared_qty", "sold_qty", "discounted_qty", "leftover_qty"])
    residual = (valid["prepared_qty"] - valid["sold_qty"] - valid["discounted_qty"]
                - valid["leftover_qty"] - valid["waste_qty"].fillna(0)).abs()
    broken = residual > 1e-6
    if broken.any():
        sample = valid[broken].head(3)[["business_date", "dish_id"]].astype(str).agg("/".join, axis=1).tolist()
        errors.append(f"{int(broken.sum())} 行数量不守恒（prepared ≠ sold + discounted + leftover + waste），例如 {', '.join(sample)}")

    conditions = frame["condition"].astype(str).str.strip().str.lower()
    unknown = ~conditions.isin(INTERVENTION | CONTROL)
    if unknown.any():
        errors.append(f"{int(unknown.sum())} 行的 condition 不是 干预/对照")
    frame["is_intervention"] = conditions.isin(INTERVENTION)

    per_week = frame.groupby("week_index")["is_intervention"].nunique()
    mixed = per_week[per_week > 1]
    if len(mixed):
        errors.append(f"第 {', '.join(map(str, mixed.index))} 周内混了两种条件（按周交替要求一周只有一种）")

    adopted = frame["adopted"].map(parse_bool)
    invalid_adopted = adopted.isna()
    if invalid_adopted.any():
        errors.append(f"{int(invalid_adopted.sum())} 行的 adopted 不是明确的 是/否")

    days = frame["business_date"].dt.date.nunique()
    if days > MAX_DAYS:
        errors.append(f"营业日 {days} 天，超过 35 天的采集上限")
    if days < MAX_DAYS:
        warnings.append(f"当前只有 {days} 个营业日，未满 35 天")

    dishes = frame["dish_id"].nunique()
    coverage = frame.groupby("dish_id")["business_date"].nunique()
    thin = coverage[coverage < MIN_DISH_COVERAGE]
    if len(thin):
        warnings.append(f"{len(thin)} 道菜品出现天数少于 {MIN_DISH_COVERAGE} 天: "
                        + ", ".join(f"{dish}({int(count)}天)" for dish, count in thin.items()))

    intervention_rows = frame[frame["is_intervention"]]
    if len(intervention_rows) and intervention_rows["suggested_qty"].isna().any():
        errors.append("干预周存在未记录建议量的行")

    deviation = pd.Series(dtype="float64")
    if len(intervention_rows):
        deviation = ((intervention_rows["prepared_qty"] - intervention_rows["suggested_qty"]).abs()
                     / intervention_rows["suggested_qty"].replace(0, np.nan))
        over = intervention_rows[(adopted.loc[intervention_rows.index] == True)  # noqa: E712
                                 & (deviation > 0.10)]
        if len(over):
            warnings.append(f"{len(over)} 行标记为采纳但偏离建议量超过 10%")

    if adoption is None:
        warnings.append("未提供采纳原因表：未采纳的行无法核对原因码")
    else:
        not_adopted = frame[adopted == False]  # noqa: E712
        if len(not_adopted):
            keys = set(zip(adoption.get("business_date", []), adoption.get("dish_id", []),
                           adoption.get("meal_period", [])))
            missing_reason = [row for row in not_adopted.itertuples()
                              if (str(row.business_date.date()), str(row.dish_id), str(row.meal_period)) not in keys]
            if missing_reason:
                errors.append(f"{len(missing_reason)} 行未采纳但缺少原因码记录")

    if "censored" in frame.columns:
        censored = pd.to_numeric(frame["censored"], errors="coerce").fillna(0) > 0
        mismatch = frame[censored & (frame["sold_qty"] + frame["discounted_qty"] < frame["prepared_qty"])]
        if len(mismatch):
            warnings.append(f"{len(mismatch)} 行标记售罄但仍有剩余，注意口径")

    summary = build_summary(frame, adopted, deviation)
    return {"status": "failed" if errors else "passed", "errors": errors,
            "warnings": warnings, "summary": summary}


def build_summary(frame: pd.DataFrame, adopted: pd.Series, deviation: pd.Series) -> dict:
    day = frame["business_date"].dt.date
    intervention = frame[frame["is_intervention"]]
    adoption_rate = float((adopted[intervention.index] == True).mean()) if len(intervention) else None  # noqa: E712

    demand = frame["sold_qty"] + frame["discounted_qty"]
    revenue = frame["sold_qty"] * frame["price"] + frame["discounted_qty"] * frame["price"] * 0.5
    profit = revenue - frame["prepared_qty"] * frame["unit_cost"]
    oracle = demand * (frame["price"] - frame["unit_cost"])
    regret = (oracle - profit).clip(lower=0)
    weight = demand.replace(0, np.nan)

    return {
        "rows": int(len(frame)),
        "business_days": int(day.nunique()),
        "weeks": int(frame["week_index"].nunique()),
        "dishes": int(frame["dish_id"].nunique()),
        "stalls": int(frame["stall_id"].nunique()),
        "intervention_rows": int(len(intervention)),
        "adoption_rate": None if adoption_rate is None else round(adoption_rate, 4),
        "execution_deviation_mean": None if deviation.empty else round(float(deviation.mean()), 4),
        "regret_per_100": round(float(regret.sum() / weight.sum() * 100), 2),
        "leftover_rate": round(float((frame["leftover_qty"] / frame["prepared_qty"].replace(0, np.nan)).mean()), 4),
        "stockout_rows": int((pd.to_numeric(frame.get("stockout_minutes", 0), errors="coerce").fillna(0) > 0).sum()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 35 天现场采集数据")
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--adoption", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if not args.ledger.exists():
        print(f"找不到台账文件：{args.ledger}", file=sys.stderr)
        return 1
    ledger = load(args.ledger)
    adoption = load(args.adoption) if args.adoption and args.adoption.exists() else None
    result = validate(ledger, adoption)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())