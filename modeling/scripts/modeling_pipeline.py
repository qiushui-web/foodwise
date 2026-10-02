"""
食刻有数 × 数据智能体 — 建模分析脚本
用途：合并两份经营CSV → 特征工程 → 多模型对比 → 生成图表
运行：pip install pandas scikit-learn matplotlib seaborn numpy prophet
     python modeling_pipeline.py
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

warnings.filterwarnings("ignore")

# ── 路径配置 ──────────────────────────────────────────────
PROJECT_CSV   = r"D:\IdeaProjects\Examples\src\main\resources\data\foodwise_operations_14d.csv"
COMPETITION_CSV = r"C:\Users\lenovo\Desktop\商业精英挑战赛\统一数据与来源\数据文件\foodwise_operations.csv"
WEATHER_JSON  = r"C:\Users\lenovo\Desktop\商业精英挑战赛\统一数据与来源\数据文件\langfang_weather_2026-07-07_2026-07-20.json"
OUTPUT_DIR    = r"C:\Users\lenovo\Desktop\商业精英挑战赛\建模输出"

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


# ═══════════════════════════════════════════════════════════
# 第一步：数据归集与合并
# ═══════════════════════════════════════════════════════════
def load_and_merge():
    """合并两份CSV + 天气JSON，输出统一的分析数据框"""
    df_july = pd.read_csv(PROJECT_CSV)
    df_june = pd.read_csv(COMPETITION_CSV)

    df = pd.concat([df_june, df_july], ignore_index=True)
    df["business_date"] = pd.to_datetime(df["business_date"])
    df = df.sort_values(["dish_id", "business_date"]).reset_index(drop=True)

    # 去重（如果两份CSV有日期重叠的话）
    df = df.drop_duplicates(subset=["business_date", "dish_id"], keep="last")

    print(f"[数据归集] 合并完成: {len(df)} 条记录")
    print(f"  日期范围: {df['business_date'].min().date()} → {df['business_date'].max().date()}")
    print(f"  菜品数量: {df['dish_name'].nunique()}")
    print(f"  档口数量: {df['stall'].nunique()}")
    print(f"  阶段分布: {df['phase'].value_counts().to_dict()}")

    # 守恒校验
    df["conservation_ok"] = df["prepared_qty"] == (df["sold_qty"] + df["leftover_qty"])
    violations = (~df["conservation_ok"]).sum()
    print(f"  守恒校验: {len(df) - violations}/{len(df)} 通过 ({violations} 条违反)")

    # 天气数值特征合并
    if os.path.exists(WEATHER_JSON):
        with open(WEATHER_JSON, "r") as f:
            weather = json.load(f)
        weather_df = pd.DataFrame({
            "business_date": pd.to_datetime(weather["daily"]["time"]),
            "temp_max": weather["daily"]["temperature_2m_max"],
            "temp_min": weather["daily"]["temperature_2m_min"],
            "precipitation_mm": weather["daily"]["precipitation_sum"],
        })
        df = df.merge(weather_df, on="business_date", how="left")
        print(f"  天气合并: {df['temp_max'].notna().sum()} 天有温度数据")

    return df


# ═══════════════════════════════════════════════════════════
# 第二步：特征工程
# ═══════════════════════════════════════════════════════════
def build_features(df):
    """为每道菜构造时序特征"""
    all_features = []

    for dish_id in df["dish_id"].unique():
        dish_df = df[df["dish_id"] == dish_id].copy()
        dish_df = dish_df.sort_values("business_date")

        # 日历特征
        dish_df["weekday"] = dish_df["business_date"].dt.dayofweek  # 0=周一 6=周日
        dish_df["is_weekend"] = (dish_df["weekday"] >= 5).astype(int)
        dish_df["is_exam_week"] = dish_df["event_tag"].str.contains("考试", na=False).astype(int)

        # 天气特征（如有）
        dish_df["has_rain"] = dish_df["weather"].str.contains("雨", na=False).astype(int)
        if "temp_max" in dish_df.columns:
            dish_df["temp_mean"] = (dish_df["temp_max"] + dish_df["temp_min"]) / 2

        # 滞后特征
        for lag in [1, 2, 3, 7]:
            dish_df[f"sold_lag{lag}"] = dish_df["sold_qty"].shift(lag)

        # 滚动统计
        dish_df["rolling_7d_mean"] = dish_df["sold_qty"].rolling(7, min_periods=3).mean()
        dish_df["rolling_7d_std"] = dish_df["sold_qty"].rolling(7, min_periods=3).std()
        dish_df["rolling_3d_mean"] = dish_df["sold_qty"].rolling(3, min_periods=2).mean()

        # 损耗率特征
        dish_df["leftover_rate"] = np.where(
            dish_df["prepared_qty"] > 0,
            dish_df["leftover_qty"] / dish_df["prepared_qty"] * 100,
            0
        )

        all_features.append(dish_df)

    return pd.concat(all_features, ignore_index=True)


# ═══════════════════════════════════════════════════════════
# 第三步：多模型训练与对比
# ═══════════════════════════════════════════════════════════
def train_and_evaluate(df):
    """4个模型逐菜训练，输出MAE/MAPE对比"""
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import TimeSeriesSplit

    feature_cols = [
        "weekday", "is_weekend", "is_exam_week", "has_rain",
        "sold_lag1", "sold_lag2", "sold_lag3", "sold_lag7",
        "rolling_7d_mean", "rolling_7d_std", "rolling_3d_mean",
    ]

    # 如果有温度特征就加上
    if "temp_mean" in df.columns and df["temp_mean"].notna().any():
        feature_cols.append("temp_mean")

    results = {
        "规则基线(已有)": [],
        "Ridge回归": [],
        "7日均线(简单)": [],
    }

    # 尝试LightGBM
    try:
        import lightgbm as lgb
        has_lgb = True
        results["LightGBM"] = []
    except ImportError:
        has_lgb = False
        print("[模型] LightGBM 未安装，跳过")

    for dish_id in df["dish_id"].unique():
        dish_name = df[df["dish_id"] == dish_id]["dish_name"].iloc[0]
        dish_df = df[df["dish_id"] == dish_id].copy().sort_values("business_date").dropna(subset=feature_cols)

        if len(dish_df) < 12:
            continue

        X = dish_df[feature_cols].values
        y = dish_df["sold_qty"].values
        n_test = min(7, len(dish_df) // 4)
        X_train, X_test = X[:-n_test], X[-n_test:]
        y_train, y_test = y[:-n_test], y[-n_test:]

        # ── 模型1: 规则基线（模拟现有PredictionService）
        baseline_preds = []
        for i in range(len(y_train), len(y)):
            window = y[max(0, i - 7):i]
            if len(window) > 0:
                weights = np.arange(1, len(window) + 1, dtype=float)
                pred = np.average(window, weights=weights)
            else:
                pred = y[i - 1] if i > 0 else y[0]
            baseline_preds.append(pred)
        baseline_preds = np.array(baseline_preds)

        # ── 模型2: Ridge回归
        scaler = StandardScaler()
        X_scaled_train = scaler.fit_transform(X_train)
        X_scaled_test = scaler.transform(X_test)
        ridge = Ridge(alpha=1.0)
        ridge.fit(X_scaled_train, y_train)
        ridge_preds = ridge.predict(X_scaled_test)

        # ── 模型3: 简单7日均线
        simple_preds = []
        for i in range(len(y_train), len(y)):
            window = y[max(0, i - 7):i]
            simple_preds.append(np.mean(window) if len(window) > 0 else y[0])
        simple_preds = np.array(simple_preds)

        # 计算指标
        for name, preds in [
            ("规则基线(已有)", baseline_preds),
            ("Ridge回归", ridge_preds),
            ("7日均线(简单)", simple_preds),
        ]:
            mae = np.mean(np.abs(y_test - preds))
            mape = np.mean(np.abs((y_test - preds) / np.maximum(y_test, 1))) * 100
            results[name].append({"dish": dish_name, "mae": mae, "mape": mape})

        # ── 模型4: LightGBM
        if has_lgb:
            lgb_model = lgb.LGBMRegressor(
                n_estimators=50, max_depth=3, learning_rate=0.1,
                num_leaves=8, min_child_samples=3,
                reg_alpha=0.1, reg_lambda=1.0, verbose=-1
            )
            lgb_model.fit(X_train, y_train)
            lgb_preds = lgb_model.predict(X_test)
            mae = np.mean(np.abs(y_test - lgb_preds))
            mape = np.mean(np.abs((y_test - lgb_preds) / np.maximum(y_test, 1))) * 100
            results["LightGBM"].append({"dish": dish_name, "mae": mae, "mape": mape})

    # 汇总
    summary = []
    for model_name, dish_results in results.items():
        if not dish_results:
            continue
        avg_mae = np.mean([d["mae"] for d in dish_results])
        avg_mape = np.mean([d["mape"] for d in dish_results])
        summary.append({"模型": model_name, "MAE(份)": round(avg_mae, 2), "MAPE(%)": round(avg_mape, 1)})

    summary_df = pd.DataFrame(summary)
    print("\n[模型对比]")
    print(summary_df.to_string(index=False))
    return summary_df, results


# ═══════════════════════════════════════════════════════════
# 第四步：可视化
# ═══════════════════════════════════════════════════════════
def generate_charts(df, model_summary):
    """生成6张分析图表，保存到建模输出目录"""

    # 图1: 28天销量趋势（按档口聚合）
    fig, ax = plt.subplots(figsize=(14, 5))
    for stall in df["stall"].unique():
        stall_df = df[df["stall"] == stall].groupby("business_date")["sold_qty"].sum()
        ax.plot(stall_df.index, stall_df.values, marker="o", markersize=3, label=stall)
    ax.axvline(x=pd.Timestamp("2026-07-07"), color="red", linestyle="--", alpha=0.5, label="基线→干预")
    ax.set_title("各档口日售出量趋势（28天）", fontsize=14)
    ax.set_xlabel("日期")
    ax.set_ylabel("售出量（份）")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "01_销量趋势.png"), dpi=150)
    plt.close()

    # 图2: 星期×菜品热力图
    df["weekday_name"] = df["business_date"].dt.dayofweek.map(
        {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    )
    heatmap_data = df.pivot_table(values="sold_qty", index="dish_name",
                                   columns="weekday_name", aggfunc="mean")
    weekday_order = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    heatmap_data = heatmap_data[[c for c in weekday_order if c in heatmap_data.columns]]

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(heatmap_data, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax, linewidths=0.5)
    ax.set_title("星期 × 菜品 平均销量热力图", fontsize=14)
    ax.set_ylabel("")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "02_星期菜品热力图.png"), dpi=150)
    plt.close()

    # 图3: 天气 vs 销量
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    weather_order = ["晴", "多云", "小雨"]
    weather_groups = [df[df["weather"] == w]["sold_qty"] for w in weather_order]
    axes[0].boxplot(weather_groups, labels=weather_order, patch_artist=True,
                    boxprops=dict(facecolor="#ffcc80"))
    axes[0].set_title("天气类型 vs 单菜日销量", fontsize=13)
    axes[0].set_ylabel("售出量（份）")

    if "temp_max" in df.columns:
        valid = df.dropna(subset=["temp_max"])
        axes[1].scatter(valid["temp_max"], valid["sold_qty"], alpha=0.5, c="#e57373", s=40)
        axes[1].set_xlabel("日最高温度 (°C)")
        axes[1].set_ylabel("售出量（份）")
        axes[1].set_title("温度 vs 销量", fontsize=13)
        axes[1].grid(True, alpha=0.3)
    else:
        axes[1].text(0.5, 0.5, "温度数据待补充", ha="center", va="center", transform=axes[1].transAxes)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "03_天气销量分析.png"), dpi=150)
    plt.close()

    # 图4: 模型MAPE对比
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#90caf9", "#66bb6a", "#ffcc80", "#ef5350"]
    bars = ax.bar(model_summary["模型"], model_summary["MAPE(%)"], color=colors[:len(model_summary)])
    ax.set_title("模型预测精度对比（MAPE越低越好）", fontsize=14)
    ax.set_ylabel("MAPE (%)")
    for bar, val in zip(bars, model_summary["MAPE(%)"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{val}%", ha="center", fontsize=11, fontweight="bold")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "04_模型对比.png"), dpi=150)
    plt.close()

    # 图5: 基线期 vs 干预期 损耗率对比
    phase_stats = df.groupby("phase").agg(
        备餐量=("prepared_qty", "sum"),
        售出量=("sold_qty", "sum"),
        剩余量=("leftover_qty", "sum")
    ).reset_index()
    phase_stats["损耗率"] = (phase_stats["剩余量"] / phase_stats["备餐量"] * 100).round(1)
    phase_stats["售罄率"] = (phase_stats["售出量"] / phase_stats["备餐量"] * 100).round(1)

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(phase_stats))
    width = 0.35
    ax.bar(x - width/2, phase_stats["损耗率"], width, label="损耗率", color="#ef5350")
    ax.bar(x + width/2, phase_stats["售罄率"], width, label="售罄率", color="#66bb6a")
    ax.set_xticks(x)
    ax.set_xticklabels(phase_stats["phase"])
    ax.set_ylabel("百分比 (%)")
    ax.set_title("基线期 vs 干预期经营对比", fontsize=14)
    ax.legend()
    for i, (lr, sr) in enumerate(zip(phase_stats["损耗率"], phase_stats["售罄率"])):
        ax.text(i - width/2, lr + 0.5, f"{lr}%", ha="center", fontsize=11, fontweight="bold", color="#c62828")
        ax.text(i + width/2, sr + 0.5, f"{sr}%", ha="center", fontsize=11, fontweight="bold", color="#2e7d32")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "05_阶段对比.png"), dpi=150)
    plt.close()

    # 图6: 菜品损耗帕累托图
    dish_waste = df.groupby("dish_name").agg(
        总剩余=("leftover_qty", "sum"),
        总备餐=("prepared_qty", "sum")
    ).reset_index()
    dish_waste["损耗率"] = (dish_waste["总剩余"] / dish_waste["总备餐"] * 100).round(1)
    dish_waste = dish_waste.sort_values("总剩余", ascending=False)
    dish_waste["累计占比"] = (dish_waste["总剩余"].cumsum() / dish_waste["总剩余"].sum() * 100).round(1)

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(dish_waste["dish_name"], dish_waste["总剩余"], color="#ffab91")
    ax1.set_ylabel("总剩余量（份）")
    ax1.set_title("菜品损耗帕累托分析", fontsize=14)

    ax2 = ax1.twinx()
    ax2.plot(dish_waste["dish_name"], dish_waste["累计占比"], "o-", color="#1565c0", linewidth=2)
    ax2.set_ylabel("累计占比 (%)")
    ax2.axhline(y=80, color="#1565c0", linestyle="--", alpha=0.5, label="80%线")
    ax2.legend(loc="center right")

    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "06_损耗帕累托.png"), dpi=150)
    plt.close()

    print(f"\n[可视化] 6张图表已保存到: {OUTPUT_DIR}")


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  食刻有数 × 数据智能体 — 建模分析流水线")
    print("=" * 60)

    # Step 1: 数据归集
    df = load_and_merge()

    # Step 2: 特征工程
    df = build_features(df)

    # Step 3: 模型训练
    model_summary, _ = train_and_evaluate(df)

    # Step 4: 可视化
    generate_charts(df, model_summary)

    # Step 5: 保存合并后的数据
    output_csv = os.path.join(OUTPUT_DIR, "merged_operations_28d.csv")
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n[输出] 合并数据已保存: {output_csv}")
    print(f"  最终数据框: {df.shape[0]} 行 × {df.shape[1]} 列")

    # 保存模型对比表
    summary_csv = os.path.join(OUTPUT_DIR, "model_comparison.csv")
    model_summary.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    print(f"  模型对比表: {summary_csv}")

    print("\n✓ 全部完成！请查看「建模输出」文件夹。")
