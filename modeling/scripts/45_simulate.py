"""校准型仿真器：生成与站点台账逐列同构的 90 天数据，并带一列真值 demand_qty。

参数来源：
  需求水平、售价、成本      ← 站点演示台账 14 天的实测均值
  星期效应、天气系数         ← ZHAW 大学食堂 60 天真实交易（周一 1.072、周五 0.757、雨天 0.967）
  日销量波动（CV≈0.17）      ← ZHAW 两食堂日销量标准差/均值
  浪费率水平 14.54%          ← 30 省 30 校 9,660 份问卷《全国高校食堂堂食浪费概况》

三种决策者（同一份需求，配对比较）：
  inertia  昨天备多少，今天照抄并抖 10%   —— 复现"备餐与客流脱钩"
  safety   近 7 日中位数 × 1.10           —— 站点的规则基线
  model    近 7 日中位数 + z(ρ)·σ          —— 站点决策卡公式

刻意不做的：类别浪费率顺序。源数据没有"备餐/剩余"分类，文献里的类别差异是餐盘浪费口径，
直接搬到备餐过剩上属于偷换口径，因此不生成、也不断言。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

RAW_DIR = Path("modeling/data/01_raw")
OUT_DIR = Path("modeling/data/03_output")

# 菜品 → 档口 / 品类 / 售价 / 成本（与站点台账一致）
DISHES = [
    {"dish_id": 1, "dish_name": "香菇滑鸡饭", "stall": "拾味小厨", "price": 13.0, "unit_cost": 5.2, "base": 76.0, "cv": 0.09},
    {"dish_id": 2, "dish_name": "番茄牛腩饭", "stall": "拾味小厨", "price": 16.0, "unit_cost": 7.1, "base": 52.8, "cv": 0.11},
    {"dish_id": 3, "dish_name": "照烧鸡腿饭", "stall": "拾味小厨", "price": 15.0, "unit_cost": 6.4, "base": 47.6, "cv": 0.10},
    {"dish_id": 4, "dish_name": "红烧牛肉面", "stall": "暖食面坊", "price": 15.0, "unit_cost": 6.8, "base": 60.6, "cv": 0.09},
    {"dish_id": 5, "dish_name": "金枪鱼全麦卷", "stall": "谷禾轻食", "price": 14.0, "unit_cost": 6.1, "base": 34.2, "cv": 0.15},
    {"dish_id": 6, "dish_name": "鸡胸谷物碗", "stall": "谷禾轻食", "price": 18.0, "unit_cost": 8.2, "base": 41.2, "cv": 0.14},
    {"dish_id": 7, "dish_name": "全麦鸡蛋三明治", "stall": "麦香烘焙", "price": 9.0, "unit_cost": 3.5, "base": 42.9, "cv": 0.16},
]

# ZHAW 60 天实测（周一…周五）；周末为假设值，因为源数据只有工作日
WEEKDAY_MULTIPLIER = {0: 1.072, 1: 1.161, 2: 1.007, 3: 1.003, 4: 0.757, 5: 0.70, 6: 0.68}
RAIN_MULTIPLIER = 0.967
EVENT_MULTIPLIER = {"正常教学": 1.0, "考试周": 0.90, "校园活动": 1.15}
DEMAND_CV = 0.10
SHORTAGE_LAMBDA = 0.3
DISCOUNT_RATIO = 0.5
SALVAGE_PROBABILITY = 0.6
DISCOUNT_TAKE_RATE = 0.60  # 与 DecisionCostModel.salvageProbability 对齐，否则临界比会系统性高估
CAPACITY = 250
MIN_BATCH = 5

# 与站点台账逐列同构；demand_qty 是仿真独有的真值列，只许用于评估
LEDGER_COLUMNS = [
    "business_date", "phase", "stall", "dish_id", "dish_name", "price", "unit_cost",
    "predicted_qty", "prepared_qty", "sold_qty", "discount_sold_qty", "leftover_qty",
    "revenue", "weather", "event_tag", "recommendation_adopted",
]
OUTPUT_COLUMNS = LEDGER_COLUMNS + ["demand_qty", "synthetic"]

FEATURE_COLUMNS = [
    "weekday", "weather_code", "event_code", "price", "unit_cost",
    "last_7_median", "last_3_median", "trend_3",
]


def cost_terms(price: float, unit_cost: float) -> tuple[float, float, float]:
    underage = (price - unit_cost) * (1 + SHORTAGE_LAMBDA)
    overage = unit_cost - price * DISCOUNT_RATIO * SALVAGE_PROBABILITY
    ratio = 0.999 if overage <= 0 else underage / (underage + overage)
    return min(max(ratio, 0.01), 0.999), underage, overage


def generate_demand(days: int, seed: int) -> pd.DataFrame:
    """先把需求生成一次，三个决策者共用，保证配对可比。"""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-09-07")  # 周一
    rows = []
    for day in range(days):
        date = start + pd.Timedelta(days=day)
        weekday = date.dayofweek
        weather = "雨" if rng.random() < 0.25 else ("晴" if rng.random() < 0.7 else "多云")
        event = "考试周" if (day // 15) % 3 == 2 else "正常教学"
        weather_factor = RAIN_MULTIPLIER if weather == "雨" else 1.0
        trend = 1.0 + 0.05 * (day / max(days - 1, 1) - 0.5)
        for dish in DISHES:
            lam = (dish["base"] * WEEKDAY_MULTIPLIER[weekday] * weather_factor
                   * EVENT_MULTIPLIER[event] * trend)
            noise = rng.lognormal(mean=0.0, sigma=dish["cv"])
            demand = max(1, int(round(lam * noise)))
            rows.append({
                "business_date": date, "weekday": weekday, "weather": weather,
                "event_tag": event, "demand_qty": demand, **dish,
            })
    return pd.DataFrame(rows)


def prepare(demand: pd.DataFrame, policy: str) -> pd.DataFrame:
    """按三种决策者逐日推演备餐量。

    inertia 复刻"师傅按上周同一天卖了多少、上浮一点"的做法——它有经验、也愿意留余量，
    但看的是上周而不是今天，所以剩余与实际客流脱钩。
    """
    frame = demand.sort_values(["dish_id", "business_date"]).copy()
    prepared_values = []
    predicted_values = []
    history: dict[int, list[tuple[pd.Timestamp, int]]] = {}
    residuals: dict[int, list[float]] = {}
    residual_ratios: dict[int, list[float]] = {}
    pooled_errors: list[float] = []
    rng = np.random.default_rng(seed=7)

    def same_weekday_last_week(dish_id: int, date: pd.Timestamp) -> int | None:
        for past_date, value in history.get(dish_id, []):
            if (date - past_date).days == 7:
                return value
        return None

    for _, row in frame.iterrows():
        dish_id = row["dish_id"]
        date = row["business_date"]
        past = [value for _, value in history.get(dish_id, [])]
        same_weekday = [value for past_date, value in history.get(dish_id, [])
                        if past_date.weekday() == date.weekday()]
        if same_weekday:
            center = float(np.median(same_weekday[-4:]))
        elif past:
            center = float(np.median(past[-7:]))
        else:
            center = float(row["base"])
        ratio, _, _ = cost_terms(row["price"], row["unit_cost"])

        if policy == "inertia":
            last_week = same_weekday_last_week(dish_id, date)
            anchor = float(last_week) if last_week is not None else float(row["base"])
            predicted = anchor
            q = anchor * (1 + rng.normal(0.15, 0.05))
        elif policy == "safety":
            predicted = center
            q = center * 1.10
        elif policy == "model":
            predicted = center
            # 直接取池化相对残差的 ρ 分位，而不是先估 σ 再套正态：
            # 误差分布不一定对称、更不一定正态，分位数用不着假设形状。
            errors = residuals.get(dish_id, [])
            own_ratios = residual_ratios.get(dish_id, [])
            if len(own_ratios) >= 20:
                q = center * (1 + float(np.quantile(own_ratios[-40:], ratio)))
            elif len(pooled_errors) >= 30:
                uplift = float(np.quantile(pooled_errors[-400:], ratio))
                q = center * (1 + uplift)
            elif len(errors) >= 3:
                sigma = 1.4826 * float(np.median(np.abs(errors[-8:])))
                q = center + norm.ppf(ratio) * max(sigma, 1.0)
            else:
                q = center * 1.10
        else:
            raise ValueError(f"unknown policy: {policy}")

        q = int(min(max(round(q), 0), CAPACITY))
        q = int(min(max(round(q / MIN_BATCH) * MIN_BATCH, MIN_BATCH), CAPACITY))
        prepared_values.append(q)
        predicted_values.append(int(round(predicted)))
        history.setdefault(dish_id, []).append((date, int(row["demand_qty"])))
        residuals.setdefault(dish_id, []).append(float(row["demand_qty"]) - center)
        pooled_errors.append((float(row["demand_qty"]) - center) / max(center, 1.0))
        residual_ratios.setdefault(dish_id, []).append((float(row["demand_qty"]) - center) / max(center, 1.0))

    frame["prepared_qty"] = prepared_values
    frame["predicted_qty"] = predicted_values
    return frame


def settle(frame: pd.DataFrame) -> pd.DataFrame:
    """售出、折价、剩余、收入。售出必须截断到备餐量——这是还原售罄的关键。"""
    sold = np.minimum(frame["prepared_qty"], frame["demand_qty"])
    leftover = frame["prepared_qty"] - sold
    discount_sold = np.minimum(np.round(leftover * DISCOUNT_TAKE_RATE), leftover).astype(int)
    frame["sold_qty"] = sold.astype(int)
    frame["discount_sold_qty"] = discount_sold
    frame["leftover_qty"] = (leftover - discount_sold).astype(int)
    frame["revenue"] = (frame["sold_qty"] * frame["price"]
                        + frame["discount_sold_qty"] * frame["price"] * DISCOUNT_RATIO).round(2)
    frame["phase"] = np.where(frame["business_date"] <= frame["business_date"].quantile(0.5), "基线期", "干预期")
    frame["recommendation_adopted"] = (frame["phase"] == "干预期") & (frame["policy"] == "model")
    frame["synthetic"] = True
    return frame.sort_values(["business_date", "dish_id"])


def calibrate(frames: dict[str, pd.DataFrame]) -> dict:
    summary = {"scenarios": {}, "feature_contract": FEATURE_COLUMNS, "generated_days": None}
    for policy, frame in frames.items():
        daily = frame.groupby("business_date")[["prepared_qty", "sold_qty", "leftover_qty", "demand_qty"]].sum()
        daily["rate"] = daily["leftover_qty"] / daily["prepared_qty"].clip(lower=1)
        cvs = []
        for _, part in frame.groupby("dish_id"):
            cvs.append(float(part["demand_qty"].std() / max(part["demand_qty"].mean(), 1)))
        profit = (frame["sold_qty"] * frame["price"]
                  + frame["discount_sold_qty"] * frame["price"] * DISCOUNT_RATIO
                  - frame["prepared_qty"] * frame["unit_cost"])
        # 事后最优：备餐恰好等于需求
        oracle = (frame["demand_qty"] * (frame["price"] - frame["unit_cost"]))
        regret = oracle - profit
        summary["scenarios"][policy] = {
            "rows": int(len(frame)),
            "days": int(frame["business_date"].nunique()),
            "waste_rate": round(float(frame["leftover_qty"].sum() / max(frame["prepared_qty"].sum(), 1)), 4),
            "unsold_rate": round(float((frame["prepared_qty"] - frame["sold_qty"]).sum()
                                       / max(frame["prepared_qty"].sum(), 1)), 4),
            "stockout_rate": round(float((frame["prepared_qty"] < frame["demand_qty"]).mean()), 4),
            "corr_prepared_demand": round(float(frame["prepared_qty"].corr(frame["demand_qty"])), 3),
            "corr_daily_rate_demand": round(float(daily["rate"].corr(daily["demand_qty"])), 3),
            "daily_rate_mean": round(float(daily["rate"].mean()), 4),
            "daily_rate_median": round(float(daily["rate"].median()), 4),
            "daily_rate_p95": round(float(daily["rate"].quantile(0.95)), 4),
            "demand_cv_mean": round(float(np.mean(cvs)), 3),
            "profit_per_day": round(float(profit.sum() / frame["business_date"].nunique()), 1),
            "regret_per_100": round(float((regret / frame["demand_qty"].clip(lower=1)).mean() * 100), 2),
            "mean_prepared": round(float(frame["prepared_qty"].mean()), 1),
            "mean_demand": round(float(frame["demand_qty"].mean()), 1),
        }
        summary["generated_days"] = int(frame["business_date"].nunique())
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20261027)
    args = parser.parse_args()

    demand = generate_demand(args.days, args.seed)
    frames = {}
    for policy in ("inertia", "safety", "model"):
        frames[policy] = settle(prepare(demand.assign(policy=policy), policy))
        frames[policy] = frames[policy][OUTPUT_COLUMNS]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for policy, frame in frames.items():
        frame.to_csv(RAW_DIR / f"sim_operations_{policy}.csv", index=False, encoding="utf-8-sig")
    summary = calibrate(frames)
    summary["seed"] = args.seed
    (OUT_DIR / "sim_calibration.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'policy':<10}{'waste':>8}{'stockout':>10}{'corr':>8}{'均值':>8}{'CV':>7}{'日率均值':>10}")
    for policy, values in summary["scenarios"].items():
        print(f"{policy:<10}{values['waste_rate']:>8.1%}{values['stockout_rate']:>10.1%}"
              f"{values['corr_prepared_demand']:>8.2f}{values['mean_prepared']:>8.1f}"
              f"{values['demand_cv_mean']:>7.2f}{values['daily_rate_mean']:>10.1%}")
    print(f"\n-> {RAW_DIR}/sim_operations_*.csv   -> {OUT_DIR}/sim_calibration.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())