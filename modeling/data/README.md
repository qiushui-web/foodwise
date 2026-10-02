# 食刻有数 智能体赛道 · 建模数据集总览

> 目录结构：01_raw/（只读原始数据）-> 02_processed/（特征工程产物，自动生成）-> 03_output/（模型、系数、报告）

---

## 当前已到位数据集（5/5；其中部分字段为派生特征）

| # | 子目录 | 名称 | 行数 | 来源 | 许可 | 角色 |
|---|---|---|---|---|---|---|
| 1 | smartbite_campus_synthesis/ | SmartBite 高校食堂合成数据集 | 33,567行（2022-2025） | GitHub nox-pie/SmartBite | MIT License | [Pre-train底座] 学到"工作日/考试周/假期/天气x销量"的通用高校食堂规律 |
| 2 | campus_real_ops/ | 食刻有数 实地经营台账 | 98行（4档口x7菜品x14日） | 团队实测 | 自有 | [Fine-tune微调+回测] 唯一真实校园标签，落地关键 |
| 3 | reduce_foodwaste/ | Reduce-Foodwaste-Dataset | train.csv 1087行 + test.csv 227行 | 公开基准 | 自带LICENSE | [学术佐证] 证明剩余率降低->减损价值的换算标准 |
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

迁移学习学的是"天气->销量、考试周->销量、周末跌多少%"这种通用统计规律，菜品名字完全不重要。

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
