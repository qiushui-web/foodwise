package org.foodwise.model.dto;

/**
 * 预测模型回测对比结果
 */
public record BacktestResult(
    double baselineMape,
    double enhancedMape,
    double baselineMae,
    double enhancedMae,
    double mapeImprovement,
    double maeImprovement,
    int totalSamples
) {}

