"""比赛版可复现验证入口。

本脚本只生成方法级证据，不声称中国校园现场效果：
* 复用 45_simulate 的需求与决策逻辑；
* 用多个随机种子和情景汇总策略的 regret、剩余和缺货；
* 提供份、公斤、升、锅的可追溯单位换算；
* 对备餐流向执行数量守恒校验。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "modeling" / "data" / "03_output"


def _load_simulator():
    path = Path(__file__).with_name("45_simulate.py")
    spec = importlib.util.spec_from_file_location("foodwise_simulator", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载仿真器: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _quantity_value(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("数量必须是非负有限数") from error
    if not np.isfinite(numeric) or numeric < 0:
        raise ValueError("数量必须是非负有限数")
    return numeric


def convert_quantity(value: float, unit: str, *, batch_size: float | None = None) -> dict:
    """保留原始值并转换为该单位的基础量；锅/批次必须显式提供折算量。"""
    numeric = _quantity_value(value)
    units = {
        "份": ("portion", "serving", 1.0),
        "portion": ("portion", "serving", 1.0),
        "个": ("piece", "count", 1.0),
        "piece": ("piece", "count", 1.0),
        "克": ("gram", "mass", 1.0),
        "g": ("gram", "mass", 1.0),
        "公斤": ("gram", "mass", 1000.0),
        "kg": ("gram", "mass", 1000.0),
        "斤": ("gram", "mass", 500.0),
        "毫升": ("milliliter", "volume", 1.0),
        "ml": ("milliliter", "volume", 1.0),
        "升": ("milliliter", "volume", 1000.0),
        "L": ("milliliter", "volume", 1000.0),
    }
    if unit in units:
        canonical, dimension, factor = units[unit]
        conversion_source = "fixed_unit_factor"
    elif unit in {"锅", "批"}:
        try:
            numeric_batch_size = float(batch_size)
        except (TypeError, ValueError) as error:
            raise ValueError("锅/批次必须提供正的 batch_size 折算量") from error
        if not np.isfinite(numeric_batch_size) or numeric_batch_size <= 0:
            raise ValueError("锅/批次必须提供正的 batch_size 折算量")
        canonical, dimension, factor = "portion_equivalent", "serving", numeric_batch_size
        conversion_source = "operator_sampled_batch_factor"
    else:
        raise ValueError(f"不支持的计量单位: {unit}")
    return {
        "raw_qty": float(value),
        "raw_unit": unit,
        "dimension": dimension,
        "canonical_unit": canonical,
        "conversion_factor": float(factor),
        "canonical_qty": round(numeric * factor, 6),
        "conversion_source": conversion_source,
    }


def validate_flow(prepared: float, sold: float, discount_sold: float,
                  leftover: float, waste: float = 0.0, *, unit: str,
                  batch_size: float | None = None, tolerance: float = 1e-6) -> None:
    """校验同一量纲下的经营数量守恒；不同量纲不能相加。"""
    values = (prepared, sold, discount_sold, leftover, waste)
    converted = [convert_quantity(v, unit, batch_size=batch_size)["canonical_qty"] for v in values]
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance 必须是非负有限数")
    if sum(converted[1:]) > converted[0] + tolerance:
        raise ValueError("售出、优惠、剩余和损耗超过备餐量")
    if abs(converted[0] - sum(converted[1:])) > tolerance:
        raise ValueError("经营数量不守恒，请补充转移、员工餐或其他去向")


def _scenario(demand: pd.DataFrame, name: str, seed: int) -> pd.DataFrame:
    frame = demand.copy()
    rng = np.random.default_rng(seed + 991)
    if name == "rain_shock":
        frame["weather"] = "雨"
        frame["demand_qty"] = np.maximum(1, np.rint(frame["demand_qty"] * 0.967)).astype(int)
    elif name == "campus_event":
        frame["event_tag"] = "校园活动"
        frame["demand_qty"] = np.maximum(1, np.rint(frame["demand_qty"] * 1.15)).astype(int)
    elif name == "high_volatility":
        multiplier = rng.lognormal(mean=0.0, sigma=0.18, size=len(frame))
        frame["demand_qty"] = np.maximum(1, np.rint(frame["demand_qty"] * multiplier)).astype(int)
    elif name != "baseline":
        raise ValueError(f"未知情景: {name}")
    return frame


def _simulate_observation_limited(demand: pd.DataFrame, policy: str, simulator) -> pd.DataFrame:
    """逐日决策；历史只使用当时可见的售出量，售罄日不进入校准。"""
    if policy not in {"inertia", "safety", "model"}:
        raise ValueError(f"未知策略: {policy}")
    frame = demand.sort_values(["business_date", "dish_id"]).copy()
    history: dict[int, list[tuple[pd.Timestamp, int, bool]]] = {}
    residual_ratios: dict[int, list[float]] = {}
    pooled_ratios: list[float] = []
    prepared_values: list[int] = []
    predicted_values: list[int] = []
    rng = np.random.default_rng(7)
    for _, row in frame.iterrows():
        dish_id = int(row["dish_id"])
        date = pd.Timestamp(row["business_date"])
        observed = history.get(dish_id, [])
        same_weekday = [qty for past_date, qty, _ in observed if past_date.weekday() == date.weekday()]
        past_sales = [qty for _, qty, _ in observed]
        center = float(np.median(same_weekday[-4:])) if same_weekday else (
            float(np.median(past_sales[-7:])) if past_sales else float(row["base"]))
        ratio, _, _ = simulator.cost_terms(float(row["price"]), float(row["unit_cost"]))
        if policy == "inertia":
            prior_week = next((qty for past_date, qty, _ in reversed(observed)
                               if (date - past_date).days == 7), float(row["base"]))
            predicted = float(prior_week)
            proposed = predicted * (1 + rng.normal(0.15, 0.05))
        elif policy == "safety":
            predicted = center
            proposed = center * 1.10
        else:
            predicted = center
            ratios = residual_ratios.get(dish_id, [])
            calibration = ratios if len(ratios) >= 20 else pooled_ratios
            proposed = center * (1 + float(np.quantile(calibration[-400:], ratio))) if len(calibration) >= 30 else center * 1.10
        qty = int(min(max(round(proposed), 0), simulator.CAPACITY))
        qty = int(min(max(round(qty / simulator.MIN_BATCH) * simulator.MIN_BATCH,
                          simulator.MIN_BATCH), simulator.CAPACITY))
        prepared_values.append(qty)
        predicted_values.append(int(round(predicted)))
        demand_qty = int(row["demand_qty"])
        sold = min(qty, demand_qty)
        # A fully sold batch is censored or exactly exhausted; neither reveals an uncensored residual.
        stockout = sold >= qty
        history.setdefault(dish_id, []).append((date, sold, stockout))
        if not stockout:
            relative = (demand_qty - center) / max(center, 1.0)
            residual_ratios.setdefault(dish_id, []).append(relative)
            pooled_ratios.append(relative)
    frame["prepared_qty"] = prepared_values
    frame["predicted_qty"] = predicted_values
    frame["policy"] = policy
    return simulator.settle(frame)


def run_experiment(seeds: Iterable[int], days: int = 90) -> dict:
    simulator = _load_simulator()
    seed_values = [int(seed) for seed in seeds]
    policies = ("inertia", "safety", "model")
    scenarios = ("baseline", "rain_shock", "campus_event", "high_volatility")
    rows: list[dict] = []
    for seed in seed_values:
        base = simulator.generate_demand(days, int(seed))
        for scenario in scenarios:
            demand = _scenario(base, scenario, int(seed))
            for policy in policies:
                frame = _simulate_observation_limited(demand, policy, simulator)
                summary = simulator.calibrate({policy: frame})["scenarios"][policy]
                rows.append({"seed": int(seed), "scenario": scenario, "policy": policy, **summary})
    detail = pd.DataFrame(rows)
    metrics = ["regret_per_100", "waste_rate", "stockout_rate", "profit_per_day"]
    aggregate = []
    for (scenario, policy), group in detail.groupby(["scenario", "policy"], sort=True):
        result = {"scenario": scenario, "policy": policy, "runs": int(len(group))}
        for metric in metrics:
            values = group[metric].astype(float)
            result[f"{metric}_mean"] = round(float(values.mean()), 6)
            result[f"{metric}_p05"] = round(float(values.quantile(0.05)), 6)
            result[f"{metric}_p95"] = round(float(values.quantile(0.95)), 6)
        aggregate.append(result)
    return {
        "evidence_type": "calibrated_simulation",
        "synthetic": True,
        "days_per_run": int(days),
        "seeds": seed_values,
        "scenarios": list(scenarios),
        "policies": list(policies),
        "metrics": metrics,
        "detail": detail.to_dict(orient="records"),
        "aggregate": aggregate,
        "source_notes": [
            "需求与成本参数复用项目现有仿真器；星期/天气量级参考 ZHAW 公开食堂数据。",
            "芬兰学校食堂公开数据仅作为外部浪费量级参照，未直接注入本轮生成参数；所有输出均为仿真，不是中国校园实测。",
            "regret 是情景指标，成本与折价参数属于项目假设。",
            "本入口逐日只使用截至当日已观察到的售出量；售罄日不用于残差校准。",
        ],
        "scenario_assumptions": {
            "rain_shock": "需求按 0.967 缩放，参考项目当前 ZHAW 估计；仅用于敏感性测试。",
            "campus_event": "需求按 1.15 缩放，情景假设，不是公开数据估计。",
            "high_volatility": "逐行乘以 lognormal(mean=0, sigma=0.18) 扰动，属于压力测试设定。",
        },
        "dataset_evidence": [
            {
                "dataset": "ZHAW canteen menu sales 2017",
                "identifier": "https://doi.org/10.5281/zenodo.3890931",
                "use": "真实食堂销售需求的外部回测；用于验证需求基线与决策指标。",
                "limit": "瑞士食堂、菜单线/品类聚合，不是中国高校档口备餐与剩余数据。",
            },
            {
                "dataset": "Finland school food waste 2024-2025",
                "identifier": "https://doi.org/10.5281/zenodo.20825233",
                "use": "提供芬兰中学厨房与供餐浪费的外部量级参照；未直接注入本轮生成参数。",
                "limit": "厨房与供餐浪费不等同于备餐剩余；无菜品备餐量，不能验证备餐预测准确率或项目减损效果。",
            },
            {
                "dataset": "Reduce-Foodwaste pastry dataset",
                "identifier": "Kaggle: pastry-prediction",
                "use": "演示单位、守恒与异常数据拒绝测试。",
                "limit": "项目审计发现标准化后 ordered/sales/unsold 不守恒，不用于定量剩余率。",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20, help="随机种子数量")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed-start", type=int, default=20261102)
    parser.add_argument("--output", type=Path, default=OUT_DIR / "competition_validation.json")
    parser.add_argument("--force", action="store_true", help="允许覆盖指定输出文件")
    args = parser.parse_args()
    if args.seeds < 2 or args.days < 30:
        raise SystemExit("--seeds 至少为 2，--days 至少为 30")
    if args.output.exists() and not args.force:
        raise SystemExit(f"输出已存在，拒绝覆盖: {args.output}（如确需覆盖请传 --force）")
    seeds = range(args.seed_start, args.seed_start + args.seeds)
    report = run_experiment(seeds, args.days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in report["aggregate"]:
        print(row)
    print(f"写入: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
