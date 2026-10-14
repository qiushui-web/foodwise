# Foodwise 界面与代码结构优化方案

日期：2026-10-13；2026-10-14 更新。状态：S0–S6 本轮实施及本地验收已完成，实际变更、兼容边界与未验证项见 [实施报告](validation/optimization-implementation-20261013/REPORT.md)。下文问题和初始观测保留为实施前基线。

## 1. 判断与范围

当前项目已有可运行的经营流程、统一 API、输入校验、数据库迁移、审计、幂等和测试基础，适合渐进整理。建议优先修复指标可信性与写入后的数据一致性，再统一界面，最后收敛实验代码和工具脚本。单纯删除目录或重新做一套页面不能解决这些问题。

初始审查仅新增文档和浏览器证据；随后按用户授权完成本地代码实施与测试，未部署或推送。工作树已有大量未提交修改、移动和删除；不能执行 git reset、git clean 或按 Git 删除记录批量清理。

上层根目录保持现有五个目录：项目代码、计划书、PPT、数据来源、软著资料。历史计划书、PPT、图片、来源和软著资料不属于此次代码清理范围。

## 2. 证据与验收边界

- 阅读当前源码、路由、模板、服务、仓库、构建配置和脚本入口。
- 使用本地已有 JAR 启动 8089 演示实例；JAR 构建时间为 2026-10-13 16:59:55，前端 app.js 为同日 16:59:47。这是已有构建的界面审查，不是本轮重新构建验证。
- Chromium 无头浏览器访问 12 个业务路由，分别使用 1440×900、390×900 视口，共 24 次页面访问。
- 两个视口均未发现整页横向溢出、pageerror 或 HTTP 400 以上响应。采集了可见内容和小字号节点，人工查看了需求分析桌面截图与总览手机截图。
- 截图和观测：`docs/screenshots/optimization-audit-20261013/`，包含六张截图与 `observations.json`。
- 此轮没有执行写入台账、发布优惠、核销、真实权限登录、完整键盘导航、触屏手势、200% 缩放或性能基准。没有验证服务器与 `/foodwise/` 前缀。
- 历史测试记录不能替代此次重构后的验收，实施时必须重跑相关测试。
- `impeccable` 上下文启动器因无法调用 curl 下载引擎而失败，未运行其检测器；依据现有源码、浏览器采集和 Web Interface Guidelines 的审查要求进行检查。交付时规则源复查遇到连接中断，因此不宣称完成最新规则的完整核验或 WCAG 合规认证。

## 3. 当前结构与实际调用关系

```text
frontend/src/app.ts → App.vue → router → AppLayout → views
Spring PageController → templates/app.html 或 login.html
模板 → app.css → theme-blue.css → visual-enhanced.css → build/app.css
页面 API → utils/vue-api.ts → /api/v1
预测页面固定 engine=rule
  → ApiV1Controller → PredictionOrchestrator → PredictionService
  → FoodwiseRepository + IntelligentDecisionService → 预测与快照
经营汇总 → FoodwiseService → FoodwiseRepository
回测分析 → AnalyticsService → 台账 + classpath 历史报告锚点
经营录入/导入 → OperationFeedbackService / OperationImportService → Repository
实验链：ModelCrossCheckService → DualPredictionService → 规则 + LgbmCampusModel
独立增强实现：EnhancedPredictionService
```

源码搜索仅发现 `PredictionService` 实现 `PredictionEngine`。没有发现当前 API/页面调用 `EnhancedPredictionService` 或 `ModelCrossCheckService`；`DualPredictionService` 被交叉校验服务引用。它们不是可以直接批量删除的已证明死文件：仍有 Spring Bean 初始化、资源加载和脚本生成关系，需要进一步检查反射、文档入口及测试后再归档。

`FoodwiseRepository.java` 约 46 KB、`AnalyticsService.java` 约 20 KB，说明数据访问与分析集中；大小只是拆分线索，不能作为删代码依据。现有 `modules/*/package-info.java` 表达模块意图，但没有自动证明实际职责已隔离。

## 4. 优先级与具体问题

此表采用实施优先级：P0 是发布前必须处理的错误或误导，P1 是主要一致性与维护问题，P2 是非阻塞整理。共 14 个主要工作项，避免把装饰细节全部升为 P0。

| 编号 | 级别 | 文件与证据 | 影响 | 具体处理与验收 |
|---|---|---|---|---|
| C01 | P0 | `service/AnalyticsService.java:88`，125–151 附近；`ReportsView.vue` | 当前台账的 samples/details 与历史报告锚点混装；缺失锚点回退 6.166/24.7245，LSTM 8.706 硬编码，MAE 又按锚点缩放；100-MAPE 被命名 hit_rate | 拆成经营复盘 DTO 和实验报告 DTO；实验必须带 runId、数据集、标签单位、划分、模型版本、样本数和来源；不存在报告则显示不可用。取消无证据回退、推导 hit_rate 和缩放 MAE。验证报告缺失/损坏/单位不符不会生成精度数字 |
| C02 | P0 | `InsightsView.vue:12`；`ReportsView.vue` | 三个模式同用售出/备餐比例柱高；“预测模型效果”并非预测对照图。“实时”“当日”实际显示最近历史营业日，复盘页称“授权台账”缺少状态依据 | 分别提供营业快照、预测验证、剩余分析内容；显示明确营业日期、更新时间、来源性质。需求图使用同一实验的 actual/prediction；无有效实验时显示解释性空状态。截图核对标题、单位与数据一致 |
| C03 | P0 | `OperationFeedbackService.submit`、`OperationImportService` 未发现缓存失效；`CacheConfig.java` 五分钟 TTL | 写入后汇总、菜品、复盘可能继续显示旧缓存；与“写入后直接使用”提示矛盾 | 建立事务提交后的经营数据变更事件，集中失效 dashboard/analytics/backtest/metadata/stalls/dishes 等依赖缓存；只失效受影响项，外部天气缓存保留。先暖缓存、写入、重新读取，验证无需等 TTL 即更新；回滚不触发提交事件 |
| C04 | P1 | `PredictionService.java:97–131`、`FoodwiseRepository.java:113`、`DualPredictionService.java:65,144` | 当前固定预测明天；历史查询返回无日期的最近七个营业记录；实验服务硬编码 0.6/0.4 和另一套特征窗口 | 统一 PredictionContext 的 targetDate、mealPeriod、historyCutoff、sourceNature；历史返回日期与营业状态。抽出 FeatureBuilder；融合权重仅来自验证后冻结配置。保留规则降级；测试缺日期、重复餐次、未来记录和不可用模型 |
| C05 | P1 | `PredictionService.java` 与 `DualPredictionService.java` | 两处重复 ±8%、首批 0.82、12:18 等经验策略；启用实验链时先调用带持久化副作用的规则预测，保存结果可能与最终融合不一致 | 分离纯计算、策略、叙述、结果落库；一次请求只保存一次最终结果和输入快照。经验参数集中配置并标注经验参考；尚未校准不能写覆盖概率。派生演示模型不得替换观测销量验证模型 |
| C06 | P1 | `FoodwiseService.java:30,194`；`FoodwiseRepository` | Map/DTO 两套查询与汇总映射，重复年化成本、碳、水计算；容易出现同名指标口径漂移 | 抽一个 SummaryCalculator，统一类型 DTO；把年化测算作为明确假设的场景结果。API 边界临时适配旧 snake_case，迁移页面后移除兼容。对相同输入比较旧/新输出及舍入 |
| C07 | P1 | `templates/app.html`、`login.html`；三个静态 CSS；各 View | 绿色基础主题→蓝色覆盖→视觉增强→scoped 样式，多个来源修改同一 sidebar/panel/btn；历史 --green 实际为蓝色，界面变化难定位 | 迁移到唯一 token、base、layout、component 样式入口；每次删旧选择器前核对覆盖与截图，不整文件盲删。保留图片路径、字体回退、focus 和响应式规则 |
| C08 | P1 | `ReportsView.vue:10`、`InsightsView.vue:13`、`AlertsView.vue:14–15` | view-head/panel/metric-grid/state 重复；预警样式先定义小字号再补丁覆盖。复盘与分析页多个关键标签仅 9–11px | 抽 PageHeader、MetricCard、DataPanel、StatusBadge、AsyncState 六个基础组件；正文默认 14–16px，辅助说明至少 12px，业务指标标签优先 13–14px；按钮推荐最小 44px，结合 WCAG 目标尺寸条件检查 |
| C09 | P1 | `StallsView.vue:24` 浏览器观测 | 平均销量 52.785714285714285、剩余率 11.168841626571336%，增加表格宽度与阅读负担 | 共用 Intl.NumberFormat：金额两位、比例一位、平均销量一位；零、缺失与不可计算分开。数据计算保留精度，展示层舍入；测试 null/0/小数 |
| C10 | P1 | `vue-api.ts:13–48`；View 中大量 any 与双字段兼容 | 泛型默认 any，遇到 items 自动拆包丢失分页元数据；无请求超时，随机幂等键在每次重试重新生成 | 独立 api/types 与领域 adapter；getPage 返回完整 PageResponse；超时/取消；同一次业务提交重试复用键，新的意图生成新键；403 与空数据分别显示。验证失败重试及分页边界 |
| C11 | P1 | `AppLayout.vue:13–23,75,81`、`router/index.ts`、`App.vue:11` | session 异常被吞掉，菜单暂按宽权限显示；移动菜单缺 expanded/controls、Escape/焦点处理；顶栏和页面标题重复，登录借 body:has 全局覆盖 | 会话加载/失败明确呈现；导航按会话确认后展示，后端权限仍为准；抽屉支持焦点返回和 Escape；App 根路由类控制登录布局；更新 document.title；未知路由给可理解状态 |
| C12 | P2 | `modeling/scripts/run_all.py:12`、`modeling_pipeline.py`、`deploy/*.py` | 历史一键管道没有包含当前 14–16 验证路径；多个一次性源码补丁脚本可能回写旧实现 | 制定唯一验证入口与 manifest，显式列出当前/历史/废弃状态；部署目录只保留运行部署工具，其余归档。先检查引用、绝对路径、源码写入，禁止把旧管道称为当前完整复现入口 |
| C13 | P2 | `docs/*.py`、`docs/product`、`assets`、`modeling/data/03_output` | 文档制作过程、正式说明、历史实验和应用资产混放，影响维护；同主题不同标题不证明内容重复 | 建立资产用途、许可证、引用与哈希清单；将计划书制作工具/中间图归到资料目录或文档工具区；实验按 runId 保存，标记 current/historical/invalid。保留原始证据 |
| C14 | P2 | `build.gradle`、`router/index.ts`、`frontend/vite.config.mjs` | 前后端构建入口分离，容易打包旧前端；页面全量静态导入，当前 chunkFileNames 固定 vendor.js | 接入可复现 frontendBuild→processResources→bootJar 流程，记录构建版本；决定构建资产是否入 Git；测量首屏后再懒加载，改唯一 chunk 命名后才多分块。依赖是否冗余须看使用与解析结果，不能仅按名称删除 |

## 5. 界面方案：让经营者知道下一步

### 5.1 导航和信息层级

保留现有业务路由，先把“经营复盘、实时经营、需求分析、减损分析”收敛到“复盘与验证”导航组或页内标签，旧地址兼容跳转。建议主导航七项：经营总览、档口与菜品、备餐建议、剩余与优惠、订单核销、经营台账、复盘与验证；预警放入总览待办与顶栏，说明放到帮助。是否最终合并页面取决于各页是否提供独立任务。

每页固定顺序：页面标题与一句目的 → 营业日期/来源/更新状态 → 首要操作 → 结果 → 补充解释。顶栏保留环境、会话与待办，不重复占用第二套大标题。英文装饰标签不能承担业务信息。

### 5.2 页面具体改法

| 页面 | 建议布局和功能边界 |
|---|---|
| 总览 | 顶部日期、数据状态、待办；中部备餐/售出/剩余/优惠四项；底部最近趋势。长使用说明折叠或链接到帮助，手机指标两列，避免整屏堆四张装饰大卡 |
| 备餐 | 桌面条件左、执行建议右；手机先条件再结果。展示目标日期、历史长度、规则/模型版本、降级原因；首批与补餐条件突出。固定停做时间需标记经验参数 |
| 台账 | 手工/CSV 保持现有两入口；数量、收入、情景分组；数量守恒即时提示；导入先预览，再确认，逐行错误可追踪；成功后链接到更新后的汇总 |
| 档口与菜品 | 上方档口筛选，下方菜品表；统一数值舍入。手机局部表格滚动并给提示，或关键字段卡片；详细成本不在每个窄卡重复 |
| 剩余与优惠 | 显示库存日期与更新时间、预计可售量、安全确认和有效时段；建议与发布按钮分开；真实图片作为同类示意保留说明 |
| 核销 | 输入取餐码作为首要操作，匹配后确认菜品/数量/状态；已核销明确显示；重复提交保持幂等，不用页面消失表示成功 |
| 预警 | 风险、原因、营业日期、处理动作同一行；处理后计数立即更新；无预警展示空状态，不以 0 代替加载失败 |
| 复盘 | 经营结果与公开实验分区。经营变化展示样本和比较期，不宣称因果改善；公开验证展示冻结基线比较、单位、划分和报告来源 |
| 帮助/登录 | 保留已有中文输入指引、来源和图片许可。演示进入与真实登录语义明确；由环境配置决定，不对真实模式做无条件演示回退 |

### 5.3 视觉与无障碍标准

沿用蓝色品牌与真实食物照片，不新增装饰图片替代数据。统一背景、边框、阴影、圆角和间距；白色面板以边界为主，减少渐变背景、圆环及重复阴影。蓝色表示主操作，橙色表示待核对，红色表示错误，绿色表示已完成，状态同时提供文字。

建议 token：spacing 4/8/12/16/24/32；组件圆角 8，面板 12；正文 14–16，说明 12–13，页标题 24–28。颜色要测普通文本至少 4.5:1，不能只看截图推断合规。统一 focus-visible，尊重 prefers-reduced-motion。

每页须有加载、空、失败可重试、权限不足、成功、数据过旧状态。关键错误关联到字段并支持屏幕阅读器；移动菜单正确反映展开状态、管理焦点与 Escape。菜单抽屉和表格手势需额外验证，窄视口截图不能证明触控有效。

## 6. 推荐目标结构

不更换技术栈，不拆微服务，不为小组件引入额外 UI 框架。目录先按职责渐进收敛。

```text
项目代码/
  frontend/src/
    api/                  # typed client、DTO、领域适配
    components/           # 六个通用基础组件
    composables/          # async 状态、会话等实际复用逻辑
    styles/               # tokens.css、base.css、layout.css、components.css
    layouts/              # AppLayout、登录布局
    views/                # 页面编排，保留现有路由
    router/ stores/ utils/
  src/main/java/org/foodwise/
    api/                  # 校验、响应、权限边界
    prediction/           # context、纯计算引擎、特征、策略、编排
    service/              # 经营写入、汇总、报告、外部叙述
    repository/           # 按经营/订单/来源/预测职责逐步拆查询
    model/dto/ config/
  src/main/resources/
    db/migration/ data/ modeling/ templates/ static/
  modeling/
    scripts/ tests/ data/  # 当前验证入口与原始复现证据
    archive/              # 明确标记的历史脚本，不参与默认管道
  deploy/                 # 当前部署、健康检查、回滚工具
  docs/
    architecture/ product/ validation/ screenshots/
```

现有 package-info 与模块约定优先保留；若采用 modules 分包，须同步移动实现并增加依赖检查，不能同时维护两套平行目录。Repository 先抽 SQL/映射相同的职责，再迁移调用，禁止先改所有包名。

## 7. 文件处置清单

| 类别 | 对象 | 处置门槛 |
|---|---|---|
| 保留 | gradlew、gradle/wrapper、源码、迁移、测试、来源、许可、模型卡、冻结推理样例 | 核心可移植运行与审计依据，不是缓存 |
| 合并 | 多层 CSS、重复页面基础样式、FoodwiseService 的双汇总、API 字段兼容 | 新入口有等价输出和页面验收后移除旧实现 |
| 归档候选 | EnhancedPredictionService、DualPredictionService、ModelCrossCheckService、历史训练/补丁脚本 | 确认当前入口无依赖、初始化无必要副作用，保留实验来源与回滚记录；LgbmCampusModel 保留一致性测试依赖 |
| 文档归位 | docs 中计划书制作脚本、改图提示和过程资产 | 先做引用清单；相对路径适配后移动，不丢正式材料或复现证据 |
| 可再生本地缓存 | build、.gradle、node_modules、.venv、__pycache__、test-results | 忽略 Git；确认无运行进程占用和唯一证据，再按明确绝对路径清理。运行依赖与缓存不能混为一谈，.venv 当前用于复现，优先保留 |
| 删除候选 | `_inspect_uwaste.py`、`09_download_real_datasets.py` | 已核对均为 0 字节，属于空文件；检查旧脚本和文档引用后移除或补充废弃说明，不能据此宣称找到两份重复业务逻辑 |
| 继续保留 | modeling/data/03_output 中历史实验 | 给失效策略结果写 invalid 标识，不能覆盖或删除成“当前结果” |
| 空目录 | 已检查 src、frontend/src、deploy、modeling/scripts | 此轮未发现空目录；不为清理数量而删除结构预留或 Git 所需目录 |

Git 管理范围也需要整理：此前移动的计划书/软著材料显示为删除不代表应删除实体。后续单独审核文件移动和 .gitignore，再决定提交；不自动暂存或推送。

## 8. 分阶段实施与回滚

| 阶段 | 工作 | 验收/回滚 |
|---|---|---|
| S0 基线 | 保存当前差异、文件用途清单、构建指纹；只登记清理候选 | 可恢复工作树快照，不覆盖用户修改；明确当前实验报告与历史失效报告 |
| S1 可信指标 | 完成 C01/C02，经营与公开实验分开；无报告不得自动填精度；图表数据与标题一致 | 报告来源/样本/单位契约测试；报告缺失与损坏测试；浏览器核对文案与数据。旧接口 adapter 作为临时回滚点 |
| S2 写读一致 | 完成 C03，提交后事件和缓存失效；统一 SummaryCalculator | 暖缓存→写入→读取、事务失败、批量部分拒绝三种测试；记录旧响应差异 |
| S3 界面收敛 | 完成 C07–C11，先壳层与 token，再逐页组件迁移；不同时换主题和数据接口 | 桌面/手机、键盘、空/错/权限、200% 缩放；旧 CSS 分批停载，每批截图对比；失败恢复该批样式入口 |
| S4 预测边界 | 完成 C04/C05，纯引擎、特征、策略、落库分离；实验模式显式隔离 | 历史窗口与缺失值测试、Python/Java 推理 fixture、最终结果只保存一次；规则引擎作为已知降级路径 |
| S5 目录与脚本 | 完成 C06/C12–C14 剩余迁移；归档历史脚本；统一构建入口和说明 | 从文档入口构建/验证；依赖与资源引用复查；归档索引支持恢复；清理前逐项核对用途 |
| S6 最终验收 | 回归核心经营链，检查根路径与 /foodwise/ 前缀 | 所有必需测试零失败、关键前缀测试不得 skip；保存日志与构建版本。服务器部署另按授权执行 |

阶段清单：S0–S6 本轮实施及本地验收完成。每个 C01–C14 的实际交付、兼容保留与限制见实施报告；拟议的全仓库结构示意不视为已完成重写。

## 9. 测试清单与完成定义

从项目代码目录执行现有工程入口：

```powershell
cd frontend
npm run typecheck
npm run build
npm run test:e2e
cd ..
.\gradlew.bat test bootJar
modeling\.venv\Scripts\python.exe -m unittest discover -s modeling/tests
```

建模验证脚本 13/14/15/16 的参数以实际 CLI 为准，先读取 `--help`，保持已有数据划分、依赖和输出目录；不要用旧 run_all.py 覆盖当前模型资源。只对本次行为风险增加测试，不写镜像实现的形式测试。

必须补充：

1. 汇总与实验结果不可混用；报告缺失时不回退精度数字；数值和图表来自同一来源。
2. 写台账后缓存立即更新；异常事务不产生有效结果；批量导入拒绝行可追踪。
3. 历史窗口无未来数据，缺失日期不当零销量，餐次与日期规则一致。
4. 同一业务请求重试复用幂等键，预测最终结果与快照一致；重复核销不重复扣减。
5. 完整流程：确认菜品→生成建议→回填/CSV 导入→更新复盘→确认可售库存→发布优惠→取餐核销。
6. 根路径和 `/foodwise/` 的登录、资源、API、导航、刷新、导出、权限回退全部验证。当前 prefix.spec.ts 有条件跳过，跳过不是通过。
7. 桌面 1440、窄手机 390 和 320、键盘、200% 文本缩放、错误状态、控制台与资源。触屏和屏幕阅读器未测则明确注明。
8. 前端源码、静态产物、JAR、启动版本一致；任何部署另保存服务器健康证据和回滚包。

完成标准：P0 全部关闭；上线入口只有一套；共享样式有单一来源；没有失去使用入口或证据的删除；工程检查通过；上述关键流程有证据；公开数据实验不能被解释为现场份数、人民币收益或实际减损。没有现场数据的部分保留验证限制。

## 10. 与既有详细设计的对应

- 第 5 节技术架构：C04–C07、C10、C12–C14，对应入口、领域职责、可复现构建与资料边界。
- 第 6 节预测策略：C01、C04、C05，区分规则、观测销量模型、派生演示模型、融合与区间校准。
- 第 9 节工程与解释验收：C02、C03、C08–C11 和第 9 节完整测试清单。
- 第 15 节实施清单：先可信展示与数据一致性，再特征/策略与验证；公开缩放数据不能用于物理产能与现金收益结论。

## 11. 目标模式状态

初始审查时已有目标处于 blocked，因此没有重复创建目标。随后沿用既有目标按本方案完成本地实施；最终状态以目标工具返回为准。

初始审查交付本方案、24 次浏览器观测与 6 张截图。后续实施交付可信实验展示、缓存一致性、预测边界、界面与类型整理、归档清单、统一构建和验收日志；Java 24 项、浏览器 30 项、Python 26 项通过。浏览器另有 2 项桌面不适用测试跳过，前缀测试实际通过。完整结果及限制见实施报告。
