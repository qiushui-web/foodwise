"""把 ZHAW 大学食堂交易明细聚合成两张日需求面板，并给出可用的基准难度。

来源：Zenodo 3890931（CC BY 4.0），2017 年秋季学期 12 周、2 个食堂、26,340 条交易明细，
Basis / Intervention 各 30 天交替，可用于真实数据上的需求回测与归因检验。

输出：
  modeling/data/01_raw/zhaw_canteen_daily_panel.csv      日期 × 食堂 × 菜品
  modeling/data/01_raw/zhaw_canteen_daily_label_panel.csv 日期 × 食堂 × 品类（序列更长，适合回测）
  modeling/data/03_output/zhaw_panel_summary.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

SRC = Path(r"E:\食刻有数\数据来源\ZHAW_canteen_menu_sales_2017\2017_ZHAW_aggregated_menu_sales_NOVANIMAL.csv")
MEAL_OUT = Path("modeling/data/01_raw/zhaw_canteen_daily_panel.csv")
LABEL_OUT = Path("modeling/data/01_raw/zhaw_canteen_daily_label_panel.csv")
SUMMARY_OUT = Path("modeling/data/03_output/zhaw_panel_summary.json")

LABEL_MAP = {
    "Vegetarisch": "素食",
    "Pflanzlich": "植物基",
    "Pflanzlich+": "植物基+",
    "Fleisch": "肉类",
    "Fisch": "鱼类",
    "Geflügel": "禽类",
    "Hot and Cold": "冷热自助",
}
VEG_LABELS = {"素食", "植物基", "植物基+"}
GROUP_COLUMNS = ["date", "shop"]


def load() -> pd.DataFrame:
    frame = pd.read_csv(SRC, encoding="utf-8", sep=";", low_memory=False)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["qty"] = pd.to_numeric(frame["qty_weight"], errors="coerce").fillna(1.0).clip(lower=0)
    frame["shop"] = frame["shop_description"].astype(str).str.strip()
    frame["meal"] = frame["meal_name"].fillna("未标注").astype(str).str.strip()
    frame["condit"] = frame["condit"].astype(str).str.strip()
    frame["label"] = frame["label_content"].map(lambda value: LABEL_MAP.get(str(value).strip(), "未标注"))
    frame["is_veg"] = frame["label"].isin(VEG_LABELS).astype(int)
    frame["revenue"] = pd.to_numeric(frame["total_amount"], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"])


def _aggregate(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    grouped = frame.groupby(keys, as_index=False).agg(
        qty=("qty", "sum"),
        transactions=("transaction_id", "nunique"),
        revenue=("revenue", "sum"),
        price=("price_article", "mean"),
        condit=("condit", lambda values: values.mode().iat[0] if not values.mode().empty else ""),
        cycle=("cycle", "max"),
        semwk=("semwk", "max"),
        week=("week", "max"),
        sun=("sun", "max"),
        clouds=("clouds", "max"),
        rainfall=("rainfall", "max"),
        outside=("outside", "max"),
    )
    grouped["weekday"] = grouped["date"].dt.dayofweek
    grouped["is_weekend"] = (grouped["weekday"] >= 5).astype(int)
    return grouped.sort_values(keys).reset_index(drop=True)


def build_meal_panel(frame: pd.DataFrame) -> pd.DataFrame:
    panel = _aggregate(frame, ["date", "shop", "meal"])
    label_mode = frame.groupby(["date", "shop", "meal"])["label"].agg(
        lambda values: values.mode().iat[0] if not values.mode().empty else "")
    veg_max = frame.groupby(["date", "shop", "meal"])["is_veg"].max()
    panel["label"] = panel.set_index(["date", "shop", "meal"]).index.map(label_mode)
    panel["is_veg"] = panel.set_index(["date", "shop", "meal"]).index.map(veg_max)
    return panel


def build_label_panel(frame: pd.DataFrame) -> pd.DataFrame:
    panel = _aggregate(frame, ["date", "shop", "label"])
    panel["is_veg"] = panel["label"].isin(VEG_LABELS).astype(int)
    return panel


def _baseline(panel: pd.DataFrame, keys: list[str]) -> dict:
    frame = panel.sort_values(keys + ["date"]).copy()
    frame["lag_7"] = frame.groupby(keys)["qty"].shift(7)
    frame["prev_day"] = frame.groupby(keys)["qty"].shift(1)
    usable = frame.dropna(subset=["lag_7"]).copy()
    if usable.empty:
        return {}
    usable["prev_day"] = usable["prev_day"].fillna(usable["qty"].mean())
    result = {
        "series": int(frame.groupby(keys).ngroups),
        "rows_with_lag7": int(len(usable)),
        "mae_same_weekday_last_week": round(float((usable["qty"] - usable["lag_7"]).abs().mean()), 2),
        "mae_previous_day": round(float((usable["qty"] - usable["prev_day"]).abs().mean()), 2),
        "wape_same_weekday_last_week": round(
            float((usable["qty"] - usable["lag_7"]).abs().sum() / max(usable["qty"].sum(), 1)), 4),
        "mean_qty": round(float(usable["qty"].mean()), 2),
    }
    return result


def summarise(frame: pd.DataFrame, meal_panel: pd.DataFrame, label_panel: pd.DataFrame) -> dict:
    per_shop = meal_panel.groupby("shop").agg(
        days=("date", "nunique"), meals=("meal", "nunique"), rows=("qty", "size"), units=("qty", "sum"))
    veg_share = (
        label_panel.groupby(["condit", "shop"])
        .apply(lambda part: float((part["qty"] * part["is_veg"]).sum() / max(part["qty"].sum(), 1)),
               include_groups=False)
        .unstack()
    )
    daily = label_panel.groupby(["date", "shop"])["qty"].sum().groupby("shop")
    condition_units = (
        label_panel.groupby(["shop", "condit"])["qty"].sum()
        / label_panel.groupby(["shop", "condit"])["date"].nunique()
    ).unstack()
    meals_per_day = meal_panel.groupby(["date", "shop"]).size()
    return {
        "transactions": int(len(frame)),
        "unlabelled_meal_rows": int((frame["meal"] == "未标注").sum()),
        "dates": int(frame["date"].nunique()),
        "date_min": str(frame["date"].min().date()),
        "date_max": str(frame["date"].max().date()),
        "shops": sorted(frame["shop"].unique().tolist()),
        "condition_days": frame.groupby("condit")["date"].nunique().to_dict(),
        "meal_panel": {
            "rows": int(len(meal_panel)),
            "meals": int(meal_panel["meal"].nunique()),
            "meals_per_day_mean": round(float(meals_per_day.mean()), 2),
            "qty_median": round(float(meal_panel["qty"].median()), 2),
            "qty_p95": round(float(meal_panel["qty"].quantile(0.95)), 2),
            "per_shop": per_shop.round(2).to_dict("index"),
            "baseline_backtest": _baseline(meal_panel, ["shop", "meal"]),
        },
        "label_panel": {
            "rows": int(len(label_panel)),
            "labels": sorted(label_panel["label"].unique().tolist()),
            "units_total": round(float(label_panel["qty"].sum()), 1),
            "daily_units_mean_by_shop": daily.mean().round(1).to_dict(),
            "daily_units_std_by_shop": daily.std().round(1).to_dict(),
            "veg_share_by_condition_shop": veg_share.round(4).to_dict(),
            "mean_daily_units_by_condition_shop": condition_units.round(1).to_dict(),
            "baseline_backtest": _baseline(label_panel, ["shop", "label"]),
        },
    }


def main() -> int:
    frame = load()
    meal_panel = build_meal_panel(frame)
    label_panel = build_label_panel(frame)
    MEAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    meal_panel.to_csv(MEAL_OUT, index=False, encoding="utf-8-sig")
    label_panel.to_csv(LABEL_OUT, index=False, encoding="utf-8-sig")
    summary = summarise(frame, meal_panel, label_panel)
    SUMMARY_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"meal  panel -> {MEAL_OUT} ({len(meal_panel)} rows)")
    print(f"label panel -> {LABEL_OUT} ({len(label_panel)} rows)")
    print(f"summary     -> {SUMMARY_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())