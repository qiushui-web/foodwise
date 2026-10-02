package org.foodwise.service;

import org.foodwise.model.PredictionResult;
import org.foodwise.repository.FoodwiseRepository;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 双引擎预测：规则引擎（Java 四因子）与真实 LightGBM 训练模型并行预测，
 * 最终建议 = 0.6 × 训练模型 + 0.4 × 规则（模型不可用时自动降级为纯规则）。
 * 返回的 Map 同时携带两条预测链路的数值与训练模型的逐特征决策归因，
 * 供前端做"训练模型 vs 规则"对比、决策路径可视化与大模型交叉解读，
 * 让"决策来自训练模型"这一点在界面上可核对、可追溯。
 */
@Service
public class DualPredictionService {

    private final PredictionService predictionService;
    private final FoodwiseRepository repository;
    private final LgbmCampusModel lgbmModel;

    // App 菜品品类 -> uwaste 模型 category_id（按需求层级对齐：1 主食高销量 … 4 烘焙低销量）
    private static final Map<String, Integer> CATEGORY_TO_MODEL_ID = Map.of(
            "套餐主食", 1,
            "粉面", 2,
            "轻食沙拉", 3,
            "烘焙点心", 4
    );

    public DualPredictionService(PredictionService predictionService,
                                 FoodwiseRepository repository,
                                 LgbmCampusModel lgbmModel) {
        this.predictionService = predictionService;
        this.repository = repository;
        this.lgbmModel = lgbmModel;
    }

    public Map<String, Object> predictDual(long dishId, String weather, boolean examWeek, boolean campusEvent) {
        // 1. 规则引擎预测（现有 PredictionService，四因子加权）
        PredictionResult rule = predictionService.predict(dishId, weather, examWeek, campusEvent);

        // 2. 真实训练模型预测
        Map<String, Object> dish = repository.dish(dishId);
        List<Integer> sales = repository.recentSales(dishId);
        Double lgbmSold = null;
        LgbmCampusModel.Explanation explanation = null;
        double[] features = buildCampusFeatures(dish, sales, weather, examWeek, campusEvent);
        if (lgbmModel.isReady()) {
            lgbmSold = lgbmModel.predict(features);
            explanation = lgbmModel.explain(features);
        }

        int ruleMid = rule.predictedMid();
        int lgbmMid = lgbmSold == null ? ruleMid : (int) Math.round(lgbmSold);

        // 3. 集成：训练模型为主（0.6），规则为辅（0.4）；模型不可用则纯规则
        double ensembleRaw = lgbmSold != null ? 0.6 * lgbmSold + 0.4 * ruleMid : ruleMid;
        int mid = Math.max(1, (int) Math.round(ensembleRaw));
        int low = Math.max(1, (int) Math.floor(mid * 0.92));
        int high = Math.max(mid + 1, (int) Math.ceil(mid * 1.08));
        int firstBatch = Math.max(1, (int) Math.round(low * 0.82));
        int replenish = Math.max(0, mid - firstBatch);

        // 4. 因子列表（规则因子 + 训练模型因子）
        List<PredictionResult.Factor> factors = new ArrayList<>(rule.factors());
        if (lgbmSold != null) {
            double deltaPct = (lgbmMid - ruleMid) * 100.0 / Math.max(1, ruleMid);
            factors.add(new PredictionResult.Factor(
                    "训练模型 LGBM",
                    lgbmModel.treeCount() + "棵回归树真实推理，预测 " + lgbmMid + " 份（滚动回测MAPE " + lgbmModel.backtestMape() + "%）",
                    BigDecimal.valueOf(deltaPct).setScale(1, RoundingMode.HALF_UP),
                    "lgbm_trained"));
        } else {
            factors.add(new PredictionResult.Factor(
                    "训练模型 LGBM",
                    "模型运行时未就绪，当前采用规则引擎预测（模型文件 " + lgbmModel.trainedRows() + " 行训练）",
                    BigDecimal.ZERO, "lgbm_unavailable"));
        }

        BigDecimal confidence = lgbmSold != null
                ? BigDecimal.valueOf(90.0).setScale(1, RoundingMode.HALF_UP)
                : rule.confidence();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("dishId", dishId);
        result.put("dishName", rule.dishName());
        result.put("predictedLow", low);
        result.put("predictedMid", mid);
        result.put("predictedHigh", high);
        result.put("firstBatch", firstBatch);
        result.put("replenishQty", replenish);
        result.put("stopHour", rule.stopHour());
        result.put("stopMinute", rule.stopMinute());
        result.put("confidence", confidence);
        result.put("soldOutRisk", rule.soldOutRisk());
        result.put("leftoverRisk", rule.leftoverRisk());
        result.put("factors", factors);
        result.put("advice", rule.advice());
        // 双引擎对比字段
        result.put("rulePrediction", ruleMid);
        result.put("lgbmPrediction", lgbmSold == null ? null : lgbmMid);
        result.put("modelReady", lgbmModel.isReady());
        result.put("modelName", "LightGBM 高校真实模型");
        result.put("modelMape", lgbmModel.backtestMape());
        result.put("trainedRows", lgbmModel.trainedRows());
        result.put("modelTrees", lgbmModel.treeCount());
        // 训练模型逐特征决策归因（决策来自训练的直接证据）
        if (explanation != null) {
            List<Map<String, Object>> contribs = new ArrayList<>();
            int topN = 0;
            for (LgbmCampusModel.Contribution c : explanation.getContributions()) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("feature", c.getFeature());
                row.put("featureZh", c.getFeatureZh());
                row.put("soldDelta", BigDecimal.valueOf(c.getSoldDelta()).setScale(1, RoundingMode.HALF_UP));
                row.put("splits", c.getSplits());
                row.put("direction", c.getSoldDelta() >= 0 ? "up" : "down");
                contribs.add(row);
                if (++topN >= 8) break;
            }
            result.put("decisionContributions", contribs);
            result.put("decisionRules", explanation.getTopRules());
            result.put("rawScore", BigDecimal.valueOf(explanation.getRawScore()).setScale(4, RoundingMode.HALF_UP));
        } else {
            result.put("decisionContributions", List.of());
            result.put("decisionRules", List.of());
        }
        return result;
    }

    /**
     * 按 campus_feature_cols.json 顺序构造 24 维特征（与 Python 训练管道严格一致）。
     */
    private double[] buildCampusFeatures(Map<String, Object> dish, List<Integer> salesRaw,
                                         String weather, boolean examWeek, boolean campusEvent) {
        LocalDate target = LocalDate.now().plusDays(1);
        int dow = target.getDayOfWeek().getValue() - 1; // 0=周一 … 6=周日
        int isWeekend = (dow == 5 || dow == 6) ? 1 : 0;
        int weatherCode = weatherCode(weather);
        int tempMax = tempMax(weather);

        String category = String.valueOf(dish.get("category"));
        int categoryId = CATEGORY_TO_MODEL_ID.getOrDefault(category, 1);
        double price = ((Number) dish.get("price")).doubleValue();
        double unitCost = dish.get("unit_cost") instanceof Number n ? n.doubleValue() : price * 0.4;

        // 销量序列：recentSales 为最近在前，反转为时间正序（末位=最近一日）
        List<Integer> chronological = new ArrayList<>(salesRaw == null ? List.of() : salesRaw);
        Collections.reverse(chronological);
        int n = chronological.size();
        double lag1 = n >= 1 ? chronological.get(n - 1) : 0;
        double lag2 = n >= 2 ? chronological.get(n - 2) : 0;
        double lag3 = n >= 3 ? chronological.get(n - 3) : 0;
        double lag7 = n >= 7 ? chronological.get(n - 7) : 0;
        double mean3 = mean(chronological, Math.max(0, n - 3), n);
        double mean7 = mean(chronological, 0, n);
        double std7 = std(chronological, 0, n, mean7);
        // 同星期近4周均值：7/14/21 天前
        List<Double> sameDow = new ArrayList<>();
        for (int back = 7; back <= 28; back += 7) {
            if (n >= back) sameDow.add(chronological.get(n - back).doubleValue());
        }
        double sameDowMean = sameDow.isEmpty() ? mean7 : sameDow.stream().mapToDouble(Double::doubleValue).average().orElse(mean7);
        // 近3日趋势：末3日均值 vs 之前均值 的方向
        double prevMean = mean(chronological, 0, Math.max(0, n - 3));
        int recentTrend = n >= 4 ? Double.compare(Math.signum(mean3 - prevMean), 0) : 0;

        return new double[]{
                dow,                                   // day_of_week
                isWeekend,                             // is_weekend
                examWeek ? 1 : 0,                      // is_exam_week
                campusEvent ? 1 : 0,                   // has_campus_event
                weatherCode,                           // weather_code
                tempMax,                               // temp_max_c
                categoryId,                            // category_id
                price,                                 // price
                unitCost,                              // unit_cost
                0.0,                                   // discount_rate
                0,                                     // promotion_flag
                lag1,                                  // lag_1_sold
                lag2,                                  // lag_2_sold
                lag3,                                  // lag_3_sold
                lag7,                                  // lag_7_sold
                mean3,                                 // rolling_mean_3
                mean7,                                 // rolling_mean_7
                std7,                                  // rolling_std_7
                sameDowMean,                           // same_dow_last_4w_mean
                0,                                     // is_school_holiday
                0,                                     // is_state_holiday
                0,                                     // special_day
                1.0,                                   // comp_price_ratio
                recentTrend                            // recent_trend_3d
        };
    }

    private double mean(List<Integer> list, int from, int to) {
        if (to <= from) return 0;
        return list.subList(from, to).stream().mapToInt(Integer::intValue).average().orElse(0);
    }

    private double std(List<Integer> list, int from, int to, double mean) {
        if (to - from <= 1) return 0;
        double variance = list.subList(from, to).stream()
                .mapToDouble(v -> Math.pow(v - mean, 2)).average().orElse(0);
        return Math.sqrt(variance);
    }

    private int weatherCode(String weather) {
        return switch (weather) {
            case "晴朗", "晴" -> 0;
            case "小雨" -> 1;
            case "大雨" -> 2;
            case "高温" -> 3;
            case "降温" -> 4;
            case "暴雨", "极端" -> 5;
            default -> 0;
        };
    }

    private int tempMax(String weather) {
        return switch (weather) {
            case "高温" -> 35;
            case "晴朗", "晴" -> 28;
            case "小雨" -> 22;
            case "大雨" -> 20;
            case "降温" -> 10;
            case "暴雨" -> 18;
            default -> 25;
        };
    }
}

