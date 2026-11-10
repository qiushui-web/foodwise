package org.foodwise.decision;

import java.time.LocalDate;
import java.util.List;

/**
 * 校准引擎的一次完整决策预览：分位 → 校准区间 → 成本 → 建议量。
 * 前端“计划页”直接消费该结构，所有字段都能在页面上找到对应解释。
 */
public record DecisionPreview(
        String engine,
        String modelVersion,
        String status,
        String unavailableReason,
        LocalDate targetDate,
        int dayOfWeek,
        int categoryId,
        double q05,
        double q95,
        double offset,
        double intervalLow,
        double intervalHigh,
        double center,
        double sigma,
        double criticalRatio,
        double underage,
        double overage,
        int quantity,
        int firstBatch,
        int replenish,
        double price,
        double unitCost,
        double lossRate,
        double effectiveUnitCost,
        double regretUpper,
        double coverage,
        String calibrationMethod,
        List<String> notes
) {
}