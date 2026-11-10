"""决策层：报童临界分位 + 批量约束 + 成本/regret 评估。

对应方案创新点 B：把“带覆盖保证的区间”转成“成本最优的备餐量”，
并用 regret（相对事后最优的利润损失）而不是预测误差来评价决策。

成本口径（单份，单位：元）：
  * 缺货损失 Cu = (售价 − 单位成本) × (1 + λ)，λ 为信任/口碑损失系数；
  * 剩余损失 Co = 单位成本 − 折价售价 × 可售概率；
  * 临界比 = Cu / (Cu + Co)，最优备餐量取需求分布的该分位。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

_STANDARD = NormalDist()
_Z90 = 1.6448536269514722


@dataclass(frozen=True)
class CostModel:
    price: float
    unit_cost: float
    discount_price: float
    salvage_probability: float = 0.6
    shortage_lambda: float = 0.3

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("PRICE_NOT_POSITIVE")
        if not 0 < self.unit_cost < self.price:
            raise ValueError("UNIT_COST_OUT_OF_RANGE")
        if not 0 <= self.discount_price <= self.price:
            raise ValueError("DISCOUNT_PRICE_OUT_OF_RANGE")
        if not 0 <= self.salvage_probability <= 1:
            raise ValueError("SALVAGE_PROBABILITY_OUT_OF_RANGE")
        if self.shortage_lambda < 0:
            raise ValueError("SHORTAGE_LAMBDA_NEGATIVE")

    @property
    def underage(self) -> float:
        return (self.price - self.unit_cost) * (1.0 + self.shortage_lambda)

    @property
    def overage(self) -> float:
        return self.unit_cost - self.discount_price * self.salvage_probability

    @property
    def critical_ratio(self) -> float:
        overage = self.overage
        if overage <= 0:
            return 0.999
        return min(max(self.underage / (self.underage + overage), 0.01), 0.999)

    def profit(self, prepared: float, demand: float) -> float:
        """单期利润：售出收入 + 折价残值 − 备餐成本；缺货只体现为少赚。"""
        sold = min(prepared, demand)
        leftover = max(prepared - demand, 0.0)
        return (
            sold * self.price
            + leftover * self.discount_price * self.salvage_probability
            - prepared * self.unit_cost
        )


def sigma_from_interval(lower: float, upper: float, coverage: float = 0.90) -> float:
    """由对称区间反推正态标准差；区间越宽，标准差越大。"""
    if upper < lower:
        raise ValueError("UPPER_BELOW_LOWER")
    if not 0.0 < coverage < 1.0:
        raise ValueError("COVERAGE_OUT_OF_RANGE")
    z = _STANDARD.inv_cdf(0.5 + coverage / 2.0)
    return max((upper - lower) / (2.0 * z), 0.0)


def newsvendor_quantile(center: float, sigma: float, critical_ratio: float) -> float:
    """报童解：q* = F⁻¹(临界比)；正态假设下即 center + z·σ。"""
    if not 0.0 < critical_ratio < 1.0:
        raise ValueError("CRITICAL_RATIO_OUT_OF_RANGE")
    if sigma < 0:
        raise ValueError("SIGMA_NEGATIVE")
    return max(center + _STANDARD.inv_cdf(critical_ratio) * sigma, 0.0)


def apply_batch(prepared: float, minimum_batch: float = 1.0, capacity: float | None = None) -> int:
    """向上取整到最小批量，并压到产能上限。"""
    if minimum_batch <= 0:
        raise ValueError("MINIMUM_BATCH_NOT_POSITIVE")
    if prepared < 0:
        raise ValueError("PREPARED_NEGATIVE")
    quantity = int(math.ceil(prepared / minimum_batch) * minimum_batch)
    if capacity is not None:
        if capacity < 0:
            raise ValueError("CAPACITY_NEGATIVE")
        quantity = min(quantity, int(capacity))
    return max(quantity, 0)


def evaluate_decisions(cost: CostModel, prepared: list[float], demand: list[float]) -> dict:
    """汇总一组决策的成本、缺货/剩余率与相对事后最优的 regret。"""
    if len(prepared) != len(demand) or not demand:
        raise ValueError("LENGTH_MISMATCH")
    if any(value < 0 for value in demand):
        raise ValueError("NEGATIVE_DEMAND")

    total_profit = 0.0
    oracle_profit = 0.0
    stockout = 0.0
    leftover = 0.0
    total_prepared = 0.0
    total_demand = 0.0
    for quantity, actual in zip(prepared, demand):
        total_profit += cost.profit(quantity, actual)
        oracle_profit += cost.profit(actual, actual)
        stockout += max(actual - quantity, 0.0)
        leftover += max(quantity - actual, 0.0)
        total_prepared += quantity
        total_demand += actual

    oracle = max(oracle_profit, 1e-9)
    loss = oracle_profit - total_profit
    return {
        "profit": total_profit,
        "oracle_profit": oracle_profit,
        "regret": loss / oracle,
        "loss_per_100": loss / total_demand * 100.0 if total_demand else 0.0,
        "stockout_rate": stockout / total_demand if total_demand else 0.0,
        "leftover_rate": leftover / total_prepared if total_prepared else 0.0,
        "mean_prepared": total_prepared / len(demand),
        "mean_demand": total_demand / len(demand),
        "n": len(demand),
    }