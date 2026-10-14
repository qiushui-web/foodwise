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
| `prepare_qty` | 备餐量 | 来源定义的单位 | 观测/派生/simulation须标记 |
| `sold_qty` | 售出量/目标 | 来源定义的单位 | 列名不证明真实观测，不默认份数 |
| `waste_pieces` | 剩余份数 | 份 | 派生或台账 |
| `waste_rate` | 剩余率 | 0-1 | 派生字段 |

## 特征字段

`day_of_week`、节假日/考试周、天气、价格、滞后销量和滚动均值均必须只使用预测时点之前可获得的信息；`lag_*` 与 `rolling_*` 使用 `shift(1)` 计算，禁止使用当日目标值。

## 指标口径

真实份数报告MAE、WAPE、偏差及分组结果，sMAPE辅助；RMSLE仅在标签和预测均非负且适用时计算。缩放可负销量以MAE为主，不做RMSLE或份数/金额换算。预测浪费与销量不能混合评估。天气/价格/活动需可用时点；未知、停业和真实0分开，lag7按日历计算。新采集口径见CAMPUS_COLLECTION_GUIDE.md。
