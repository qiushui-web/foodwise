# -*- coding: utf-8 -*-
"""
02_build_pretrain_features.py
=============================
数据来源说明：
  - smartbite_campus_synthesis：MIT学术研究合成数据集（33,567行，CC-BY-4.0），用作预训练底座
  - campus_simulation：基于4因子规则模型生成的模拟台账（AI生成，非实地采集），用于管线验证
  - kaggle_food_demand / kaggle_cc0：Kaggle真实数据集，用于外部验证

把 01_raw/ 下的多源数据转换为 统一24维 Schema，输出到 02_processed/ 下。
把 01_raw/ 下的多源数据（SmartBite 33k / 98条台账 / 可选CC0 / 可选Genpack）
转换为 统一24维 Schema，输出到 02_processed/ 下。

严格遵守：
  - 全局特征名唯一（见 FEATURE_COLS）
  - 时间序列 lag/rolling 严禁用未来数据（只用 shift + 历史窗口）
  - 缺失值：分类用 "UNK"/0，连续用 列中位数/品类均值
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# =========================== 路径 ===========================
BASE = Path(__file__).resolve().parent.parent / "data"
RAW = BASE / "01_raw"
PROC = BASE / "02_processed"
PROC.mkdir(parents=True, exist_ok=True)

SMARTBITE_CSV = RAW / "smartbite_campus_synthesis" / "data" / "smartbite_cafeteria_dataset_2022_2025.csv"
CAMPUS_CSV   = RAW / "campus_simulation" / "foodwise_operations_14d.csv"
CC0_CSV      = RAW / "kaggle_cc0" / "demand_forecasting.csv"        # 可选
GENPACK_CSV  = RAW / "kaggle_food_demand" / "train.csv"             # 可选

# =========================== 统一 Schema ===========================
FEATURE_COLS = [
    # 时间（7）
    "day_of_week","week_of_month","month","is_weekend","is_exam_week",
    "has_campus_event","days_to_vacation",
    # 天气（4）
    "weather_code","temp_max_c","precipitation_mm","weather_x_weekday",
    # 价格/品类（7）
    "category_id","price","unit_cost","markup_ratio",
    "price_rank_in_stall","category_volatility","discount_rate",
    # 销量滞后（6）
    "lag_1_sold","lag_7_sold","rolling_mean_3","rolling_mean_7",
    "rolling_std_7","same_dow_last_4w_mean",
]
TARGET = "sold_qty"
META_COLS = ["date","source","stall_name","dish_id","dish_name","meal_type_raw"]
ALL_COLS = META_COLS + FEATURE_COLS + [TARGET]

# =========================== 品类/档口映射规则 ===========================
CATEGORY_NAMES = ["套餐主食", "轻食沙拉", "粉面", "烘焙点心"]  # 0 1 2 3
CATEGORY_PRICE = {0: 12.8, 1: 15.2, 2: 14.0, 3: 8.5}         # 单位：元（典型零售价）
CATEGORY_COST_RATIO = 0.40                                   # 毛利率60% -> unit_cost = price*0.4

def _map_smartbite_meal_type_to_category(meal: str, dish: str) -> int:
    """按 README.md 表：Breakfast/Lunch -> 套餐(0)，Snacks -> 烘焙(3)，Dinner -> 粉面(2)
    含 Salad/Veg/Bowl 词 -> 轻食(1)"""
    d = (dish or "").lower()
    m = (meal or "").lower()
    if any(k in d for k in ["salad","bowl","curd","yogurt","raita"]): return 1
    if "snack" in m: return 3
    if "dinner" in m: return 2
    if "breakfast" in m: return 0
    if "lunch" in m: return 0
    return 0

def _map_campus_dish_to_category(dish_name: str) -> int:
    """98条台账的7菜映射（对应项目中4档口分类）"""
    dn = (dish_name or "").lower()
    if any(k in dn for k in ["三明治","卷","轻食","谷物碗","鸡胸","沙拉"]): return 1
    if any(k in dn for k in ["面","粉"]): return 2
    if any(k in dn for k in ["烘焙","蛋糕","饼","面包"]): return 3
    return 0  # 饭/套餐 默认

WEATHER_MAP = {"晴":0,"阴":1,"多云":1,"小雨":2,"中雨":3,"大雨":3,"高温":4,"降温":5}
def _encode_weather(w: str) -> int:
    if pd.isna(w): return 1
    for k,v in WEATHER_MAP.items():
        if k in str(w): return v
    return 1
# =========================== 核心：lag/滚动特征（防未来泄漏） ===========================
def add_lag_features(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    """按 [stall_name, dish_id] 分组 → 严格对 TARGET=sold_qty 做历史偏移"""
    df = df.sort_values(key_cols + ["date"]).reset_index(drop=True)
    grp = df.groupby(key_cols, group_keys=False)[TARGET]

    df["lag_1_sold"] = grp.shift(1)
    df["lag_7_sold"] = grp.shift(7)

    df["rolling_mean_3"] = grp.shift(1).transform(lambda s: s.rolling(3, min_periods=1).mean())
    df["rolling_mean_7"] = grp.shift(1).transform(lambda s: s.rolling(7, min_periods=1).mean())
    df["rolling_std_7"]  = grp.shift(1).transform(lambda s: s.rolling(7, min_periods=2).std()).fillna(0.0)

    # 同星期过去4周平均（dow=day_of_week）
    def _same_dow_mean(sub):
        dow_col = sub["day_of_week"].values
        sold   = sub[TARGET].values
        out = np.full(len(sub), np.nan)
        seen: dict[int, list] = {d: [] for d in range(7)}
        for i, d in enumerate(dow_col):
            if seen[d]:
                last4 = seen[d][-4:]
                out[i] = float(np.mean(last4))
            seen[d].append(sold[i])
        sub = sub.copy()
        sub["same_dow_last_4w_mean"] = out
        return sub
    df = df.groupby(key_cols, group_keys=False).apply(_same_dow_mean).reset_index(drop=True)
    return df

def _fill_lag_with_group_median(df: pd.DataFrame, cols: list[str], by: str = "category_id") -> pd.DataFrame:
    """lag列如果是NaN（刚开始前N天没有历史），按category_id中位数填，再fallback全局列中位数"""
    for c in cols:
        df[c] = df.groupby(by)[c].transform(lambda s: s.fillna(s.median()))
        df[c] = df[c].fillna(df[c].median())
    return df

# =========================== Loader: SmartBite ===========================
def load_smartbite() -> pd.DataFrame:
    df = pd.read_csv(SMARTBITE_CSV)
    print(f"[SmartBite] 原始行数: {len(df):,}")
    df["Date"] = pd.to_datetime(df["Date"])

    out = pd.DataFrame()
    out["date"] = df["Date"]
    out["source"] = "SmartBite"
    out["stall_name"] = "SmartBite_" + df["Meal_Type"].astype(str)
    out["dish_id"]  = df["Dish_Name"].factorize()[0]        # 任意整数ID
    out["dish_name"]= df["Dish_Name"]
    out["meal_type_raw"] = df["Meal_Type"]

    # 时间
    out["day_of_week"] = out["date"].dt.dayofweek
    out["week_of_month"] = ((out["date"].dt.day - 1) // 7) + 1
    out["month"] = out["date"].dt.month
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)

    # 考试周：北半球学年 ~9开学，学期末(6月/12月)前两周猜为考试周
    dm = out["date"].dt
    is_jun_dec = dm.month.isin([6, 12])
    is_late = dm.day >= 15
    out["is_exam_week"] = ((is_jun_dec & is_late) | df["Vacation_Flag"].astype(int)).astype(int)

    out["has_campus_event"] = df["Event_Flag"].astype(int)

    # 距离假期：Vacation_Flag 1出现前7天内递减填充（简化近似）
    vf = df["Vacation_Flag"].astype(int)
    dt = out["date"]
    # 简化版：若下一行或接下来N行为1，则days递减
    out["days_to_vacation"] = np.where(vf.shift(-1).fillna(0)==1, 1, 0)
    for shift in range(2, 8):
        mask = (vf.shift(-shift).fillna(0) == 1) & (out["days_to_vacation"] == 0)
        out.loc[mask, "days_to_vacation"] = shift
    out["days_to_vacation"] = out["days_to_vacation"].fillna(0).astype(int)

    # 天气（SmartBite缺）：先按CC0校准后的月份×星期 均值填充，脚本05可再用Open-Meteo补
    out["weather_code"] = 1   # 默认阴天/中性
    out.loc[(dm.month.isin([12,1,2])), "weather_code"] = 5   # 冬天=降温
    out.loc[(dm.month.isin([7,8])), "weather_code"] = 4     # 夏天=高温
    out["temp_max_c"] = np.where(out["weather_code"]==4, 33,
                                np.where(out["weather_code"]==5, 8, 22))
    out["precipitation_mm"] = np.where(out["weather_code"].isin([2,3]), 6.0, 0.0)
    out["weather_x_weekday"] = out["weather_code"] * out["day_of_week"]

    # 品类/价格
    out["category_id"] = [_map_smartbite_meal_type_to_category(m, d)
                          for m,d in zip(df["Meal_Type"], df["Dish_Name"])]
    out["price"] = out["category_id"].map(CATEGORY_PRICE)
    out["unit_cost"] = (out["price"] * CATEGORY_COST_RATIO).round(2)
    out["markup_ratio"] = ((out["price"] - out["unit_cost"]) / out["price"]).round(3)

    # 档口内价格排名分位（0-1）
    out["price_rank_in_stall"] = out.groupby("stall_name")["price"].rank(pct=True, method="dense").round(3)

    # 品类波动率（事后按训练集统计，此处先占位=1.0，脚本03跑完回填）
    out["category_volatility"] = 1.0

    # 折扣率：event==1时给0.85，否则1.0
    out["discount_rate"] = np.where(out["has_campus_event"]==1, 0.85, 1.0)

    # 目标
    out[TARGET] = df["Servings"].astype(int)

    # lag 特征（关键：在 category_id/dish_id 等准备好之后）
    key_cols = ["stall_name", "dish_id"]
    out = add_lag_features(out, key_cols)
    out = _fill_lag_with_group_median(out,
        ["lag_1_sold","lag_7_sold","rolling_mean_3","rolling_mean_7","rolling_std_7","same_dow_last_4w_mean"])

    out = out[ALL_COLS].copy()
    print(f"[SmartBite] 处理后特征行数: {len(out):,}, 日期范围: {out['date'].min().date()} ~ {out['date'].max().date()}")
    return out

# =========================== Loader: 98条校园台账 ===========================
def load_campus_ops_as_features() -> pd.DataFrame:
    df = pd.read_csv(CAMPUS_CSV)
    print(f"[CampusOps] 原始行数: {len(df)}")
    df["business_date"] = pd.to_datetime(df["business_date"])

    out = pd.DataFrame()
    out["date"] = df["business_date"]
    out["source"] = "Campus98"
    out["stall_name"] = df["stall"]
    out["dish_id"]  = df["dish_id"].astype(int)
    out["dish_name"]= df["dish_name"]
    out["meal_type_raw"] = "Lunch"  # 98条默认午市

    out["day_of_week"] = out["date"].dt.dayofweek
    out["week_of_month"] = ((out["date"].dt.day - 1) // 7) + 1
    out["month"] = out["date"].dt.month
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)

    tag = df["event_tag"].fillna("正常").astype(str)
    out["is_exam_week"]      = tag.str.contains("考试").astype(int)
    out["has_campus_event"]  = tag.str.contains("活动|毕业|典礼").astype(int)
    out["days_to_vacation"]  = tag.str.contains("暑假|寒假").astype(int) * 7

    out["weather_code"]      = df["weather"].map(_encode_weather).fillna(1).astype(int)
    out["temp_max_c"] = np.where(out["weather_code"]==4, 33,
                                np.where(out["weather_code"]==5, 8,
                                        np.where(out["weather_code"].isin([2,3]), 20, 26)))
    out["precipitation_mm"] = np.where(out["weather_code"].isin([2,3]), 5.0, 0.0)
    out["weather_x_weekday"] = out["weather_code"] * out["day_of_week"]

    out["category_id"] = [_map_campus_dish_to_category(x) for x in df["dish_name"]]
    out["price"] = df["price"].astype(float)
    out["unit_cost"] = df["unit_cost"].astype(float)
    out["markup_ratio"] = ((out["price"] - out["unit_cost"]) / out["price"]).round(3)
    out["price_rank_in_stall"] = out.groupby("stall_name")["price"].rank(pct=True, method="dense").round(3)
    out["category_volatility"] = 1.0

    has_disc = (df["discount_sold_qty"].fillna(0).astype(float) > 0).astype(int)
    avg_disc_ratio = np.where(has_disc==1, 0.82, 1.0)
    out["discount_rate"] = avg_disc_ratio

    out[TARGET] = df["sold_qty"].astype(int)

    key_cols = ["stall_name", "dish_id"]
    out = add_lag_features(out, key_cols)
    out = _fill_lag_with_group_median(out,
        ["lag_1_sold","lag_7_sold","rolling_mean_3","rolling_mean_7","rolling_std_7","same_dow_last_4w_mean"])

    out = out[ALL_COLS].copy()
    print(f"[CampusOps] 处理后特征行数: {len(out)}, 日期范围: {out['date'].min().date()} ~ {out['date'].max().date()}")
    return out

# =========================== Loader: CC0 零售天气数据集 ===========================
# CC0 Weather Condition -> 校园天气编码映射
CC0_WEATHER_MAP = {
    "Clear": 0, "Sunny": 0,
    "Cloudy": 1, "Foggy": 1, "Fog": 1,
    "Rainy": 2, "Drizzle": 2, "Rain": 2,
    "Stormy": 3, "Storm": 3, "Thunderstorm": 3,
    "Snowy": 5, "Snow": 5,
}

def _encode_cc0_weather(w: str) -> int:
    if pd.isna(w): return 1
    for k, v in CC0_WEATHER_MAP.items():
        if k.lower() in str(w).lower():
            return v
    return 1  # 默认阴天

def load_cc0_weather() -> pd.DataFrame:
    """
    加载 CC0 零售天气数据集，映射到校园天气体系并生成统一特征。

    将 Weather Condition 映射到校园天气编码（Clear=0, Cloudy/Fog=1,
    Rain=2, Storm=3, Snow=5），按 (Store ID, Category) 分组模拟档口+菜品，
    提取销量滞后特征（lag1/lag2/lag3/lag7）。
    """
    df = pd.read_csv(CC0_CSV)
    print(f"[CC0] 原始行数: {len(df):,}")
    df["Date"] = pd.to_datetime(df["Date"])

    out = pd.DataFrame()
    out["date"] = df["Date"]
    out["source"] = "CC0"
    # 按 Store ID + Category 模拟档口+菜品
    out["stall_name"] = "CC0_" + df["Store ID"].astype(str)
    out["dish_id"] = df["Category"].factorize()[0] + 1000  # 偏移避免与校内ID冲突
    out["dish_name"] = df["Category"]
    out["meal_type_raw"] = "Unknown"

    # 时间特征
    out["day_of_week"] = out["date"].dt.dayofweek
    out["week_of_month"] = ((out["date"].dt.day - 1) // 7) + 1
    out["month"] = out["date"].dt.month
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)
    out["is_exam_week"] = 0
    out["has_campus_event"] = 0
    out["days_to_vacation"] = 0

    # 天气编码
    out["weather_code"] = df["Weather Condition"].astype(str).apply(_encode_cc0_weather).astype(int)
    out["temp_max_c"] = np.where(out["weather_code"] == 0, 30,
                                 np.where(out["weather_code"] == 1, 24,
                                 np.where(out["weather_code"] == 2, 18,
                                 np.where(out["weather_code"] == 3, 15,
                                 np.where(out["weather_code"] == 5, 2, 26)))))
    out["precipitation_mm"] = np.where(out["weather_code"].isin([2, 3]), 8.0, 0.0)
    out["weather_x_weekday"] = out["weather_code"] * out["day_of_week"]

    # 品类/价格
    out["category_id"] = df["Category"].factorize()[0]
    out["price"] = df["Price"].astype(float)
    out["unit_cost"] = (out["price"] * CATEGORY_COST_RATIO).round(2)
    out["markup_ratio"] = ((out["price"] - out["unit_cost"]) / out["price"]).round(3)
    out["price_rank_in_stall"] = out.groupby("stall_name")["price"].rank(pct=True, method="dense").round(3)
    out["category_volatility"] = 1.0

    # 折扣率
    out["discount_rate"] = np.where(df["Discount"].fillna(0).astype(float) > 0,
                                    (100 - df["Discount"].astype(float)) / 100, 1.0)
    # 目标变量
    out[TARGET] = df["Demand"].astype(int)

    # 提取滞后特征（lag1/lag2/lag3/lag7）
    key_cols = ["stall_name", "dish_id"]
    out = out.sort_values(key_cols + ["date"]).reset_index(drop=True)
    grp = out.groupby(key_cols, group_keys=False)[TARGET]
    out["lag_1_sold"] = grp.shift(1)
    out["lag_2_sold"] = grp.shift(2)
    out["lag_3_sold"] = grp.shift(3)
    out["lag_7_sold"] = grp.shift(7)

    out["rolling_mean_3"] = grp.shift(1).transform(lambda s: s.rolling(3, min_periods=1).mean())
    out["rolling_mean_7"] = grp.shift(1).transform(lambda s: s.rolling(7, min_periods=1).mean())
    out["rolling_std_7"] = grp.shift(1).transform(lambda s: s.rolling(7, min_periods=2).std()).fillna(0.0)

    def _same_dow_mean(sub):
        dow_col = sub["day_of_week"].values
        sold = sub[TARGET].values
        o = np.full(len(sub), np.nan)
        seen: dict[int, list] = {d: [] for d in range(7)}
        for i, d in enumerate(dow_col):
            if seen[d]:
                last4 = seen[d][-4:]
                o[i] = float(np.mean(last4))
            seen[d].append(sold[i])
        sub = sub.copy()
        sub["same_dow_last_4w_mean"] = o
        return sub
    out = out.groupby(key_cols, group_keys=False).apply(_same_dow_mean).reset_index(drop=True)

    lag_cols = ["lag_1_sold", "lag_2_sold", "lag_3_sold", "lag_7_sold",
                "rolling_mean_3", "rolling_mean_7", "rolling_std_7", "same_dow_last_4w_mean"]
    out = _fill_lag_with_group_median(out, lag_cols)

    available_cols = [c for c in ALL_COLS if c in out.columns]
    out = out[available_cols].copy()
    print(f"[CC0] 处理后特征行数: {len(out):,}, 日期范围: {out['date'].min().date()} ~ {out['date'].max().date()}")
    return out

# =========================== 主入口 ===========================
def main() -> int:
    datasets = {}
    if SMARTBITE_CSV.exists():
        datasets["pretrain_smartbite"] = load_smartbite()
    if CAMPUS_CSV.exists():
        datasets["campus_98_processed"] = load_campus_ops_as_features()
    if CC0_CSV.exists():
        print("[CC0] 检测到 CC0 数据集，开始加载...")
        datasets["cc0_weather"] = load_cc0_weather()
    if GENPACK_CSV.exists():
        print("[Genpack] 检测到，后续版本将作为跨域验证（当前骨架预留）")

    for name, df in datasets.items():
        out_path = PROC / f"{name}.parquet"
        df.to_parquet(out_path, index=False)
        print(f"[保存] {out_path}  rows={len(df):,}  cols={len(df.columns)}")

    for name, df in datasets.items():
        df.head(500).to_csv(PROC / f"{name}__sample500.csv", index=False, encoding="utf-8-sig")

    print("\n===== 02_build_pretrain_features 完成 =====")
    print(f"可用数据集: {list(datasets.keys())}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
