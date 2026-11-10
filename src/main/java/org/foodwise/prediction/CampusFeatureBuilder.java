package org.foodwise.prediction;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * 按 campus_feature_cols.json 顺序构造 24 维模型输入。
 *
 * 规则引擎与校准引擎共用同一套特征口径，避免“同一个网站两种特征定义”。
 * 日期窗口与缺失值语义仍需与 Python 侧逐值验收（见 quantile_parity_fixture 测试）。
 */
public final class CampusFeatureBuilder {

    // App 菜品品类 -> uwaste 模型 category_id（按需求层级对齐：1 主食高销量 … 4 烘焙低销量）
    private static final Map<String, Integer> CATEGORY_TO_MODEL_ID = Map.of(
            "套餐主食", 1,
            "粉面", 2,
            "轻食沙拉", 3,
            "烘焙点心", 4
    );

    private CampusFeatureBuilder() {
    }

    public static double[] build(Map<String, Object> dish, List<Integer> salesRecentFirst,
                                 String weather, boolean examWeek, boolean campusEvent,
                                 LocalDate targetDate) {
        int dow = targetDate.getDayOfWeek().getValue() - 1; // 0=周一 … 6=周日
        int isWeekend = (dow == 5 || dow == 6) ? 1 : 0;
        int weatherCode = weatherCode(weather);
        int tempMax = tempMax(weather);

        String category = String.valueOf(dish.get("category"));
        int categoryId = CATEGORY_TO_MODEL_ID.getOrDefault(category, 1);
        double price = ((Number) dish.get("price")).doubleValue();
        double unitCost = dish.get("unit_cost") instanceof Number n ? n.doubleValue() : price * 0.4;

        // 销量序列：recentSales 为最近在前，反转为时间正序（末位=最近一日）
        List<Integer> chronological = new ArrayList<>(salesRecentFirst == null ? List.of() : salesRecentFirst);
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
        double sameDowMean = sameDow.isEmpty()
                ? mean7
                : sameDow.stream().mapToDouble(Double::doubleValue).average().orElse(mean7);
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

    public static int categoryId(Map<String, Object> dish) {
        return CATEGORY_TO_MODEL_ID.getOrDefault(String.valueOf(dish.get("category")), 1);
    }

    public static int dayOfWeek(LocalDate targetDate) {
        return targetDate.getDayOfWeek().getValue() - 1;
    }

    /** 与 DuckDB 侧 category_id 对齐：App 品类名 -> 模型品类号。 */
    public static Map<String, Integer> categoryMapping() {
        return CATEGORY_TO_MODEL_ID;
    }

    private static double mean(List<Integer> list, int from, int to) {
        if (to <= from) return 0;
        return list.subList(from, to).stream().mapToInt(Integer::intValue).average().orElse(0);
    }

    private static double std(List<Integer> list, int from, int to, double mean) {
        if (to - from <= 1) return 0;
        double variance = list.subList(from, to).stream()
                .mapToDouble(v -> Math.pow(v - mean, 2)).average().orElse(0);
        return Math.sqrt(variance);
    }

    public static int weatherCode(String weather) {
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

    public static int tempMax(String weather) {
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