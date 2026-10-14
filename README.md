# 食刻有数

## 本地目录布局

项目工作目录为 `项目代码/`，Git 仓库、后端、前端、模型、部署脚本和工程文档均在此目录。运行本 README 中的命令前，请先进入该目录。

上一级目录仅保留 `项目代码/`、`计划书/`、`PPT/`、`数据来源/`、`软著资料/` 五类内容。网站截图位于 `../计划书/计划书照片/网站截图/`。历史计划书生成脚本已归档至 docs/archive/20261013/，不参与应用构建。

原先被 Git 跟踪的计划书和软著文件已迁出代码仓库，Git 状态会显示这些旧路径为删除；材料文件仍保存在上一级对应目录中，历史版本仍可从 Git 查看。

高校食堂精细化经营与食品减损平台。当前主技术路线为 Spring Boot、Java 21、Vue 3、Vue Router、Pinia、Vite、TypeScript、MySQL/H2 和 Flyway，围绕“经营数据 - 销量预测 - 分批备餐 - 限时优惠 - 订单核销 - 效果复盘”形成可追踪的运营闭环。

## 页面与验证

当前应用入口为 `/app/dashboard`，生产环境加 `/foodwise/` 前缀。

- `/app/stalls`：档口与菜品；数值统一舍入，图片为同类菜品示意。
- `/app/prediction`：按目标日期、餐次生成规则备餐参考；经验范围尚未校准。
- `/app/operations/feedback`：手工回填、CSV 预览与逐行导入、台账导出。
- `/app/offers`、`/app/orders`、`/app/alerts`：优惠、核销、预警。
- `/app/reports`：经营测算与冻结公开实验分别展示。
- `/app/insights/realtime`：最近营业日快照，不代表实时监测。
- `/app/insights/demand`：同源公开销量观测、基线、模型预测对照。
- `/app/insights/waste`：剩余测算；不代表现场减损收益。
- `/app/about`：输入要求、使用步骤与来源说明。

工程整理与验收见 [优化实施报告](docs/validation/optimization-implementation-20261013/REPORT.md)。
建模当前入口为 `modeling/scripts/verify_current.py`；添加 `--experiment` 运行新的不可覆盖公开销量实验。
历史管道只有显式 `--historical` 才可运行，并不能替代当前验证。

## 本机启动

项目统一使用 Java 21。请先确认 `java -version` 显示 21 或更高版本。

默认启用 `local` 配置，使用H2的MySQL兼容模式，无需安装数据库：

```powershell
.\gradlew.bat bootRun
```

访问：<http://localhost:8089>

## MySQL启动

创建数据库：

```sql
CREATE DATABASE foodwise CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'foodwise'@'localhost' IDENTIFIED BY '替换为强密码';
GRANT ALL PRIVILEGES ON foodwise.* TO 'foodwise'@'localhost';
```

设置环境变量并启动：

```powershell
$env:SPRING_PROFILES_ACTIVE="mysql"
$env:FOODWISE_DB_USERNAME="foodwise"
$env:FOODWISE_DB_PASSWORD="替换为强密码"
.\gradlew.bat bootRun
```

## 构建测试

```powershell
.\gradlew.bat test
.\gradlew.bat bootJar
```

低内存服务器运行建议：

```bash
java -Xms96m -Xmx256m -jar foodwise-0.0.1-SNAPSHOT.jar --spring.profiles.active=mysql
```

## 数据说明

### 智谱智能解释（可选）

网站的销量、成本、风险、备餐与优惠数值由后端规则计算；智谱模型只负责将结构化结果转化为经营摘要。未配置密钥或接口不可用时，会自动使用本地建议，不影响核心功能。

PowerShell中临时配置：

```powershell
$env:ZHIPU_API_KEY="<填写你自己的 API 密钥>"
$env:ZHIPU_MODEL="glm-4-flash"
```

不要把API Key写入`application.yml`、JavaScript、HTML或Git仓库。已在聊天或截图中暴露的密钥应先在智谱控制台轮换。

### 经营数据回传与滚动更新

工作人员可通过`/operations/feedback`回传当天的建议备餐、实际备餐、售出、优惠售出、闭餐剩余、收入、天气和校园事件。后端会校验数量守恒与食品安全确认，同一菜品同一天再次提交按“修正”处理并保留操作记录。

这里的在线学习采用固定的“最近7日递增权重滚动更新”方法。新台账写入后会自动进入下一次预测窗口，并记录更新前后基线和调整幅度。智谱模型不训练、不修改公式，也不生成数量、金额和经营动作，只能填写固定页面模板中的简短经营概括。

### 上线登录保护

本地演示默认不启用登录拦截。部署到公网前必须设置管理员密码并开启登录保护：

```powershell
$env:FOODWISE_SECURITY_ENABLED="true"
$env:FOODWISE_ADMIN_USER="foodwise-admin"
$env:FOODWISE_ADMIN_PASSWORD="请设置至少10位的独立强密码"
```

启用后，经营页面和接口均需要登录；密码只从服务器环境变量读取，不写入源码或配置文件。

网站启动时优先读取高校餐饮经营测算资料，并在事务中校验、刷新数据库经营记录：

```text
src/main/resources/data/foodwise_operations_14d.csv
```

可通过环境变量覆盖路径：

```powershell
$env:FOODWISE_CSV_PATH="D:\data\foodwise_operations.csv"
.\gradlew.bat bootRun
```

如果外部文件不存在，程序使用JAR内同哈希数据快照。当前98条记录属于经营测算样本，并接入Open-Meteo公开城市级天气，用于验证网站、模型回测、财务分析和经营流程，不代表真实问卷、访谈或档口试点成果。

数据与分析接口：

- `GET /api/health`：应用和数据库连通性检查。

- `GET /api/v1/analytics/metadata`：样本性质、记录数、时间范围、校验率和来源。
- `GET /api/v1/analytics/backtest`：近7日滚动平均与天气/校历增强预测的时间滚动回测。
- `POST /api/v1/operations/import`：上传经营 CSV，复用数量守恒和食品安全校验后批量写入。
- `POST /api/v1/operations/import/preview`：预览 CSV 表头、样例行和缺失字段，不写入数据库。
- `GET /api/v1/weather?city=131000`：调用高德地图天气接口查询校区所在城市实时天气，并转换为预测模型标签。
批量导入 CSV 至少需要这些字段：`business_date,dish_id,planned_qty,prepared_qty,sold_qty,discount_sold_qty,leftover_qty,revenue,weather`；可选字段为 `event_tag,recommendation_adopted`。

生产角色可通过环境变量增加运营员和分析员账号：`FOODWISE_OPERATOR_USER`、`FOODWISE_OPERATOR_PASSWORD`、`FOODWISE_ANALYST_USER`、`FOODWISE_ANALYST_PASSWORD`。管理员负责写操作，分析员只读。

新版模块化接口位于 `/api/v1`，返回统一的 `success/data/code/message/traceId/timestamp` 结构。列表接口支持 `page`、`size` 参数，分页数据包含 `items/page/size/total/totalPages`；前端 getPage 保留完整元数据，getAllPages 用于需要加载全部分页的列表。

- `GET /api/v1/predictions/engines`：可用预测引擎。
- `POST /api/v1/predictions`：按 `dishId/weather/examWeek/campusEvent/engine/targetDate/mealPeriod` 生成带模型版本的预测，未提供日期与餐次时默认明天、全日。
- `GET /api/v1/analytics/metadata`、`GET /api/v1/analytics/backtest`：数据元信息和回测结果。

写接口必须携带 `Idempotency-Key`，重复提交返回 `409 IDEMPOTENCY_CONFLICT`。预测、优惠、核销、预警处理和经营反馈会写入 `audit_log`，记录 trace、账号、角色、资源和请求路径。`ADMIN` 拥有全部权限；`OPERATOR` 负责经营写操作；`ANALYST` 仅可读取分析与经营数据。

Spring AI OpenAI-compatible 适配器默认关闭。设置 `FOODWISE_SPRING_AI_ENABLED=true` 并提供 `ZHIPU_API_KEY` 后才启用；默认的本地规则摘要和智谱 HTTP 适配器仍可作为降级路径。AI 输出只用于文字概括，并经过长度和数字事实校验。

财务口径为：食材成本=`备餐量×菜品单位成本`，贡献利润=`收入−食材成本`；暂未计入人工、租金和平台固定成本。


## 构建系统

### 后端 (Gradle)

```powershell
# JAVA_HOME 指向本机 Java 21 安装目录
.\gradlew.bat build          # 编译 + 测试 + 打包
.\gradlew.bat bootRun        # 本地启动
```

### 前端 (Vue 3 + Vue Router + Vite + TypeScript)

前端源码位于 `frontend/`，使用 Vite 构建后输出到 `src/main/resources/static/build/`：

```powershell
cd frontend
npm ci                # 首次运行前按锁文件安装依赖
npx vite build        # 生产构建
npx vite              # 开发模式（热更新）
```

前端主入口为 `frontend/src/app.ts`，使用 Vue 单文件组件、Vue Router 和 Pinia 管理 `/app/**` 路由，构建产物自动作为 Spring Boot 静态资源提供。旧原生 DOM 运行时代码已移除。

Gradle 构建已经接入 frontendBuild → processResources → bootJar，打包前会构建前端；首次使用仍需在 frontend 执行 npm ci。静态构建资产沿用仓库既有跟踪方式，发布前必须统一重新构建。当前建模验证入口为 `modeling/scripts/verify_current.py`，旧管道须显式 `--historical`；完整本地与前缀验收命令、临时测试账号配置和验证限制见优化实施报告。

Vue 应用入口：

```text
frontend/src/app.ts
frontend/src/App.vue
frontend/src/router/index.ts
frontend/src/layouts/AppLayout.vue
frontend/src/views/
```

新前端访问地址为 `/app`，后端 API 统一使用 `/api/v1`。

## 缓存策略

使用 Caffeine 本地缓存加速以下高频查询（5 分钟 TTL）：
- `dashboard`：经营驾驶舱摘要与复盘报告
- `analytics`：经营分析聚合指标
- `backtest`：预测模型回测结果
- `metadata`：数据元信息
- `stalls`、`dishes`、`offers`：基础字典数据

写操作（创建优惠、回传数据等）自动失效对应缓存，确保数据一致性。

