# 校园数据准入规则与运行说明

本程序是离线结构与口径检查，不连接线上平台，不替换模型。CSV中的“verified”、授权编号和哈希属于提交者声明；程序不会据此认证票据真实性或授权有效性，原件和原始文件仍需人工复核。

## 使用者准备

档口负责人提供授权、菜品映射、计量单位、按餐次聚合的POS或台账、库存事件，以及退款净额口径。管理员按 CAMPUS_COLLECTION_GUIDE.md 映射字段，保留未经修改的原始文件，另生成观察结果表、预测输入表、来源登记表。不要导入顾客身份信息。

来源登记约定：`permitted_use`用分号分隔，可含`model_training`、`model_features`；`label_origin=observed`才可作为校园观察标签；`provenance_status=verified`需事先人工核验。结果来源的`target_definition=net_sales_disjoint_refunds_already_deducted`，`time_granularity=meal`，`entity_granularity=dish`，单位`portion`或`kg`，`sha256`填写原始文件的SHA256。来源授权至少分别覆盖训练或特征使用，不能用“展示许可”替代。

## 结果记录如何判断

同一学校、档口、菜品、日期、餐次只允许一行；所有重复行均隔离，不擅自保留第一条。菜品单位发生变化时隔离该实体此次批次的全部记录。份数为非负整数，公斤为非负数；未知保持空值，禁止将漏报补0。停业行保留在隔离输出中，后续日历构造要读取营业状态，不能当成缺报或正常营业零销量。

普通和折价销量互斥、均已扣退款；`refund_qty`保留原字段，不重复扣减。库存遵循“期初+制作+调入=普通净售出+优惠净售出+调出+退回厨房+报损+期末”。v1采用十进制精确守恒；称重存在精度差异时应先登记测量精度与调整事件，程序不自动容忍或填平差额。

缺货记录可进入观察结果，输出`supply_censored=True`，只表示销量被供给限制；不能自动推算潜在需求。训练需求模型时必须预先指定此类记录的处理与单独评价方式。任意非空`quality_flags`表示尚待处理，先隔离。

结果记录时间、来源取得时间不能晚于本次审计`as-of`。这只证明“本次审计时已可获得”，不代表历史预测截止时也可获得。训练链必须针对每个历史预测时点再检查来源取得时间和记录时间。

## 预测输入如何判断

预测输入与结果分表；主键加入`prediction_cutoff_at`以保留多次预测快照。`available_at`不得晚于截止时间，有天气值时`forecast_issued_at`也不得晚于截止。可选字段缺失保持缺失。当前v1保守要求价格已生效；已公告但未来生效的价格需增加公告时间字段后另行验收。

此检查不证明餐次开始前截止、活动/天气真实性、价格与菜品映射正确、跨时区日期一致或历史来源可用。正式采集统一使用河北当地日期和`+08:00`时间戳，尚未统一者不得进入正式训练。多来源复合行先拆分来源或建立逐字段血缘，不用一条来源声明覆盖全部字段。

## 运行及查看结果

在代码仓库根目录运行，输出目录必须是新目录：

```powershell
./modeling/.venv/Scripts/python.exe modeling/scripts/25_campus_admission.py --observations modeling/templates/campus_observations.csv --sources modeling/templates/source_register.csv --forecasts modeling/templates/campus_forecast_inputs.csv --as-of 2026-10-13T23:59:59+08:00 --output modeling/data/03_output/campus_admission_new_run
```

输出`accepted.csv`、`quarantined.csv`、两份预测输入结果和`report.json`。隔离表保留原字段、CSV行号和原因码；报告保存分母、通过率、隔离原因、输入/脚本哈希。成功退出只表示审计完成，应查看报告中的行数和拒绝原因，不能当成数据通过。现有模板只有表头，实跑0条，`training_ready=false`。

即使有通过行，程序仍返回`training_ready=false`：还须人工核对来源原件/哈希、历史特征可用性、覆盖周期、日历完整性、时间切分、供给截尾处理及独立验证。当前准入器不承担这些后续验收职责。

## 测试与证据

2026-10-13新增10项准入边界测试：净销量退款口径、零销量、缺货标记、空模板、重复主键、来源权限/重复登记、单位变化、非整数份数、异常标签/数值/库存/时间、预测截止与缺失值。构造记录仅用于代码测试，不是现场样本。本轮完整`unittest discover -s modeling/tests -v`共22项通过。

空模板运行证据位于`data/03_output/campus_admission_20261013_templates/report.json`。尚未对真实河北台账进行准入实测，也未接入在线CSV导入端点。
