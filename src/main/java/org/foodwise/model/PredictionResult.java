package org.foodwise.model;

import java.math.BigDecimal;
import java.util.List;

public record PredictionResult(
        long predictionId,
        long dishId,
        String dishName,
        int predictedLow,
        int predictedMid,
        int predictedHigh,
        int firstBatch,
        int replenishQty,
        int stopHour,
        int stopMinute,
        BigDecimal confidence,
        String soldOutRisk,
        String leftoverRisk,
        List<Factor> factors,
        IntelligentAdvice advice
) {
    public PredictionResult(long dishId, String dishName, int predictedLow, int predictedMid,
                            int predictedHigh, int firstBatch, int replenishQty, int stopHour,
                            int stopMinute, BigDecimal confidence, String soldOutRisk,
                            String leftoverRisk, List<Factor> factors, IntelligentAdvice advice) {
        this(0, dishId, dishName, predictedLow, predictedMid, predictedHigh, firstBatch,
                replenishQty, stopHour, stopMinute, confidence, soldOutRisk, leftoverRisk, factors, advice);
    }

    public record Factor(String name, String detail, BigDecimal value, String type) {
    }
}

