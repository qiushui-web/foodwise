# 第二轮实体、区间与训练链验证

日期：2026-10-13。目标模式active。本轮结果为公开缩放销量探索，不是河北现场成效。

## 设计与内部验证

entity-interval-v1在运行前保存协议。原训练期3个扩展窗口，每窗留出5家拟合店中的一家，共15组留店；拟合和early stopping都排除该店，但允许其预测前历史构造lag。评估模型未见实体且已有28天历史，不是无历史启动。7叶、最小叶样本50、学习率0.03、树上限300、seed42。L1/L2训练均按MAE早停，与首轮默认L2早停协议不同。

| 方法 | 时间窗MAE | 留店MAE |
|---|---:|---:|
| L1直接 | **0.374199** | **0.387228** |
| L2直接 | 0.379604 | 0.394182 |
| L1半融合 | 0.437508 | 0.441850 |
| 未见实体回退同星期均值 | 0.437508 | 0.540674 |
| 上周同日 | 0.457306 | 0.457306 |
| 同星期均值 | 0.540674 | 0.540674 |
| EWMA0.2 | 0.589722 | 0.589722 |
| EWMA0.5 | 0.565785 | 0.565785 |

EWMA在日历序列shift1后计算，未知缺日不补0。留店拟合不使用该店标签，汇总按行数加权，不当独立样本。L1略优，EWMA没有优势；新店回退早期反而差，与后段新店退化方向相反，不能认证通用门控。

## 后段探索

原tune选择L1门控，MAE0.310834；最终L1模型220棵、L2模型198棵。已看后段MAE：同星期基线0.229702、L1直接0.228215、L1半融合0.205336、门控0.200698。门控较基线改善约12.63%，但设计受旧后段问题启发、tune重复使用，**不是独立确认**。不能略去训练期留店不利证据，更不能换算河北精度或收益。

## 区间比较

原calibration622行仅校准；分店门槛预设50，不足回退全局。分位数模型只在训练期拟合，交叉排序。CQR采用max(lower-y,y-upper,0)非负分数，只扩宽不缩窄，未根据后段选方法。

| 方法 | 80%后段覆盖 | 80%宽度 | 90%后段覆盖 | 90%宽度 |
|---|---:|---:|---:|---:|
| 全局残差 | 89.13% | 0.826653 | 95.07% | 1.220946 |
| 分店残差 | 89.86% | 0.839589 | 96.81% | 1.203619 |
| 原分位数 | 80.29% | 0.976402 | 90.87% | 1.412589 |
| 非负CQR | 85.58% | 1.069173 | 94.35% | 1.521207 |

宽度为缩放单位。分位数更接近名义覆盖但更宽，CQR没有明确优势；分店覆盖、宽度、interval score、逐行上下界均保存。校准期为拟合后描述，相关时序与漂移下无严格覆盖保证。

## 来源与旧链证据

核对[机构项目页](https://www.green-ai-hub.de/pilotprojekte/pilotprojekt-brammibals-donuts-foodtracks)与[Green-AI Hub仓库](https://github.com/Green-AI-Hub-Mittelstand/Reduce-Foodwaste-Dataset)：README/LICENSE/train的Git blob SHA与本地一致。副本一致不认证采样真实性；官方减损目标不能作本项目收益。数据专用许可范围、缩放公式/拟合时段待明确。没有上传私密数据或下载新销量样本。

来源报告provenance_20261013T095952264187Z/review.json。首命令保存报告后GBK打印德文失败；systematic-debugging定位控制台编码，修复JSON安全输出并离线重放通过，未替换原核验事实。

旧02构造反例：滚动统计串组导致第二实体首行得到前组均值15；全量中位数填补使修改未来目标后最早lag由3变1003；按记录lag7使1月15日取1月1日而非1月8日。构造反例不是现场样本，也不证明缺失uwaste生成器一定使用这些函数。

finetune_uwaste_metadata2600行sold_qty/category_id与parquet逐行一致；两处导出边界均train_max2025-08-10晚于valid_min2025-06-11，不支持严格时间回测。行值匹配不等于稳定主键；parquet缺日期/实体/来源，已审查目录未找到生成器，现有预训练产物与02—05脚本特征不同。完整链未成立。审计保存training_chain_20261013T100717188404Z/audit.json。旧代码行为未修复，线上模型未改，数据文档新增有效口径。

## 复现与推进

首轮entity_interval_20261013T095827758320Z；复现entity_interval_20261013T100719991891Z。10项关键产物字节一致，12项协议测试通过，保存候选、逐行预测、每窗/留店指标、树数、校准、依赖、哈希、日志和耗时。非跨平台或能耗结论。

```powershell
./modeling/.venv/Scripts/python.exe modeling/scripts/21_entity_and_interval_validation.py
./modeling/.venv/Scripts/python.exe modeling/scripts/21_entity_and_interval_validation.py
./modeling/.venv/Scripts/python.exe modeling/scripts/24_verify_entity_replay.py
./modeling/.venv/Scripts/python.exe modeling/scripts/23_legacy_training_chain_audit.py
```

下一步：校园CSV可执行质量验收、候选模型卡及重建规范；设计新尾段确认协议，再判断现有truth适用性。真实河北授权台账、校园推理一致性及现场对照仍待条件具备。
