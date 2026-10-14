package org.foodwise.service;

import org.foodwise.model.PredictionResult;
import org.foodwise.model.IntelligentAdvice;
import org.foodwise.model.dto.DishDetail;
import org.foodwise.prediction.PredictionContext;
import org.foodwise.prediction.PredictionEngine;
import org.foodwise.prediction.PredictionEngineResult;
import org.foodwise.repository.FoodwiseRepository;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class PredictionService implements PredictionEngine {

    private final FoodwiseRepository repository;
    private final IntelligentDecisionService intelligentDecisionService;

    // 品类×天气系数缓存：key = "categoryId:weatherCode" -> coef
    private final Map<String, Double> categoryWeatherCoef = new ConcurrentHashMap<>();

    // 外部动态更新的菜品因子缓存
    private final Map<Long, Map<String, Double>> dishDynamicFactors = new ConcurrentHashMap<>();

    // 外部动态更新的趋势因子缓存
    private final Map<Long, Double> dishTrendFactors = new ConcurrentHashMap<>();

    // 品类名称到ID的映射
    private static final Map<String, Integer> CATEGORY_NAME_TO_ID = Map.of(
            "套餐主食", 0,
            "轻食沙拉", 1,
            "粉面", 2,
            "烘焙点心", 3
    );

    public PredictionService(FoodwiseRepository repository, IntelligentDecisionService intelligentDecisionService) {
        this.repository = repository;
        this.intelligentDecisionService = intelligentDecisionService;
    }

    @PostConstruct
    public void init() {
        loadCategoryCoefTable();
    }

    /**
     * 加载 category_coef_table.csv 到内存缓存
     */
    private void loadCategoryCoefTable() {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        Objects.requireNonNull(getClass().getClassLoader().getResourceAsStream("modeling/category_coef_table.csv")),
                        StandardCharsets.UTF_8))) {
            String line;
            boolean firstLine = true;
            while ((line = reader.readLine()) != null) {
                if (firstLine) {
                    firstLine = false;
                    continue;
                }
                String[] parts = line.split(",");
                if (parts.length < 5) continue;
                String categoryId = parts[0].trim();
                String weatherCode = parts[2].trim();
                // 只加载有具体天气编码的行（跳过汇总行）
                if (weatherCode.isEmpty() || "null".equals(weatherCode)) continue;
                String coefStr = parts[4].trim();
                if (coefStr.isEmpty()) continue;
                String key = categoryId + ":" + (int) Double.parseDouble(weatherCode);
                categoryWeatherCoef.put(key, Double.parseDouble(coefStr));
            }
        } catch (Exception e) {
            // 加载失败时降级使用默认天气因子
            System.err.println("品类天气系数表加载失败，将使用默认天气因子: " + e.getMessage());
        }
    }

    @org.springframework.transaction.annotation.Transactional
    public PredictionResult predict(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        return calculateAndSave(new PredictionContext(dishId, weather, examWeek, campusEvent));
    }

    private PredictionResult calculateAndSave(PredictionContext context) {
        long dishId = context.dishId(); String weather = context.weather();
        boolean examWeek = context.examWeek(); boolean campusEvent = context.campusEvent();
        String traceId = context.traceId(); String idempotencyKey = context.idempotencyKey();
        String operatorName = context.operatorName();
        DishDetail dish = repository.dishDto(dishId);
        var observations = repository.recentSalesObservations(dishId, context.historyCutoff(), context.mealPeriod());
        var features = org.foodwise.prediction.FeatureBuilder.build(observations);
        double weighted = features.weightedDemand();

        // 从动态天气因子缓存获取系数，优先使用外部更新的因子，其次查询品类系数表，最后降级默认值
        double weatherFactor = getDynamicWeatherFactor(dish, weather, context.historyCutoff().equals(LocalDate.now()));

        double calendarFactor = examWeek ? 0.94 : 1.00;
        double eventFactor = campusEvent ? 1.08 : 1.00;
        double trendFactor = features.trend();
        double predicted = weighted * weatherFactor * calendarFactor * eventFactor * trendFactor;

        var quantities = org.foodwise.prediction.PredictionPolicy.quantities(predicted);
        int mid = quantities.mid(), low = quantities.low(), high = quantities.high();
        int firstBatch = quantities.firstBatch(), replenish = quantities.replenish();
        BigDecimal confidence = BigDecimal.valueOf(Math.max(72, 91 - features.variability()))
                .setScale(1, RoundingMode.HALF_UP);

        List<PredictionResult.Factor> factors = new ArrayList<>();
        factors.add(new PredictionResult.Factor("历史基线", "截至" + context.historyCutoff() + "，最近" + features.observations() + "个有记录营业日的" + context.mealPeriod() + "加权销量 " + Math.round(weighted) + " 份",
                BigDecimal.valueOf(weighted).setScale(1, RoundingMode.HALF_UP), "baseline"));
        factors.add(new PredictionResult.Factor("天气影响", weather + "，需求系数 " + weatherFactor,
                BigDecimal.valueOf((weatherFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "weather"));
        factors.add(new PredictionResult.Factor("校历影响", examWeek ? "考试周，需求略有下降" : "正常教学周",
                BigDecimal.valueOf((calendarFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "calendar"));
        factors.add(new PredictionResult.Factor("近期趋势", trendFactor >= 1 ? "近期销量上升" : "近期销量下降",
                BigDecimal.valueOf((trendFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "trend"));

        long predictionId = repository.savePrediction(dishId, context.targetDate(), low, mid, high,
                firstBatch, replenish, confidence, BigDecimal.valueOf(weatherFactor),
                BigDecimal.valueOf(calendarFactor), BigDecimal.valueOf(trendFactor), traceId,
                idempotencyKey, operatorName);

        IntelligentAdvice advice = intelligentDecisionService.predictionAdvice(
                dish.name(), low, mid, high, firstBatch, replenish,
                org.foodwise.prediction.PredictionPolicy.STOP_HOUR, org.foodwise.prediction.PredictionPolicy.STOP_MINUTE,
                confidence, weather, examWeek, campusEvent, factors.stream().map(PredictionResult.Factor::detail).toList());

        PredictionResult result = new PredictionResult(
                predictionId,
                dishId,
                dish.name(),
                low,
                mid,
                high,
                firstBatch,
                replenish,
                org.foodwise.prediction.PredictionPolicy.STOP_HOUR,
                org.foodwise.prediction.PredictionPolicy.STOP_MINUTE,
                confidence,
                high - mid > 10 ? "中" : "低",
                weatherFactor < 0.9 ? "中" : "低",
                factors,
                advice
        );
        repository.savePredictionSnapshot(predictionId, modelVersion(),
                context, result);
        return result;
    }

    @Override
    public String key() {
        return "rule";
    }

    @Override
    public String modelVersion() {
        return "rule-v1";
    }

    @Override
    @org.springframework.transaction.annotation.Transactional
    public PredictionEngineResult predict(PredictionContext context) {
        return new PredictionEngineResult(key(), modelVersion(),
                calculateAndSave(context),
                java.time.Instant.now());
    }

    /**
     * 获取动态天气因子：优先使用外部更新的因子，其次从品类系数表查询，最后降级默认值
     */
    private double getDynamicWeatherFactor(DishDetail dish, String weather, boolean useCommittedFeedback) {
        // 先检查是否有外部动态更新的因子
        long dishId = dish.id();
        Map<String, Double> dynamicFactors = dishDynamicFactors.get(dishId);
        if (useCommittedFeedback && dynamicFactors != null && dynamicFactors.containsKey("weatherFactor")) {
            return dynamicFactors.get("weatherFactor");
        }

        // 从品类系数表中查询
        String category = dish.category();
        Integer categoryId = CATEGORY_NAME_TO_ID.get(category);
        if (categoryId != null) {
            double wc = weatherCode(weather);
            String key = categoryId + ":" + (int) wc;
            Double coef = categoryWeatherCoef.get(key);
            if (coef != null) {
                return coef;
            }
        }

        // 降级使用默认值
        return switch (weather) {
            case "小雨" -> 0.92;
            case "大雨" -> 0.82;
            case "高温" -> 0.90;
            case "降温" -> 1.04;
            default -> 1.00;
        };
    }

    /**
     * 天气描述转数值编码（与Python管道保持一致）
     */
    public double weatherCode(String weather) {
        return switch (weather) {
            case "晴朗", "晴" -> 0.0;
            case "小雨" -> 1.0;
            case "大雨" -> 2.0;
            case "高温" -> 3.0;
            case "降温" -> 4.0;
            case "暴雨", "极端" -> 5.0;
            default -> 0.0;
        };
    }

    /**
     * 外部更新菜品动态因子（支持反馈闭环更新）
     */
    public void updateFactors(long dishId, Map<String, Double> factors) {
        dishDynamicFactors.put(dishId, new ConcurrentHashMap<>(factors));
    }

    /**
     * 外部更新趋势因子（支持反馈闭环更新）
     */
    public void updateTrendFactor(long dishId, double newTrend) {
        dishTrendFactors.put(dishId, Math.max(0.92, Math.min(1.08, newTrend)));
    }

}
