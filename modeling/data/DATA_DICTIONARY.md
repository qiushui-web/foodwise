# 统一数据字典

## 主键与观测字段

| 字段 | 含义 | 类型/单位 | 来源性质 |
|---|---|---|---|
| `business_date` / `date` | 营业日期 | date | 原始观测 |
| `stall_name` | 档口 | string | 原始/映射 |
| `dish_id` | 菜品标识 | integer | 原始/映射 |
| `category_id` | 统一品类编码 | integer | 派生映射 |
| `price` | 售价 | RMB/份 | 原始或口径补全 |
| `unit_cost` | 单位食材成本 | RMB/份 | 原始或规则估计 |
| `prepare_qty` | 备餐量 | 份 | 原始台账 |
| `sold_qty` | 售出量 | 份 | 原始台账/预测目标 |
| `waste_pieces` | 剩余份数 | 份 | 派生或台账 |
| `waste_rate` | 剩余率 | 0-1 | 派生字段 |

## 特征字段

`day_of_week`、节假日/考试周、天气、价格、滞后销量和滚动均值均必须只使用预测时点之前可获得的信息；`lag_*` 与 `rolling_*` 使用 `shift(1)` 计算，禁止使用当日目标值。

## 指标口径

销量预测报告必须同时输出 MAE、WAPE、sMAPE、RMSLE。`pred_waste` 只代表浪费估计，不得与 `sold_qty` 预测列混合评估。
