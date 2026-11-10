"""决策回放：把区间变成备餐量，比较四种策略的期望成本与 regret。

输入：modeling/data/03_output/interval_test_predictions.csv（由 32_fit_intervals.py 产出）
输出：modeling/data/03_output/decision_backtest_metrics.json

方法：
  1. rule_10pct              现状口径：中心值 × 安全系数
  2. newsvendor_raw          用未校准区间估 σ，再取临界分位
  3. newsvendor_calibrated   用 CQR 校准区间估 σ，再取临界分位
  4. newsvendor_batch        校准区间 + 最小批量/产能约束

评价：以“事后最优备餐”为基准计算 regret（利润损失占比），而不是看预测误差。
场景扫描：改变剩余可折价售出概率（决定临界比），检验固定安全系数在成本结构变化时是否失效。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modeling"))

from foodwise_ml.decision import (  # noqa: E402
    CostModel,
    apply_batch,
    newsvendor_quantile,
    sigma_from_interval,
)

PREDICTIONS = ROOT / "modeling" / "data" / "03_output" / "interval_test_predictions.csv"
INTERVAL_METRICS = ROOT / "modeling" / "data" / "03_output" / "interval_backtest_metrics.json"
OUTPUT = ROOT / "modeling" / "data" / "03_output" / "decision_backtest_metrics.json"


def load_bias() -> float:
    if not INTERVAL_METRICS.is_file():
        return 0.0
    doc = json.loads(INTERVAL_METRICS.read_text(encoding="utf-8"))
    return float(doc.get("calibration", {}).get("bias", 0.0))


def degenerate_rows(frame: pd.DataFrame, salvage: float, discount_ratio: float) -> int:
    """剩余损失 ≤ 0 时报童问题无界（越备越赚），该场景不作为比较对象。"""
    overage = frame["unit_cost"].astype(float) - frame["price"].astype(float) * discount_ratio * salvage
    return int((overage <= 0).sum())


def bootstrap_regret_diff(models, prepared_a, prepared_b, demand, reps=1000, seed=42, block=14):
    """分块自助法：按连续 14 行成块重采样，尊重时间自相关，避免把行当独立样本。"""
    profits_a = np.array([model.profit(q, y) for model, q, y in zip(models, prepared_a, demand)])
    profits_b = np.array([model.profit(q, y) for model, q, y in zip(models, prepared_b, demand)])
    oracle = np.array([model.profit(y, y) for model, y in zip(models, demand)])
    rng = np.random.default_rng(seed)
    count = len(demand)
    block = max(1, min(int(block), count))
    blocks = int(np.ceil(count / block))
    diffs = np.empty(reps)
    for index in range(reps):
        starts = rng.integers(0, count, blocks)
        sample = np.concatenate([(np.arange(start, start + block) % count) for start in starts])[:count]
        total = oracle[sample].sum()
        diffs[index] = ((total - profits_a[sample].sum()) - (total - profits_b[sample].sum())) / max(total, 1e-9)
    return {
        "mean": float(np.mean(diffs)),
        "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
        "reps": reps,
        "block": block,
    }


def scenario_inputs(frame: pd.DataFrame, salvage: float, args):
    models = [
        CostModel(
            price=float(row["price"]),
            unit_cost=float(row["unit_cost"]),
            discount_price=float(row["price"]) * args.discount_ratio,
            salvage_probability=salvage,
            shortage_lambda=args.shortage_lambda,
        )
        for _, row in frame.iterrows()
    ]
    return models


def quantities_for(models, centers, sigma_raw, sigma_cal, args):
    ratios = [model.critical_ratio for model in models]
    return {
        "rule_10pct": [center * args.safety_factor for center in centers],
        "newsvendor_raw": [
            newsvendor_quantile(center, sigma, ratio)
            for center, sigma, ratio in zip(centers, sigma_raw, ratios)
        ],
        "newsvendor_calibrated": [
            newsvendor_quantile(center, sigma, ratio)
            for center, sigma, ratio in zip(centers, sigma_cal, ratios)
        ],
        "newsvendor_batch": [
            apply_batch(newsvendor_quantile(center, sigma, ratio), args.minimum_batch, args.capacity)
            for center, sigma, ratio in zip(centers, sigma_cal, ratios)
        ],
    }


def run_scenario(frame: pd.DataFrame, centers, sigma_raw, sigma_cal, salvage: float, args) -> dict:
    models = scenario_inputs(frame, salvage, args)
    ratios = [model.critical_ratio for model in models]
    demand = frame["sold_qty"].astype(float).tolist()
    prepared = quantities_for(models, centers, sigma_raw, sigma_cal, args)

    results = {}
    for name, quantities in prepared.items():
        totals = {"profit": 0.0, "oracle": 0.0, "stockout": 0.0, "leftover": 0.0, "prepared": 0.0}
        for model, quantity, actual in zip(models, quantities, demand):
            totals["profit"] += model.profit(quantity, actual)
            totals["oracle"] += model.profit(actual, actual)
            totals["stockout"] += max(actual - quantity, 0.0)
            totals["leftover"] += max(quantity - actual, 0.0)
            totals["prepared"] += quantity
        results[name] = {
            "profit": totals["profit"],
            "oracle_profit": totals["oracle"],
            "regret": (totals["oracle"] - totals["profit"]) / max(totals["oracle"], 1e-9),
            "loss_per_100": (totals["oracle"] - totals["profit"]) / sum(demand) * 100.0,
            "stockout_rate": totals["stockout"] / sum(demand),
            "leftover_rate": totals["leftover"] / max(totals["prepared"], 1e-9),
            "mean_prepared": totals["prepared"] / len(demand),
            "n": len(demand),
        }
    return {
        "salvage_probability": salvage,
        "mean_critical_ratio": sum(ratios) / len(ratios),
        "methods": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discount-ratio", type=float, default=0.5, help="折价售价 / 原价")
    parser.add_argument("--salvage-probability", type=float, default=0.6, help="基准场景：剩余可售概率")
    parser.add_argument("--shortage-lambda", type=float, default=0.3, help="缺货的信任损失系数")
    parser.add_argument("--safety-factor", type=float, default=1.10, help="现状规则的安全系数")
    parser.add_argument("--minimum-batch", type=float, default=5.0)
    parser.add_argument("--capacity", type=float, default=250.0)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if not PREDICTIONS.is_file():
        raise SystemExit(f"PREDICTIONS_MISSING:{PREDICTIONS}（先跑 32_fit_intervals.py）")
    frame = pd.read_csv(PREDICTIONS)
    if frame.empty:
        raise SystemExit("PREDICTIONS_EMPTY")

    bias = load_bias()
    centers = [((lo + hi) / 2.0) + bias for lo, hi in zip(frame["lo_cal"], frame["hi_cal"])]
    sigma_raw = [
        sigma_from_interval(lo, hi)
        for lo, hi in zip(frame["lo_raw"].astype(float), frame["hi_raw"].astype(float))
    ]
    sigma_cal = [
        sigma_from_interval(lo, hi)
        for lo, hi in zip(frame["lo_cal"].astype(float), frame["hi_cal"].astype(float))
    ]

    base = run_scenario(frame, centers, sigma_raw, sigma_cal, args.salvage_probability, args)
    demand = frame["sold_qty"].astype(float).tolist()
    base_models = scenario_inputs(frame, args.salvage_probability, args)
    base_prepared = quantities_for(base_models, centers, sigma_raw, sigma_cal, args)
    base["bootstrap"] = {
        "rule_minus_calibrated": bootstrap_regret_diff(
            base_models, base_prepared["rule_10pct"], base_prepared["newsvendor_calibrated"], demand
        ),
        "rule_minus_raw": bootstrap_regret_diff(
            base_models, base_prepared["rule_10pct"], base_prepared["newsvendor_raw"], demand
        ),
    }

    sweep = []
    skipped = []
    for salvage in (0.0, 0.2, 0.4, 0.6, 0.7):
        if degenerate_rows(frame, salvage, args.discount_ratio):
            skipped.append(salvage)
            continue
        sweep.append(run_scenario(frame, centers, sigma_raw, sigma_cal, salvage, args))

    if sweep:
        lowest = sweep[0]
        low_models = scenario_inputs(frame, lowest["salvage_probability"], args)
        low_prepared = quantities_for(low_models, centers, sigma_raw, sigma_cal, args)
        lowest["bootstrap"] = {
            "rule_minus_calibrated": bootstrap_regret_diff(
                low_models, low_prepared["rule_10pct"], low_prepared["newsvendor_calibrated"], demand
            )
        }

    metrics = {
        "dataset": "finetune_uwaste",
        "rows": len(frame),
        "assumptions": {
            "discount_ratio": args.discount_ratio,
            "shortage_lambda": args.shortage_lambda,
            "safety_factor": args.safety_factor,
            "minimum_batch": args.minimum_batch,
            "capacity": args.capacity,
        },
        "cost_summary": {
            "mean_price": float(frame["price"].mean()),
            "mean_unit_cost": float(frame["unit_cost"].mean()),
            "mean_demand": float(frame["sold_qty"].mean()),
        },
        "base_scenario": base,
        "scenarios": sweep,
        "skipped_salvage": skipped,
        "bias_correction": bias,
        "limits": [
            "成本参数（折价比例、可售概率、信任损失）为情景假设，未经现场财务数据校准。",
            "需求为派生目标，regret 只反映策略相对排序，不等于现场减损金额。",
            "未建模分时段售卖与二次补餐，单期报童是简化。",
            "安全系数只取 1.10 一个值，未做规则参数调优，规则与算法并非同等调参预算。",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_copy = ROOT / "src" / "main" / "resources" / "modeling" / "decision_backtest_metrics.json"
    evidence_copy.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"rows={len(frame)} price={metrics['cost_summary']['mean_price']:.2f} "
          f"unit_cost={metrics['cost_summary']['mean_unit_cost']:.2f} "
          f"critical_ratio={base['mean_critical_ratio']:.3f}")
    print(f"\n[base] salvage={args.salvage_probability}")
    print(f"{'method':<24}{'regret':>8}{'loss/100':>10}{'stockout':>10}{'leftover':>10}{'mean_q':>9}")
    for name, row in base["methods"].items():
        print(
            f"{name:<24}{row['regret']:>8.3%}{row['loss_per_100']:>10.2f}"
            f"{row['stockout_rate']:>10.3f}{row['leftover_rate']:>10.3f}{row['mean_prepared']:>9.1f}"
        )

    print("\n[sweep] regret by critical ratio")
    print(f"{'salvage':>8}{'ratio':>8}{'rule':>9}{'nv_raw':>9}{'nv_cal':>9}{'nv_batch':>10}{'rule-nv':>9}")
    for scenario in sweep:
        methods = scenario["methods"]
        rule = methods["rule_10pct"]["regret"]
        calibrated = methods["newsvendor_calibrated"]["regret"]
        print(
            f"{scenario['salvage_probability']:>8.1f}{scenario['mean_critical_ratio']:>8.3f}"
            f"{rule:>9.3%}{methods['newsvendor_raw']['regret']:>9.3%}{calibrated:>9.3%}"
            f"{methods['newsvendor_batch']['regret']:>10.3%}{(rule - calibrated) * 100:>9.2f}"
        )

    print("\n[bootstrap 95% CI] regret(rule) - regret(method); 正值表示成本感知更优")
    for label, block in (("base", base), ("lowest-ratio", sweep[0] if sweep else None)):
        if not block or "bootstrap" not in block:
            continue
        for name, stats in block["bootstrap"].items():
            print(
                f"{label:<14}{name:<24}{stats['mean'] * 100:>8.2f}pp "
                f"[{stats['ci95'][0] * 100:.2f}, {stats['ci95'][1] * 100:.2f}]"
            )
    if skipped:
        print(f"skipped degenerate salvage (overage<=0): {skipped}")
    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())