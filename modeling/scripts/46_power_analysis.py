"""E1：需要多少天才能看出差别。

两个问题：
  (1) 按仿真器给出的真实效应量（很小区间），多少天能检出？
  (2) 如果效应真有 7.7pp（台账前后对比观察到的差），多少天能检出？

配对设计：同一份需求同时喂给 inertia 与 model，逐日比较剩余率 / 每百份后悔 / 日利润，
用配对 t 检验，显著性 0.05，理想检出率 0.80。
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
sim = importlib.import_module("45_simulate")

OUT = Path("modeling/data/03_output/experiment_e1_power.json")
REPLICATES = 100
DAYS = 90
WINDOWS = (7, 14, 21, 28, 35, 45, 60, 90)
ALPHA = 0.05


def daily_metrics(frame, policy: str) -> dict[str, np.ndarray]:
    grouped = frame.groupby("business_date")
    prepared = grouped["prepared_qty"].sum().to_numpy(dtype=float)
    sold = grouped["sold_qty"].sum().to_numpy(dtype=float)
    demand = grouped["demand_qty"].sum().to_numpy(dtype=float)
    leftover = grouped["leftover_qty"].sum().to_numpy(dtype=float)
    profit = (frame["sold_qty"] * frame["price"]
              + frame["discount_sold_qty"] * frame["price"] * sim.DISCOUNT_RATIO
              - frame["prepared_qty"] * frame["unit_cost"]).groupby(frame["business_date"]).sum()
    return {
        "waste_rate": leftover / np.clip(prepared, 1, None),
        "profit": profit.to_numpy(dtype=float),
        "regret_per_100": ((demand * (frame.groupby("business_date")["price"].mean().to_numpy() - 0))
                           * 0 + 1) * 0,  # 占位，下面重算
    }


def run_replicate(seed: int) -> dict[str, np.ndarray]:
    demand = sim.generate_demand(DAYS, seed)
    results = {}
    for policy in ("inertia", "model"):
        frame = sim.settle(sim.prepare(demand.assign(policy=policy), policy))
        grouped = frame.groupby("business_date")
        prepared = grouped["prepared_qty"].sum().to_numpy(dtype=float)
        demand_daily = grouped["demand_qty"].sum().to_numpy(dtype=float)
        leftover = grouped["leftover_qty"].sum().to_numpy(dtype=float)
        profit = (frame["sold_qty"] * frame["price"]
                  + frame["discount_sold_qty"] * frame["price"] * sim.DISCOUNT_RATIO
                  - frame["prepared_qty"] * frame["unit_cost"]).groupby(
            frame["business_date"]).sum().to_numpy(dtype=float)
        # 每百份后悔：事后最优（备餐=需求）利润减去实际利润，按需求归一
        oracle = (frame["demand_qty"] * (frame["price"] - frame["unit_cost"])).groupby(
            frame["business_date"]).sum().to_numpy(dtype=float)
        results[policy] = {
            "waste_rate": leftover / np.clip(prepared, 1, None),
            "profit": profit,
            "regret_per_100": (oracle - profit) / np.clip(demand_daily, 1, None) * 100,
        }
    return results


def power_curve(differences: np.ndarray, windows=WINDOWS) -> list[dict]:
    rows = []
    for n in windows:
        detected = 0
        for replicate in differences:
            sample = replicate[:n]
            if np.std(sample, ddof=1) == 0:
                continue
            _, p_value = stats.ttest_rel(sample, np.zeros_like(sample))
            if p_value < ALPHA and sample.mean() < 0:  # 只算"正确方向的检出"
                detected += 1
        rows.append({
            "days": n,
            "effect_pp": round(float(np.mean([r[:n].mean() for r in differences])), 4),
            "power": round(detected / len(differences), 3),
        })
    return rows


def ledger_sigma() -> float:
    """真实台账基线期逐日剩余率的标准差——用来回答"14 天够不够"。"""
    import pandas as pd
    frame = pd.read_csv("src/main/resources/data/foodwise_operations_14d.csv")
    base = frame[frame["phase"] == "基线期"].groupby("business_date")[
        ["prepared_qty", "leftover_qty"]].sum()
    return float((base["leftover_qty"] / base["prepared_qty"]).std(ddof=1))


def main() -> int:
    waste_diffs, regret_diffs, profit_diffs = [], [], []
    for seed in range(REPLICATES):
        result = run_replicate(seed)
        inertia, model = result["inertia"], result["model"]
        waste_diffs.append(model["waste_rate"] - inertia["waste_rate"])
        regret_diffs.append(model["regret_per_100"] - inertia["regret_per_100"])
        profit_diffs.append(model["profit"] - inertia["profit"])

    waste_diffs = np.array(waste_diffs)
    sigma_daily = float(np.std(waste_diffs))  # 配对差的标准差
    effect = float(np.mean(waste_diffs))
    sigma_ledger = ledger_sigma()

    def required_days(delta: float, sigma: float = sigma_daily) -> float:
        return (1.96 + 0.8416) ** 2 * sigma ** 2 / max(delta, 1e-9) ** 2

    payload = {
        "replicates": REPLICATES,
        "days": DAYS,
        "alpha": ALPHA,
        "paired_effect": {
            "waste_rate_diff": round(effect, 5),
            "regret_per_100_diff": round(float(np.mean(regret_diffs)), 3),
            "profit_per_day_diff": round(float(np.mean(profit_diffs)), 2),
            "sigma_daily_waste_rate": round(sigma_daily, 5),
        },
        "power_waste_rate": power_curve(waste_diffs),
        "power_regret": power_curve(regret_diffs),
        "power_profit": power_curve(profit_diffs),
        "required_days_for_5pp": round(required_days(0.05), 1),
        "required_days_for_observed_7_7pp": round(required_days(0.077), 1),
        "ledger_sigma_daily": round(sigma_ledger, 5),
        "required_days_ledger_sigma": {
            "for_5pp": round(required_days(0.05, sigma_ledger), 1),
            "for_7_7pp": round(required_days(0.077, sigma_ledger), 1),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"配对差：剩余率 {effect*100:+.2f}pp，σ={sigma_daily*100:.2f}pp；"
          f"regret {np.mean(regret_diffs):+.2f}/百份；利润 {np.mean(profit_diffs):+.1f}/日")
    print(f"{'days':>5}{'power(剩余率)':>16}{'power(regret)':>16}{'power(利润)':>14}")
    for row_w, row_r, row_p in zip(payload["power_waste_rate"], payload["power_regret"],
                                   payload["power_profit"]):
        print(f"{row_w['days']:>5}{row_w['power']:>16.2f}{row_r['power']:>16.2f}{row_p['power']:>14.2f}")
    print(f"\n检 5pp 需要 {payload['required_days_for_5pp']} 天；"
          f"检 7.7pp 需要 {payload['required_days_for_observed_7_7pp']} 天 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())