# -*- coding: utf-8 -*-
"""把真实 LGBM 模型接入 Java 应用 + 前端真实数据改造（幂等补丁）"""
import shutil
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
STAGE = Path(r"c:\Users\lenovo\Desktop\商业精英挑战赛\deploy\staging")

def patch(path, old, new, label):
    text = path.read_text(encoding="utf-8")
    if new.strip() in text:
        print(f"[SKIP] {label} 已打过补丁")
        return
    if old not in text:
        raise SystemExit(f"[FAIL] {label}: 找不到锚点:\n{old[:120]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[OK] {label}")

# ---------- 0. 新服务文件落位 ----------
svc = SRC / "src/main/java/org/foodwise/service"
for f in ["LgbmCampusModel.java", "DualPredictionService.java"]:
    shutil.copy2(STAGE / f, svc / f)
    print(f"[COPY] {f}")

# ---------- 1. build.gradle 加依赖 ----------
gradle = SRC / "build.gradle"
patch(gradle,
    "    implementation 'org.springframework.boot:spring-boot-starter-security'\n",
    "    implementation 'org.springframework.boot:spring-boot-starter-security'\n"
    "    implementation 'com.microsoft.ml.lightgbm:lightgbmlib:3.3.510'\n",
    "build.gradle lightgbmlib依赖")

# ---------- 2. ApiController：import + 字段 + 构造器 + 3个接口 ----------
api = SRC / "src/main/java/org/foodwise/api/v1/ApiV1Controller.java"
patch(api,
    "import org.foodwise.service.EnhancedPredictionService;\n",
    "import org.foodwise.service.EnhancedPredictionService;\n"
    "import org.foodwise.service.DualPredictionService;\n",
    "ApiController import")
patch(api,
    "    private final EnhancedPredictionService enhancedPredictionService;\n",
    "    private final EnhancedPredictionService enhancedPredictionService;\n"
    "    private final DualPredictionService dualPredictionService;\n",
    "ApiController 字段")
patch(api,
    "                         EnhancedPredictionService enhancedPredictionService) {\n",
    "                         EnhancedPredictionService enhancedPredictionService,\n"
    "                         DualPredictionService dualPredictionService) {\n",
    "ApiController 构造器参数")
patch(api,
    "        this.enhancedPredictionService = enhancedPredictionService;\n    }\n",
    "        this.enhancedPredictionService = enhancedPredictionService;\n"
    "        this.dualPredictionService = dualPredictionService;\n    }\n",
    "ApiController 构造器赋值")
patch(api,
    """    @PostMapping("/predictions/cold-start")""",
    """    @PostMapping("/predictions/dual")
    public Map<String, Object> predictDual(@RequestBody @Validated PredictionRequest request) {
        return dualPredictionService.predictDual(
                request.dishId(), request.weather(), request.examWeek(), request.campusEvent());
    }

    @GetMapping("/model/campus-series")
    public Map<String, Object> campusSeries() {
        return analyticsService.campusSeries();
    }

    @GetMapping("/model/feature-importance")
    public java.util.List<Map<String, Object>> featureImportance() {
        return analyticsService.featureImportance();
    }

    @PostMapping("/predictions/cold-start")""",
    "ApiController 3个新接口")

# ---------- 3. AnalyticsService：真实回测序列 + 特征重要性 ----------
ana = SRC / "src/main/java/org/foodwise/service/AnalyticsService.java"
NEW_METHODS = '''    /** 高校真实回测序列：campus_backtest_predictions.csv（LGBM真实模型滚动回测逐日预测），每4行聚合成日级点 */
    public Map<String, Object> campusSeries() {
        List<String> labels = new ArrayList<>();
        List<Double> actual = new ArrayList<>();
        List<Double> lgbm = new ArrayList<>();
        List<Double> rule = new ArrayList<>();
        List<double[]> bin = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                new ClassPathResource("modeling/campus_backtest_predictions.csv").getInputStream(),
                StandardCharsets.UTF_8))) {
            reader.readLine();
            String line;
            while ((line = reader.readLine()) != null) {
                String[] p = line.split(",");
                if (p.length < 5) continue;
                bin.add(new double[]{Double.parseDouble(p[2]), Double.parseDouble(p[3]), Double.parseDouble(p[4])});
                if (bin.size() == 4) {
                    labels.add("回测" + (labels.size() + 1));
                    actual.add(round(bin.stream().mapToDouble(x -> x[0]).average().orElse(0), 1));
                    lgbm.add(round(bin.stream().mapToDouble(x -> x[1]).average().orElse(0), 1));
                    rule.add(round(bin.stream().mapToDouble(x -> x[2]).average().orElse(0), 1));
                    bin.clear();
                }
            }
        } catch (Exception ignored) { }
        int take = 30;
        if (labels.size() > take) {
            int from = labels.size() - take;
            labels = labels.subList(from, labels.size());
            actual = actual.subList(from, actual.size());
            lgbm = lgbm.subList(from, lgbm.size());
            rule = rule.subList(from, rule.size());
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("labels", labels);
        result.put("actual", actual);
        result.put("lgbm", lgbm);
        result.put("rule", rule);
        result.put("source", "campus_backtest_predictions.csv · LGBM真实模型滚动回测");
        return result;
    }

    private static final Map<String, String> FEATURE_NAME_ZH = Map.ofEntries(
            Map.entry("day_of_week", "星期"), Map.entry("is_weekend", "周末"),
            Map.entry("is_exam_week", "考试周"), Map.entry("has_campus_event", "校园活动"),
            Map.entry("weather_code", "天气类型"), Map.entry("temp_max_c", "最高气温"),
            Map.entry("category_id", "品类"), Map.entry("price", "售价"),
            Map.entry("unit_cost", "单位成本"), Map.entry("discount_rate", "折扣率"),
            Map.entry("promotion_flag", "促销标记"), Map.entry("lag_1_sold", "前1日销量"),
            Map.entry("lag_2_sold", "前2日销量"), Map.entry("lag_3_sold", "前3日销量"),
            Map.entry("lag_7_sold", "前7日销量"), Map.entry("rolling_mean_3", "3日滚动均值"),
            Map.entry("rolling_mean_7", "7日滚动均值"), Map.entry("rolling_std_7", "7日波动标准差"),
            Map.entry("same_dow_last_4w_mean", "同星期4周均值"), Map.entry("is_school_holiday", "寒暑假"),
            Map.entry("is_state_holiday", "法定节假日"), Map.entry("special_day", "特殊日"),
            Map.entry("comp_price_ratio", "竞品价格比"), Map.entry("recent_trend_3d", "近3日趋势"));

    /** 真实 LGBM 模型特征重要性（gain）Top10 */
    public List<Map<String, Object>> featureImportance() {
        List<Map<String, Object>> result = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                new ClassPathResource("modeling/feature_importance_campus.csv").getInputStream(),
                StandardCharsets.UTF_8))) {
            reader.readLine();
            String line;
            while ((line = reader.readLine()) != null) {
                String[] p = line.split(",");
                if (p.length < 2) continue;
                String zh = FEATURE_NAME_ZH.getOrDefault(p[0].trim(), p[0].trim());
                result.add(Map.of("name", zh, "gain", round(Double.parseDouble(p[1].trim()), 1)));
                if (result.size() >= 10) break;
            }
        } catch (Exception ignored) { }
        return result;
    }

    public Map<String, Object> financial() {'''
patch(ana, "    public Map<String, Object> financial() {", NEW_METHODS, "AnalyticsService 两个新方法")

# ---------- 4. app.js ----------
appjs = SRC / "src/main/resources/static/build/app.js"
patch(appjs, "fetch('/api/predictions/run'", "fetch('/api/predictions/dual'", "app.js 预测接口切换dual")

# 4.2 renderPrediction 加双引擎对比条
old_head = '<div class="result-head"><div><span class="kicker">需求区间与经营动作</span>'
dual_block = ('<div class="result-head"><div><span class="kicker">需求区间与经营动作</span>'
    '${data.rulePrediction != null ? `<div style="display:flex;gap:8px;align-items:stretch;margin:10px 0;flex-wrap:wrap">'
    + '<div style="flex:1;min-width:90px;background:#f2f7f6;border:1px solid #dceae7;border-radius:10px;padding:8px 10px;text-align:center"><div style="font-size:10px;color:#7a8c85">规则引擎</div><strong style="font-size:17px;color:#536b62">'+ '${data.rulePrediction}</strong><small style="display:block;color:#9ab0a8;font-size:9px">四因子加权</small></div>'
    + '<div style="align-self:center;color:#9ab0a8;font-weight:700">＋</div>'
    + '<div style="flex:1;min-width:90px;background:linear-gradient(160deg,#eaf4ff,#eef9f4);border:1.5px solid #6fb7d6;border-radius:10px;padding:8px 10px;text-align:center;box-shadow:0 4px 14px rgba(89,150,200,.18)"><div style="font-size:10px;color:#2f7fa6;font-weight:700">训练模型 LGBM</div><strong style="font-size:17px;color:#1f6f96">${data.lgbmPrediction ?? \'—\'}</strong><small style="display:block;color:#5f93ab;font-size:9px">${data.modelReady ? \'2600行真实数据 · MAPE \'+data.modelMape+\'%\' : \'模型未就绪\'}</small></div>'
    + '<div style="align-self:center;color:#9ab0a8;font-weight:700">＝</div>'
    + '<div style="flex:1;min-width:90px;background:#123f36;border-radius:10px;padding:8px 10px;text-align:center"><div style="font-size:10px;color:#9fd4c4">最终建议</div><strong style="font-size:17px;color:#fff">${data.predictedMid}份</strong><small style="display:block;color:#7fb8a8;font-size:9px">60%模型+40%规则</small></div>'
    + '</div>` : \'\'}<span class="kicker" style="display:none">需求区间与经营动作</span>')
# 上面的写法会重复kicker，改为直接在原kicker后插块：
dual_block = ('<div class="result-head"><div><span class="kicker">需求区间与经营动作</span>'
    '${data.rulePrediction != null ? `<div style="display:flex;gap:8px;align-items:center;margin:10px 0;flex-wrap:wrap">'
    '<div style="flex:1;min-width:88px;background:#f2f7f6;border:1px solid #dceae7;border-radius:10px;padding:8px 6px;text-align:center"><div style="font-size:10px;color:#7a8c85">规则引擎</div><strong style="font-size:17px;color:#536b62">${data.rulePrediction}份</strong><div style="color:#9ab0a8;font-size:9px">四因子加权</div></div>'
    '<div style="color:#9ab0a8;font-weight:700">＋</div>'
    '<div style="flex:1;min-width:88px;background:linear-gradient(160deg,#eaf4ff,#eef9f4);border:1.5px solid #6fb7d6;border-radius:10px;padding:8px 6px;text-align:center;box-shadow:0 4px 14px rgba(89,150,200,.18)"><div style="font-size:10px;color:#2f7fa6;font-weight:700">训练模型 LGBM</div><strong style="font-size:17px;color:#1f6f96">${data.lgbmPrediction ?? \'—\'}份</strong><div style="color:#5f93ab;font-size:9px">${data.modelReady ? \'2600行真实训练 · MAPE \'+data.modelMape+\'%\' : \'模型运行时未就绪\'}</div></div>'
    '<div style="color:#9ab0a8;font-weight:700">＝</div>'
    '<div style="flex:1;min-width:88px;background:#123f36;border-radius:10px;padding:8px 6px;text-align:center"><div style="font-size:10px;color:#9fd4c4">最终建议</div><strong style="font-size:17px;color:#fff">${data.predictedMid}份</strong><div style="color:#7fb8a8;font-size:9px">60%模型+40%规则</div></div>'
    '</div>` : \'\'}')
patch(appjs, old_head, dual_block, "app.js 双引擎对比条")

# 4.3 模型对比图：硬编码 -> 真实接口
old_chart = """function initModelComparisonChart(add, colors) {
    var days = ['周一','周二','周三','周四','周五','周六','周日'];
    var actual = [320, 385, 410, 375, 390, 280, 260];
    var rulePred = [300, 360, 390, 350, 370, 260, 240];
    var enhancedPred = [315, 378, 405, 372, 385, 275, 258];
    var chart = add('modelComparisonChart', {"""
new_chart = """function initModelComparisonChart(add, colors) {
    var chart = add('modelComparisonChart', {"""
patch(appjs, old_chart, new_chart, "app.js 删除硬编码数据")

old_series_end = """    });
    return chart;
}"""
# 在对比图函数末尾（return chart 前）加 fetch；该锚点在文件中多处出现，需用更长上下文
old_chart_tail = """            { name: '增强模型预测', type: 'line', smooth: true, symbol: 'none', data: enhancedPred, lineStyle: { color: colors.cyan, width: 2, type: 'dotted' } }
        ]
    });
    return chart;
}"""
new_chart_tail = """            { name: 'LGBM训练模型预测', type: 'line', smooth: true, symbol: 'none', data: [], lineStyle: { color: colors.cyan, width: 2.5 } }
        ]
    });
    if (chart) {
        fetch('/api/model/campus-series').then(r => r.json()).then(d => {
            chart.setOption({
                xAxis: { type: 'category', data: d.labels, axisTick: { show: false }, axisLine: { lineStyle: { color: colors.grid } }, axisLabel: { color: '#80918a', fontSize: 9 } },
                series: [{ data: d.actual }, { data: d.rule }, { data: d.lgbm }]
            });
        }).catch(() => { });
    }
    return chart;
}

function initFeatureImportanceChart(add, colors) {
    var chart = add('featureImportanceChart', {
        animationDuration: 1100,
        tooltip: darkTooltip(),
        grid: { left: 110, right: 46, top: 18, bottom: 20 },
        xAxis: { type: 'value', axisLabel: { color: '#91a09a', fontSize: 9 }, splitLine: { lineStyle: { color: colors.grid, type: 'dashed' } } },
        yAxis: { type: 'category', inverse: true, data: [], axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: '#62756d', fontSize: 10 } },
        series: [{ name: 'gain', type: 'bar', barWidth: 12, data: [], label: { show: true, position: 'right', color: '#536b62', fontSize: 9 }, itemStyle: { color: colors.cyan, borderRadius: 7 } }]
    });
    if (chart) {
        fetch('/api/model/feature-importance').then(r => r.json()).then(d => {
            chart.setOption({
                yAxis: { data: d.map(x => x.name) },
                series: [{ data: d.map(x => Number(x.gain)) }]
            });
        }).catch(() => { });
    }
    return chart;
}"""
patch(appjs, old_chart_tail, new_chart_tail, "app.js 对比图真实序列+特征重要性图")

# 4.4 initDemandInsights 调用特征重要性图
patch(appjs,
    "    initModelComparisonChart(add, colors);\n}",
    "    initModelComparisonChart(add, colors);\n    initFeatureImportanceChart(add, colors);\n}",
    "app.js 注册特征重要性图")

# ---------- 5. insights-demand.html 加特征重要性面板 ----------
html = SRC / "src/main/resources/templates/insights-demand.html"
patch(html,
    """                <div id="modelComparisonChart" class="chart model-chart-wrap"></div>
            </article>
            </section>""",
    """                <div id="modelComparisonChart" class="chart model-chart-wrap"></div>
            </article>
            <article class="panel span-12">
                <div class="panel-head"><div><span class="kicker">训练模型可解释性</span><h3>LightGBM 特征重要性（真实模型 gain）</h3></div><span class="model-tag">24特征 · 2600行真实高校数据训练</span></div>
                <div id="featureImportanceChart" class="chart model-chart-wrap"></div>
            </article>
            </section>""",
    "insights-demand.html 特征重要性面板")

print("\n===== 全部补丁完成 =====")

