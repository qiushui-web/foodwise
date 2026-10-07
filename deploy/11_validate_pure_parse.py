# -*- coding: utf-8 -*-
"""
11_validate_pure_parse.py
验证「纯解析 LGBM 文本模型」与 LightGBM 原生 booster.predict 完全一致。
通过后，同一套树遍历逻辑 1:1 移植到 Java(LgbmCampusModel)，彻底摆脱 JNI/原生库。
"""
import re
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[1]
MODEL_TXT = ROOT / "src" / "main" / "resources" / "modeling" / "lgbm_campus_model.txt"
PARQUET = ROOT / "modeling" / "data" / "02_processed" / "finetune_uwaste.parquet"


def parse_txt(path: Path):
    trees = []
    feature_names = []
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("feature_names="):
            feature_names = ln.split("=", 1)[1].split()
        m = re.match(r"Tree=(\d+)$", ln)
        if m:
            block = {}
            i += 1
            while i < len(lines) and not lines[i].startswith("Tree=") and lines[i] != "end of trees":
                cur = lines[i]
                if "=" in cur and not cur.startswith(" "):
                    k, v = cur.split("=", 1)
                    block[k.strip()] = v.strip()
                i += 1
            trees.append(block)
            continue
        i += 1
    parsed = []
    for b in trees:
        def ints(k):
            return [int(x) for x in b[k].split()] if b.get(k) else []
        def flts(k):
            return [float(x) for x in b[k].split()] if b.get(k) else []
        parsed.append(dict(
            split_feature=ints("split_feature"),
            threshold=flts("threshold"),
            decision_type=ints("decision_type"),
            left_child=ints("left_child"),
            right_child=ints("right_child"),
            leaf_value=flts("leaf_value"),
            num_leaves=int(b.get("num_leaves", "0")),
            num_cat=int(b.get("num_cat", "0")),
        ))
    return feature_names, parsed


def walk_tree(tree, x, nan_go="left"):
    """返回该树的 leaf_value。nan_go: left / right —— 用于验证缺失值方向。"""
    node = 0
    sf, th, dt = tree["split_feature"], tree["threshold"], tree["decision_type"]
    lc, rc, lv = tree["left_child"], tree["right_child"], tree["leaf_value"]
    while True:
        fidx = sf[node]
        v = x[fidx]
        go_left = v <= th[node]
        if np.isnan(v):
            go_left = (nan_go == "left")
        child = lc[node] if go_left else rc[node]
        if child < 0:
            return lv[-child - 1]
        node = child


def predict_raw(trees, X, nan_go="left"):
    out = np.zeros(len(X))
    for i in range(len(X)):
        s = 0.0
        x = X[i]
        for t in trees:
            s += walk_tree(t, x, nan_go)
        out[i] = s
    return out


def main():
    feats, trees = parse_txt(MODEL_TXT)
    print(f"[Parse] {len(trees)} trees, {len(feats)} features")
    assert all(t["num_cat"] == 0 for t in trees), "存在类别分裂,需另行处理"
    assert all(all(d in (0, 1, 2, 3, 4, 5) for d in t["decision_type"]) for t in trees)
    print("[Parse] 全部为数值分裂(num_cat=0), decision_type 取值集合:",
          sorted({d for t in trees for d in t["decision_type"]}))

    df = pd.read_parquet(PARQUET)
    X = df[feats].astype(float).values
    print(f"[Data] X={X.shape}, NaN 数量={np.isnan(X).sum()}")

    booster = lgb.Booster(model_file=str(MODEL_TXT))
    ref = booster.predict(df[feats])

    for nan_go in ("left", "right"):
        mine = predict_raw(trees, X, nan_go=nan_go)
        diff = np.abs(mine - ref)
        print(f"[Compare] nan_go={nan_go:5s}  max|diff|={diff.max():.3e}  "
              f"mean|diff|={diff.mean():.3e}  match={np.allclose(mine, ref, atol=1e-6)}")

    # 最终预测: expm1 + clip
    mine_final = np.clip(np.expm1(predict_raw(trees, X, nan_go="right")), 1.0, 400.0)
    ref_final = np.clip(np.expm1(ref), 1.0, 400.0)
    print(f"[Final] expm1+clip 后 max|diff|={np.abs(mine_final - ref_final).max():.3e}")

    # 抽样 5 行展示
    for i in np.linspace(0, len(X) - 1, 5, dtype=int):
        print(f"  row{i:4d}: raw_ref={ref[i]:.6f} raw_parse={predict_raw(trees, X[i:i+1])[0]:.6f} "
              f"final={mine_final[i]:.2f}")


if __name__ == "__main__":
    main()
