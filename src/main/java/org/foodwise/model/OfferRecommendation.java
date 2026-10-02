package org.foodwise.model;

import java.math.BigDecimal;

public record OfferRecommendation(
        long dishId,
        String dishName,
        int recommendedQty,
        BigDecimal recommendedPrice,
        int discountRate,
        String startTime,
        String endTime,
        int expectedRecoveredQty,
        BigDecimal estimatedRevenue,
        String riskLevel,
        IntelligentAdvice advice
) {
}

