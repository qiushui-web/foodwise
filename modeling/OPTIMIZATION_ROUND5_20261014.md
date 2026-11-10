# 第五轮：本地模型包与线上完整性保护

本轮针对“模型保存到本地是否能提升网站效率”完成工程化完善。

## 已实现

- 本地模型包脚本 `27_build_local_model_bundle.py`：复制模型、特征契约和校准参数，生成版本、来源类型、文件大小、SHA256及限制说明。
- 训练链接入修订去重：若记录包含`observation_id`、`available_at`、`revision_at`，训练前保留可见修订中的最新版本；派生标签和供给截尾记录仍不进入主训练。
- 可用性/区间工具 `28_availability_revision_interval.py`：按预测截止时间回放可见记录，独立校准集计算绝对残差区间半径。
- Java classpath完整性保护：新增`src/main/resources/modeling/model_manifest.json`，`LgbmCampusModel`启动时先校验模型和特征文件SHA256，失败则保持未就绪并回退规则引擎。

## 运行证据

- Python完整测试：30项通过。
- Java冻结推理一致性：`./gradlew.bat test --tests org.foodwise.CampusInferenceParityTests`通过，构建成功。
- 本地bundle：`modeling/data/03_output/local_model_bundle_20261014/`已生成。
- bundle当前来源类型是`derived-target-demonstration`，不覆盖线上模型。

## 对网站效率的实际影响

当前Java模型已在Spring启动时解析一次并保存在内存，接口请求不会重复加载模型或训练。新增manifest校验只发生在启动阶段，不增加每次请求的模型开销。网站整体耗时仍需拆分数据库查询、特征构造、Java推理、序列化和前端渲染后判断；本地模型主要减少模型加载和训练开销。

## 仍未声称完成的部分

当前bundle仍来自派生目标演示模型，独立校准文件不能迁移为河北份数区间。真实河北台账授权、原始文件核验、逐预测时点来源血缘、现场实体留出、Python-Java在线特征值一致性和影子试点仍待完成。未执行部署、上传或模型切换。
