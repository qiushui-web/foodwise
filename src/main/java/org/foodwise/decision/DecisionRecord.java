package org.foodwise.decision;

import java.time.LocalDateTime;
import java.util.List;

/** 一次校准决策的完整留痕，用于重放与证据页。 */
public record DecisionRecord(
        long id,
        long dishId,
        java.time.LocalDate targetDate,
        String weather,
        boolean examWeek,
        boolean campusEvent,
        String engine,
        String modelVersion,
        String calibrationSha256,
        double[] features,
        int categoryId,
        int dayOfWeek,
        double q05,
        double q95,
        double intervalOffset,
        int intervalLow,
        int intervalHigh,
        double center,
        double sigma,
        double price,
        double unitCost,
        double discountPrice,
        double salvageProbability,
        double shortageLambda,
        double criticalRatio,
        int quantity,
        int firstBatch,
        int replenish,
        LocalDateTime createdAt
) {
    public DecisionCostModel costModel() {
        return new DecisionCostModel(price, unitCost, discountPrice, salvageProbability, shortageLambda);
    }

    public List<Double> featureList() {
        List<Double> values = new java.util.ArrayList<>(features.length);
        for (double value : features) values.add(value);
        return values;
    }
}