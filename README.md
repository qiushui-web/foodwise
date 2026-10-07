# 食刻有数

高校食堂精细化经营与食品减损平台。当前主技术路线为 Spring Boot、Java 21、Vue 3、Vue Router、Pinia、Vite、TypeScript、MySQL/H2 和 Flyway，围绕“经营数据 - 销量预测 - 分批备餐 - 限时优惠 - 订单核销 - 效果复盘”形成可追踪的运营闭环。

## 页面

- `/dashboard`：经营驾驶舱
- `/stalls`：档口与菜品
- `/prediction`：智能备餐中心
- `/offers`：限时优惠
- `/orders`：订单核销
- `/reports`：经营仿真报告
- `/insights/realtime`：实时经营分析（售速、排队和档口效率）
- `/insights/demand`：需求预测分析（置信区间、因素贡献和需求热力）
- `/insights/waste`：减损成效分析（餐品流向、价值挽回和试点对比）
- `/about`：服务说明

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
$env:ZHIPU_API_KEY="重新生成后的智谱API Key"
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

新版模块化接口位于 `/api/v1`，返回统一的 `success/data/code/message/traceId/timestamp` 结构。列表接口支持 `page`、`size` 参数，分页数据包含 `items/page/size/total/totalPages`；前端会自动展开 `items` 以保持页面组件简单。

- `GET /api/v1/predictions/engines`：可用预测引擎。
- `POST /api/v1/predictions`：按 `dishId/weather/examWeek/campusEvent/engine` 生成带模型版本的预测。
- `GET /api/v1/analytics/metadata`、`GET /api/v1/analytics/backtest`：数据元信息和回测结果。

写接口必须携带 `Idempotency-Key`，重复提交返回 `409 IDEMPOTENCY_CONFLICT`。预测、优惠、核销、预警处理和经营反馈会写入 `audit_log`，记录 trace、账号、角色、资源和请求路径。`ADMIN` 拥有全部权限；`OPERATOR` 负责经营写操作；`ANALYST` 仅可读取分析与经营数据。

Spring AI OpenAI-compatible 适配器默认关闭。设置 `FOODWISE_SPRING_AI_ENABLED=true` 并提供 `ZHIPU_API_KEY` 后才启用；默认的本地规则摘要和智谱 HTTP 适配器仍可作为降级路径。AI 输出只用于文字概括，并经过长度和数字事实校验。

财务口径为：食材成本=`备餐量×菜品单位成本`，贡献利润=`收入−食材成本`；暂未计入人工、租金和平台固定成本。


## 构建系统

### 后端 (Gradle)

```powershell
$env:JAVA_HOME = "D:\Program Files\Java\jdk-21.0.12.1+1"
.\gradlew.bat build          # 编译 + 测试 + 打包
.\gradlew.bat bootRun        # 本地启动
```

### 前端 (Vue 3 + Vue Router + Vite + TypeScript)

前端源码位于 `frontend/`，使用 Vite 构建后输出到 `src/main/resources/static/build/`：

```powershell
cd frontend
npm install           # 首次运行前安装依赖
npx vite build        # 生产构建
npx vite              # 开发模式（热更新）
```

前端主入口为 `frontend/src/app.ts`，使用 Vue 单文件组件、Vue Router 和 Pinia 管理 `/app/**` 路由，构建产物自动作为 Spring Boot 静态资源提供。旧原生 DOM 运行时代码已移除。

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

