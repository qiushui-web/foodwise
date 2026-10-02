package org.foodwise.model;

import java.math.BigDecimal;
import java.time.LocalDate;

public record OperationLearningResult(
        long operationId,
        long dishId,
        String dishName,
        LocalDate businessDate,
        boolean updated,
        int sampleCount,
        BigDecimal baselineBefore,
        BigDecimal baselineAfter,
        BigDecimal adjustmentRate,
        BigDecimal leftoverRate,
        String learningMethod,
        String summary,
        String nextAction
) {
}

