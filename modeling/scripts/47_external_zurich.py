"""外部效度：在 ZHAW 食堂 2017 真实点单数据上重跑"基线 vs GBDT"。

与 44_baseline_vs_gbdt.py 的区别：
- 数据是真实点单流水（60 个营业日、7 个菜单线），不是我们自己的台账；
- 切分是时间向前的：前 40 天训练/标定，后 20 天逐日滚动预测，不能回看未来；
- 决策口径与站内一致：中心 + 残差分位 σ → 临界比 → 建议量 → regret。

数据集：ZHAW canteen menu sales 2017（NOVANIMAL 版），transaction 级。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / "数据来源" / "ZHAW_canteen_menu_sales_2017" / "2017_ZHAW_aggregated_menu_sales_NOVANIMAL.csv"
OUT = ROOT / "modeling" / "data" / "03_output" / "external_zurich.json"

PRICE = 7.0            # CHF，取自 price_article 的众数
UNIT_COST_RATIO = 0.4
DISCOUNT_RATIO = 0.5
SALVAGE = 0.6
LAMBDA = 0.3
MIN_BATCH = 5
CAPACITY = 250
TRAIN_DAYS = 40
TEST_DAYS = 20
Z90 = 1.6448536269514722


def load_daily() -> pd.DataFrame:
    frame = pd.read_csv(RAW, sep=";", encoding="utf-8")
    frame = frame[frame["qty_weight"] > 0].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    daily = (frame.groupby(["date", "article_description"], as_index=False)
             .agg(demand=("qty_weight", "sum"),
                  revenue=("total_amount", "sum"),
                  rain=("rainfall", "max"),
                  sun=("sun", "max"),
                  clouds=("clouds", "max")))
    # 只保留 60 天全在的菜单线，避免缺失日被当成 0 需求
    counts = daily.groupby("article_description")["date"].nunique()
    keep = counts[counts == daily["date"].nunique()].index
    daily = daily[daily["article_description"].isin(keep)].copy()
    daily["weekday"] = daily["date"].dt.dayofweek
    daily = daily.sort_values(["article_description", "date"]).reset_index(drop=True)
    return daily


def cost_model(price: float = PRICE, unit_cost: float | None = None) -> dict:
    unit_cost = price * UNIT_COST_RATIO if unit_cost is None else unit_cost
    discount = price * DISCOUNT_RATIO
    underage = (price - unit_cost) * (1 + LAMBDA)
    overage = unit_cost - discount * SALVAGE
    return {
        "price": price, "unit_cost": unit_cost, "discount": discount,
        "underage": underage, "overage": overage,
        "critical_ratio": 0.999 if overage <= 0 else underage / (underage + overage),
    }


def profit(quantity: float, demand: float, cost: dict) -> float:
    sold = min(quantity, demand)
    discounted = max(0.0, quantity - sold) * SALVAGE
    return sold * cost["price"] + discounted * cost["discount"] - quantity * cost["unit_cost"]


def batch(raw: float) -> int:
    if not np.isfinite(raw):
        return MIN_BATCH
    rounded = int(np.ceil(max(raw, 0) / MIN_BATCH) * MIN_BATCH)
    return int(min(max(rounded, 0), CAPACITY))


def same_weekday_median(history: pd.DataFrame, weekday: int, points: int = 4) -> float:
    same = history[history["weekday"] == weekday]["demand"].tail(points)
    if len(same) == 0:
        return float(history["demand"].median())
    return float(same.median())


def sigma_from_residuals(history: pd.DataFrame) -> float:
    """留一残差：每一行只用它之前的数据估中心，避免用自己的值算自己的误差。"""
    residuals = []
    for i in range(1, len(history)):
        prior = history.iloc[:i]
        center = same_weekday_median(prior, int(history.iloc[i]["weekday"]))
        residuals.append(history.iloc[i]["demand"] - center)
    if not residuals:
        return 1.0
    return max(float(np.quantile(np.abs(residuals), 0.90)) / Z90, 1.0)


def build_features(history: pd.DataFrame, row: pd.Series) -> list[float]:
    demand = history["demand"].to_numpy()
    lags = [float(demand[-k]) if len(demand) >= k else float(np.mean(demand)) for k in range(1, 8)]
    return [float(row["weekday"]), float(np.mean(demand[-7:])), float(np.median(demand[-7:])),
            float(np.std(demand[-7:])), float(row.get("rain", 0) or 0), float(row.get("sun", 0) or 0),
            float(row.get("clouds", 0) or 0), *lags]


def methods_for(history: pd.DataFrame) -> dict[str, float]:
    demand = history["demand"].to_numpy()
    return {
        "same_weekday_median": same_weekday_median(history, int(history.iloc[-1]["weekday"]) + 0),
        "median_roll7": float(np.median(demand[-7:])),
        "mean_roll7": float(np.mean(demand[-7:])),
        "yesterday": float(demand[-1]),
    }


def paired_bootstrap(frame: pd.DataFrame, a: str, b: str, draws: int = 1000, seed: int = 20261027) -> dict:
    """按"菜品 × 日"配对重采样，回答"两条方法的差是不是噪声"。"""
    wide_regret = frame.pivot_table(index=["article", "date"], columns="method", values="regret")
    wide_abs = frame.assign(abs_err=lambda f: (f["center"] - f["demand"]).abs()) \
        .pivot_table(index=["article", "date"], columns="method", values="abs_err")
    rng = np.random.default_rng(seed)
    pairs = np.arange(len(wide_regret))
    regret_diffs, mae_diffs = [], []
    for _ in range(draws):
        sample = rng.choice(pairs, size=len(pairs), replace=True)
        regret_diffs.append(wide_regret[a].to_numpy()[sample].mean() - wide_regret[b].to_numpy()[sample].mean())
        mae_diffs.append(wide_abs[a].to_numpy()[sample].mean() - wide_abs[b].to_numpy()[sample].mean())
    regret_diffs = np.asarray(regret_diffs)
    mae_diffs = np.asarray(mae_diffs)
    return {
        "comparison": f"{a} - {b}",
        "regret_diff_mean": float(regret_diffs.mean()),
        "regret_diff_ci95": [float(np.quantile(regret_diffs, 0.025)), float(np.quantile(regret_diffs, 0.975))],
        "mae_diff_mean": float(mae_diffs.mean()),
        "mae_diff_ci95": [float(np.quantile(mae_diffs, 0.025)), float(np.quantile(mae_diffs, 0.975))],
        "draws": draws,
    }


def run() -> dict:
    daily = load_daily()
    cost = cost_model()
    records: list[dict] = []
    articles = sorted(daily["article_description"].unique())
    for article in articles:
        series = daily[daily["article_description"] == article].reset_index(drop=True)
        train = series.iloc[:TRAIN_DAYS]
        test = series.iloc[TRAIN_DAYS:TRAIN_DAYS + TEST_DAYS]
        sigma = sigma_from_residuals(train)
        history = train.copy()
        for _, row in test.iterrows():
            actual = float(row["demand"])
            centers = {
                "same_weekday_median": same_weekday_median(history, int(row["weekday"])),
                "median_roll7": float(np.median(history["demand"].to_numpy()[-7:])),
                "mean_roll7": float(np.mean(history["demand"].to_numpy()[-7:])),
                "yesterday": float(history["demand"].to_numpy()[-1]),
                "gbdt": run_gbdt(history, row),
            }
            for name, center in centers.items():
                quantity = batch(center + inv_norm(cost["critical_ratio"]) * sigma)
                records.append({
                    "article": article, "date": row["date"].date().isoformat(), "method": name,
                    "center": center, "sigma": sigma, "quantity": quantity, "demand": actual,
                    "profit": profit(quantity, actual, cost),
                    "oracle_profit": profit(actual, actual, cost),
                })
            history = pd.concat([history, row.to_frame().T], ignore_index=True)
    frame = pd.DataFrame(records)
    frame["regret"] = frame["oracle_profit"] - frame["profit"]
    frame["waste"] = (frame["quantity"] - frame["demand"]).clip(lower=0) / frame["quantity"].replace(0, np.nan)
    frame["stockout"] = frame["demand"] > frame["quantity"]
    summary = {}
    for name, group in frame.groupby("method"):
        summary[name] = {
            "mae": float(np.mean(np.abs(group["center"] - group["demand"]))),
            "wape": float(np.sum(np.abs(group["center"] - group["demand"])) / np.sum(group["demand"])),
            "regret_per_100": float(group["regret"].sum() / group["demand"].sum() * 100),
            "waste_rate": float(group["waste"].mean()),
            "stockout_rate": float(group["stockout"].mean()),
            "mean_quantity": float(group["quantity"].mean()),
            "n": int(len(group)),
        }
    best = min(summary.items(), key=lambda item: item[1]["regret_per_100"])[0]
    payload = {
        "dataset": "ZHAW_canteen_menu_sales_2017",
        "source_file": RAW.name,
        "days": int(daily["date"].nunique()),
        "articles": articles,
        "train_days": TRAIN_DAYS,
        "test_days": TEST_DAYS,
        "decisions": int(len(frame)),
        "cost_model": cost,
        "methods": summary,
        "best_by_regret": best,
        "ordering_by_regret": [name for name, _ in sorted(summary.items(), key=lambda i: i[1]["regret_per_100"])],
        "ordering_by_mae": [name for name, _ in sorted(summary.items(), key=lambda i: i[1]["mae"])],
        "comparisons": [
            paired_bootstrap(frame, "gbdt", "same_weekday_median"),
            paired_bootstrap(frame, "gbdt", "mean_roll7"),
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(OUT.with_suffix(".csv"), index=False, encoding="utf-8")
    return payload


_MODEL = None


def run_gbdt(history: pd.DataFrame, row: pd.Series) -> float:
    """每天重新拟合一次小模型：只用历史，不碰当天真值。"""
    import lightgbm as lgb

    rows, targets = [], []
    for i in range(7, len(history)):
        prior = history.iloc[:i]
        rows.append(build_features(prior, history.iloc[i]))
        targets.append(float(history.iloc[i]["demand"]))
    if len(rows) < 10:
        return same_weekday_median(history, int(row["weekday"]))
    model = lgb.LGBMRegressor(n_estimators=120, learning_rate=0.08, num_leaves=7,
                              min_child_samples=5, verbose=-1)
    model.fit(np.asarray(rows), np.asarray(targets))
    return float(model.predict(np.asarray([build_features(history, row)]))[0])


def inv_norm(p: float) -> float:
    """Acklam 近似，与 Java 侧 NormalQuantile 同源。"""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p <= 0 or p >= 1:
        raise ValueError("probability out of range")
    if p < p_low:
        q = np.sqrt(-2 * np.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
               (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    q = np.sqrt(-2 * np.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
           ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)


if __name__ == "__main__":
    result = run()
    print(json.dumps({"decisions": result["decisions"], "best_by_regret": result["best_by_regret"],
                      "ordering_by_regret": result["ordering_by_regret"],
                      "methods": result["methods"]}, ensure_ascii=False, indent=2))