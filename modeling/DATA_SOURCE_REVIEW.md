# 原始标签审计与实验准入

审计入口：`scripts/13_source_audit.py`；逐文件哈希、字段、行数写入 `data/03_output/source_audit_v1.json`。

`university_food_waste/university_canteen_waste.csv` 的 2600 行仅有 Date、Meal、Canteen_Section、Food_Category、Waste_Weight_kg、Unit_Price_per_kg、Cost_Loss。没有原始销量和备餐量，因此旧模型及 3.867%/6.166% 等指标不能充当真实销量预测证据。派生目标只能作为假设场景，历史文件保留用于追溯。

`kaggle_food_demand/train.csv` 包含周级 num_orders 标签，456548 行；sample_submission 是提交模板，不是观测标签。周订单保持周级，不拆成独立日观测。来源许可与供应方采集背景仍待核验。

`reduce_foodwaste/train.csv` 包含 5142 行 sales，按供应方 README 为缩放店铺日销量；unsold/ordered 并非全量存在。可做该公开来源内的离线方法评估，不能直接换算本地份数、实际人民币收益。truth 标签需用 row_id 与 test 对齐，不能独立处理为有日期的数据。

`kaggle_cc0` 有 Units Sold，但许可和采集/生成背景需核实，CC0 不证明真实采集。GYLAF 只审查必要聚合数据的日期、单位与许可，不读取个人姓名、性别与客户流水。

公开文件的可计算性、许可、来源可信度、目标适用性分别验收。当前所有结果保留来源核验状态，不宣称现场或独立外部验证。
