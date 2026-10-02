package org.foodwise.service;

import org.foodwise.model.PredictionResult;
import org.foodwise.model.IntelligentAdvice;
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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@Service
public class EnhancedPredictionService {

    private final PredictionService predictionService;
    private final FoodwiseRepository repository;

    // 特征权重表：featureName -> weight
    private final Map<String, Double> featureWeights = new LinkedHashMap<>();

    // 特征名称列表（保持顺序）
    private final List<String> featureNames = new ArrayList<>();

    // 品类系数表缓存：key = "categoryId:weatherCode" -> coef
    private final Map<String, Double> categoryCoefCache = new LinkedHashMap<>();

    // 品类名称到ID的映射
    private static final Map<String, Integer> CATEGORY_NAME_TO_ID = Map.of(
            "套餐主食", 0,
            "轻食沙拉", 1,
            "粉面", 2,
            "烘焙点心", 3
    );

    // 品类波动率
    private static final Map<Integer, Double> CATEGORY_VOLATILITY = Map.of(
            0, 1.417,
            1, 0.8411,
            2, 1.3093,
            3, 0.5748
    );

    public EnhancedPredictionService(PredictionService predictionService, FoodwiseRepository repository) {
        this.predictionService = predictionService;
        this.repository = repository;
    }

    @PostConstruct
    public void init() {
        loadFeatureWeights();
        loadCategoryCoef();
    }

    /**
     * 加载特征权重表 feature_weight_rule.csv
     */
    private void loadFeatureWeights() {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(
                        Objects.requireNonNull(getClass().getClassLoader().getResourceAsStream("modeling/feature_weight_rule.csv")),
                        StandardCharsets.UTF_8))) {
            String line;
            boolean firstLine = true;
            while ((line = reader.readLine()) != null) {
                if (firstLine) {
                    firstLine = false;
                    continue;
                }
                String[] parts = line.split(",");
                if (parts.length < 2) continue;
                String feature = parts[0].trim();
                String weight = parts[1].trim();
                if (feature.isEmpty() || weight.isEmpty()) continue;
                featureNames.add(feature);
                featureWeights.put(feature, Double.parseDouble(weight));
            }
        } catch (Exception e) {
            System.err.println("特征权重表加载失败: " + e.getMessage());
        }
    }

    /**
     * 加载品类系数表 category_coef_table.csv
     */
    private void loadCategoryCoef() {
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
                categoryCoefCache.put(key, Double.parseDouble(coefStr));
            }
        } catch (Exception e) {
            System.err.println("品类系数表加载失败: " + e.getMessage());
        }
    }

    /**
     * 增强预测：融合规则预测 + ML加权得分 + 品类系数
     */
    public PredictionResult predictEnhanced(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        // 1. 先获取规则预测结果
        PredictionResult ruleResult = predictionService.predict(dishId, weather, examWeek, campusEvent);

        // 2. 获取菜品数据和销量数据
        Map<String, Object> dish = repository.dish(dishId);
        List<Integer> sales = repository.recentSales(dishId);

        // 3. 计算ML加权得分（24维特征线性加权）
        List<Double> featureValues = extractFeatures(dish, sales, weather, examWeek, campusEvent);
        double mlScore = computeMlScore(featureValues);

        // 4. 查询品类系数
        double categoryCoef = lookupCategoryCoef(dish, weather);

        // 5. 融合规则预测与ML得分
        double ruleMid = ruleResult.predictedMid();
        double enhancedMid = 0.5 * ruleMid + 0.5 * mlScore * categoryCoef;
        int mid = Math.max(1, (int) Math.round(enhancedMid));
        int low = Math.max(1, (int) Math.floor(mid * 0.92));
        int high = Math.max(mid + 1, (int) Math.ceil(mid * 1.08));
        int firstBatch = Math.max(1, (int) Math.round(low * 0.82));
        int replenish = Math.max(0, mid - firstBatch);

        // 计算变异性（使用规则结果的置信度逻辑）
        double variability = sales.isEmpty() ? 19.0 : computeVariability(sales);
        BigDecimal confidence = BigDecimal.valueOf(Math.max(72, 91 - variability))
                .setScale(1, RoundingMode.HALF_UP);

        // 构建增强因子列表
        List<PredictionResult.Factor> factors = new ArrayList<>(ruleResult.factors());
        factors.add(new PredictionResult.Factor("ML增强", "ML加权得分 " + String.format("%.2f", mlScore)
                + "，品类系数 " + categoryCoef,
                BigDecimal.valueOf((mlScore * categoryCoef / ruleMid - 1) * 100).setScale(1, RoundingMode.HALF_UP),
                "ml_boost"));

        // 生成IntelligentAdvice（复用规则预测中的advice逻辑，但更新数值）
        String dishName = String.valueOf(dish.get("name"));
        String risk = high - mid > 10 ? "中" : "低";
        String weatherRisk = getWeatherFactor(dish, weather) < 0.9 ? "中" : "低";

        IntelligentAdvice advice = ruleResult.advice();

        return new PredictionResult(
                dishId,
                dishName,
                low,
                mid,
                high,
                firstBatch,
                replenish,
                12,
                18,
                confidence,
                risk,
                weatherRisk,
                factors,
                advice
        );
    }

    /**
     * 冷启动预测：新档口无历史数据时使用品类级参数进行预测
     */
    public PredictionResult predictColdStart(long categoryId, String weather, boolean examWeek, boolean campusEvent) {
        // 使用品类级默认销量基线
        double baseline = getCategoryBaseline((int) categoryId);

        // 查询品类系数作为天气因子
        String key = (int) categoryId + ":" + (int) weatherCode(weather);
        Double coef = categoryCoefCache.get(key);
        double weatherFactor = coef != null ? coef : defaultWeatherFactor(weather);

        double calendarFactor = examWeek ? 0.94 : 1.00;
        double eventFactor = campusEvent ? 1.08 : 1.00;
        double trendFactor = 1.0; // 冷启动无趋势

        double predicted = baseline * weatherFactor * calendarFactor * eventFactor;

        int mid = Math.max(1, (int) Math.round(predicted));
        int low = Math.max(1, (int) Math.floor(mid * 0.92));
        int high = Math.max(mid + 1, (int) Math.ceil(mid * 1.08));
        int firstBatch = Math.max(1, (int) Math.round(low * 0.82));
        int replenish = Math.max(0, mid - firstBatch);
        BigDecimal confidence = BigDecimal.valueOf(72.0).setScale(1, RoundingMode.HALF_UP);

        // 构建因子列表
        List<PredictionResult.Factor> factors = new ArrayList<>();
        factors.add(new PredictionResult.Factor("冷启动基线", "品类默认基线 " + Math.round(baseline) + " 份",
                BigDecimal.valueOf(baseline).setScale(1, RoundingMode.HALF_UP), "baseline"));
        factors.add(new PredictionResult.Factor("天气影响", weather + "，需求系数 " + weatherFactor,
                BigDecimal.valueOf((weatherFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "weather"));
        factors.add(new PredictionResult.Factor("校历影响", examWeek ? "考试周，需求略有下降" : "正常教学周",
                BigDecimal.valueOf((calendarFactor - 1) * 100).setScale(1, RoundingMode.HALF_UP), "calendar"));
        factors.add(new PredictionResult.Factor("冷启动提示", "该菜品暂无历史数据，基于品类均值估算",
                BigDecimal.ZERO, "cold_start"));

        // 冷启动模式下返回简化版IntelligentAdvice
        IntelligentAdvice advice = new IntelligentAdvice(
                0, "冷启动备餐建议",
                "该菜品暂无历史销量数据，基于" + getCategoryName((int) categoryId) + "品类均值进行冷启动预测。"
                        + "建议首批备餐" + firstBatch + "份，并根据实际销售情况动态调整。",
                "MEDIUM",
                List.of("基于品类均值估算，实际需求可能偏差较大", "当前天气:" + weather + "，系数:" + weatherFactor),
                List.of(new IntelligentAdvice.Action("ACTION_1", "建议1", "首批备餐控制在" + firstBatch + "份", "HIGH"),
                        new IntelligentAdvice.Action("ACTION_2", "建议2", "密切关注开餐后销售速度，及时调整", "MEDIUM")),
                List.of("冷启动预测精度较低，强烈建议首日后根据实际数据重新预测"),
                "品类均值 · 规则判断", false,
                java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"))
        );

        // 获取品类名称
        String categoryName = getCategoryName((int) categoryId);

        return new PredictionResult(
                -1,
                categoryName + "-冷启动",
                low,
                mid,
                high,
                firstBatch,
                replenish,
                12,
                18,
                confidence,
                "中",
                weatherFactor < 0.9 ? "中" : "低",
                factors,
                advice
        );
    }

    /**
     * 提取24维特征向量
     */
    private List<Double> extractFeatures(Map<String, Object> dish, List<Integer> sales, String weather,
                                          boolean examWeek, boolean campusEvent) {
        LocalDate today = LocalDate.now();
        LocalDate targetDate = today.plusDays(1);
        int dow = targetDate.getDayOfWeek().getValue() % 7; // 0=周一, 6=周日
        int weekOfMonth = (targetDate.getDayOfMonth() - 1) / 7 + 1;
        int month = targetDate.getMonthValue();
        int isWeekend = (dow == 5 || dow == 6) ? 1 : 0;
        int isExamWeek = examWeek ? 1 : 0;
        int hasCampusEvent = campusEvent ? 1 : 0;
        int daysToVacation = 0; // 简化为0
        double wc = weatherCode(weather);
        double tempMax = switch (weather) {
            case "高温" -> 35.0;
            case "晴朗", "晴" -> 28.0;
            case "小雨" -> 22.0;
            case "大雨" -> 20.0;
            case "降温" -> 10.0;
            case "暴雨" -> 18.0;
            default -> 25.0;
        };
        double precipitation = switch (weather) {
            case "小雨" -> 5.0;
            case "大雨" -> 25.0;
            case "暴雨" -> 50.0;
            default -> 0.0;
        };
        double weatherXWeekday = wc * dow;

        String category = String.valueOf(dish.get("category"));
        int categoryId = CATEGORY_NAME_TO_ID.getOrDefault(category, 0);
        double price = ((Number) dish.get("price")).doubleValue();
        double unitCost = ((Number) dish.get("unit_cost")).doubleValue();
        double markupRatio = unitCost > 0 ? price / unitCost : 1.0;
        double priceRankInStall = 0.5; // 默认中间价
        double categoryVolatility = CATEGORY_VOLATILITY.getOrDefault(categoryId, 1.0);
        double discountRate = 1.0; // 默认无折扣

        // 销量相关特征
        List<Integer> chronological = new ArrayList<>(sales);
        Collections.reverse(chronological);

        double lag1Sold = chronological.isEmpty() ? 0 : chronological.get(chronological.size() - 1);
        double lag7Sold = chronological.stream().mapToInt(Integer::intValue).sum();
        double rollingMean3 = chronological.size() >= 3
                ? chronological.subList(chronological.size() - 3, chronological.size()).stream()
                .mapToInt(Integer::intValue).average().orElse(0)
                : chronological.stream().mapToInt(Integer::intValue).average().orElse(0);
        double rollingMean7 = chronological.stream().mapToInt(Integer::intValue).average().orElse(0);
        double rollingStd7 = computeStd(chronological, rollingMean7);
        double sameDowLast4wMean = rollingMean7; // 简化：使用7日均值

        List<Double> values = new ArrayList<>();
        values.add((double) dow);
        values.add((double) weekOfMonth);
        values.add((double) month);
        values.add((double) isWeekend);
        values.add((double) isExamWeek);
        values.add((double) hasCampusEvent);
        values.add((double) daysToVacation);
        values.add(wc);
        values.add(tempMax);
        values.add(precipitation);
        values.add(weatherXWeekday);
        values.add((double) categoryId);
        values.add(price);
        values.add(unitCost);
        values.add(markupRatio);
        values.add(priceRankInStall);
        values.add(categoryVolatility);
        values.add(discountRate);
        values.add(lag1Sold);
        values.add(lag7Sold);
        values.add(rollingMean3);
        values.add(rollingMean7);
        values.add(rollingStd7);
        values.add(sameDowLast4wMean);

        return values;
    }

    /**
     * 计算ML加权得分 = 特征值×权重 的线性组合，归一化后乘以基线销量
     */
    private double computeMlScore(List<Double> featureValues) {
        if (featureValues.isEmpty() || featureWeights.isEmpty()) return 1.0;

        double dotProduct = 0;
        double sumAbsWeights = 0;
        int size = Math.min(featureValues.size(), featureNames.size());

        for (int i = 0; i < size; i++) {
            double weight = featureWeights.getOrDefault(featureNames.get(i), 0.0);
            dotProduct += featureValues.get(i) * weight;
            sumAbsWeights += Math.abs(weight);
        }

        // 归一化得到ML乘数（围绕1.0波动）
        double mlMultiplier = sumAbsWeights > 0 ? dotProduct / sumAbsWeights : 1.0;

        // 限制在合理范围内
        mlMultiplier = Math.max(0.5, Math.min(2.0, mlMultiplier));

        // 以基线销量50为参考，乘以ML乘数得到ML得分
        return 50.0 * mlMultiplier;
    }

    /**
     * 查询品类系数
     */
    private double lookupCategoryCoef(Map<String, Object> dish, String weather) {
        String category = String.valueOf(dish.get("category"));
        Integer categoryId = CATEGORY_NAME_TO_ID.get(category);
        if (categoryId == null) return 1.0;

        double wc = weatherCode(weather);
        String key = categoryId + ":" + (int) wc;
        Double coef = categoryCoefCache.get(key);
        return coef != null ? coef : 1.0;
    }

    /**
     * 获取天气因子（用于风险评估）
     */
    private double getWeatherFactor(Map<String, Object> dish, String weather) {
        String category = String.valueOf(dish.get("category"));
        Integer categoryId = CATEGORY_NAME_TO_ID.get(category);
        if (categoryId != null) {
            double wc = weatherCode(weather);
            String key = categoryId + ":" + (int) wc;
            Double coef = categoryCoefCache.get(key);
            if (coef != null) return coef;
        }
        return defaultWeatherFactor(weather);
    }

    /**
     * 获取品类默认基线销量
     */
    private double getCategoryBaseline(int categoryId) {
        return switch (categoryId) {
            case 0 -> 50.0; // 套餐主食
            case 1 -> 30.0; // 轻食沙拉
            case 2 -> 45.0; // 粉面
            case 3 -> 25.0; // 烘焙点心
            default -> 35.0;
        };
    }

    /**
     * 获取品类名称
     */
    private String getCategoryName(int categoryId) {
        return switch (categoryId) {
            case 0 -> "套餐主食";
            case 1 -> "轻食沙拉";
            case 2 -> "粉面";
            case 3 -> "烘焙点心";
            default -> "其他";
        };
    }

    /**
     * 天气描述转数值编码
     */
    private double weatherCode(String weather) {
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
     * 默认天气因子
     */
    private double defaultWeatherFactor(String weather) {
        return switch (weather) {
            case "小雨" -> 0.92;
            case "大雨" -> 0.82;
            case "高温" -> 0.90;
            case "降温" -> 1.04;
            default -> 1.00;
        };
    }

    /**
     * 计算标准差
     */
    private double computeStd(List<Integer> values, double mean) {
        if (values.size() <= 1) return 0;
        double variance = values.stream()
                .mapToDouble(v -> Math.pow(v - mean, 2))
                .average().orElse(0);
        return Math.sqrt(variance);
    }

    /**
     * 计算变异性（用于置信度）
     */
    private double computeVariability(List<Integer> sales) {
        double mean = sales.stream().mapToInt(Integer::intValue).average().orElse(0);
        if (mean == 0) return 19;
        double variance = sales.stream().mapToDouble(v -> Math.pow(v - mean, 2)).average().orElse(0);
        return Math.min(19, Math.sqrt(variance) / mean * 100);
    }
}

