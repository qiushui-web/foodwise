package org.foodwise.service;

import org.foodwise.repository.FoodwiseRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.cache.annotation.Cacheable;

import java.time.DayOfWeek;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class AnalyticsService {

    private static final List<String> WEEKDAYS = List.of("周1", "周2", "周3", "周4", "周5", "周6", "周日");

    private final FoodwiseRepository repository;
    private final String dataNature;
    private final String sourceLabel;
    private final boolean demoEnabled;
    private final PublicExperimentReportService experiments;

    public AnalyticsService(
            FoodwiseRepository repository,
            PublicExperimentReportService experiments,
            @Value("${foodwise.data.nature:高校餐饮经营测算资料}") String dataNature,
            @Value("${foodwise.data.source-label:高校餐饮经营测算资料}") String sourceLabel,
            @Value("${foodwise.data.demo-enabled:false}") boolean demoEnabled
    ) {
        this.repository = repository;
        this.experiments = experiments;
        this.dataNature = dataNature;
        this.sourceLabel = sourceLabel;
        this.demoEnabled = demoEnabled;
    }

    @Cacheable(value = "metadata", key = "#root.methodName")
    public Map<String, Object> metadata() {
        Map<String, Object> result = new LinkedHashMap<>(repository.dataMetadataSummary());
        result.put("nature", dataNature);
        result.put("source_label", sourceLabel);
        result.put("sources", repository.dataSources());
        result.put("statement", demoEnabled
                ? "演示经营测算资料；不代表真实档口试点成果"
                : "当前数据库台账；来源资料仅供核对，实际经营记录需逐笔验证");
        long records = longValue(result.get("records"));
        long violations = longValue(result.get("conservation_violations")) + longValue(result.get("discount_violations"));
        result.put("validation_rate", records == 0 ? 0 : round((records - violations) * 100.0 / records, 1));
        return result;
    }

    public Map<String, Object> backtest() {
        return experiments.report();
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

    /** 历史派生场景模型特征重要性（gain），不得作为公开销量模型的归因 */
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

    @Cacheable(value = "analytics", key = "#root.methodName")
    public Map<String, Object> financial() {
        List<Map<String, Object>> phases = repository.financialByPhase();
        Map<String, Object> baseline = phases.stream().filter(row -> "基线期".equals(String.valueOf(row.get("phase")))).findFirst().orElse(Map.of());
        Map<String, Object> intervention = phases.stream().filter(row -> "干预期".equals(String.valueOf(row.get("phase")))).findFirst().orElse(Map.of());
        Map<String, Object> change = new LinkedHashMap<>();
        change.put("revenue", round(doubleValue(intervention.get("revenue")) - doubleValue(baseline.get("revenue")), 2));
        change.put("leftover_cost", round(doubleValue(intervention.get("leftover_cost")) - doubleValue(baseline.get("leftover_cost")), 2));
        change.put("contribution_profit", round(doubleValue(intervention.get("contribution_profit")) - doubleValue(baseline.get("contribution_profit")), 2));
        change.put("avoided_leftover_cost", round(doubleValue(baseline.get("leftover_cost")) - doubleValue(intervention.get("leftover_cost")), 2));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("data_nature", dataNature);
        result.put("cost_method", "食材成本=备餐量*菜品单位成本");
        result.put("phases", phases);
        result.put("change", change);
        return result;
    }

    @Cacheable(value = "analytics", key = "#root.methodName")
    public Map<String, Object> dashboardAnalytics() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("summary", repository.dashboardSummary());
        result.put("metadata", metadata());
        result.put("backtest", backtest());
        result.put("financial", financial());
        result.put("report_summary", repository.reportSummary());
        result.put("forecast_series", repository.dailyForecastSeries());
        result.put("latest_dishes", repository.latestDishOperations());
        result.put("stall_efficiency", repository.stallEfficiency());
        result.put("demand_factors", demandFactors());
        result.put("weekday_demand", weekdayDemand());
        Map<String, Long> phaseCounts = new LinkedHashMap<>();
        for (Map<String, Object> row : repository.operationRows()) {
            String phase = String.valueOf(row.get("phase"));
            phaseCounts.merge(phase, 1L, Long::sum);
        }
        result.put("phase_counts", phaseCounts);
        result.put("trial_effectiveness", repository.trialEffectiveness());
        return result;
    }

    @Cacheable(value = "analytics", key = "#root.methodName")
    public Map<String, Object> trialEffectiveness() {
        Map<String, Object> result = new LinkedHashMap<>(repository.trialEffectiveness());
        result.put("data_nature", dataNature);
        result.put("source_label", sourceLabel);
        return result;
    }

    private Map<String, Object> demandFactors() {
        List<Map<String, Object>> rows = repository.operationRows();
        double overall = rows.stream().mapToDouble(row -> doubleValue(row.get("sold_qty"))).average().orElse(0);
        double firstHalf = rows.stream().filter(row -> dateValue(row.get("business_date")).isBefore(LocalDate.of(2026, 7, 14))).mapToDouble(row -> doubleValue(row.get("sold_qty"))).average().orElse(overall);
        double secondHalf = rows.stream().filter(row -> !dateValue(row.get("business_date")).isBefore(LocalDate.of(2026, 7, 14))).mapToDouble(row -> doubleValue(row.get("sold_qty"))).average().orElse(overall);
        double exam = rows.stream().filter(row -> String.valueOf(row.get("event_tag")).contains("考试")).mapToDouble(row -> doubleValue(row.get("sold_qty"))).average().orElse(overall);
        double normal = rows.stream().filter(row -> !String.valueOf(row.get("event_tag")).contains("考试")).mapToDouble(row -> doubleValue(row.get("sold_qty"))).average().orElse(overall);
        double rain = rows.stream().filter(row -> String.valueOf(row.get("weather")).contains("雨")).mapToDouble(row -> doubleValue(row.get("sold_qty"))).average().orElse(overall);
        double clear = rows.stream().filter(row -> "晴".equals(String.valueOf(row.get("weather")))).mapToDouble(row -> doubleValue(row.get("sold_qty"))).average().orElse(overall);
        return Map.of(
                "labels", List.of("近期趋势", "考试周", "降雨天气"),
                "values", List.of(percentChange(secondHalf, firstHalf), percentChange(exam, normal), percentChange(rain, clear))
        );
    }

    private Map<String, Object> weekdayDemand() {
        List<Map<String, Object>> rows = repository.operationRows();
        List<String> dishes = rows.stream().map(row -> String.valueOf(row.get("dish_name"))).distinct().toList();
        Map<String, List<Double>> grouped = new LinkedHashMap<>();
        for (Map<String, Object> row : rows) {
            int dayIndex = dateValue(row.get("business_date")).getDayOfWeek().getValue() - DayOfWeek.MONDAY.getValue();
            String key = dayIndex + "|" + row.get("dish_name");
            grouped.computeIfAbsent(key, ignored -> new ArrayList<>()).add(doubleValue(row.get("sold_qty")));
        }
        List<List<Object>> values = new ArrayList<>();
        double maximum = 0;
        for (int dayIndex = 0; dayIndex < WEEKDAYS.size(); dayIndex++) {
            for (int dishIndex = 0; dishIndex < dishes.size(); dishIndex++) {
                List<Double> cell = grouped.getOrDefault(dayIndex + "|" + dishes.get(dishIndex), List.of());
                double average = cell.stream().mapToDouble(Double::doubleValue).average().orElse(0);
                maximum = Math.max(maximum, average);
                values.add(List.of(dayIndex, dishIndex, round(average, 1)));
            }
        }
        return Map.of("days", WEEKDAYS, "dishes", dishes, "values", values, "max", Math.ceil(maximum));
    }

    private double percentChange(double value, double reference) {
        return reference == 0 ? 0 : round((value / reference - 1) * 100, 1);
    }

    private LocalDate dateValue(Object value) {
        if (value instanceof LocalDate date) return date;
        if (value instanceof java.sql.Date date) return date.toLocalDate();
        return LocalDate.parse(String.valueOf(value));
    }

    private long longValue(Object value) {
        return value instanceof Number number ? number.longValue() : value == null ? 0 : Long.parseLong(String.valueOf(value));
    }

    private double doubleValue(Object value) {
        return value instanceof Number number ? number.doubleValue() : value == null ? 0 : Double.parseDouble(String.valueOf(value));
    }

    private double round(double value, int scale) {
        double factor = Math.pow(10, scale);
        return Math.round(value * factor) / factor;
    }
}

