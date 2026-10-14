# Foodwise 优化实施验收记录

实施与主要回归日期：2026-10-13；证据收尾核验：2026-10-14。

本次按优化方案实施 S0–S6，保留已有工作树修改及资料。完成可信指标、写读一致性、预测边界、界面与类型整理、历史工具归档和本地验收。没有部署服务器、提交或推送 Git；本记录不证明服务器当前版本与本地一致。

## 工作项与验收

| 工作项 | 实际实现与证据 | 保留边界 |
|---|---|---|
| C01 | PublicExperimentReportService 读取冻结公开实验，校验来源、单位、划分、有限值；缺失或损坏返回不可用。报告契约测试通过 | 不把缩放销量换算为份数或收益 |
| C02 | 营业快照、需求验证、剩余分析使用各自数据与来源说明；需求 actual/prediction 来自同一冻结实验 | 经营变化不证明因果改善 |
| C03 | 提交后事件集中失效经营缓存；缓存键碰撞修复；CSV 有效行与拒绝行可追踪；状态字段扩容 | 天气缓存保留；独立 H2 验证，未验证外部 MySQL |
| C04 | PredictionContext 统一目标日期、餐次、来源和截断日期；带日期观测构造特征，不以缺失日期补零 | 在线实验特征值未全面验证 |
| C05 | FeatureBuilder、PredictionPolicy 分离计算；经验参数集中；结果、建议、快照同事务，故障回滚测试通过；实验链默认关闭 | 没有冻结融合权重，因此不提供未经验证的融合；经验区间不代表覆盖概率 |
| C06 | SummaryCalculator 统一 Map/DTO 场景汇总，输出一致性测试通过；年化假设明确 | 旧 snake_case API 适配继续保留以兼容现有调用，未强制改写整个 Repository |
| C07 | 单一静态 foodwise.css 入口，统一前端组件样式与 token；旧三份 CSS 归档停载，保留原始层叠顺序 | 合并文件内仍保留必要旧选择器与兼容变量，未宣称每个选择器都已去重 |
| C08 | PageHeader、MetricCard、DataPanel、StatusBadge、AsyncState 复用；小字号修正；移动复盘面板拥挤修正 | 原方案称“六个”但列出五个名称，本次实际交付五个；并非所有业务组件均替换 |
| C09 | 档口数值使用 Intl 格式化，零与缺失分开显示 | 底层计算保持原始精度 |
| C10 | 领域类型、完整分页元数据、超时/取消清理；业务意图重试复用幂等键，成功或内容变化换键；CSV 内容纳入签名 | 重复成功请求返回 409，未增加响应重放 |
| C11 | 会话错误明确、确认角色后显示导航；抽屉 Escape、焦点循环与返回；标题及未知路由状态统一 | 未做真实触屏手势或屏幕阅读器测试 |
| C12 | verify_current.py 为当前验证入口；旧管道要求 --historical；空脚本改为说明性失败入口；部署补丁工具归档 | 历史脚本仍可复查，不能用作当前完整验证入口 |
| C13 | 25 项归档映射及 SHA256 全部核对；资产清单更新；实验、模型资源、来源、许可保留 | 不删除历史失效实验；恢复旧源码前须审查，不可覆盖现有实现 |
| C14 | frontendBuild → processResources → bootJar；路由懒加载且 chunk 唯一命名；静态资源与 JAR 哈希逐项一致 | 按现有仓库惯例继续跟踪构建资产，避免未安装 Node 的使用者拿到缺失资产；发布仍须统一重新构建 |

S0 保存工作树保护材料；S1 可信指标、S2 写读一致、S3 界面收敛、S4 预测边界、S5 目录与脚本、S6 本地回归均完成本轮实施范围。方案中的整体目录示意与进一步兼容移除属于渐进方向，不是已完成的全仓库重写。

## 验证结果

- Java：24 项测试，0 失败、0 错误、0 跳过；覆盖缓存提交/回滚、CSV 部分拒绝、预测历史与策略、快照失败原子回滚、汇总一致性、冻结报告和原生模型推理样例。
- Playwright：30 项通过、2 项跳过、0 失败；两项跳过仅为桌面环境的移动菜单测试。根路径 12 个页面，以及独立 `/foodwise/` 实例的登录、所有子页面、资源、API、导出、权限、CSV、预测、优惠与重复核销实际运行；前缀测试没有跳过。
- Python：收尾运行 verify_current.py，26 项 unittest 通过，特征字段顺序检查通过。字段顺序不等于在线特征值正确，Java 推理样例是另一项独立测试。
- 最终 Gradle 测试构建、bootJar 成功。JAR 与 static/build 全部文件、foodwise.css、冻结实验报告的字节哈希一致；具体指纹见 build-fingerprint.json。
- 浏览器覆盖 1440、390、320 宽度、200% 文本放大、错误/会话/权限状态、键盘与控制台资源检查。截图见 ../../screenshots/optimization-implementation-20261013/。
- 收尾本地 http://127.0.0.1:8089/app/dashboard 返回 200。浏览器及构建日志保存在本目录，Java XML 位于 java-test-results/。

公开实验冻结 runId 为 public_sales_20261012T090638369705Z，测试集 1380 行；基线 MAE 0.22970244366896791，LightGBM MAE 0.30838332138091995。LightGBM 在该划分上更差。标签是可能为负的连续缩放量，不能解释为现场饭菜份数、人民币、实际减损量。独立重跑保留新的 runId，未覆盖冻结报告。

## 复现与使用

先安装 Java 21 与 Node/npm，frontend 内运行 npm ci，然后从代码目录运行：

```powershell
.\gradlew.bat test bootJar
modeling\.venv\Scripts\python.exe modeling\scripts\verify_current.py
cd frontend
npm run typecheck
npm run test:e2e -- --workers=1
```

完整前缀与写操作测试必须配置 FOODWISE_PREFIX_TEST_URL 和 FOODWISE_TEST_PASSWORD，指向独立临时 H2、启用真实安全配置并配置 foodwise-admin、foodwise-analyst 测试账号的实例。不要指向生产库。未设置这两个环境变量时，相关测试会跳过，不能据此称完整验收通过。实验重跑另使用 verify_current.py --experiment；历史管道不作为当前入口。

## 证据与限制

build-fingerprint.json、java-build-tests.log、package-build.log、browser-tests.log、python-verification.log 为本次保存的验收证据。docs/archive/20261013/manifest.json 提供原路径、归档路径与哈希，README 说明恢复边界。根目录仍仅有项目代码、计划书、PPT、数据来源、软著资料。

未执行服务器部署或版本比对、外部数据库回归、负载测试、真实食堂现场试验、真实触屏/屏幕阅读器验证；没有完成最新外部 Web Interface Guidelines 的全面复核，也不宣称 WCAG 认证。保留构建依赖与建模虚拟环境供运行复现，未把它们当成冗余源码删除。
