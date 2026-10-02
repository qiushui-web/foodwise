package org.foodwise.service;

import org.foodwise.model.OperationLearningResult;
import org.foodwise.repository.FoodwiseRepository;
import org.foodwise.model.dto.DishDetail;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class OperationFeedbackService {

    private static final String LEARNING_METHOD = "最近7日递增权重滚动更新";
    private final FoodwiseRepository repository;
    private final PredictionService predictionService;

    public OperationFeedbackService(FoodwiseRepository repository, PredictionService predictionService) {
        this.repository = repository;
        this.predictionService = predictionService;
    }

    @Transactional
    public OperationLearningResult submit(LocalDate businessDate, String mealPeriod, long dishId, int plannedQty,
                                          int preparedQty, int soldQty, int discountSoldQty,
                                          int leftoverQty, BigDecimal revenue, String weather,
                                          String eventTag, boolean recommendationAdopted,
                                          boolean safetyConfirmed, String operatorName, String note) {
        if (businessDate == null || businessDate.isAfter(LocalDate.now())) {
            throw new IllegalArgumentException("营业日期不能为空，也不能晚于今天");
        }
        if (!List.of("早餐", "午餐", "晚餐", "未标注").contains(mealPeriod)) {
            throw new IllegalArgumentException("餐次必须是早餐、午餐或晚餐");
        }
        if (!safetyConfirmed) {
            throw new IllegalArgumentException("请先确认回传数据对应当餐经营记录和食品安全边界");
        }
        if (preparedQty != soldQty + leftoverQty) {
            throw new IllegalArgumentException("数量不守恒：备餐量应等于售出量与剩余量之和");
        }
        if (discountSoldQty > soldQty) {
            throw new IllegalArgumentException("优惠售出量不能大于总售出量");
        }
        if (plannedQty < 0 || preparedQty < 0 || soldQty < 0 || discountSoldQty < 0 || leftoverQty < 0) {
            throw new IllegalArgumentException("经营数量不能为负数");
        }
        if (revenue == null || revenue.signum() < 0) {
            throw new IllegalArgumentException("营业收入不能为空或为负数");
        }

        DishDetail dish = repository.dishDto(dishId);
        List<Integer> beforeSales = repository.recentSales(dishId);
        BigDecimal baselineBefore = weightedAverage(beforeSales);
        FoodwiseRepository.OperationSaveResult saved = repository.upsertOperation(
                businessDate, mealPeriod, dishId, plannedQty, preparedQty, soldQty, discountSoldQty,
                leftoverQty, revenue.setScale(2, RoundingMode.HALF_UP), weather,
                eventTag, recommendationAdopted);
        repository.saveOperationFeedback(saved.operationId(), operatorName, safetyConfirmed, note,
                saved.updated() ? "修正" : "新增");

        List<Integer> afterSales = repository.recentSales(dishId);
        BigDecimal baselineAfter = weightedAverage(afterSales);
        BigDecimal adjustmentRate = baselineBefore.signum() == 0 ? BigDecimal.ZERO : baselineAfter
                .subtract(baselineBefore).multiply(BigDecimal.valueOf(100))
                .divide(baselineBefore, 2, RoundingMode.HALF_UP);
        repository.saveLearningLog(saved.operationId(), dishId, LEARNING_METHOD, afterSales.size(),
                baselineBefore, baselineAfter, adjustmentRate);
        repository.replaceOperationAlerts(businessDate, dishId, preparedQty, soldQty, leftoverQty);

        BigDecimal leftoverRate = preparedQty == 0 ? BigDecimal.ZERO : BigDecimal.valueOf(leftoverQty * 100.0 / preparedQty)
                .setScale(1, RoundingMode.HALF_UP);
        String direction = adjustmentRate.signum() > 0 ? "上调" : adjustmentRate.signum() < 0 ? "下调" : "保持";
        String summary = String.format("%s的经营记录已%s。纳入本次销量后，近7日加权需求基线由%s份%s为%s份。",
                dish.name(), saved.updated() ? "修正" : "写入", baselineBefore, direction, baselineAfter);
        String nextAction = leftoverRate.compareTo(BigDecimal.valueOf(8)) >= 0
                ? "剩余率偏高，下一次备餐建议将优先控制首批投入，并保留人工调整。"
                : "供需处于可控范围，新记录将在下一次备餐预测和经营复盘中直接使用。";

        // 反馈闭环：自动更新模型参数
        autoUpdateModel(dishId);

        return new OperationLearningResult(saved.operationId(), dishId, dish.name(),
                businessDate, saved.updated(), afterSales.size(), baselineBefore, baselineAfter,
                adjustmentRate, leftoverRate, LEARNING_METHOD, summary, nextAction);
    }

    /**
     * 反馈闭环：统计该菜品积累的新反馈数据，达到阈值时自动更新模型参数
     */
    private void autoUpdateModel(long dishId) {
        try {
            // 统计该菜品从最近一次模型更新到现在的反馈记录数
            long newFeedbackCount = repository.countFeedbackSinceLastUpdate(dishId);

            // 如果积累 >= 4 条新反馈，则重新计算并更新参数
            if (newFeedbackCount >= 4) {
                // 获取最近销量数据
                List<Integer> sales = repository.recentSales(dishId);
                if (sales.size() < 4) {
                    return; // 数据不足，跳过更新
                }

                // 重新计算天气因子：根据最近操作记录中的天气情况
                double newWeatherFactor = recalculateWeatherFactor(dishId);

                // 重新计算趋势因子
                double newTrendFactor = recalculateTrendFactor(sales);

                // 通过 PredictionService 更新参数
                Map<String, Double> factors = new HashMap<>();
                factors.put("weatherFactor", newWeatherFactor);
                predictionService.updateFactors(dishId, factors);
                predictionService.updateTrendFactor(dishId, newTrendFactor);

                // 记录日志
                System.out.printf("反馈闭环自动更新：菜品%d 天气因子调整为 %.2f，趋势因子调整为 %.2f（基于%d条新反馈）%n",
                        dishId, newWeatherFactor, newTrendFactor, newFeedbackCount);
            }
        } catch (Exception e) {
            // 反馈闭环异常不影响主流程，仅记录日志
            System.err.println("反馈闭环自动更新失败（菜品" + dishId + "）: " + e.getMessage());
        }
    }

    /**
     * 根据最近操作记录重新计算天气因子
     */
    private double recalculateWeatherFactor(long dishId) {
        try {
            // 获取最近操作记录中的天气
            List<Map<String, Object>> recentOps = repository.recentOperationsByDish(dishId);
            if (recentOps.isEmpty()) {
                return 1.0;
            }

            // 统计最近5条记录中各种天气的出现频率
            Map<String, Integer> weatherCount = new HashMap<>();
            for (Map<String, Object> op : recentOps) {
                String w = String.valueOf(op.get("weather"));
                weatherCount.merge(w, 1, Integer::sum);
            }

            // 取出现次数最多的天气
            String mostCommonWeather = weatherCount.entrySet().stream()
                    .max(Map.Entry.comparingByValue())
                    .map(Map.Entry::getKey)
                    .orElse("晴朗");

            // 使用 PredictionService 的 weatherCode 方法获取对应系数
            double wc = predictionService.weatherCode(mostCommonWeather);
            // 根据天气编码映射到系数（简化为使用默认天气因子）
            return switch (mostCommonWeather) {
                case "小雨" -> 0.92;
                case "大雨" -> 0.82;
                case "高温" -> 0.90;
                case "降温" -> 1.04;
                default -> 1.00;
            };
        } catch (Exception e) {
            return 1.0;
        }
    }

    /**
     * 根据最近销量数据重新计算趋势因子
     */
    private double recalculateTrendFactor(List<Integer> sales) {
        if (sales.size() < 4) return 1.0;
        List<Integer> chronological = new java.util.ArrayList<>(sales);
        java.util.Collections.reverse(chronological);
        double early = chronological.subList(0, chronological.size() / 2).stream()
                .mapToInt(Integer::intValue).average().orElse(1);
        double recent = chronological.subList(chronological.size() / 2, chronological.size()).stream()
                .mapToInt(Integer::intValue).average().orElse(early);
        return Math.max(0.92, Math.min(1.08, recent / early));
    }

    public Map<String, Object> learningStatus() {
        return repository.learningStatus();
    }

    public List<Map<String, Object>> recentFeedback() {
        return repository.recentOperationFeedback();
    }

    private BigDecimal weightedAverage(List<Integer> newestFirst) {
        if (newestFirst.isEmpty()) return BigDecimal.ZERO.setScale(1);
        double total = 0;
        double weights = 0;
        for (int index = 0; index < newestFirst.size(); index++) {
            double weight = newestFirst.size() - index;
            total += newestFirst.get(index) * weight;
            weights += weight;
        }
        return BigDecimal.valueOf(total / weights).setScale(1, RoundingMode.HALF_UP);
    }
}

