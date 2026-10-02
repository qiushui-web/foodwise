package org.foodwise.model.dto;

import java.math.BigDecimal;

/**
 * 复盘报告核心摘要
 */
public record ReportSummary(
    BigDecimal avoidedLoss,
    double baselineWasteRate,
    double interventionWasteRate,
    int baselineLeftover,
    int interventionLeftover,
    int baselinePieces,
    int interventionPieces,
    long records,
    int baselineDays,
    int interventionDays
) {}

