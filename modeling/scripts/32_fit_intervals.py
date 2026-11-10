"""训练分位模型并校准区间：CQR → 分层收缩 → ACI，产出校准产物与回测指标。

数据：modeling/data/02_processed/finetune_uwaste.parquet（派生目标，非现场观测）。
切分：按行序做时间切分（行序即日期序，品类交错），train / calib / test 顺序不重叠。

产出：
  * src/main/resources/modeling/lgbm_campus_q{lo,hi}.txt   分位模型（Java 侧加载）
  * src/main/resources/modeling/campus_interval_calibration.json  校准产物
  * modeling/data/03_output/interval_backtest_metrics.json  四方法回测指标

诚实边界：该数据标签为派生目标，指标只用于方法对比与回归测试，不得当作现场精度。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modeling"))

from foodwise_ml.intervals import (  # noqa: E402
    ACIController,
    build_calibration_artifact,
    conformal_quantile,
    interval_report,
    shrink_offset,
)
from foodwise_ml.manifest import build_manifest, sha256_file, write_manifest  # noqa: E402

DATA = ROOT / "modeling" / "data" / "02_processed" / "finetune_uwaste.parquet"
FEATURES_FILE = ROOT / "src" / "main" / "resources" / "modeling" / "campus_feature_cols.json"
MODEL_FILE = ROOT / "src" / "main" / "resources" / "modeling" / "lgbm_campus_model.txt"
RESOURCES = ROOT / "src" / "main" / "resources"
OUTPUT = ROOT / "modeling" / "data" / "03_output" / "interval_backtest_metrics.json"
PREDICTIONS = ROOT / "modeling" / "data" / "03_output" / "interval_test_predictions.csv"

PARAMS = {
    "objective": "quantile",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.9,
    "bagging_freq": 1,
    "verbosity": -1,
    "seed": 42,
}
ROUNDS = 400


def load_frame() -> tuple[pd.DataFrame, list[str]]:
    frame = pd.read_parquet(DATA).reset_index(drop=True)
    feature_doc = json.loads(FEATURES_FILE.read_text(encoding="utf-8"))
    features = feature_doc["features"]
    missing = [name for name in features if name not in frame.columns]
    if missing:
        raise SystemExit(f"FEATURES_MISSING:{','.join(missing)}")
    return frame, features


def fit_quantile(train: pd.DataFrame, features: list[str], level: float, rounds: int) -> lgb.Booster:
    params = dict(PARAMS, alpha=level)
    dataset = lgb.Dataset(train[features], label=train["sold_qty"].astype(float), free_raw_data=False)
    return lgb.train(params, dataset, num_boost_round=rounds)


def predict(booster: lgb.Booster, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.clip(booster.predict(frame[features]), 0.0, None)


def stratified_offsets(
    calib: pd.DataFrame, scores: np.ndarray, alpha: float, kappa: float
) -> tuple[float, dict[str, dict]]:
    global_offset = conformal_quantile(scores, alpha)
    strata: dict[str, dict] = {}
    keys = calib["day_of_week"].astype(int).astype(str) + "|" + calib["category_id"].astype(int).astype(str)
    for key, group in pd.DataFrame({"key": keys, "score": scores}).groupby("key"):
        values = group["score"].to_numpy()
        if values.size < 5:
            continue
        raw = conformal_quantile(values, alpha)
        strata[str(key)] = {
            "offset": shrink_offset(global_offset, raw, int(values.size), kappa),
            "n": int(values.size),
        }
    return global_offset, strata


def offset_for(alpha: float, grid: np.ndarray, offsets: np.ndarray) -> float:
    return float(np.interp(alpha, grid, offsets))


def build_offset_table(scores, grid: np.ndarray) -> np.ndarray:
    return np.array([conformal_quantile(list(scores), float(a)) for a in grid])


def eval_rolling(y, lo, hi, alpha, base_scores, grid, every=25, aci=None):
    """滚动重校准：每 every 个观测用「历史残差池」重算偏移表，可选叠加 ACI。"""
    pool = list(base_scores)
    table = build_offset_table(pool, grid)
    lows, highs = [], []
    for index in range(len(y)):
        if index and index % every == 0:
            table = build_offset_table(pool, grid)
        level = aci.alpha_current if aci is not None else alpha
        offset = offset_for(level, grid, table)
        low, high = lo[index] - offset, hi[index] + offset
        lows.append(low)
        highs.append(high)
        covered = bool(low <= y[index] <= high)
        pool.append(float(max(lo[index] - y[index], y[index] - hi[index])))
        if aci is not None:
            aci.update(covered)
    return np.array(lows), np.array(highs), (aci.coverage() if aci is not None else None), (
        aci.alpha_current if aci is not None else None
    )


def eval_sliding(y, lo, hi, alpha, base_scores, grid, window=150, every=10):
    """滑动窗口重校准：只用最近 window 个残差，适应波动率漂移。"""
    pool = list(base_scores)[-window:]
    table = build_offset_table(pool, grid)
    lows, highs = [], []
    for index in range(len(y)):
        if index and index % every == 0:
            table = build_offset_table(pool, grid)
        offset = offset_for(alpha, grid, table)
        low, high = lo[index] - offset, hi[index] + offset
        lows.append(low)
        highs.append(high)
        pool.append(float(max(lo[index] - y[index], y[index] - hi[index])))
        pool = pool[-window:]
    return np.array(lows), np.array(highs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--kappa", type=float, default=20.0)
    parser.add_argument("--train-frac", type=float, default=0.70)
    parser.add_argument("--calib-frac", type=float, default=0.15)
    parser.add_argument("--rounds", type=int, default=ROUNDS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-version", default="2026.10.27-interval-v1")
    args = parser.parse_args()

    frame, features = load_frame()
    n = len(frame)
    train_end = int(n * args.train_frac)
    calib_end = int(n * (args.train_frac + args.calib_frac))
    train, calib, test = frame.iloc[:train_end], frame.iloc[train_end:calib_end], frame.iloc[calib_end:]
    if min(len(train), len(calib), len(test)) < 50:
        raise SystemExit("SPLIT_TOO_SMALL")

    lo_level, hi_level = args.alpha / 2, 1 - args.alpha / 2
    booster_lo = fit_quantile(train, features, lo_level, args.rounds)
    booster_hi = fit_quantile(train, features, hi_level, args.rounds)

    calib_lo, calib_hi = predict(booster_lo, calib, features), predict(booster_hi, calib, features)
    calib_hi = np.maximum(calib_lo, calib_hi)
    scores = np.maximum(calib_lo - calib["sold_qty"].to_numpy(), calib["sold_qty"].to_numpy() - calib_hi)
    # 位置偏差：分位区间中点不等于期望需求，决策层需要先校正再套临界分位。
    bias = float(np.mean(calib["sold_qty"].to_numpy() - (calib_lo + calib_hi) / 2.0))
    global_offset, strata = stratified_offsets(calib, scores, args.alpha, args.kappa)

    # ACI 需要一张 alpha → 偏移量表（同一份校准集，按不同 alpha 取分位）
    grid = np.round(np.arange(0.02, 0.401, 0.01), 2)
    table = np.array([conformal_quantile(scores, float(a)) for a in grid])

    test_lo, test_hi = predict(booster_lo, test, features), predict(booster_hi, test, features)
    test_hi = np.maximum(test_lo, test_hi)
    y = test["sold_qty"].to_numpy()
    test_keys = test["day_of_week"].astype(int).astype(str) + "|" + test["category_id"].astype(int).astype(str)

    raw = interval_report(y, test_lo, test_hi, args.alpha)
    global_cqr = interval_report(y, test_lo - global_offset, test_hi + global_offset, args.alpha)

    offsets_by_row = np.array(
        [strata.get(key, {"offset": global_offset})["offset"] for key in test_keys], dtype=float
    )
    stratified = interval_report(y, test_lo - offsets_by_row, test_hi + offsets_by_row, args.alpha)

    predictions = pd.DataFrame(
        {
            "sold_qty": y,
            "lo_raw": test_lo,
            "hi_raw": test_hi,
            "lo_cal": test_lo - offsets_by_row,
            "hi_cal": test_hi + offsets_by_row,
            "day_of_week": test["day_of_week"].to_numpy(),
            "category_id": test["category_id"].to_numpy(),
            "price": test["price"].to_numpy(),
            "unit_cost": test["unit_cost"].to_numpy(),
            "discount_rate": test["discount_rate"].to_numpy(),
        }
    )
    predictions.to_csv(PREDICTIONS, index=False)

    fixture = {
        "feature_order": features,
        "model_files": {
            "q05": f"modeling/lgbm_campus_q{int(round(lo_level * 100)):02d}.txt",
            "q95": f"modeling/lgbm_campus_q{int(round(hi_level * 100)):02d}.txt",
        },
        "rows": [
            {
                "features": [float(value) for value in row],
                "q05": float(low),
                "q95": float(high),
                "sold": float(actual),
            }
            for row, low, high, actual in zip(
                test[features].to_numpy()[:8], test_lo[:8], test_hi[:8], y[:8]
            )
        ],
    }
    (OUTPUT.parent / "quantile_parity_fixture.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Java 侧逐值对齐测试读取同一份冻结样本
    parity_copy = ROOT / "src" / "test" / "resources" / "modeling" / "quantile_parity_fixture.json"
    parity_copy.parent.mkdir(parents=True, exist_ok=True)
    parity_copy.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")

    aci = ACIController(alpha_target=args.alpha, gamma0=0.01, gamma_min=0.002, mode="decay")
    aci_lo, aci_hi, aci_cov, aci_alpha = eval_rolling(
        y, test_lo, test_hi, args.alpha, scores, grid, every=len(test) + 1, aci=aci
    )
    aci_metrics = interval_report(y, aci_lo, aci_hi, args.alpha)
    aci_metrics.update(
        {"online_coverage": aci_cov, "final_alpha": aci_alpha, "alpha_target": args.alpha}
    )

    roll_lo, roll_hi, _, _ = eval_rolling(y, test_lo, test_hi, args.alpha, scores, grid, every=25)
    rolling = interval_report(y, roll_lo, roll_hi, args.alpha)
    rolling.update({"recalibration_every": 25})

    roll_aci = ACIController(alpha_target=args.alpha, gamma0=0.01, gamma_min=0.002, mode="decay")
    raci_lo, raci_hi, raci_cov, raci_alpha = eval_rolling(
        y, test_lo, test_hi, args.alpha, scores, grid, every=25, aci=roll_aci
    )
    rolling_aci = interval_report(y, raci_lo, raci_hi, args.alpha)
    rolling_aci.update(
        {"online_coverage": raci_cov, "final_alpha": raci_alpha, "recalibration_every": 25}
    )

    slide_lo, slide_hi = eval_sliding(y, test_lo, test_hi, args.alpha, scores, grid, window=150)
    sliding = interval_report(y, slide_lo, slide_hi, args.alpha)
    sliding.update({"window": 150, "recalibration_every": 10})

    metrics = {
        "dataset": "finetune_uwaste",
        "label_note": "派生目标（由 waste_rate 反推），非现场观测销量",
        "rows": n,
        "split": {"train_rows": len(train), "calib_rows": len(calib), "test_rows": len(test)},
        "params": dict(PARAMS, num_boost_round=args.rounds, seed=args.seed),
        "alpha": args.alpha,
        "kappa": args.kappa,
        "calibration": {"global_offset": global_offset, "strata": strata, "bias": bias},
        "offset_table": {"alpha": grid.tolist(), "offset": table.tolist()},
        "methods": {
            "quantile_raw": raw,
            "cqr_global": global_cqr,
            "cqr_stratified": stratified,
            "cqr_aci": aci_metrics,
            "cqr_rolling": rolling,
            "cqr_rolling_aci": rolling_aci,
            "cqr_sliding": sliding,
        },
        "limits": [
            "标签为派生目标，指标只反映方法相对表现，不外推到现场销量。",
            "切分为单次时间切分，未做 30 个滚动原点，方差未估计。",
            "分位模型与校准基于同一份公开数据，独立同分布假设不成立。",
            "滚动重校准使用测试期已观测残差，属于在线评估口径，不是纯离线泛化。",
        ],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    # 证据页直接读取该副本，避免前端读取构建目录之外的文件
    evidence_copy = RESOURCES / "modeling" / "interval_backtest_metrics.json"
    evidence_copy.parent.mkdir(parents=True, exist_ok=True)
    evidence_copy.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    lo_path = RESOURCES / "modeling" / f"lgbm_campus_q{int(round(lo_level * 100)):02d}.txt"
    hi_path = RESOURCES / "modeling" / f"lgbm_campus_q{int(round(hi_level * 100)):02d}.txt"
    # LightGBM 的 C++ 写盘接口不支持非 ASCII 路径，先写临时目录再用 Python 复制。
    with tempfile.TemporaryDirectory() as staging:
        for booster, target in ((booster_lo, lo_path), (booster_hi, hi_path)):
            staging_file = Path(staging) / target.name
            booster.save_model(str(staging_file))
            shutil.copyfile(staging_file, target)

    artifact = build_calibration_artifact(
        alpha=args.alpha,
        global_offset=global_offset,
        strata=strata,
        kappa=args.kappa,
        model_sha256=sha256_file(MODEL_FILE),
        feature_sha256=sha256_file(FEATURES_FILE),
        split={"train_rows": len(train), "calib_rows": len(calib), "test_rows": len(test)},
        aci=aci,
    )
    artifact["quantile_models"] = {
        str(lo_level): {"file": f"modeling/{lo_path.name}", "sha256": sha256_file(lo_path)},
        str(hi_level): {"file": f"modeling/{hi_path.name}", "sha256": sha256_file(hi_path)},
    }
    artifact["offset_table"] = {"alpha": grid.tolist(), "offset": table.tolist()}
    artifact["bias"] = bias
    artifact["metrics"] = {name: metrics["methods"][name] for name in metrics["methods"]}
    calibration_path = RESOURCES / "modeling" / "campus_interval_calibration.json"
    calibration_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    deployed = metrics["methods"]["cqr_stratified"]
    manifest = build_manifest(
        base_dir=RESOURCES,
        model_file="modeling/lgbm_campus_model.txt",
        feature_file="modeling/campus_feature_cols.json",
        data_file=DATA,
        dataset="finetune_uwaste",
        model_version=args.model_version,
        model_kind="calibrated-quantile",
        quantiles=[lo_level, hi_level],
        quantile_models={
            str(lo_level): f"modeling/{lo_path.name}",
            str(hi_level): f"modeling/{hi_path.name}",
        },
        calibration={
            "method": "cqr+stratified-aci",
            "status": "calibrated",
            "alpha": args.alpha,
            "artifact": "modeling/campus_interval_calibration.json",
            "artifact_sha256": sha256_file(calibration_path),
            "picp90": deployed["picp"],
        },
        metrics={
            "picp90": deployed["picp"],
            "pinaw90": deployed["pinaw"],
            "winkler90": deployed["winkler"],
            "evaluated_on": f"finetune_uwaste:test({len(test)}rows)",
        },
        limits=[
            "标签为派生目标，覆盖率与宽度只代表方法在构造数据上的表现。",
            "一次性离线校准在波动率漂移时会过覆盖，部署需按周滚动重校准。",
            "单次时间切分，未做滚动原点重复，指标方差未估计。",
            "派生目标数据不得用于对外宣称现场减损效果。",
        ],
    )
    write_manifest(RESOURCES / "modeling" / "model_manifest.json", manifest)

    print(f"rows={n} train={len(train)} calib={len(calib)} test={len(test)}")
    print(f"global_offset={global_offset:.3f} strata={len(strata)} kappa={args.kappa}")
    print(f"{'method':<16}{'PICP':>8}{'PINAW':>8}{'Winkler':>10}")
    for name, row in metrics["methods"].items():
        print(f"{name:<16}{row['picp']:>8.3f}{row['pinaw']:>8.3f}{row['winkler']:>10.2f}")
    print(f"wrote {OUTPUT}")
    print(f"wrote {calibration_path}")
    print(f"wrote {lo_path.name}, {hi_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())