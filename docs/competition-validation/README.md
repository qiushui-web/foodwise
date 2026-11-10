# 比赛验证包

更新：2026-11-02。用途：在无法取得中国高校真实经营台账的比赛阶段，用公开数据、校准仿真和工程测试支撑方法与系统可行性。所有证据类型分开展示；本包不证明食刻有数已在校园产生减损效果。

## 数据证据分工

| 数据 | 来源 | 本项目用途 | 不支持的结论 |
|---|---|---|---|
| ZHAW canteen menu sales 2017 | [Zenodo DOI 10.5281/zenodo.3890931](https://doi.org/10.5281/zenodo.3890931)，记录级 API 元数据 `license.id=cc-by-4.0`（2026-11-02 查询） | 真实大学食堂销售需求的时间回测；比较同星期基线、滚动基线与复杂模型；检查点预测改善是否转成决策收益 | 中国高校档口、菜品级备餐剩余或食刻有数现场减损效果 |
| Finland school food waste 2024–2025 | [Zenodo DOI 10.5281/zenodo.20825233](https://doi.org/10.5281/zenodo.20825233)，记录级 API 元数据 `license.id=cc-by-4.0`（2026-11-02 查询） | 厨房/供餐环节浪费的波动形态和外部量级参照；未直接注入本轮生成参数 | 备餐预测精度；公斤转份数；食刻有数减损效果 |
| Reduce-Foodwaste pastry dataset | Kaggle `pastry-prediction`，项目需随引用保留其仓库许可说明 | 数据质量拒绝案例：单位/标准化和 `ordered/sales/unsold` 守恒审计 | 绝对剩余量、真实剩余率或成本收益。项目审计发现关键字段不守恒且存在负值 |
| FreshRetailNet-50K | 项目已有来源登记与原始文件；引用应按其原始论文/发布页及许可核验 | 售罄标记下的需求截断方法测试；单独报告零售外推边界 | 食堂销量或剩余的直接效果 |
| 项目本地台账 | `src/main/resources/data/foodwise_operations_14d.csv` | 接口、页面和工程流程的构造/测算数据验收 | 真实校园数据、访谈或试点成果 |

不同公开数据集不拼接成一份“高校食堂数据”。其真实用途、原始许可和转换过程以各数据发布页面及项目 `数据来源/README.md` 为准。报告中的外部指标需注明数据粒度、日期范围、样本数、转换方法和许可。

公开数据每次重跑生成唯一目录 `modeling/data/03_output/competition-public-data/<run-id>/`，重复指定 `--run-id` 时拒绝覆盖。摘要记录原件 SHA-256、分析脚本 SHA-256、文件大小、运行环境及 Zenodo API 返回的许可证元数据；API 不可用时明确记为 `unavailable`，不推断许可证。结果路径与运行编号见 [结果记录](RESULTS_20261102.md)。

## 多种子仿真

新增入口：`modeling/scripts/51_competition_validation.py`。它复用项目现有的需求参数和成本假设，但按日期逐步模拟决策；策略只能使用此前可见的售出量，售罄日不用于残差校准。仿真真值仅用于事后评价。输出带 `synthetic: true` 和 `evidence_type: calibrated_simulation` 标记。

默认运行：

```powershell
modeling\.venv\Scripts\python.exe modeling\scripts\51_competition_validation.py --seeds 20 --days 90
modeling\.venv\Scripts\python.exe modeling\scripts\52_run_public_data_validation.py
```

公开数据脚本可用 `--output-root` 指定输出根目录、`--run-id` 指定可复现的目录名；运行目录必须不存在。例如：

```powershell
modeling\.venv\Scripts\python.exe modeling\scripts\52_run_public_data_validation.py --run-id public-data-recheck-01
```

快速 smoke test：

```powershell
modeling\.venv\Scripts\python.exe modeling\scripts\51_competition_validation.py --seeds 2 --days 30 --output modeling\data\03_output\competition_validation_smoke.json
```

主要输出 `modeling/data/03_output/competition_validation.json`，包含种子和情景级明细，以及按策略汇总的 regret/100、剩余率、缺货率和利润/日均值与 P5/P95。P5/P95 是跨随机种子的经验分位数，不是统计置信区间。

当前情景有基线、雨天需求整体缩放、校园活动需求整体缩放和高波动压力测试。雨天系数沿用项目现有 ZHAW 估计；活动系数及高波动参数是压力测试假设，不是公开数据估计。脚本不自动选出“赢家”；竞赛结论应报告跨种子结果、参数来源和该策略在哪些场景失效。

## 单位与数据契约

`convert_quantity` 保留原始值、原始单位、转换因子、基础单位和转换来源。份、个、公斤、升分别保留不可混加的量纲；锅/批次只有在提供经抽样确定的 `batch_size` 后才能折算为份等价量。不同菜品之间不得使用同一个未核验折算系数。

`validate_flow` 检查备餐量是否由售出、优惠售出、剩余和损耗完整解释。若实际存在转档、员工餐等去向，应显式扩展字段后再校验，不能为满足等式而改写现场记录。

运行测试：

```powershell
modeling\.venv\Scripts\python.exe -m unittest modeling.tests.test_competition_validation -v
```

测试包含单位和批次折算、非法/不守恒数据拒绝、多种子输出契约、“修改未来需求真值不得改变过去建议”的防泄漏检查，以及公开数据结果目录拒绝覆盖和 run-id 校验。公开数据重跑作为独立分析命令执行，不属于单元测试。

## 答辩口径

- 可说：系统已在公开食堂销售数据上做外部回测，并以公开浪费数据校准部分仿真参数。
- 可说：多种子仿真与工程测试验证了策略比较、单位契约、异常拒绝和时点回放机制。
- 不可说：已在中国高校验证减损比例、用户采纳率、利润提升或校园部署效果。
- 单次或单数据集结果均不等于普遍规律；仿真结论只对写明的生成过程和参数成立。
