package org.foodwise.model.dto;

/**
 * 档口经营效率指标
 */
public record StallEfficiency(
    String stallName,
    double soldRate,
    double revenueShare,
    double leftoverRate,
    int totalPrepared,
    int totalSold
) {}

