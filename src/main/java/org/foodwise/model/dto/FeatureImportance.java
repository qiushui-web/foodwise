package org.foodwise.model.dto;

/**
 * 特征重要性（用于需求预测模型分析）
 */
public record FeatureImportance(
    String feature,
    double importance
) {}

