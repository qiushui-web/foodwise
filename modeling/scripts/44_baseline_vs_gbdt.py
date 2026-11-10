"""14 天台账上「分层基线 vs LightGBM」的留一天对照（LODO）。

这不是为了证明谁更准，而是回答一个具体问题：
在 98 行、有效独立样本约 14 天的数据上，24 维 GBDT 到底比"同菜品同星期中位数 + 保形尺度"好还是差。

评估口径采用站点同一套成本结构（DecisionCostModel）：
  Cu = (售价 − 成本) × (1 + 信任损失 0.3)
  Co = 成本 − 折价价 × 残值概率
  q  = round(center + z(ρ) · σ)
  regret = 事后最优利润（备餐 = 实际需求）− 该决策的利润
"""

from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import norm

SRC = Path("src/main/resources/data/foodwise_operations_14d.csv")
OUT = Path("modeling/data/03_output/baseline_vs_gbdt_14d.json")

SHORTAGE_LAMBDA = 0.3
DISCOUNT_RATIO = 0.5
SALVAGE_PROBABILITY = 0.6
MIN_TRAIN_DAYS = 3

WEATHER_CODE = {"晴": 0, "多云": 1, "阴": 2, "小雨": 3, "中雨": 4, "大雨": 5, "高温": 6}
EVENT_CODE = {"正常教学": 0, "考试周": 1, "校园活动": 2}


def cost_terms(price: float, unit_cost: float) -> tuple[float, float, float, float]:
    underage = (price - unit_cost) * (1 + SHORTAGE_LAMBDA)
    discount_price = price * DISCOUNT_RATIO
    overage = unit_cost - discount_price * SALVAGE_PROBABILITY
    ratio = 0.999 if overage <= 0 else underage / (underage + overage)
    return underage, overage, min(max(ratio, 0.01), 0.999), discount_price


def profit(prepared: float, demand: float, price: float, unit_cost: float, discount_price: float) -> float:
    sold = min(prepared, demand)
    leftover = max(prepared - demand, 0.0)
    return sold * price + leftover * discount_price * SALVAGE_PROBABILITY - prepared * unit_cost


def regret(prepared: float, demand: float, price: float, unit_cost: float, discount_price: float) -> float:
    # 单期利润在 q = demand 处取最大
    best = profit(demand, demand, price, unit_cost, discount_price)
    return best - profit(prepared, demand, price, unit_cost, discount_price)


def load_ledger() -> pd.DataFrame:
    frame = pd.read_csv(SRC)
    frame["business_date"] = pd.to_datetime(frame["business_date"])
    frame = frame.sort_values(["business_date", "dish_id"]).reset_index(drop=True)
    frame["weekday"] = frame["business_date"].dt.dayofweek
    frame["weather_code"] = frame["weather"].map(WEATHER_CODE).fillna(2)
    frame["event_code"] = frame["event_tag"].map(EVENT_CODE).fillna(0)
    return frame


def mad_scale(values: np.ndarray) -> float:
    if len(values) < 2:
        return 3.0
    med = np.median(values)
    return float(1.4826 * np.median(np.abs(values - med)))


def build_features(history: pd.DataFrame, row: pd.Series) -> list[float] | None:
    dish_history = history[history["dish_id"] == row["dish_id"]].sort_values("business_date")
    sold = dish_history["sold_qty"].to_numpy(dtype=float)
    if len(sold) == 0:
        return None
    lag1 = sold[-1]
    lag2 = sold[-2] if len(sold) >= 2 else lag1
    roll3 = float(np.median(sold[-3:]))
    roll7 = float(np.median(sold[-7:]))
    trend = float(sold[-1] - sold[-min(3, len(sold))]) / min(3, len(sold))
    return [
        row["weekday"], row["weather_code"], row["event_code"],
        row["price"], row["unit_cost"], row["dish_id"],
        lag1, lag2, roll3, roll7, trend, float(len(sold)),
    ]


def walk_forward_centers(frame: pd.DataFrame, dates: list) -> dict:
    """每个 (日期, 菜品) 只用当日之前的历史算 7 日中位数，用于构造滚动残差。"""
    centers = {}
    for date in dates:
        history = frame[frame["business_date"] < date]
        for dish_id in frame["dish_id"].unique():
            values = history[history["dish_id"] == dish_id]["sold_qty"].to_numpy(dtype=float)
            if len(values):
                centers[(date, dish_id)] = float(np.median(values[-7:]))
    return centers


def sigma_scan(detail: pd.DataFrame) -> list[dict]:
    """σ 缩放扫描：q = center + k·z·σ，看 k 取多少时 regret 最小。

    14 天数据上对 k 做网格搜索本身有过拟合风险，结果只用于判断"σ 是否量级错了"。
    """
    results = []
    for k in (0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6):
        prepared = np.array([
            max(0.0, round(row["center"] + k * row["z"] * row["sigma_level"]))
            for _, row in detail.iterrows()
        ])
        demand = detail["demand"].to_numpy(dtype=float)
        regrets = np.array([
            regret(q, d, row["price"], row["unit_cost"], row["price"] * DISCOUNT_RATIO)
            for q, d, (_, row) in zip(prepared, demand, detail.iterrows())
        ])
        results.append({
            "k": k,
            "regret_per_100": round(float(np.mean(regrets / np.maximum(demand, 1)) * 100), 2),
            "leftover_rate": round(float(np.sum(np.maximum(prepared - demand, 0)) / max(np.sum(prepared), 1)), 4),
            "stockout_rate": round(float(np.mean(prepared < demand)), 4),
            "mean_qty": round(float(np.mean(prepared)), 1),
        })
    return results


def evaluate() -> dict:
    frame = load_ledger()
    dates = sorted(frame["business_date"].unique())
    centers = walk_forward_centers(frame, dates)
    residual_by_dish: dict[int, list[float]] = {}
    pooled_residuals: list[float] = []
    rows = []
    for date_index, date in enumerate(dates):
        if date_index < MIN_TRAIN_DAYS:
            continue
        history = frame[frame["business_date"] < date]
        today = frame[frame["business_date"] == date]

        features, targets = [], []
        for _, past in history.iterrows():
            past_history = history[history["business_date"] < past["business_date"]]
            vector = build_features(past_history, past)
            if vector is not None:
                features.append(vector)
                targets.append(float(past["sold_qty"]))
        gbdt = None
        if len(features) >= 20:
            gbdt = lgb.LGBMRegressor(
                n_estimators=80, learning_rate=0.08, num_leaves=4,
                min_child_samples=4, subsample=1.0, random_state=7, verbose=-1,
            )
            gbdt.fit(np.asarray(features, dtype=float), np.asarray(targets, dtype=float))

        for _, row in today.iterrows():
            underage, overage, ratio, discount_price = cost_terms(row["price"], row["unit_cost"])
            z = float(norm.ppf(ratio))
            dish_history = history[history["dish_id"] == row["dish_id"]]
            sold_history = dish_history["sold_qty"].to_numpy(dtype=float)
            same_dow = dish_history[dish_history["weekday"] == row["weekday"]]["sold_qty"].to_numpy(dtype=float)

            baseline = {}
            if len(sold_history):
                baseline["median_roll7"] = float(np.median(sold_history[-7:]))
                baseline["mean_roll7"] = float(np.mean(sold_history[-7:]))
            if len(same_dow):
                baseline["median_same_dow"] = float(np.median(same_dow))
            baseline["yesterday"] = float(sold_history[-1]) if len(sold_history) else float(row["prepared_qty"])
            # 同星期样本常常只有 1 个点，缺就回落到 7 日中位数，避免整列 NaN
            baseline.setdefault("median_same_dow", baseline.get("median_roll7", baseline["yesterday"]))

            sigma = mad_scale(sold_history) if len(sold_history) >= 3 else 3.0

            entry = {
                "date": str(pd.Timestamp(date).date()),
                "dish_id": int(row["dish_id"]),
                "demand": float(row["sold_qty"]),
                "price": float(row["price"]),
                "unit_cost": float(row["unit_cost"]),
                "critical_ratio": round(ratio, 4),
                "actual_prepared": float(row["prepared_qty"]),
            }

            for name, center in baseline.items():
                entry[f"{name}_q"] = int(max(0, round(center + z * sigma)))

            # 残差尺度版：用同菜品滚动残差的中位绝对偏差，避免把"水平差异"当成"波动"
            residual_pool = residual_by_dish.get(int(row["dish_id"]), [])
            reference = residual_pool if len(residual_pool) >= 3 else pooled_residuals
            if reference:
                ratio_scale = 1.4826 * float(np.median(np.abs(reference)))
                sigma_residual = max(ratio_scale * max(baseline["median_roll7"], 1.0), 1.0)
            else:
                sigma_residual = max(0.08 * max(baseline["median_roll7"], 1.0), 1.0)
            entry["median_roll7_rs_q"] = int(max(0, round(
                baseline["median_roll7"] + z * sigma_residual)))
            entry["sigma_residual"] = round(sigma_residual, 2)
            entry["center"] = round(baseline["median_roll7"], 2)
            entry["z"] = round(z, 3)
            entry["sigma_level"] = round(sigma, 2)

            # 站点规则基线：昨日售出 × 1.10
            entry["rule_10pct_q"] = int(max(0, round(baseline["yesterday"] * 1.10)))

            # LightGBM：点预测 + 同一套 σ 规则
            if gbdt is not None:
                vector = build_features(history, row)
                if vector is not None:
                    entry["gbdt_q"] = int(max(0, round(float(gbdt.predict([vector])[0]) + z * sigma)))
                else:
                    entry["gbdt_q"] = entry["median_roll7_q"]
            else:
                entry["gbdt_q"] = entry["median_roll7_q"]

            entry["actual_q"] = int(row["prepared_qty"])
            for key in [item for item in list(entry) if item.endswith("_q")]:
                entry[f"{key[:-2]}_regret"] = round(
                    regret(entry[key], entry["demand"], entry["price"], entry["unit_cost"], discount_price), 2)
            rows.append(entry)

        # 当日结束后才把残差写入历史，保证不泄漏
        for _, row in today.iterrows():
            center = centers.get((date, row["dish_id"]))
            if center is None or center <= 0:
                continue
            error = (float(row["sold_qty"]) - center) / max(center, 1.0)
            residual_by_dish.setdefault(int(row["dish_id"]), []).append(error)
            pooled_residuals.append(error)

    detail = pd.DataFrame(rows)
    methods = [column[:-2] for column in detail.columns if column.endswith("_q")]
    metrics = {}
    for method in methods:
        prepared = detail[f"{method}_q"].to_numpy(dtype=float)
        demand = detail["demand"].to_numpy(dtype=float)
        regrets = detail[f"{method}_regret"].to_numpy(dtype=float)
        metrics[method] = {
            "mae": round(float(np.mean(np.abs(prepared - demand))), 2),
            "wape": round(float(np.sum(np.abs(prepared - demand)) / max(np.sum(demand), 1)), 4),
            "regret_per_100": round(float(np.mean(regrets / np.maximum(demand, 1)) * 100), 2),
            "leftover_rate": round(float(np.sum(np.maximum(prepared - demand, 0)) / max(np.sum(prepared), 1)), 4),
            "stockout_rate": round(float(np.mean(prepared < demand)), 4),
            "mean_qty": round(float(np.mean(prepared)), 1),
        }
    return {
        "source": "foodwise_operations_14d.csv",
        "rows_evaluated": int(len(detail)),
        "days_evaluated": int(detail["date"].nunique()),
        "min_train_days": MIN_TRAIN_DAYS,
        "sigma_scan": sigma_scan(detail),
        "cost_assumptions": {
            "shortage_lambda": SHORTAGE_LAMBDA,
            "discount_ratio": DISCOUNT_RATIO,
            "salvage_probability": SALVAGE_PROBABILITY,
        },
        "critical_ratio_by_dish": detail.groupby("dish_id")["critical_ratio"].first().round(4).to_dict(),
        "metrics": metrics,
    }


def main() -> int:
    result = evaluate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    header = f"{'method':<20}{'MAE':>7}{'WAPE':>8}{'regret/100':>12}{'剩余率':>9}{'缺货率':>9}{'均量':>7}"
    print(header)
    for name, values in result["metrics"].items():
        print(f"{name:<20}{values['mae']:>7.2f}{values['wape']:>8.3f}"
              f"{values['regret_per_100']:>12.2f}{values['leftover_rate']:>9.1%}"
              f"{values['stockout_rate']:>9.1%}{values['mean_qty']:>7.1f}")
    print(f"\nrows={result['rows_evaluated']} days={result['days_evaluated']} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())