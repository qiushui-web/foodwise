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
import java.util.Collections;
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

    public PredictionResult predict(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        return predict(dishId, weather, examWeek, campusEvent, "system", null, "system");
    }

    private PredictionResult predict(long dishId, String weather, boolean examWeek, boolean campusEvent,
                                     String traceId, String idempotencyKey, String operatorName) {
        DishDetail dish = repository.dishDto(dishId);
        List<Integer> sales = repository.recentSales(dishId);
        if (sales.isEmpty()) {
            throw new IllegalArgumentException("该菜品暂无历史销量，无法生成预测");
        }

        double weighted = weightedAverage(sales);

        // 从动态天气因子缓存获取系数，优先使用外部更新的因子，其次查询品类系数表，最后降级默认值
        double weatherFactor = getDynamicWeatherFactor(dish, weather);

        double calendarFactor = examWeek ? 0.94 : 1.00;
        double eventFactor = campusEvent ? 1.08 : 1.00;
        double trendFactor = dishTrendFactors.getOrDefault(dishId, trendFactor(sales));
        double predicted = weighted * weatherFactor * calendarFactor * eventFactor * trendFactor;

        int mid = Math.max(1, (int) Math.round(predicted));
        int low = Math.max(1, (int) Math.floor(mid * 0.92));
        int high = Math.max(mid + 1, (int) Math.ceil(mid * 1.08));
        int firstBatch = Math.max(1, (int) Math.round(low * 0.82));
        int replenish = Math.max(0, mid - firstBatch);
        BigDecimal confidence = BigDecimal.valueOf(Math.max(72, 91 - variability(sales)))
                .setScale(1, RoundingMode.HALF_UP);

        List<PredictionResult.Factor> factors = new ArrayList<>();
        factors.add(new PredictionResult.Factor("历史基线", "最近7日加权销量 " + Math.round(weighted) + " 份",
                BigDecimal.valueOf(weighted).setScale(1, RoundingMode.HALF_UP), "baseline"));
        factors.add(new PredictionResult.Factor("天气影响", weather + "，需求系数 " + weatherFactor,
                BigDecimal.valueOf((weatherFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "weather"));
        factors.add(new PredictionResult.Factor("校历影响", examWeek ? "考试周，需求略有下降" : "正常教学周",
                BigDecimal.valueOf((calendarFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "calendar"));
        factors.add(new PredictionResult.Factor("近期趋势", trendFactor >= 1 ? "近期销量上升" : "近期销量下降",
                BigDecimal.valueOf((trendFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "trend"));

        long predictionId = repository.savePrediction(dishId, LocalDate.now().plusDays(1), low, mid, high,
                firstBatch, replenish, confidence, BigDecimal.valueOf(weatherFactor),
                BigDecimal.valueOf(calendarFactor), BigDecimal.valueOf(trendFactor), traceId,
                idempotencyKey, operatorName);

        IntelligentAdvice advice = intelligentDecisionService.predictionAdvice(
                dish.name(), low, mid, high, firstBatch, replenish, 12, 18,
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
                12,
                18,
                confidence,
                high - mid > 10 ? "中" : "低",
                weatherFactor < 0.9 ? "中" : "低",
                factors,
                advice
        );
        repository.savePredictionSnapshot(predictionId, modelVersion(),
                new PredictionContext(dishId, weather, examWeek, campusEvent, traceId, idempotencyKey, operatorName), result);
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
    public PredictionEngineResult predict(PredictionContext context) {
        return new PredictionEngineResult(key(), modelVersion(),
                predict(context.dishId(), context.weather(), context.examWeek(), context.campusEvent(),
                        context.traceId(), context.idempotencyKey(), context.operatorName()),
                java.time.Instant.now());
    }

    /**
     * 获取动态天气因子：优先使用外部更新的因子，其次从品类系数表查询，最后降级默认值
     */
    private double getDynamicWeatherFactor(DishDetail dish, String weather) {
        // 先检查是否有外部动态更新的因子
        long dishId = dish.id();
        Map<String, Double> dynamicFactors = dishDynamicFactors.get(dishId);
        if (dynamicFactors != null && dynamicFactors.containsKey("weatherFactor")) {
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

    private double weightedAverage(List<Integer> newestFirst) {
        double total = 0;
        double weights = 0;
        for (int index = 0; index < newestFirst.size(); index++) {
            double weight = newestFirst.size() - index;
            total += newestFirst.get(index) * weight;
            weights += weight;
        }
        return total / weights;
    }

    private double trendFactor(List<Integer> newestFirst) {
        if (newestFirst.size() < 4) return 1.0;
        List<Integer> chronological = new ArrayList<>(newestFirst);
        Collections.reverse(chronological);
        double early = chronological.subList(0, chronological.size() / 2).stream()
                .mapToInt(Integer::intValue).average().orElse(1);
        double recent = chronological.subList(chronological.size() / 2, chronological.size()).stream()
                .mapToInt(Integer::intValue).average().orElse(early);
        return Math.max(0.92, Math.min(1.08, recent / early));
    }

    private double variability(List<Integer> sales) {
        double mean = sales.stream().mapToInt(Integer::intValue).average().orElse(0);
        if (mean == 0) return 19;
        double variance = sales.stream().mapToDouble(value -> Math.pow(value - mean, 2)).average().orElse(0);
        return Math.min(19, Math.sqrt(variance) / mean * 100);
    }
}

