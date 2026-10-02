# 食刻有数平台升级架构设计

## 1. 目标与边界

食刻有数面向高校食堂运营人员，提供经营台账、需求预测、分批备餐、限时优惠、订单核销、减损复盘和 AI 经营摘要。升级目标是把现有可运行单体整理为可持续演进的模块化单体，同时保留本地 H2 一键演示和 MySQL 试点部署能力。

本阶段不部署到外部平台，不引入 Kubernetes、Kafka 或微服务注册中心。Python 模型服务、Redis 和 Keycloak 只预留边界，在确有规模需求时接入。

## 2. 目标架构

```text
Thymeleaf SSR + TypeScript/Vite + ECharts
                         |
Spring Boot 模块化单体
  operations  prediction  waste  orders  analytics  intelligence  identity
                         |
Flyway -> MySQL/H2
                         |
Caffeine（单实例） -> Redis（多实例时）
```

采用 Spring Modulith 风格包边界，不在第一阶段拆成多个部署单元。每个模块通过应用服务和事件交互，禁止控制器直接访问其他模块的 Repository。

## 3. 模块职责

| 模块 | 职责 | 关键持久化对象 |
|---|---|---|
| operations | 经营台账导入、反馈、数量守恒、数据来源 | `daily_operation`, `operation_feedback_record`, `data_source_metadata` |
| prediction | 需求预测、备餐区间、模型融合 | `prediction_record`, `model_learning_log`, `model_version` |
| waste | 剩余分析、限时优惠、减损指标 | `discount_offer`, `operation_alert` |
| orders | 订单创建、取餐核销、审计 | `meal_order`, `verification_record` |
| analytics | 趋势、回测、财务和减损报告 | 只读聚合查询 |
| intelligence | AI 摘要、建议反馈、供应商适配 | `ai_advice_record`, `advice_feedback` |
| identity | 登录、角色、操作员上下文 | 后续新增用户与角色表 |

## 4. 数据库迁移策略

当前项目同时使用 `schema.sql`、`data.sql` 和 `DataBootstrapService`。迁移时采用以下顺序：

1. 将现有建表 SQL 固化为 Flyway `V1__baseline.sql`。
2. 将固定校历和数据来源元数据固化为 `V2__seed_reference_data.sql`。
3. 将模型版本和预测输入快照等新表放入后续版本迁移。
4. 关闭 Spring SQL 初始化，避免 Flyway 与 `schema.sql` 重复执行。
5. 保留 `DataBootstrapService`，但只负责读取、校验和幂等导入经营 CSV，不再建表或承担静态种子职责。

H2 使用 MySQL 兼容模式执行同一套迁移；出现 H2/MySQL 方言差异时，在迁移脚本中使用两者都支持的 SQL，而不是恢复双重初始化。

## 5. 预测引擎边界

新增 `PredictionEngine` 接口，输出包含预测区间、置信度、因素贡献、模型版本和输入快照的结果。默认实现为当前规则引擎，后续可增加：

- `RulePredictionEngine`：冷启动、数据不足和食品安全约束。
- `StatisticalPredictionEngine`：有足够历史记录时使用统计模型。
- `OnnxPredictionEngine`：模型文件可部署时使用 ONNX Runtime。
- `PredictionOrchestrator`：校验候选结果、执行降级和记录模型版本。

AI 只能生成解释文本，不能修改数量、金额、风险和经营动作。

## 6. API 与 DTO 规范

新接口使用统一响应包装：

```json
{
  "success": true,
  "data": {},
  "message": null,
  "traceId": "..."
}
```

业务错误使用统一异常处理器输出 `success=false`，不向客户端暴露堆栈。现有接口先保持兼容，再逐步迁移到 `/api/v1`。

## 7. AI 适配层

通过 `NarrativeProvider` 接口隔离供应商，保留本地规则摘要作为必选降级实现。当前保留智谱 HTTP 适配器，并加入 Spring AI OpenAI-compatible 适配器；通过 `FOODWISE_SPRING_AI_ENABLED=false` 默认关闭，开启后才由 Spring AI provider 接管文字摘要。两种适配器只接收结构化事实，不能直接访问数据库，也不能决定核心业务数值；输出经过长度和数字事实白名单校验。

## 8. 权限与缓存

权限分为管理员、运营中心、档口操作员和只读分析员。当前内存管理员配置保留用于演示，接口层先使用角色常量和方法级授权边界；真实试点再接入持久化用户或 Keycloak。

Caffeine 只缓存只读聚合和字典数据。任何经营反馈、优惠发布、预警处理和订单核销都必须失效相关缓存。多实例部署前再引入 Redis，不提前承担分布式缓存复杂度。

## 9. 实施与验收

实施顺序：

1. Flyway 基线迁移并验证 H2/MySQL 配置。
2. 模块包边界和统一 API 响应。
3. 预测引擎接口、模型版本和回测记录。
4. AI Provider 适配层。
5. 权限、缓存失效和操作审计。
6. 前端 API 类型、关键流程测试和文档更新。

验收证据：`gradlew test`、`gradlew bootJar`、前端 Vite 构建、H2 启动、MySQL 配置检查，以及预测、反馈、优惠、核销和报告主流程的接口验证。当前旧 Thymeleaf 兼容层和增强模型内部特征计算仍允许 Map 查询；新版 `/api/v1` 与核心写路径优先使用 DTO。
