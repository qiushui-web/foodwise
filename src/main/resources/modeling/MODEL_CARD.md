# Model Card（全真实 · 零模拟 · waste_rate重估）

**生成时间**: 2026-08-31 09:38:15.283912

## 数据来源（原始观测与派生字段分开记录）

- pretrain底座 534,326 行：
  ① kaggle_food_demand 456,548 行（真实77团餐中心×51餐品×145周订单）
  ② gylaf_campus 天津师大 14品类×126天 真实高校销量+天气编码
  ③ kaggle_cc0 76,000 行（真实零售+天气+促销×2年）
- 微调/回测 2,600 行：university_food_waste（真实中国高校 4档口×3餐次×4品类 1学年实测）
- waste_rate 重估：gylaf真实高校日销量 × (meal×cat×stall) 三维行业权重 → waste_rate≈17.5%

## 预训练（log1p sold_qty）

- model=LGBMRegressor(log target) n=500 lr=0.04 leaves=95
- val_MAE=28.8206  val_MAPE=89.1719%
- Top5 features=['lag_1_sold', 'same_dow_last_4w_mean', 'rolling_mean_7', 'rolling_mean_3', 'promotion_flag']

## 校园回测（项目内 14 天 simulation 台账）

- rolling_windows=5，扩展训练集逐日预测
- MAE、WAPE、sMAPE、RMSLE 见 `03_output/campus_metrics_report.json`


## 字段真实性与版本

原始销量、交易、天气和浪费重量属于观测数据；`prepare_qty`、`waste_pieces`、`waste_rate` 及滞后/滚动特征属于规则或统计派生数据；模型输出属于预测数据。运行数据审计脚本后，以 `03_output/DATA_VERSION.json` 的哈希清单作为 Java 加载模型与训练产物的一致性依据。

项目内 14 天经营台账明确标记为 `simulation`，只能用于流程和回测管线验证；真实试点结论必须来自新增的带来源证明的现场数据。五窗口销量指标见 `03_output/campus_metrics_report.json`，其中 `pred_waste` 不参与销量评估。
