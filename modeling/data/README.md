# 食刻有数 智能体赛道 · 建模数据集总览

> 目录结构：01_raw/（只读原始数据）-> 02_processed/（特征工程产物）-> 03_output/（独立实验目录）

## 当前有效口径（2026-10-13）

下文保留的旧设计不作为当前来源、训练链或成效事实。实际目录与源审计对应：university_food_waste2600行仅浪费重量，无销量/备餐；reduce_foodwaste的train5142行、test/truth各1575行是缩放日销量；kaggle_cc0有76000行，但采样/生成背景和Demand语义待核实；kaggle_food_demand的456548行是周订单，不拆为校园日销量。GYLAF个人流水本轮未读取。98条经营台账为simulation。

Reduce Foodwaste本地README/LICENSE/train的Git blob SHA与上游Green-AI Hub仓库一致，机构项目页背景相符；缩放公式、拟合时段、数据专用许可范围仍待明确，不换算份数、货币或校园减损。SmartBite旧目录/合计行数不证明当前模型效果，跨域规律需单独验证。

当前线上派生演示链为finetune_uwaste.parquet→校园导出脚本→Java资源；已审查modeling/scripts和deploy未找到其生成器，完整重建链未成立。匹配元数据证明两处导出行切分时间重叠，不能称严格时间回测。旧02特征脚本串组滚动、全量填补未来泄漏、按记录lag7已用反例复现；不重跑旧导出覆盖线上模型。

新独立实验14/17/18/21与旧链隔离，22审查来源、23审查旧链、20/24验复现。有效方案与结果见modeling/OPTIMIZATION_PLAN_20261013.md、OPTIMIZATION_RESULTS_20261013.md、OPTIMIZATION_ROUND2_20261013.md；新校园用户采集见CAMPUS_COLLECTION_GUIDE.md。以下旧描述仅追溯，不作效果证据。

---

## 当前已到位数据集（5/5；其中部分字段为派生特征）

| # | 子目录 | 名称 | 行数 | 来源 | 许可 | 角色 |
|---|---|---|---|---|---|---|
| 1 | smartbite_campus_synthesis/ | SmartBite 高校食堂合成数据集 | 33,567行（2022-2025） | GitHub nox-pie/SmartBite | MIT License | [Pre-train底座] 学到"工作日/考试周/假期/天气x销量"的通用高校食堂规律 |
| 2 | campus_real_ops/ | 食刻有数 经营测算台账 | 98行（4档口x7菜品x14日） | 项目内 simulation | 自有 | [流程与回测管线] 不作为现场试点或真实校园标签 |
| 3 | reduce_foodwaste/ | Reduce-Foodwaste-Dataset | train5142行、test1575行 | 公开缩放销量 | MIT文本与上游一致，数据专用范围待明确 | 方法研究，不用于份数/金额/现场减损换算 |
| 4 | cc0_retail_weather/ | Demand Forecasting Dataset (Ramin Huseyn) | ~6-8万行 | Kaggle（已落盘） | CC0 Public Domain | [系数校准] 独立估计天气x促销x季节系数，与SmartBite取平均 |
| 5 | genpack_food_demand/ | Food Demand Forecasting (Genpack) | ~456,548行 | Kaggle（已落盘） | 学术可引用 | [跨域验证 加分项] 证明模型可拓展至团餐 |

---

## 核心字段映射表（SmartBite 33k -> 98条台账 -> 统一24维Schema）

| 统一特征列 | SmartBite字段 | 98条台账字段 |
|---|---|---|
| date | Date | business_date |
| day_of_week | Day编码 (Mon=0..Sun=6) | business_date计算 |
| is_weekend | Day in (Sat,Sun) | 同上 |
| is_exam_week | Event_Flag+学期末规则 | event_tag含"考试" |
| has_campus_event | Event_Flag==1 | event_tag含"活动/毕业" |
| weather_code | CC0迁移+Open-Meteo回填 | weather编码(晴0..降温5) |
| temp_max_c | Open-Meteo回填对应日期 | data_boot加载已有 |
| category_id | Dish_Name映射主食/轻食/粉面/烘焙 | dish_name映射 |
| price | 品类典型价(13/15/14/8元) | price |
| unit_cost | price*0.4 (毛利率60%) | unit_cost |
| discount_rate | Event=1时0.85否则1.00 | discount_sold_qty推算 |
| lag_1_sold / lag_7_sold | Servings滑窗 | sold_qty滑窗 |
| rolling_mean_3/7 | Servings近3/7日均值 | sold_qty近3/7日均值 |
| rolling_std_7 | Servings近7日标准差 | sold_qty近7日标准差 |
| target: sold_qty | Servings | sold_qty |

---

## 建模运行顺序

01_download_datasets.py        -> 下载Kaggle（当前由浏览器/手动处理）
                                   |
02_build_pretrain_features.py  <- 先跑这个！01_raw下所有源 -> 02_processed/*.parquet
                                   |
03_train_pretrain_lgbm.py      -> LightGBM预训练 -> 模型+特征重要性+品类系数
                                   |
04_build_finetune_features.py  -> 98条台账 -> 同24维特征
                                   |
05_finetune_and_backtest.py    -> 领域微调 + 滚动回测 + 规则模型对比报告
                                   |
06_export_for_java.py          -> 导出系数CSV + 报告JSON -> Java DataBootstrapService直接读

---

## SmartBite菜品映射（不看名字语义，只看销量分布规律！）

以下为旧迁移映射假设。餐次、品类、单位、供给限制与校历必须对齐，不能预先认定规律通用；需实测负迁移。

| SmartBite Meal_Type | 映射您的category | 映射您的stall假设 |
|---|---|---|
| Breakfast (Pongal/Idly等) | 主食/套餐 | 拾味小厨 |
| Lunch (Sambar Rice等) | 主食/套餐 | 拾味小厨 + 谷禾轻食 |
| Snacks (Bajji/Samosa等) | 烘焙/轻食 | 晨语烘焙 + 拾味轻食 |
| Dinner (Chapathi/Dosa) | 粉面/套餐 | 匠心粉面 + 拾味小厨 |

---

## Kaggle数据集下载指引（已落盘）

如需重新构建，可将同名文件放回对应目录。若不想登录Kaggle，可手动搜同名数据集下载CSV放入：

- cc0_retail_weather/   <- 放 demand_forecasting.csv
- genpack_food_demand/  <- 放 train.csv / test.csv

字段完全兼容，不需要改脚本。


## 数据口径与版本

统一字段定义见 [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md)。主键统一为 `date/business_date + stall_name + dish_id`；原始供应方无表头时由导入脚本指定列名，不直接把第一行当作表头。

- 原始观测：交易、销量、天气、浪费重量与金额。
- 派生字段：`prepare_qty`、`waste_pieces`、`waste_rate`、滞后/滚动特征、价格成本比。
- 预测字段：模型输出的 `sold_qty` 预测值及置信区间。
- 不将派生浪费率描述为直接实测；其来源和规则必须记录在元数据中。
- 运行 `python modeling/scripts/10_data_quality_audit.py` 生成 `03_output/data_quality_report.json` 与 `03_output/DATA_VERSION.json`。
- 原始交易文件统一字段约定：`customer_id, food_id, unit_price, quantity, amount, business_date`；若供应方无表头，必须在导入层显式指定。

评估指标使用 MAE、WAPE、sMAPE、RMSLE；低销量场景不以 MAPE 作为唯一结论。时间序列回测使用 5 个扩展窗口，脚本为 `modeling/scripts/12_campus_rolling_baseline.py`，结果写入 `03_output/campus_metrics_report.json`。14 天台账被标记为 simulation，不能作为真实试点效果证明。
