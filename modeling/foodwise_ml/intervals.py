"""区间校准：CQR 偏移、分层收缩、自适应保形推断（ACI）与区间指标。

方法对应方案创新点 A：
  1. CQR（Conformalized Quantile Regression）：用校准集残差分位数偏移分位模型，
     得到有限样本近似覆盖的区间。
  2. 分层收缩：按 星期×品类 分层估计偏移，小样本层向全局收缩，避免层内噪声。
  3. ACI（Adaptive Conformal Inference）：非可交换序列上在线更新显著性水平，
     长期误覆盖频率趋近名义值。

只依赖 numpy，便于在离线环境与 CI 中复现。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

import numpy as np

CALIBRATION_SCHEMA_VERSION = 1
CALIBRATION_METHOD = "cqr+stratified-aci"
_ALPHA_FLOOR = 0.01
_ALPHA_CEIL = 0.5


# --------------------------------------------------------------------------- #
# 1. CQR 偏移
# --------------------------------------------------------------------------- #
def conformity_scores(y_true, lower, upper) -> np.ndarray:
    """CQR 一致性分数：max(下界 − 实际, 实际 − 上界)，负值表示真实值落在区间内。"""
    y = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    if not (y.shape == lo.shape == hi.shape):
        raise ValueError("SHAPE_MISMATCH")
    if np.any(~np.isfinite(y)) or np.any(~np.isfinite(lo)) or np.any(~np.isfinite(hi)):
        raise ValueError("NON_FINITE_INPUT")
    if np.any(hi < lo):
        raise ValueError("UPPER_BELOW_LOWER")
    return np.maximum(lo - y, y - hi)


def conformal_quantile(scores: Iterable[float], alpha: float) -> float:
    """分割保形分位数：排序后取第 ceil((n+1)(1−α)) 个分数（越界时取最大值）。"""
    values = np.sort(np.asarray(list(scores), dtype=float))
    if values.size == 0:
        raise ValueError("EMPTY_SCORES")
    if not 0.0 < alpha < 1.0:
        raise ValueError("ALPHA_OUT_OF_RANGE")
    rank = int(math.ceil((values.size + 1) * (1.0 - alpha)))
    rank = min(max(rank, 1), values.size)
    return float(values[rank - 1])


def shrink_offset(global_offset: float, stratum_offset: float, stratum_rows: int, kappa: float) -> float:
    """分层收缩：n 越大越信层内估计，n 越小越靠全局。"""
    if stratum_rows < 0:
        raise ValueError("NEGATIVE_ROWS")
    if kappa < 0:
        raise ValueError("NEGATIVE_KAPPA")
    if stratum_rows == 0:
        return float(global_offset)
    weight = stratum_rows / (stratum_rows + kappa)
    return float(weight * stratum_offset + (1.0 - weight) * global_offset)


def apply_offset(lower, upper, offset: float):
    """把校准偏移套用到分位模型输出上；偏移为负时区间收窄，但不得交叉。"""
    lo = np.asarray(lower, dtype=float) - offset
    hi = np.asarray(upper, dtype=float) + offset
    return np.minimum(lo, hi), np.maximum(lo, hi)


# --------------------------------------------------------------------------- #
# 2. ACI 在线校准
# --------------------------------------------------------------------------- #
@dataclass
class ACIController:
    """长期误覆盖率控制：α_{t+1} = α_t + γ_t(α* − err_t)。"""

    alpha_target: float = 0.1
    gamma0: float = 0.01
    gamma_min: float = 0.002
    mode: str = "decay"  # decay | fixed
    alpha_current: float | None = None
    errors: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha_target < 1.0:
            raise ValueError("ALPHA_TARGET_OUT_OF_RANGE")
        if self.mode not in {"decay", "fixed"}:
            raise ValueError("ACI_MODE_INVALID")
        if self.gamma0 <= 0 or self.gamma_min < 0:
            raise ValueError("GAMMA_INVALID")
        if self.alpha_current is None:
            self.alpha_current = self.alpha_target
        self._clamp()

    @property
    def t(self) -> int:
        return len(self.errors)

    def _clamp(self) -> None:
        self.alpha_current = float(min(max(self.alpha_current, _ALPHA_FLOOR), _ALPHA_CEIL))

    def gamma(self) -> float:
        if self.mode == "fixed":
            return float(self.gamma0)
        return float(max(self.gamma_min, self.gamma0 / math.sqrt(1.0 + self.t)))

    def update(self, covered: bool) -> float:
        error = 0.0 if covered else 1.0
        self.errors.append(0 if covered else 1)
        self.alpha_current = self.alpha_current + self.gamma() * (self.alpha_target - error)
        self._clamp()
        return float(self.alpha_current)

    def coverage(self) -> float:
        if not self.errors:
            return float("nan")
        return 1.0 - sum(self.errors) / len(self.errors)

    def to_dict(self) -> dict:
        return {
            "alpha_target": float(self.alpha_target),
            "alpha_current": float(self.alpha_current),
            "gamma0": float(self.gamma0),
            "gamma_min": float(self.gamma_min),
            "mode": self.mode,
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, doc: dict) -> "ACIController":
        return cls(
            alpha_target=float(doc["alpha_target"]),
            alpha_current=float(doc["alpha_current"]),
            gamma0=float(doc["gamma0"]),
            gamma_min=float(doc["gamma_min"]),
            mode=str(doc["mode"]),
            errors=[int(value) for value in doc.get("errors", [])],
        )


# --------------------------------------------------------------------------- #
# 3. 区间指标（论文主表与页面诊断共用）
# --------------------------------------------------------------------------- #
def picp(y_true, lower, upper) -> float:
    """预测区间覆盖率 Prediction Interval Coverage Probability。"""
    y = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    if y.size == 0:
        raise ValueError("EMPTY_INPUT")
    return float(np.mean((y >= lo) & (y <= hi)))


def pinaw(y_true, lower, upper) -> float:
    """归一化平均区间宽度；用观测极差归一，避免量纲依赖。"""
    y = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    span = float(np.max(y) - np.min(y))
    if span <= 0:
        raise ValueError("DEGENERATE_SPAN")
    return float(np.mean(hi - lo) / span)


def winkler_score(y_true, lower, upper, alpha: float) -> float:
    """Winkler / interval score，越小越好；对漏覆盖施以 2/α 惩罚。"""
    y = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    if not 0.0 < alpha < 1.0:
        raise ValueError("ALPHA_OUT_OF_RANGE")
    width = hi - lo
    penalty_low = np.where(y < lo, (2.0 / alpha) * (lo - y), 0.0)
    penalty_high = np.where(y > hi, (2.0 / alpha) * (y - hi), 0.0)
    return float(np.mean(width + penalty_low + penalty_high))


def interval_report(y_true, lower, upper, alpha: float) -> dict:
    """一次算齐报告用指标，避免各处重复实现口径不一致。"""
    return {
        "picp": picp(y_true, lower, upper),
        "pinaw": pinaw(y_true, lower, upper),
        "winkler": winkler_score(y_true, lower, upper, alpha),
        "n": int(np.asarray(y_true).size),
        "alpha": float(alpha),
    }


# --------------------------------------------------------------------------- #
# 4. 校准产物读写与校验
# --------------------------------------------------------------------------- #
def build_calibration_artifact(
    *,
    alpha: float,
    global_offset: float,
    strata: dict[str, dict],
    kappa: float,
    model_sha256: str,
    feature_sha256: str,
    split: dict,
    aci: ACIController | None = None,
    method: str = CALIBRATION_METHOD,
) -> dict:
    if not (isinstance(alpha, (int, float)) and 0.0 < float(alpha) < 1.0):
        raise ValueError("CALIBRATION_ALPHA_INVALID")
    artifact = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "method": method,
        "alpha": float(alpha),
        "kappa": float(kappa),
        "global_offset": float(global_offset),
        "strata": {
            str(key): {"offset": float(value["offset"]), "n": int(value["n"])}
            for key, value in strata.items()
        },
        "aci": (aci or ACIController(alpha_target=alpha)).to_dict(),
        "model_sha256": model_sha256,
        "feature_sha256": feature_sha256,
        "split": {key: int(value) for key, value in split.items()},
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    errors = validate_calibration_artifact(artifact)
    if errors:
        raise ValueError("; ".join(errors))
    return artifact


def validate_calibration_artifact(doc) -> list[str]:
    if not isinstance(doc, dict):
        return ["CALIBRATION_MUST_BE_OBJECT"]
    errors: list[str] = []
    if doc.get("schema_version") != CALIBRATION_SCHEMA_VERSION:
        errors.append(f"CALIBRATION_SCHEMA_UNSUPPORTED:{doc.get('schema_version')}")
    if not isinstance(doc.get("method"), str) or not doc["method"]:
        errors.append("CALIBRATION_METHOD_INVALID")
    alpha = doc.get("alpha")
    if not (isinstance(alpha, (int, float)) and 0.0 < float(alpha) < 1.0):
        errors.append("CALIBRATION_ALPHA_INVALID")
    for key in ("kappa", "global_offset"):
        value = doc.get(key)
        if not (isinstance(value, (int, float)) and float(value) >= 0):
            errors.append(f"CALIBRATION_VALUE_INVALID:{key}")
    strata = doc.get("strata")
    if not isinstance(strata, dict):
        errors.append("CALIBRATION_STRATA_INVALID")
    else:
        for key, value in strata.items():
            if not isinstance(value, dict):
                errors.append(f"STRATUM_NOT_OBJECT:{key}")
                continue
            offset = value.get("offset")
            rows = value.get("n")
            if not (isinstance(offset, (int, float)) and float(offset) >= 0):
                errors.append(f"STRATUM_OFFSET_INVALID:{key}")
            if not (isinstance(rows, int) and not isinstance(rows, bool) and rows > 0):
                errors.append(f"STRATUM_ROWS_INVALID:{key}")
    aci = doc.get("aci")
    if not isinstance(aci, dict):
        errors.append("CALIBRATION_ACI_INVALID")
    else:
        target = aci.get("alpha_target")
        current = aci.get("alpha_current")
        if not (isinstance(target, (int, float)) and 0.0 < float(target) < 1.0):
            errors.append("ACI_ALPHA_TARGET_INVALID")
        if not (isinstance(current, (int, float)) and 0.0 < float(current) <= 1.0):
            errors.append("ACI_ALPHA_CURRENT_INVALID")
        if aci.get("mode") not in {"decay", "fixed"}:
            errors.append("ACI_MODE_INVALID")
        if not isinstance(aci.get("errors"), list):
            errors.append("ACI_ERRORS_INVALID")
    for key in ("model_sha256", "feature_sha256"):
        value = doc.get(key)
        if not (isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())):
            errors.append(f"CALIBRATION_BINDING_INVALID:{key}")
    split = doc.get("split")
    if not isinstance(split, dict) or not split:
        errors.append("CALIBRATION_SPLIT_MISSING")
    else:
        for key, value in split.items():
            if not (isinstance(value, int) and not isinstance(value, bool) and value >= 0):
                errors.append(f"SPLIT_VALUE_INVALID:{key}")
    return errors